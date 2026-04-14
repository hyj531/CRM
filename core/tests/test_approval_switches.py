from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from approval import models as approval_models
from core import models
from core.services import approval_switches


class ApprovalSwitchesAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = models.Region.objects.create(name='华东', code='east-switch')
        cls.role = models.Role.objects.create(
            name='销售-开关测试',
            code='sales-switch',
            data_scope=models.Role.SCOPE_REGION_CHILDREN,
        )
        cls.approver_role = models.Role.objects.create(
            name='审批人-开关测试',
            code='approver-switch',
            data_scope=models.Role.SCOPE_REGION_CHILDREN,
        )
        cls.submitter = models.User.objects.create_user(
            username='approval_switch_submitter',
            password='pass1234',
            region=cls.region,
            role=cls.role,
        )
        cls.approver = models.User.objects.create_user(
            username='approval_switch_approver',
            password='pass1234',
            region=cls.region,
            role=cls.approver_role,
        )
        models.RolePermission.objects.create(
            role=cls.role,
            module=models.RolePermission.MODULE_CONTRACT,
            can_create=True,
            can_update=True,
            can_delete=True,
            can_approve=True,
        )
        models.RolePermission.objects.create(
            role=cls.role,
            module=models.RolePermission.MODULE_INVOICE,
            can_create=True,
            can_update=True,
            can_delete=True,
            can_approve=True,
        )
        cls.account = models.Account.objects.create(
            full_name='审批开关测试客户',
            short_name='开关测试',
            region=cls.region,
            owner=cls.submitter,
        )
        cls.contract = models.Contract.objects.create(
            account=cls.account,
            amount='1000.00',
            region=cls.region,
            owner=cls.submitter,
            approval_status='pending',
        )
        cls.invoice = models.Invoice.objects.create(
            contract=cls.contract,
            account=cls.account,
            amount='500.00',
            region=cls.region,
            owner=cls.submitter,
            approval_status='pending',
        )
        contract_flow = approval_models.ApprovalFlow.objects.create(
            name='合同审批流-开关测试',
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
            name='开票审批流-开关测试',
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
        self.client.force_authenticate(user=self.submitter)
        self._set_switches(contract=True, invoice=True)

    def _set_switches(self, contract=None, invoice=None):
        setting, _ = models.ApprovalModuleSetting.objects.get_or_create(
            singleton_key=models.ApprovalModuleSetting.SINGLETON_KEY_DEFAULT
        )
        if contract is not None:
            setting.contract_approval_enabled = bool(contract)
        if invoice is not None:
            setting.invoice_approval_enabled = bool(invoice)
        setting.save()
        approval_switches.clear_approval_switches_cache()

    def test_auth_me_returns_approval_switches(self):
        response = self.client.get(reverse('current_user'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data.get('approval_switches'),
            {'contract': True, 'invoice': True},
        )

    def test_auth_me_reflects_switch_updates(self):
        self._set_switches(contract=False, invoice=False)
        response = self.client.get(reverse('current_user'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data.get('approval_switches'),
            {'contract': False, 'invoice': False},
        )

    def test_contract_submit_approval_blocks_when_switch_disabled(self):
        self._set_switches(contract=False)
        response = self.client.post(reverse('contract-submit-approval', args=[self.contract.id]), {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('合同审批未启用', response.data.get('detail', ''))
        self.assertFalse(
            approval_models.ApprovalInstance.objects.filter(
                target_type=approval_models.ApprovalFlow.TARGET_CONTRACT,
                object_id=self.contract.id,
            ).exists()
        )

    def test_invoice_submit_approval_blocks_when_switch_disabled(self):
        self._set_switches(invoice=False)
        response = self.client.post(reverse('invoice-submit-approval', args=[self.invoice.id]), {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('开票审批未启用', response.data.get('detail', ''))
        self.assertFalse(
            approval_models.ApprovalInstance.objects.filter(
                target_type=approval_models.ApprovalFlow.TARGET_INVOICE,
                object_id=self.invoice.id,
            ).exists()
        )

    def test_default_switch_true_allows_contract_submit_approval(self):
        response = self.client.post(reverse('contract-submit-approval', args=[self.contract.id]), {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            approval_models.ApprovalInstance.objects.filter(
                target_type=approval_models.ApprovalFlow.TARGET_CONTRACT,
                object_id=self.contract.id,
                status=approval_models.ApprovalInstance.STATUS_PENDING,
            ).exists()
        )

    def test_default_switch_true_allows_invoice_submit_approval(self):
        response = self.client.post(reverse('invoice-submit-approval', args=[self.invoice.id]), {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            approval_models.ApprovalInstance.objects.filter(
                target_type=approval_models.ApprovalFlow.TARGET_INVOICE,
                object_id=self.invoice.id,
                status=approval_models.ApprovalInstance.STATUS_PENDING,
            ).exists()
        )

    def test_contract_delete_pending_blocked_only_when_switch_enabled(self):
        contract = models.Contract.objects.create(
            account=self.account,
            amount='200.00',
            region=self.region,
            owner=self.submitter,
            approval_status='pending',
        )

        self._set_switches(contract=True)
        blocked = self.client.delete(reverse('contract-detail', args=[contract.id]))
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('禁止删除', blocked.data.get('detail', ''))
        self.assertTrue(models.Contract.objects.filter(id=contract.id).exists())

        self._set_switches(contract=False)
        allowed = self.client.delete(reverse('contract-detail', args=[contract.id]))
        self.assertEqual(allowed.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(models.Contract.objects.filter(id=contract.id).exists())

    def test_invoice_delete_pending_blocked_only_when_switch_enabled(self):
        invoice = models.Invoice.objects.create(
            contract=self.contract,
            account=self.account,
            amount='180.00',
            region=self.region,
            owner=self.submitter,
            approval_status='pending',
        )

        self._set_switches(invoice=True)
        blocked = self.client.delete(reverse('invoice-detail', args=[invoice.id]))
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('禁止删除', blocked.data.get('detail', ''))
        self.assertTrue(models.Invoice.objects.filter(id=invoice.id).exists())

        self._set_switches(invoice=False)
        allowed = self.client.delete(reverse('invoice-detail', args=[invoice.id]))
        self.assertEqual(allowed.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(models.Invoice.objects.filter(id=invoice.id).exists())

    def test_engine_entry_create_approval_instance_blocks_when_contract_switch_disabled(self):
        self._set_switches(contract=False)
        response = self.client.post(
            reverse('approval-instance-list'),
            {'target_type': approval_models.ApprovalFlow.TARGET_CONTRACT, 'object_id': self.contract.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('合同审批未启用', response.data.get('detail', ''))

    def test_contract_approval_status_is_readonly_when_switch_enabled(self):
        response = self.client.patch(
            reverse('contract-detail', args=[self.contract.id]),
            {'approval_status': 'approved'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.approval_status, 'pending')

    def test_invoice_approval_status_is_readonly_when_switch_enabled(self):
        response = self.client.patch(
            reverse('invoice-detail', args=[self.invoice.id]),
            {'approval_status': 'approved'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.approval_status, 'pending')

    def test_contract_approval_status_can_be_updated_when_switch_disabled(self):
        self._set_switches(contract=False)
        response = self.client.patch(
            reverse('contract-detail', args=[self.contract.id]),
            {'approval_status': 'approved'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.approval_status, 'approved')

    def test_invoice_approval_status_can_be_updated_when_switch_disabled(self):
        self._set_switches(invoice=False)
        response = self.client.patch(
            reverse('invoice-detail', args=[self.invoice.id]),
            {'approval_status': 'approved'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.approval_status, 'approved')
