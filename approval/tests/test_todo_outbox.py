from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from approval import models as approval_models
from approval.services import engine, todo
from core import models as core_models


class ApprovalTodoOutboxTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = core_models.Region.objects.create(name='华东', code='east')
        cls.owner_role = core_models.Role.objects.create(name='销售', code='sales')
        cls.approver_role = core_models.Role.objects.create(name='审批人', code='approver')

    def setUp(self):
        self.owner = core_models.User.objects.create_user(
            username=f'owner_{core_models.User.objects.count() + 1}',
            password='pass1234',
            region=self.region,
            role=self.owner_role,
        )
        self.approver_a = core_models.User.objects.create_user(
            username=f'approver_a_{core_models.User.objects.count() + 1}',
            password='pass1234',
            region=self.region,
            role=self.approver_role,
            dingtalk_user_id='dt_user_a',
            dingtalk_union_id='dt_union_a',
        )
        self.approver_b = core_models.User.objects.create_user(
            username=f'approver_b_{core_models.User.objects.count() + 1}',
            password='pass1234',
            region=self.region,
            role=self.approver_role,
            dingtalk_user_id='dt_user_b',
            dingtalk_union_id='dt_union_b',
        )
        self.approver_c = core_models.User.objects.create_user(
            username=f'approver_c_{core_models.User.objects.count() + 1}',
            password='pass1234',
            region=self.region,
            role=self.approver_role,
            dingtalk_user_id='dt_user_c',
            dingtalk_union_id='dt_union_c',
        )
        self.account = core_models.Account.objects.create(
            full_name=f'测试客户{core_models.Account.objects.count() + 1}',
            short_name='测试客户',
            region=self.region,
            owner=self.owner,
        )
        self.contract = core_models.Contract.objects.create(
            account=self.account,
            amount='1000.00',
            region=self.region,
            owner=self.owner,
            approval_status='pending',
        )

    def _create_flow(self, parallel=False):
        flow = approval_models.ApprovalFlow.objects.create(
            name='合同审批流',
            target_type=approval_models.ApprovalFlow.TARGET_CONTRACT,
            region=self.region,
            is_active=True,
        )
        if parallel:
            approval_models.ApprovalStep.objects.create(
                flow=flow,
                order=1,
                name='会签节点',
                approver_role=self.approver_role,
            )
        else:
            approval_models.ApprovalStep.objects.create(
                flow=flow,
                order=1,
                name='单人审批',
                approver_user=self.approver_a,
            )
        return flow

    def _create_pending_task(self):
        content_type = ContentType.objects.get_for_model(core_models.Contract)
        instance = approval_models.ApprovalInstance.objects.create(
            content_type=content_type,
            object_id=self.contract.id,
            target_type=approval_models.ApprovalFlow.TARGET_CONTRACT,
            region=self.region,
            status=approval_models.ApprovalInstance.STATUS_PENDING,
            started_by=self.owner,
            current_step=1,
        )
        step = approval_models.ApprovalStep.objects.create(
            flow=approval_models.ApprovalFlow.objects.create(
                name='临时流程',
                target_type=approval_models.ApprovalFlow.TARGET_CONTRACT,
                region=self.region,
                is_active=False,
            ),
            order=1,
            name='临时审批',
            approver_user=self.approver_a,
        )
        task = approval_models.ApprovalTask.objects.create(
            instance=instance,
            step=step,
            assignee=self.approver_a,
            status=approval_models.ApprovalTask.STATUS_PENDING,
        )
        return instance, task

    def test_schedule_create_outbox_is_idempotent_by_source_id(self):
        _, task = self._create_pending_task()
        with self.captureOnCommitCallbacks(execute=True):
            todo.schedule_create_for_task(task, originator=self.owner)
            todo.schedule_create_for_task(task, originator=self.owner)

        outbox = approval_models.ApprovalTodoOutbox.objects.filter(
            task=task,
            action=approval_models.ApprovalTodoOutbox.ACTION_CREATE,
            source_id=todo.build_todo_source_id(task.id),
        )
        self.assertEqual(outbox.count(), 1)

    def test_start_approval_non_blocking_with_outbox(self):
        self._create_flow(parallel=False)
        with self.captureOnCommitCallbacks(execute=True):
            instance = engine.start_approval(self.contract, self.owner)
        self.assertEqual(instance.status, approval_models.ApprovalInstance.STATUS_PENDING)
        self.assertEqual(instance.tasks.filter(status=approval_models.ApprovalTask.STATUS_PENDING).count(), 1)
        self.assertEqual(
            approval_models.ApprovalTodoOutbox.objects.filter(
                task__instance=instance, action=approval_models.ApprovalTodoOutbox.ACTION_CREATE
            ).count(),
            1,
        )

    @patch('approval.services.todo.send_todo_task_result')
    def test_process_create_outbox_success_updates_task_status(self, mocked_send):
        mocked_send.return_value = todo.TodoGatewayResult(
            ok=True,
            channel=approval_models.ApprovalTask.TODO_CHANNEL_TODO_API,
            task_id='ding_task_001',
            error='',
            raw={},
        )
        _, task = self._create_pending_task()
        with self.captureOnCommitCallbacks(execute=True):
            todo.schedule_create_for_task(task, originator=self.owner)
        summary = todo.process_outbox(batch_size=10)

        task.refresh_from_db()
        self.assertEqual(summary['succeeded'], 1)
        self.assertEqual(task.todo_status, approval_models.ApprovalTask.TODO_STATUS_CREATED)
        self.assertEqual(task.todo_task_id, 'ding_task_001')
        self.assertEqual(task.todo_source_id, todo.build_todo_source_id(task.id))

    def test_parallel_reject_closes_other_pending_tasks(self):
        self._create_flow(parallel=True)
        with self.captureOnCommitCallbacks(execute=True):
            instance = engine.start_approval(self.contract, self.owner)

        pending_tasks = list(instance.tasks.filter(status=approval_models.ApprovalTask.STATUS_PENDING).order_by('id'))
        self.assertGreaterEqual(len(pending_tasks), 2)

        with self.captureOnCommitCallbacks(execute=True):
            engine.approve_task(pending_tasks[0], self.approver_a, approved=False, comment='驳回')

        instance.refresh_from_db()
        self.assertEqual(instance.status, approval_models.ApprovalInstance.STATUS_REJECTED)
        for other_task in pending_tasks[1:]:
            other_task.refresh_from_db()
            self.assertEqual(other_task.status, approval_models.ApprovalTask.STATUS_CANCELED)
        self.assertGreaterEqual(
            approval_models.ApprovalTodoOutbox.objects.filter(
                task__instance=instance,
                action=approval_models.ApprovalTodoOutbox.ACTION_COMPLETE,
            ).count(),
            2,
        )

    def test_withdraw_closes_pending_tasks_and_enqueue_complete(self):
        self._create_flow(parallel=False)
        with self.captureOnCommitCallbacks(execute=True):
            instance = engine.start_approval(self.contract, self.owner)
        pending_task = instance.tasks.filter(status=approval_models.ApprovalTask.STATUS_PENDING).first()

        with self.captureOnCommitCallbacks(execute=True):
            engine.withdraw_approval(instance, self.owner, comment='撤回')

        instance.refresh_from_db()
        pending_task.refresh_from_db()
        self.assertEqual(instance.status, approval_models.ApprovalInstance.STATUS_WITHDRAWN)
        self.assertEqual(pending_task.status, approval_models.ApprovalTask.STATUS_CANCELED)
        self.assertTrue(
            approval_models.ApprovalTodoOutbox.objects.filter(
                task=pending_task,
                action=approval_models.ApprovalTodoOutbox.ACTION_COMPLETE,
            ).exists()
        )

    def test_transfer_task_enqueue_complete_and_new_create(self):
        self._create_flow(parallel=False)
        with self.captureOnCommitCallbacks(execute=True):
            instance = engine.start_approval(self.contract, self.owner)
        pending_task = instance.tasks.filter(status=approval_models.ApprovalTask.STATUS_PENDING).first()

        with self.captureOnCommitCallbacks(execute=True):
            new_task = engine.transfer_task(pending_task, self.approver_a, self.approver_b, comment='转交')

        pending_task.refresh_from_db()
        new_task.refresh_from_db()
        self.assertEqual(pending_task.status, approval_models.ApprovalTask.STATUS_CANCELED)
        self.assertEqual(new_task.status, approval_models.ApprovalTask.STATUS_PENDING)
        self.assertEqual(new_task.assignee_id, self.approver_b.id)
        self.assertTrue(
            approval_models.ApprovalTodoOutbox.objects.filter(
                task=pending_task,
                action=approval_models.ApprovalTodoOutbox.ACTION_COMPLETE,
            ).exists()
        )
        self.assertTrue(
            approval_models.ApprovalTodoOutbox.objects.filter(
                task=new_task,
                action=approval_models.ApprovalTodoOutbox.ACTION_CREATE,
            ).exists()
        )

    def test_add_sign_task_enqueue_new_create(self):
        self._create_flow(parallel=False)
        with self.captureOnCommitCallbacks(execute=True):
            instance = engine.start_approval(self.contract, self.owner)
        pending_task = instance.tasks.filter(status=approval_models.ApprovalTask.STATUS_PENDING).first()

        with self.captureOnCommitCallbacks(execute=True):
            add_task = engine.add_sign_task(pending_task, self.approver_a, self.approver_b, comment='加签')

        add_task.refresh_from_db()
        self.assertEqual(add_task.status, approval_models.ApprovalTask.STATUS_PENDING)
        self.assertEqual(add_task.assignee_id, self.approver_b.id)
        self.assertTrue(
            approval_models.ApprovalTodoOutbox.objects.filter(
                task=add_task,
                action=approval_models.ApprovalTodoOutbox.ACTION_CREATE,
            ).exists()
        )

    def test_add_sign_task_suspends_parent_and_resume_after_feedback(self):
        self._create_flow(parallel=False)
        with self.captureOnCommitCallbacks(execute=True):
            instance = engine.start_approval(self.contract, self.owner)
        parent_task = instance.tasks.filter(status=approval_models.ApprovalTask.STATUS_PENDING).first()

        with self.captureOnCommitCallbacks(execute=True):
            add_task = engine.add_sign_task(parent_task, self.approver_a, self.approver_b, comment='请补充意见')

        parent_task.refresh_from_db()
        add_task.refresh_from_db()
        self.assertEqual(parent_task.status, approval_models.ApprovalTask.STATUS_BLOCKED)
        self.assertEqual(add_task.status, approval_models.ApprovalTask.STATUS_PENDING)
        self.assertEqual(add_task.parent_task_id, parent_task.id)
        self.assertTrue(
            approval_models.ApprovalTodoOutbox.objects.filter(
                task=parent_task,
                action=approval_models.ApprovalTodoOutbox.ACTION_COMPLETE,
            ).exists()
        )

        with self.captureOnCommitCallbacks(execute=True):
            engine.approve_task(add_task, self.approver_b, approved=True, comment='已给出意见')

        parent_task.refresh_from_db()
        add_task.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(add_task.status, approval_models.ApprovalTask.STATUS_APPROVED)
        self.assertEqual(parent_task.status, approval_models.ApprovalTask.STATUS_PENDING)
        self.assertEqual(instance.status, approval_models.ApprovalInstance.STATUS_PENDING)

    def test_add_sign_task_cannot_reject_instance(self):
        self._create_flow(parallel=False)
        with self.captureOnCommitCallbacks(execute=True):
            instance = engine.start_approval(self.contract, self.owner)
        parent_task = instance.tasks.filter(status=approval_models.ApprovalTask.STATUS_PENDING).first()

        with self.captureOnCommitCallbacks(execute=True):
            add_task = engine.add_sign_task(parent_task, self.approver_a, self.approver_b, comment='请补充意见')

        with self.assertRaisesMessage(ValueError, '加签任务仅支持提交意见，不可驳回流程'):
            with self.captureOnCommitCallbacks(execute=True):
                engine.approve_task(add_task, self.approver_b, approved=False, comment='驳回')

    def test_parent_task_cannot_decide_while_add_sign_pending(self):
        self._create_flow(parallel=False)
        with self.captureOnCommitCallbacks(execute=True):
            instance = engine.start_approval(self.contract, self.owner)
        parent_task = instance.tasks.filter(status=approval_models.ApprovalTask.STATUS_PENDING).first()

        with self.captureOnCommitCallbacks(execute=True):
            engine.add_sign_task(parent_task, self.approver_a, self.approver_b, comment='加签')

        with self.assertRaisesMessage(ValueError, 'Task is not pending'):
            with self.captureOnCommitCallbacks(execute=True):
                engine.approve_task(parent_task, self.approver_a, approved=True, comment='尝试直接同意')

    def test_add_sign_task_disallows_parallel_add_sign(self):
        self._create_flow(parallel=False)
        with self.captureOnCommitCallbacks(execute=True):
            instance = engine.start_approval(self.contract, self.owner)
        parent_task = instance.tasks.filter(status=approval_models.ApprovalTask.STATUS_PENDING).first()

        with self.captureOnCommitCallbacks(execute=True):
            engine.add_sign_task(parent_task, self.approver_a, self.approver_b, comment='第一次加签')

        with self.assertRaisesMessage(ValueError, '当前任务已有进行中的加签'):
            with self.captureOnCommitCallbacks(execute=True):
                engine.add_sign_task(parent_task, self.approver_a, self.approver_c, comment='第二次加签')

    def test_transfer_add_sign_task_keeps_parent_relation(self):
        self._create_flow(parallel=False)
        with self.captureOnCommitCallbacks(execute=True):
            instance = engine.start_approval(self.contract, self.owner)
        parent_task = instance.tasks.filter(status=approval_models.ApprovalTask.STATUS_PENDING).first()

        with self.captureOnCommitCallbacks(execute=True):
            add_task = engine.add_sign_task(parent_task, self.approver_a, self.approver_b, comment='加签')
        with self.captureOnCommitCallbacks(execute=True):
            transferred_task = engine.transfer_task(add_task, self.approver_b, self.approver_c, comment='转办加签')

        add_task.refresh_from_db()
        transferred_task.refresh_from_db()
        self.assertEqual(add_task.status, approval_models.ApprovalTask.STATUS_CANCELED)
        self.assertEqual(transferred_task.status, approval_models.ApprovalTask.STATUS_PENDING)
        self.assertEqual(transferred_task.parent_task_id, parent_task.id)

    def test_auto_skip_same_assignee_on_later_steps(self):
        flow = approval_models.ApprovalFlow.objects.create(
            name='同人后续自动跳过',
            target_type=approval_models.ApprovalFlow.TARGET_CONTRACT,
            region=self.region,
            is_active=True,
        )
        approval_models.ApprovalStep.objects.create(
            flow=flow,
            order=1,
            name='一级审批',
            approver_user=self.approver_a,
        )
        approval_models.ApprovalStep.objects.create(
            flow=flow,
            order=2,
            name='二级审批（同人）',
            approver_user=self.approver_a,
        )
        approval_models.ApprovalStep.objects.create(
            flow=flow,
            order=3,
            name='三级审批',
            approver_user=self.approver_b,
        )

        with self.captureOnCommitCallbacks(execute=True):
            instance = engine.start_approval(self.contract, self.owner)
        step1_task = instance.tasks.get(step__order=1, assignee=self.approver_a)

        with self.captureOnCommitCallbacks(execute=True):
            engine.approve_task(step1_task, self.approver_a, approved=True, comment='同意')

        instance.refresh_from_db()
        step2_task = instance.tasks.get(step__order=2, assignee=self.approver_a)
        step3_task = instance.tasks.get(step__order=3, assignee=self.approver_b)

        self.assertEqual(step2_task.status, approval_models.ApprovalTask.STATUS_APPROVED)
        self.assertIn('系统自动跳过', step2_task.comment)
        self.assertEqual(step3_task.status, approval_models.ApprovalTask.STATUS_PENDING)
        self.assertEqual(instance.current_step, 3)

    @patch('approval.services.todo.send_todo_task_result')
    @override_settings(DINGTALK={'TODO_RETRY_ENABLED': '1'})
    def test_outbox_failure_retries_then_dead_letter(self, mocked_send):
        mocked_send.return_value = todo.TodoGatewayResult(
            ok=False,
            channel=approval_models.ApprovalTask.TODO_CHANNEL_TODO_API,
            task_id='',
            error='network timeout',
            raw={},
        )
        _, task = self._create_pending_task()
        with self.captureOnCommitCallbacks(execute=True):
            todo.schedule_create_for_task(task, originator=self.owner)

        max_round = len(todo.RETRY_DELAYS_SECONDS) + 1
        for _ in range(max_round):
            todo.process_outbox(batch_size=10)
            approval_models.ApprovalTodoOutbox.objects.filter(task=task).update(next_retry_at=timezone.now())

        outbox_item = approval_models.ApprovalTodoOutbox.objects.filter(task=task).first()
        task.refresh_from_db()
        self.assertEqual(outbox_item.status, approval_models.ApprovalTodoOutbox.STATUS_DEAD)
        self.assertEqual(task.todo_status, approval_models.ApprovalTask.TODO_STATUS_FAILED)
        self.assertGreaterEqual(task.todo_retry_count, len(todo.RETRY_DELAYS_SECONDS))

    @patch('approval.services.todo.send_todo_task_result')
    @override_settings(DINGTALK={'TODO_RETRY_ENABLED': '0'})
    def test_outbox_failure_no_retry_goes_dead_immediately(self, mocked_send):
        mocked_send.return_value = todo.TodoGatewayResult(
            ok=False,
            channel=approval_models.ApprovalTask.TODO_CHANNEL_TODO_API,
            task_id='',
            error='network timeout',
            raw={},
        )
        _, task = self._create_pending_task()
        with self.captureOnCommitCallbacks(execute=True):
            todo.schedule_create_for_task(task, originator=self.owner)

        summary = todo.process_outbox(batch_size=10)

        outbox_item = approval_models.ApprovalTodoOutbox.objects.filter(task=task).first()
        task.refresh_from_db()
        self.assertEqual(summary['dead'], 1)
        self.assertEqual(outbox_item.status, approval_models.ApprovalTodoOutbox.STATUS_DEAD)
        self.assertEqual(task.todo_status, approval_models.ApprovalTask.TODO_STATUS_FAILED)
        self.assertEqual(task.todo_retry_count, 1)
        self.assertIsNone(task.todo_next_retry_at)

    @override_settings(DINGTALK={'TODO_RETRY_ENABLED': '0'})
    def test_process_outbox_skips_failed_items_when_retry_disabled(self):
        _, task = self._create_pending_task()
        item = approval_models.ApprovalTodoOutbox.objects.create(
            task=task,
            action=approval_models.ApprovalTodoOutbox.ACTION_CREATE,
            source_id=todo.build_todo_source_id(task.id),
            payload={},
            status=approval_models.ApprovalTodoOutbox.STATUS_FAILED,
            next_retry_at=timezone.now(),
            retry_count=2,
        )

        summary = todo.process_outbox(batch_size=10)

        item.refresh_from_db()
        self.assertEqual(summary['processed'], 0)
        self.assertEqual(item.status, approval_models.ApprovalTodoOutbox.STATUS_FAILED)
