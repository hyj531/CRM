from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from approval import models as approval_models
from approval.services import engine as approval_engine
from core import models


class ApprovalProgressEndpointTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = models.Region.objects.create(name='华南', code='south-progress')
        cls.other_region = models.Region.objects.create(name='华北', code='north-progress')
        cls.owner_role = models.Role.objects.create(
            name='销售-进度测试',
            code='sales-progress',
            data_scope=models.Role.SCOPE_REGION_CHILDREN,
        )
        cls.approver_role = models.Role.objects.create(
            name='审批-进度测试',
            code='approver-progress',
            data_scope=models.Role.SCOPE_REGION_CHILDREN,
        )
        cls.owner = models.User.objects.create_user(
            username='owner_progress_test',
            password='pass1234',
            region=cls.region,
            role=cls.owner_role,
        )
        cls.approver = models.User.objects.create_user(
            username='approver_progress_test',
            password='pass1234',
            region=cls.region,
            role=cls.approver_role,
        )
        cls.other_user = models.User.objects.create_user(
            username='other_progress_test',
            password='pass1234',
            region=cls.other_region,
            role=cls.owner_role,
        )
        cls.account = models.Account.objects.create(
            full_name='进度接口测试客户',
            short_name='进度客户',
            region=cls.region,
            owner=cls.owner,
        )
        cls.contract = models.Contract.objects.create(
            account=cls.account,
            name='进度合同A',
            amount='500.00',
            region=cls.region,
            owner=cls.owner,
            approval_status='pending',
        )
        cls.invoice = models.Invoice.objects.create(
            contract=cls.contract,
            account=cls.account,
            amount='300.00',
            region=cls.region,
            owner=cls.owner,
            approval_status='pending',
        )

        contract_flow = approval_models.ApprovalFlow.objects.create(
            name='合同进度测试流程',
            target_type=approval_models.ApprovalFlow.TARGET_CONTRACT,
            region=cls.region,
            is_active=True,
        )
        approval_models.ApprovalStep.objects.create(
            flow=contract_flow,
            order=1,
            name='合同审批节点',
            approver_user=cls.approver,
        )
        invoice_flow = approval_models.ApprovalFlow.objects.create(
            name='开票进度测试流程',
            target_type=approval_models.ApprovalFlow.TARGET_INVOICE,
            region=cls.region,
            is_active=True,
        )
        approval_models.ApprovalStep.objects.create(
            flow=invoice_flow,
            order=1,
            name='开票审批节点',
            approver_user=cls.approver,
        )

    def setUp(self):
        self.client.force_authenticate(user=self.owner)

    def test_contract_progress_returns_empty_when_no_instance(self):
        response = self.client.get(reverse('contract-approval-progress', args=[self.contract.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data.get('has_instance'))
        self.assertIsNone(response.data.get('instance_id'))

    def test_contract_progress_prefers_pending_instance(self):
        with self.captureOnCommitCallbacks(execute=True):
            approval_engine.start_approval(self.contract, self.owner)

        response = self.client.get(reverse('contract-approval-progress', args=[self.contract.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('has_instance'))
        self.assertEqual(response.data.get('instance_status'), approval_models.ApprovalInstance.STATUS_PENDING)
        self.assertEqual(response.data.get('current_step_name'), '合同审批节点')
        pending_approvers = response.data.get('pending_approvers') or []
        self.assertTrue(pending_approvers)
        self.assertEqual(pending_approvers[0].get('username'), self.approver.username)

    def test_contract_progress_falls_back_to_latest_history_instance(self):
        with self.captureOnCommitCallbacks(execute=True):
            instance = approval_engine.start_approval(self.contract, self.owner)
        task = instance.tasks.filter(status=approval_models.ApprovalTask.STATUS_PENDING).first()
        with self.captureOnCommitCallbacks(execute=True):
            approval_engine.approve_task(task, self.approver, approved=True, comment='同意')

        response = self.client.get(reverse('contract-approval-progress', args=[self.contract.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('has_instance'))
        self.assertEqual(response.data.get('instance_status'), approval_models.ApprovalInstance.STATUS_APPROVED)
        self.assertEqual(response.data.get('pending_approvers'), [])

    def test_invoice_progress_returns_pending_instance_summary(self):
        with self.captureOnCommitCallbacks(execute=True):
            approval_engine.start_approval(self.invoice, self.owner)

        response = self.client.get(reverse('invoice-approval-progress', args=[self.invoice.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('has_instance'))
        self.assertEqual(response.data.get('instance_status'), approval_models.ApprovalInstance.STATUS_PENDING)
        self.assertEqual(response.data.get('current_step_name'), '开票审批节点')

    def test_progress_endpoint_respects_scope(self):
        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(reverse('contract-approval-progress', args=[self.contract.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
