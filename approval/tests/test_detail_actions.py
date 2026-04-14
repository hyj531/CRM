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
