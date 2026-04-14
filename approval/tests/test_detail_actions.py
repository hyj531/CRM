from rest_framework import status
from rest_framework.test import APITestCase

from approval import models as approval_models
from approval.services import engine
from core import models as core_models


class ApprovalDetailActionsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = core_models.Region.objects.create(name='华北', code='north-detail')
        cls.owner_role = core_models.Role.objects.create(
            name='销售-详情测试',
            code='sales-detail',
            data_scope=core_models.Role.SCOPE_REGION_CHILDREN,
        )
        cls.approver_role = core_models.Role.objects.create(
            name='审批-详情测试',
            code='approver-detail',
            data_scope=core_models.Role.SCOPE_REGION_CHILDREN,
        )
        cls.owner = core_models.User.objects.create_user(
            username='owner_detail_test',
            password='pass1234',
            region=cls.region,
            role=cls.owner_role,
        )
        cls.approver = core_models.User.objects.create_user(
            username='approver_detail_test',
            password='pass1234',
            region=cls.region,
            role=cls.approver_role,
        )
        cls.approver_b = core_models.User.objects.create_user(
            username='approver_detail_test_b',
            password='pass1234',
            region=cls.region,
            role=cls.approver_role,
        )
        cls.staff_admin = core_models.User.objects.create_user(
            username='staff_detail_admin',
            password='pass1234',
            region=cls.region,
            role=cls.owner_role,
            is_staff=True,
        )
        cls.outsider = core_models.User.objects.create_user(
            username='detail_outsider',
            password='pass1234',
            region=cls.region,
            role=cls.owner_role,
        )
        cls.account = core_models.Account.objects.create(
            full_name='详情测试客户',
            short_name='详情客户',
            region=cls.region,
            owner=cls.owner,
        )
        cls.contract = core_models.Contract.objects.create(
            account=cls.account,
            amount='1200.00',
            region=cls.region,
            owner=cls.owner,
            approval_status='pending',
        )
        flow = approval_models.ApprovalFlow.objects.create(
            name='详情测试流程',
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

    def setUp(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.instance = engine.start_approval(self.contract, self.owner)
        self.task = self.instance.tasks.filter(status=approval_models.ApprovalTask.STATUS_PENDING).first()

    def test_task_detail_endpoint_returns_expected_shape(self):
        self.client.force_authenticate(user=self.approver)
        response = self.client.get(f'/api/approval-tasks/{self.task.id}/detail/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('task', response.data)
        self.assertIn('instance', response.data)
        self.assertIn('target', response.data)

    def test_instance_detail_endpoint_returns_expected_shape(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f'/api/approval-instances/{self.instance.id}/detail/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('instance', response.data)
        self.assertIn('tasks', response.data)
        self.assertIn('logs', response.data)

    def test_decision_endpoint_still_works_after_detail_action_rename(self):
        self.client.force_authenticate(user=self.approver)
        response = self.client.post(
            f'/api/approval-tasks/{self.task.id}/decision/',
            {'approved': True, 'comment': '同意'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('status'), approval_models.ApprovalInstance.STATUS_APPROVED)

    def test_invoice_task_detail_includes_contract_attachments(self):
        core_models.ContractAttachment.objects.create(
            contract=self.contract,
            region=self.region,
            owner=self.owner,
            file='contract_attachments/2026/04/test-attachment.pdf',
            original_name='测试合同附件.pdf',
        )
        invoice = core_models.Invoice.objects.create(
            contract=self.contract,
            account=self.account,
            amount='300.00',
            region=self.region,
            owner=self.owner,
            approval_status='pending',
        )
        flow = approval_models.ApprovalFlow.objects.create(
            name='开票详情测试流程',
            target_type=approval_models.ApprovalFlow.TARGET_INVOICE,
            region=self.region,
            is_active=True,
        )
        approval_models.ApprovalStep.objects.create(
            flow=flow,
            order=1,
            name='开票审批节点',
            approver_user=self.approver,
        )

        with self.captureOnCommitCallbacks(execute=True):
            invoice_instance = engine.start_approval(invoice, self.owner)
        invoice_task = invoice_instance.tasks.filter(status=approval_models.ApprovalTask.STATUS_PENDING).first()

        self.client.force_authenticate(user=self.approver)
        response = self.client.get(f'/api/approval-tasks/{invoice_task.id}/detail/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        attachments = response.data.get('target', {}).get('attachments', [])
        self.assertTrue(attachments)
        self.assertEqual(attachments[0].get('original_name'), '测试合同附件.pdf')

    def test_add_sign_task_reject_is_forbidden_via_decision_api(self):
        self.client.force_authenticate(user=self.approver)
        add_sign_resp = self.client.post(
            f'/api/approval-tasks/{self.task.id}/add_sign/',
            {'assignee_id': self.approver_b.id, 'comment': '请补充意见'},
            format='json',
        )
        self.assertEqual(add_sign_resp.status_code, status.HTTP_201_CREATED)
        add_sign_task_id = add_sign_resp.data.get('id')
        self.assertTrue(add_sign_task_id)

        self.client.force_authenticate(user=self.approver_b)
        reject_resp = self.client.post(
            f'/api/approval-tasks/{add_sign_task_id}/decision/',
            {'approved': False, 'comment': '不同意'},
            format='json',
        )
        self.assertEqual(reject_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(reject_resp.data.get('detail'), '加签任务仅支持提交意见，不可驳回流程')

    def test_transfer_and_add_sign_permissions(self):
        self.client.force_authenticate(user=self.outsider)
        denied_resp = self.client.post(
            f'/api/approval-tasks/{self.task.id}/transfer/',
            {'assignee_id': self.approver_b.id, 'comment': '无权转办'},
            format='json',
        )
        self.assertEqual(denied_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(denied_resp.data.get('detail'), 'Not allowed to transfer this task')

        self.client.force_authenticate(user=self.staff_admin)
        add_sign_resp = self.client.post(
            f'/api/approval-tasks/{self.task.id}/add_sign/',
            {'assignee_id': self.approver_b.id, 'comment': '管理员发起加签'},
            format='json',
        )
        self.assertEqual(add_sign_resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(add_sign_resp.data.get('parent_task'), self.task.id)

    def test_detail_response_includes_parent_task_and_task_kind(self):
        with self.captureOnCommitCallbacks(execute=True):
            add_task = engine.add_sign_task(self.task, self.approver, self.approver_b, comment='请给意见')

        self.client.force_authenticate(user=self.owner)
        instance_resp = self.client.get(f'/api/approval-instances/{self.instance.id}/detail/')
        self.assertEqual(instance_resp.status_code, status.HTTP_200_OK)
        tasks = instance_resp.data.get('tasks', [])
        add_task_row = next(item for item in tasks if item.get('id') == add_task.id)
        self.assertEqual(add_task_row.get('parent_task_id'), self.task.id)
        self.assertEqual(add_task_row.get('task_kind'), 'add_sign')
