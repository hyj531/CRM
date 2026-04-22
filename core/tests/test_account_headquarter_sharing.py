from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core import models


class AccountHeadquarterSharingTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region_root_a = models.Region.objects.create(name='总部A', code='hq-a')
        cls.region_child_a = models.Region.objects.create(name='分区A1', code='hq-a-1', parent=cls.region_root_a)
        cls.region_root_b = models.Region.objects.create(name='总部B', code='hq-b')

        cls.role_region = models.Role.objects.create(
            name='区域权限-客户共享',
            code='account-share-region',
            data_scope=models.Role.SCOPE_REGION,
        )
        cls.owner_root_a = models.User.objects.create_user(
            username='owner_root_a',
            password='pass1234',
            region=cls.region_root_a,
            role=cls.role_region,
        )
        cls.owner_child_a = models.User.objects.create_user(
            username='owner_child_a',
            password='pass1234',
            region=cls.region_child_a,
            role=cls.role_region,
        )
        cls.owner_root_b = models.User.objects.create_user(
            username='owner_root_b',
            password='pass1234',
            region=cls.region_root_b,
            role=cls.role_region,
        )

        cls.account_root_a = models.Account.objects.create(
            full_name='总部A客户',
            short_name='总部A',
            region=cls.region_root_a,
            owner=cls.owner_root_a,
        )
        cls.account_child_a_self = models.Account.objects.create(
            full_name='分区A1-本人客户',
            short_name='A1-本人',
            region=cls.region_child_a,
            owner=cls.owner_child_a,
        )
        cls.account_child_a_other = models.Account.objects.create(
            full_name='分区A1-他人客户',
            short_name='A1-他人',
            region=cls.region_child_a,
            owner=cls.owner_child_a,
        )
        cls.account_root_b = models.Account.objects.create(
            full_name='总部B客户',
            short_name='总部B',
            region=cls.region_root_b,
            owner=cls.owner_root_b,
        )

    def _results(self, response):
        payload = response.data
        if isinstance(payload, dict) and 'results' in payload:
            return payload['results']
        return payload

    def test_child_region_user_can_see_same_tree_headquarter_accounts(self):
        user_child = models.User.objects.create_user(
            username='user_child_region_scope',
            password='pass1234',
            region=self.region_child_a,
            role=self.role_region,
        )
        self.client.force_authenticate(user=user_child)
        response = self.client.get(reverse('account-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {item['full_name'] for item in self._results(response)}

        self.assertIn(self.account_root_a.full_name, names)
        self.assertIn(self.account_child_a_self.full_name, names)
        self.assertIn(self.account_child_a_other.full_name, names)
        self.assertNotIn(self.account_root_b.full_name, names)

    def test_account_detail_allows_same_tree_headquarter_and_blocks_other_tree(self):
        user_child = models.User.objects.create_user(
            username='user_child_region_scope_detail',
            password='pass1234',
            region=self.region_child_a,
            role=self.role_region,
        )
        self.client.force_authenticate(user=user_child)

        detail_ok = self.client.get(reverse('account-detail', args=[self.account_root_a.id]))
        self.assertEqual(detail_ok.status_code, status.HTTP_200_OK)
        detail_forbidden_tree = self.client.get(reverse('account-detail', args=[self.account_root_b.id]))
        self.assertEqual(detail_forbidden_tree.status_code, status.HTTP_404_NOT_FOUND)
