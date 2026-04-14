from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core import models


class ContractNoGenerationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = models.Region.objects.create(name='华东-合同编号', code='east-contract-no')
        cls.role = models.Role.objects.create(
            name='合同编号测试角色',
            code='contract-no-role',
            data_scope=models.Role.SCOPE_REGION_CHILDREN,
        )
        cls.user = models.User.objects.create_user(
            username='contract_no_user',
            password='pass1234',
            region=cls.region,
            role=cls.role,
        )
        cls.admin = models.User.objects.create_user(
            username='contract_no_admin',
            password='pass1234',
            region=cls.region,
            role=cls.role,
            is_staff=True,
        )
        cls.account = models.Account.objects.create(
            full_name='合同编号测试客户',
            short_name='编号客户',
            region=cls.region,
            owner=cls.user,
        )

    def _create_contract(self, **extra):
        payload = {
            'name': '测试合同',
            'account': self.account.id,
            'amount': '100.00',
            'status': 'draft',
        }
        payload.update(extra)
        return self.client.post(reverse('contract-list'), payload, format='json')

    def test_create_generates_contract_no_and_ignores_input_value(self):
        self.client.force_authenticate(user=self.user)
        today_prefix = timezone.localdate().strftime('%Y%m%d')

        first = self._create_contract(contract_no='MANUAL-001')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first.data['contract_no'], f'{today_prefix}001')

        second = self._create_contract(contract_no='MANUAL-002')
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.data['contract_no'], f'{today_prefix}002')

    def test_create_uses_existing_same_day_max_serial_as_baseline(self):
        self.client.force_authenticate(user=self.user)
        today_prefix = timezone.localdate().strftime('%Y%m%d')
        models.Contract.objects.create(
            contract_no=f'{today_prefix}005',
            name='历史合同',
            account=self.account,
            amount='88.00',
            region=self.region,
            owner=self.user,
        )
        models.Contract.objects.create(
            contract_no=f'{today_prefix}ABC',
            name='无效编号合同',
            account=self.account,
            amount='66.00',
            region=self.region,
            owner=self.user,
        )

        response = self._create_contract()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['contract_no'], f'{today_prefix}006')

    def test_contract_no_update_is_admin_only(self):
        today_prefix = timezone.localdate().strftime('%Y%m%d')
        contract = models.Contract.objects.create(
            contract_no=f'{today_prefix}101',
            name='待修改合同',
            account=self.account,
            amount='200.00',
            region=self.region,
            owner=self.user,
        )

        self.client.force_authenticate(user=self.user)
        deny_resp = self.client.patch(
            reverse('contract-detail', args=[contract.id]),
            {'contract_no': f'{today_prefix}888'},
            format='json',
        )
        self.assertEqual(deny_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('contract_no', deny_resp.data)
        contract.refresh_from_db()
        self.assertEqual(contract.contract_no, f'{today_prefix}101')

        self.client.force_authenticate(user=self.admin)
        allow_resp = self.client.patch(
            reverse('contract-detail', args=[contract.id]),
            {'contract_no': f'{today_prefix}888'},
            format='json',
        )
        self.assertEqual(allow_resp.status_code, status.HTTP_200_OK)
        contract.refresh_from_db()
        self.assertEqual(contract.contract_no, f'{today_prefix}888')

    def test_create_returns_error_when_daily_serial_reaches_999(self):
        self.client.force_authenticate(user=self.user)
        today = timezone.localdate()
        models.ContractNoSequence.objects.create(sequence_date=today, last_serial=999)

        response = self._create_contract()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('contract_no', response.data)
