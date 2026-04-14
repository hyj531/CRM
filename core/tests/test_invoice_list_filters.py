from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from core import models


class InvoiceListFilterTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = models.Region.objects.create(name='华东', code='east-invoice-filter')
        cls.other_region = models.Region.objects.create(name='华北', code='north-invoice-filter')
        cls.role = models.Role.objects.create(
            name='销售-开票筛选',
            code='sales-invoice-filter',
            data_scope=models.Role.SCOPE_REGION,
        )

        user_model = get_user_model()
        cls.user = user_model.objects.create_user(
            username='invoice_filter_user',
            password='pass1234',
            region=cls.region,
            role=cls.role,
        )
        cls.other_user = user_model.objects.create_user(
            username='invoice_filter_other_user',
            password='pass1234',
            region=cls.other_region,
            role=cls.role,
        )

    def setUp(self):
        self.client.force_authenticate(user=self.user)
        self.list_url = reverse('invoice-list')

    def _list_results(self, response):
        data = response.data
        if isinstance(data, dict) and 'results' in data:
            return data['results']
        return data

    def _decimal(self, value):
        if value is None:
            return Decimal('0')
        return Decimal(str(value))

    def _create_invoice(
        self,
        *,
        suffix,
        invoice_no,
        contract_no,
        contract_name,
        account_full_name,
        account_short_name='',
        amount='100.00',
        status='draft',
        approval_status='pending',
        issued_at='2026-04-01',
        region=None,
        owner=None,
    ):
        region = region or self.region
        owner = owner or self.user
        account = models.Account.objects.create(
            full_name=account_full_name,
            short_name=account_short_name,
            region=region,
            owner=owner,
        )
        contract = models.Contract.objects.create(
            contract_no=contract_no,
            name=contract_name,
            account=account,
            amount='1000.00',
            region=region,
            owner=owner,
        )
        return models.Invoice.objects.create(
            invoice_no=invoice_no,
            contract=contract,
            account=account,
            amount=amount,
            status=status,
            approval_status=approval_status,
            issued_at=issued_at,
            region=region,
            owner=owner,
        )

    def test_search_matches_invoice_contract_and_account_fields(self):
        invoice_by_no = self._create_invoice(
            suffix='A',
            invoice_no='INV-ALPHA-001',
            contract_no='HT-001',
            contract_name='标准合同A',
            account_full_name='阿尔法科技有限公司',
            amount='100.00',
        )
        invoice_by_contract = self._create_invoice(
            suffix='B',
            invoice_no='INV-BETA-002',
            contract_no='HT-COMBO-002',
            contract_name='组合合同B',
            account_full_name='贝塔商贸有限公司',
            amount='200.00',
        )
        invoice_by_account = self._create_invoice(
            suffix='C',
            invoice_no='INV-GAMMA-003',
            contract_no='HT-003',
            contract_name='标准合同C',
            account_full_name='伽马工业有限公司',
            account_short_name='伽马',
            amount='300.00',
        )
        self._create_invoice(
            suffix='D',
            invoice_no='INV-OUTSIDE-004',
            contract_no='HT-004',
            contract_name='其他合同',
            account_full_name='其他客户',
            amount='400.00',
            region=self.other_region,
            owner=self.other_user,
        )

        response_no = self.client.get(self.list_url, {'search': 'ALPHA-001'})
        self.assertEqual(response_no.status_code, 200)
        ids_no = {item['id'] for item in self._list_results(response_no)}
        self.assertEqual(ids_no, {invoice_by_no.id})

        response_contract = self.client.get(self.list_url, {'search': 'COMBO-002'})
        self.assertEqual(response_contract.status_code, 200)
        ids_contract = {item['id'] for item in self._list_results(response_contract)}
        self.assertEqual(ids_contract, {invoice_by_contract.id})

        response_account = self.client.get(self.list_url, {'search': '伽马'})
        self.assertEqual(response_account.status_code, 200)
        ids_account = {item['id'] for item in self._list_results(response_account)}
        self.assertEqual(ids_account, {invoice_by_account.id})

    def test_issued_at_date_range_is_inclusive(self):
        before = self._create_invoice(
            suffix='E',
            invoice_no='INV-RANGE-BEFORE',
            contract_no='HT-RANGE-1',
            contract_name='范围前',
            account_full_name='范围客户前',
            amount='100.00',
            issued_at='2026-04-09',
        )
        start_day = self._create_invoice(
            suffix='F',
            invoice_no='INV-RANGE-START',
            contract_no='HT-RANGE-2',
            contract_name='范围起',
            account_full_name='范围客户起',
            amount='200.00',
            issued_at='2026-04-10',
        )
        end_day = self._create_invoice(
            suffix='G',
            invoice_no='INV-RANGE-END',
            contract_no='HT-RANGE-3',
            contract_name='范围止',
            account_full_name='范围客户止',
            amount='300.00',
            issued_at='2026-04-20',
        )
        self._create_invoice(
            suffix='H',
            invoice_no='INV-RANGE-AFTER',
            contract_no='HT-RANGE-4',
            contract_name='范围后',
            account_full_name='范围客户后',
            amount='400.00',
            issued_at='2026-04-21',
        )

        response = self.client.get(
            self.list_url,
            {'issued_at_start': '2026-04-10', 'issued_at_end': '2026-04-20', 'ordering': 'created_at'},
        )
        self.assertEqual(response.status_code, 200)
        ids = {item['id'] for item in self._list_results(response)}
        self.assertEqual(ids, {start_day.id, end_day.id})
        self.assertNotIn(before.id, ids)

    def test_total_amount_is_based_on_filtered_queryset_not_page(self):
        self._create_invoice(
            suffix='I',
            invoice_no='INV-TOTAL-1',
            contract_no='HT-TOTAL-1',
            contract_name='总额合同1',
            account_full_name='总额客户1',
            amount='100.00',
            status='draft',
        )
        self._create_invoice(
            suffix='J',
            invoice_no='INV-TOTAL-2',
            contract_no='HT-TOTAL-2',
            contract_name='总额合同2',
            account_full_name='总额客户2',
            amount='200.00',
            status='draft',
        )
        self._create_invoice(
            suffix='K',
            invoice_no='INV-TOTAL-3',
            contract_no='HT-TOTAL-3',
            contract_name='总额合同3',
            account_full_name='总额客户3',
            amount='300.00',
            status='paid',
        )

        response_page_1 = self.client.get(self.list_url, {'status': 'draft', 'page_size': 1, 'page': 1})
        self.assertEqual(response_page_1.status_code, 200)
        self.assertEqual(response_page_1.data.get('count'), 2)
        self.assertEqual(len(self._list_results(response_page_1)), 1)
        self.assertEqual(self._decimal(response_page_1.data.get('total_amount')), Decimal('300.00'))

        response_page_2 = self.client.get(self.list_url, {'status': 'draft', 'page_size': 1, 'page': 2})
        self.assertEqual(response_page_2.status_code, 200)
        self.assertEqual(response_page_2.data.get('count'), 2)
        self.assertEqual(len(self._list_results(response_page_2)), 1)
        self.assertEqual(self._decimal(response_page_2.data.get('total_amount')), Decimal('300.00'))

    def test_combined_filters_keep_count_results_and_total_consistent(self):
        kept_low = self._create_invoice(
            suffix='L',
            invoice_no='COMBO-LOW',
            contract_no='HT-COMBO-L',
            contract_name='组合合同低',
            account_full_name='组合客户低',
            amount='80.00',
            status='issued',
            approval_status='approved',
            issued_at='2026-04-05',
        )
        kept_high = self._create_invoice(
            suffix='M',
            invoice_no='COMBO-HIGH',
            contract_no='HT-COMBO-H',
            contract_name='组合合同高',
            account_full_name='组合客户高',
            amount='120.00',
            status='issued',
            approval_status='approved',
            issued_at='2026-04-06',
        )
        self._create_invoice(
            suffix='N',
            invoice_no='COMBO-WRONG-STATUS',
            contract_no='HT-COMBO-N',
            contract_name='组合合同状态不符',
            account_full_name='组合客户状态不符',
            amount='500.00',
            status='void',
            approval_status='approved',
            issued_at='2026-04-07',
        )
        self._create_invoice(
            suffix='O',
            invoice_no='COMBO-WRONG-APPROVAL',
            contract_no='HT-COMBO-O',
            contract_name='组合合同审批不符',
            account_full_name='组合客户审批不符',
            amount='600.00',
            status='issued',
            approval_status='pending',
            issued_at='2026-04-08',
        )
        self._create_invoice(
            suffix='P',
            invoice_no='COMBO-WRONG-DATE',
            contract_no='HT-COMBO-P',
            contract_name='组合合同日期不符',
            account_full_name='组合客户日期不符',
            amount='700.00',
            status='issued',
            approval_status='approved',
            issued_at='2026-03-25',
        )

        response = self.client.get(
            self.list_url,
            {
                'search': 'COMBO',
                'status': 'issued',
                'approval_status': 'approved',
                'issued_at_start': '2026-04-01',
                'issued_at_end': '2026-04-30',
                'ordering': 'amount',
            },
        )
        self.assertEqual(response.status_code, 200)
        results = self._list_results(response)
        self.assertEqual(response.data.get('count'), 2)
        self.assertEqual([item['id'] for item in results], [kept_low.id, kept_high.id])
        self.assertEqual(self._decimal(response.data.get('total_amount')), Decimal('200.00'))
