from rest_framework import status
from rest_framework.test import APITestCase

from approval import models as approval_models
from approval.services import engine
from core import models as core_models
from django.utils import timezone
from datetime import timedelta


class ApprovalInstanceMineTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = core_models.Region.objects.create(name='华东', code='east-mine')
        cls.other_region = core_models.Region.objects.create(name='华南', code='south-mine')
        cls.owner_role = core_models.Role.objects.create(
            name='销售-实例列表测试',
            code='sales-instance-mine',
            data_scope=core_models.Role.SCOPE_REGION_CHILDREN,
        )
        cls.approver_role = core_models.Role.objects.create(
            name='审批-实例列表测试',
            code='approver-instance-mine',
            data_scope=core_models.Role.SCOPE_REGION_CHILDREN,
        )
        cls.owner = core_models.User.objects.create_user(
            username='owner_instance_mine',
            password='pass1234',
            region=cls.region,
            role=cls.owner_role,
        )
        cls.approver = core_models.User.objects.create_user(
            username='approver_instance_mine',
            password='pass1234',
            region=cls.region,
            role=cls.approver_role,
        )
        cls.final_approver = core_models.User.objects.create_user(
            username='final_approver_instance_mine',
            password='pass1234',
            region=cls.region,
            role=cls.approver_role,
        )
        cls.cross_region_approver = core_models.User.objects.create_user(
            username='cross_region_approver_instance_mine',
            password='pass1234',
            region=cls.other_region,
            role=cls.approver_role,
        )
        cls.account = core_models.Account.objects.create(
            full_name='实例列表测试客户',
            short_name='实例客户',
            region=cls.region,
            owner=cls.owner,
        )
        flow = approval_models.ApprovalFlow.objects.create(
            name='实例列表测试流程',
            target_type=approval_models.ApprovalFlow.TARGET_CONTRACT,
            region=cls.region,
            is_active=True,
        )
        approval_models.ApprovalStep.objects.create(
            flow=flow,
            order=1,
            name='审批节点',
            approver_user=cls.approver,
        )
        approval_models.ApprovalStep.objects.create(
            flow=flow,
            order=2,
            name='终审节点',
            approver_user=cls.final_approver,
        )

    def setUp(self):
        self.contract = core_models.Contract.objects.create(
            account=self.account,
            amount='100.00',
            region=self.region,
            owner=self.owner,
            approval_status='pending',
        )
        with self.captureOnCommitCallbacks(execute=True):
            self.instance = engine.start_approval(self.contract, self.owner)
        self.task = self.instance.tasks.filter(status=approval_models.ApprovalTask.STATUS_PENDING).first()

    def test_pending_tab_returns_instance_rows(self):
        self.client.force_authenticate(user=self.approver)
        response = self.client.get('/api/approval-instances/mine/?tab=pending&page_size=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data.get('results', [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get('instance_id'), self.instance.id)
        self.assertEqual(rows[0].get('instance_status'), approval_models.ApprovalInstance.STATUS_PENDING)
        self.assertEqual(rows[0].get('my_pending_task_ids'), [self.task.id])

    def test_processed_tab_returns_instances_i_have_handled(self):
        with self.captureOnCommitCallbacks(execute=True):
            engine.approve_task(self.task, self.approver, approved=True, comment='同意')

        self.client.force_authenticate(user=self.approver)
        response = self.client.get('/api/approval-instances/mine/?tab=processed&page_size=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data.get('results', [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get('instance_id'), self.instance.id)
        self.assertEqual(rows[0].get('instance_status'), approval_models.ApprovalInstance.STATUS_PENDING)
        self.assertEqual(rows[0].get('my_last_action_status'), approval_models.ApprovalTask.STATUS_APPROVED)
        self.assertEqual(rows[0].get('my_pending_task_ids'), [])

    def test_started_tab_returns_instances_started_by_me(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get('/api/approval-instances/mine/?tab=started&page_size=100')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data.get('results', [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get('instance_id'), self.instance.id)
        self.assertEqual(rows[0].get('started_by'), self.owner.id)

    def test_started_tab_supports_keyword_filter(self):
        second_contract = core_models.Contract.objects.create(
            account=self.account,
            name='华东-二号合同',
            amount='220.00',
            region=self.region,
            owner=self.owner,
            approval_status='pending',
        )
        with self.captureOnCommitCallbacks(execute=True):
            engine.start_approval(second_contract, self.owner)

        self.client.force_authenticate(user=self.owner)
        response = self.client.get('/api/approval-instances/mine/?tab=started&keyword=二号')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data.get('results', [])
        self.assertEqual(len(rows), 1)
        self.assertIn('二号', rows[0].get('target_title', ''))

    def test_mine_stats_returns_expected_counts(self):
        stale_time = timezone.now() - timedelta(days=2)
        approval_models.ApprovalInstance.objects.filter(id=self.instance.id).update(created_at=stale_time)
        self.instance.refresh_from_db()

        second_contract = core_models.Contract.objects.create(
            account=self.account,
            name='华东-已处理合同',
            amount='320.00',
            region=self.region,
            owner=self.owner,
            approval_status='pending',
        )
        with self.captureOnCommitCallbacks(execute=True):
            second_instance = engine.start_approval(second_contract, self.owner)
        second_task = second_instance.tasks.filter(status=approval_models.ApprovalTask.STATUS_PENDING).first()
        with self.captureOnCommitCallbacks(execute=True):
            engine.approve_task(second_task, self.approver, approved=True, comment='同意')

        self.client.force_authenticate(user=self.approver)
        response = self.client.get('/api/approval-instances/mine/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('pending_count'), 1)
        self.assertEqual(response.data.get('overdue_count'), 1)
        self.assertEqual(response.data.get('processed_today_count'), 1)
        self.assertEqual(response.data.get('started_running_count'), 0)

    def test_cross_region_add_sign_assignee_can_see_pending_instance_and_details(self):
        with self.captureOnCommitCallbacks(execute=True):
            add_task = engine.add_sign_task(
                self.task,
                self.approver,
                self.cross_region_approver,
                comment='跨区域加签',
            )

        self.client.force_authenticate(user=self.cross_region_approver)
        pending_resp = self.client.get('/api/approval-instances/mine/?tab=pending&page_size=100')
        self.assertEqual(pending_resp.status_code, status.HTTP_200_OK)
        rows = pending_resp.data.get('results', [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get('instance_id'), self.instance.id)
        self.assertIn(add_task.id, rows[0].get('my_pending_task_ids', []))

        instance_detail_resp = self.client.get(f'/api/approval-instances/{self.instance.id}/detail/')
        self.assertEqual(instance_detail_resp.status_code, status.HTTP_200_OK)
        task_detail_resp = self.client.get(f'/api/approval-tasks/{add_task.id}/detail/')
        self.assertEqual(task_detail_resp.status_code, status.HTTP_200_OK)
