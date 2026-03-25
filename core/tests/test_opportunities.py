from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APITestCase

from core import models


class OpportunityAPITests(APITestCase):
    def _list_results(self, response):
        data = response.data
        if isinstance(data, dict) and 'results' in data:
            return data['results']
        return data
    @classmethod
    def setUpTestData(cls):
        cls.region_parent = models.Region.objects.create(name='Parent', code='parent')
        cls.region_child = models.Region.objects.create(
            name='Child',
            code='child',
            parent=cls.region_parent,
        )
        cls.region_other = models.Region.objects.create(name='Other', code='other')

        cls.role_self = models.Role.objects.create(
            name='Self',
            code='self',
            data_scope=models.Role.SCOPE_SELF,
        )
        cls.role_region = models.Role.objects.create(
            name='Region',
            code='region',
            data_scope=models.Role.SCOPE_REGION,
        )
        cls.role_region_children = models.Role.objects.create(
            name='RegionChildren',
            code='region_children',
            data_scope=models.Role.SCOPE_REGION_CHILDREN,
        )

        cls.lookup_opportunity_category = models.LookupCategory.objects.create(
            code='opportunity_category',
            name='Opportunity Category',
        )
        cls.lookup_lead_source = models.LookupCategory.objects.create(
            code='lead_source',
            name='Lead Source',
        )
        cls.opportunity_category_opt = models.LookupOption.objects.create(
            category=cls.lookup_opportunity_category,
            code='cat1',
            name='Category 1',
        )
        cls.lead_source_opt = models.LookupOption.objects.create(
            category=cls.lookup_lead_source,
            code='lead1',
            name='Lead Source 1',
        )

    def create_user(self, username, region, role):
        User = get_user_model()
        return User.objects.create_user(
            username=username,
            password='pass1234',
            region=region,
            role=role,
        )

    def test_unauthenticated_access_denied(self):
        url = reverse('opportunity-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)

    def test_create_opportunity_defaults(self):
        user = self.create_user('alice', self.region_parent, self.role_region_children)
        self.client.force_authenticate(user=user)

        url = reverse('opportunity-list')
        payload = {
            'opportunity_name': 'Opp A',
        }
        response = self.client.post(url, payload, format='json')

        self.assertEqual(response.status_code, 201)
        data = response.data
        self.assertEqual(data['opportunity_name'], 'Opp A')
        self.assertEqual(data['stage'], models.Opportunity.STAGE_LEAD)
        self.assertEqual(data['win_probability'], 5)
        self.assertIsNotNone(data['stage_entered_at'])
        self.assertEqual(data['owner'], user.id)
        self.assertEqual(data['region'], self.region_parent.id)

    def test_update_stage_updates_stage_entered_at_and_defaults(self):
        user = self.create_user('bob', self.region_parent, self.role_region_children)
        opp = models.Opportunity.objects.create(
            opportunity_name='Opp B',
            region=self.region_parent,
            owner=user,
            stage=models.Opportunity.STAGE_DEMAND,
            win_probability=10,
            stage_entered_at=timezone.now() - timedelta(days=2),
        )
        previous_entered_at = opp.stage_entered_at
        self.client.force_authenticate(user=user)

        url = reverse('opportunity-detail', args=[opp.id])
        response = self.client.patch(url, {'stage': models.Opportunity.STAGE_WON}, format='json')
        self.assertEqual(response.status_code, 200)

        opp.refresh_from_db()
        self.assertEqual(opp.stage, models.Opportunity.STAGE_WON)
        self.assertEqual(opp.win_probability, 100)
        self.assertGreater(opp.stage_entered_at, previous_entered_at)

    def test_lookup_category_validation(self):
        user = self.create_user('carol', self.region_parent, self.role_region_children)
        self.client.force_authenticate(user=user)

        url = reverse('opportunity-list')
        payload = {
            'opportunity_name': 'Opp C',
            'opportunity_category': self.lead_source_opt.id,
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('opportunity_category', response.data)

        payload['opportunity_category'] = self.opportunity_category_opt.id
        response_ok = self.client.post(url, payload, format='json')
        self.assertEqual(response_ok.status_code, 201)

    def test_scoping_self_only_sees_own(self):
        user_self = self.create_user('dave', self.region_parent, self.role_self)
        user_other = self.create_user('erin', self.region_parent, self.role_self)

        models.Opportunity.objects.create(
            opportunity_name='Mine',
            region=self.region_parent,
            owner=user_self,
        )
        models.Opportunity.objects.create(
            opportunity_name='Not Mine',
            region=self.region_parent,
            owner=user_other,
        )

        self.client.force_authenticate(user=user_self)
        url = reverse('opportunity-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        results = self._list_results(response)
        names = {item['opportunity_name'] for item in results}
        self.assertEqual(names, {'Mine'})

    def test_scoping_region_children(self):
        user_parent = self.create_user('frank', self.region_parent, self.role_region_children)
        user_child = self.create_user('gina', self.region_child, self.role_region_children)
        user_other = self.create_user('harry', self.region_other, self.role_region_children)

        models.Opportunity.objects.create(
            opportunity_name='Parent Opp',
            region=self.region_parent,
            owner=user_parent,
        )
        models.Opportunity.objects.create(
            opportunity_name='Child Opp',
            region=self.region_child,
            owner=user_child,
        )
        models.Opportunity.objects.create(
            opportunity_name='Other Opp',
            region=self.region_other,
            owner=user_other,
        )

        self.client.force_authenticate(user=user_parent)
        url = reverse('opportunity-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        results = self._list_results(response)
        names = {item['opportunity_name'] for item in results}
        self.assertEqual(names, {'Parent Opp', 'Child Opp'})

    def test_filter_and_search(self):
        user = self.create_user('ivy', self.region_parent, self.role_region_children)

        models.Opportunity.objects.create(
            opportunity_name='Alpha Deal',
            region=self.region_parent,
            owner=user,
            stage=models.Opportunity.STAGE_WON,
        )
        models.Opportunity.objects.create(
            opportunity_name='Beta Deal',
            region=self.region_parent,
            owner=user,
            stage=models.Opportunity.STAGE_DEMAND,
        )

        self.client.force_authenticate(user=user)
        url = reverse('opportunity-list')

        response_search = self.client.get(url, {'search': 'Alpha'})
        self.assertEqual(response_search.status_code, 200)
        results_search = self._list_results(response_search)
        names_search = {item['opportunity_name'] for item in results_search}
        self.assertEqual(names_search, {'Alpha Deal'})

        response_stage = self.client.get(url, {'stage': models.Opportunity.STAGE_WON})
        self.assertEqual(response_stage.status_code, 200)
        results_stage = self._list_results(response_stage)
        names_stage = {item['opportunity_name'] for item in results_stage}
        self.assertEqual(names_stage, {'Alpha Deal'})

    def test_stage_stay_days_calculation(self):
        user = self.create_user('jane', self.region_parent, self.role_region_children)
        entered_at = timezone.now() - timedelta(days=5)
        opp = models.Opportunity.objects.create(
            opportunity_name='Stay Days',
            region=self.region_parent,
            owner=user,
            stage_entered_at=entered_at,
        )

        self.client.force_authenticate(user=user)
        url = reverse('opportunity-detail', args=[opp.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['stage_stay_days'], 5)

        parsed = parse_datetime(response.data['stage_entered_at'])
        self.assertIsNotNone(parsed)
