from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from approval import models as approval_models
from approval.services import engine
from core import models as core_models
from core.services import approval_switches


class MultiRegionApprovalFlowTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region_east = core_models.Region.objects.create(name='华东', code='east-multi')
        cls.region_west = core_models.Region.objects.create(name='华西', code='west-multi')
        cls.region_north = core_models.Region.objects.create(name='华北', code='north-multi')

        cls.role_sales = core_models.Role.objects.create(name='经办人', code='sales-multi')
        cls.role_partner = core_models.Role.objects.create(name='区域合伙人', code='partner-multi')
        cls.role_manager = core_models.Role.objects.create(name='区域负责人', code='manager-multi')
        cls.role_hq = core_models.Role.objects.create(name='总部负责人', code='hq-multi')
        cls.role_missing = core_models.Role.objects.create(name='空角色', code='missing-multi')

        cls.admin = core_models.User.objects.create_user(
            username='approval_config_admin',
            password='pass1234',
            is_staff=True,
            is_superuser=True,
        )
        cls.submitter_east = core_models.User.objects.create_user(
            username='submitter_east',
            password='pass1234',
            region=cls.region_east,
            role=cls.role_sales,
        )
        cls.submitter_west = core_models.User.objects.create_user(
            username='submitter_west',
            password='pass1234',
            region=cls.region_west,
            role=cls.role_sales,
        )
        cls.submitter_north = core_models.User.objects.create_user(
            username='submitter_north',
            password='pass1234',
            region=cls.region_north,
            role=cls.role_sales,
        )

        cls.partner_east = core_models.User.objects.create_user(
            username='partner_east',
            password='pass1234',
            region=cls.region_east,
            role=cls.role_partner,
        )
        cls.partner_west = core_models.User.objects.create_user(
            username='partner_west',
            password='pass1234',
            region=cls.region_west,
            role=cls.role_partner,
        )

        cls.manager_east = core_models.User.objects.create_user(
            username='manager_east',
            password='pass1234',
            region=cls.region_east,
            role=cls.role_manager,
        )
        cls.manager_west = core_models.User.objects.create_user(
            username='manager_west',
            password='pass1234',
            region=cls.region_west,
            role=cls.role_manager,
        )
        cls.hq_owner = core_models.User.objects.create_user(
            username='hq_owner',
            password='pass1234',
            region=cls.region_north,
            role=cls.role_hq,
        )

        cls.account_east = core_models.Account.objects.create(
            full_name='客户A',
            short_name='A',
            region=cls.region_east,
            owner=cls.submitter_east,
        )
        cls.account_west = core_models.Account.objects.create(
            full_name='客户B',
            short_name='B',
            region=cls.region_west,
            owner=cls.submitter_west,
        )
        cls.account_north = core_models.Account.objects.create(
            full_name='客户C',
            short_name='C',
            region=cls.region_north,
            owner=cls.submitter_north,
        )

        cls.contract_east = core_models.Contract.objects.create(
            account=cls.account_east,
            amount='1000.00',
            region=cls.region_east,
            owner=cls.submitter_east,
            approval_status='pending',
        )
        cls.contract_west = core_models.Contract.objects.create(
            account=cls.account_west,
            amount='1200.00',
            region=cls.region_west,
            owner=cls.submitter_west,
            approval_status='pending',
        )
        cls.contract_north = core_models.Contract.objects.create(
            account=cls.account_north,
            amount='1500.00',
            region=cls.region_north,
            owner=cls.submitter_north,
            approval_status='pending',
        )

    def setUp(self):
        approval_models.ApprovalFlow.objects.all().delete()
        approval_switches.clear_approval_switches_cache()
        setting, _ = core_models.ApprovalModuleSetting.objects.get_or_create(
            singleton_key=core_models.ApprovalModuleSetting.SINGLETON_KEY_DEFAULT
        )
        setting.contract_approval_enabled = True
        setting.invoice_approval_enabled = True
        setting.save()
        approval_switches.clear_approval_switches_cache()

    def _create_flow(
        self,
        *,
        name,
        scope_mode,
        regions,
        steps,
        is_active=True,
        target_type='contract',
        status=approval_models.ApprovalFlow.STATUS_PUBLISHED,
        priority=100,
        effective_from=None,
        effective_to=None,
    ):
        flow = approval_models.ApprovalFlow.objects.create(
            name=name,
            target_type=target_type,
            scope_mode=scope_mode,
            status=status,
            priority=priority,
            effective_from=effective_from,
            effective_to=effective_to,
            is_active=is_active,
        )
        if regions:
            flow.regions.set(regions)
        for idx, step in enumerate(steps, start=1):
            approval_models.ApprovalStep.objects.create(
                flow=flow,
                order=idx,
                name=step['name'],
                assignee_type=step['assignee_type'],
                assignee_scope=step.get('assignee_scope', approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION),
                approver_role=step.get('approver_role'),
                approver_user=step.get('approver_user'),
            )
        return flow

    def _pending_tasks(self, instance):
        return list(instance.tasks.filter(status=approval_models.ApprovalTask.STATUS_PENDING).order_by('step__order', 'id'))

    def test_multi_region_role_resolution_and_hq_global_step(self):
        self._create_flow(
            name='多区域主流程',
            scope_mode=approval_models.ApprovalFlow.SCOPE_SELECTED_REGIONS,
            regions=[self.region_east, self.region_west],
            steps=[
                {
                    'name': '区域合伙人审批',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_partner,
                },
                {
                    'name': '区域负责人审批',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_manager,
                },
                {
                    'name': '总部负责人审批',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_GLOBAL,
                    'approver_role': self.role_hq,
                },
            ],
        )

        with self.captureOnCommitCallbacks(execute=True):
            east_instance = engine.start_approval(self.contract_east, self.submitter_east)
        east_pending = self._pending_tasks(east_instance)
        self.assertEqual(len(east_pending), 1)
        self.assertEqual(east_pending[0].assignee_id, self.partner_east.id)

        with self.captureOnCommitCallbacks(execute=True):
            engine.approve_task(east_pending[0], self.partner_east, approved=True, comment='同意')
        east_instance.refresh_from_db()
        east_step2_pending = self._pending_tasks(east_instance)
        self.assertEqual(len(east_step2_pending), 1)
        self.assertEqual(east_step2_pending[0].assignee_id, self.manager_east.id)

        with self.captureOnCommitCallbacks(execute=True):
            engine.approve_task(east_step2_pending[0], self.manager_east, approved=True, comment='同意')
        east_instance.refresh_from_db()
        east_step3_pending = self._pending_tasks(east_instance)
        self.assertEqual(len(east_step3_pending), 1)
        self.assertEqual(east_step3_pending[0].assignee_id, self.hq_owner.id)

        with self.captureOnCommitCallbacks(execute=True):
            west_instance = engine.start_approval(self.contract_west, self.submitter_west)
        west_pending = self._pending_tasks(west_instance)
        self.assertEqual(len(west_pending), 1)
        self.assertEqual(west_pending[0].assignee_id, self.partner_west.id)

    def test_multi_match_requires_all_sign(self):
        partner_east_2 = core_models.User.objects.create_user(
            username='partner_east_2',
            password='pass1234',
            region=self.region_east,
            role=self.role_partner,
        )
        self._create_flow(
            name='会签流程',
            scope_mode=approval_models.ApprovalFlow.SCOPE_SELECTED_REGIONS,
            regions=[self.region_east],
            steps=[
                {
                    'name': '区域合伙人会签',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_partner,
                },
                {
                    'name': '区域负责人',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_manager,
                },
            ],
        )

        with self.captureOnCommitCallbacks(execute=True):
            instance = engine.start_approval(self.contract_east, self.submitter_east)
        first_step_pending = self._pending_tasks(instance)
        self.assertEqual(len(first_step_pending), 2)

        first = first_step_pending[0]
        second = first_step_pending[1]
        with self.captureOnCommitCallbacks(execute=True):
            engine.approve_task(first, first.assignee, approved=True, comment='同意')
        instance.refresh_from_db()
        self.assertEqual(instance.current_step, 1)
        self.assertEqual(len(self._pending_tasks(instance)), 1)

        with self.captureOnCommitCallbacks(execute=True):
            engine.approve_task(second, second.assignee, approved=True, comment='同意')
        instance.refresh_from_db()
        self.assertEqual(instance.current_step, 2)
        step2_pending = self._pending_tasks(instance)
        self.assertEqual(len(step2_pending), 1)
        self.assertEqual(step2_pending[0].assignee_id, self.manager_east.id)
        self.assertIn(partner_east_2.id, [first.assignee_id, second.assignee_id])

    def test_all_steps_missing_assignee_auto_approves(self):
        self._create_flow(
            name='空审批人流程',
            scope_mode=approval_models.ApprovalFlow.SCOPE_SELECTED_REGIONS,
            regions=[self.region_east],
            steps=[
                {
                    'name': '缺失角色',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_missing,
                },
            ],
        )

        with self.captureOnCommitCallbacks(execute=True):
            instance = engine.start_approval(self.contract_east, self.submitter_east)
        instance.refresh_from_db()
        self.contract_east.refresh_from_db()

        self.assertEqual(instance.status, approval_models.ApprovalInstance.STATUS_APPROVED)
        self.assertEqual(instance.tasks.count(), 0)
        self.assertEqual(self.contract_east.approval_status, 'approved')
        self.assertTrue(instance.action_logs.filter(extra__op='auto_skip_no_assignee').exists())
        self.assertTrue(instance.action_logs.filter(extra__op='auto_skip_no_assignee_all').exists())

    def test_first_step_missing_auto_skips_to_next_pending_step(self):
        self._create_flow(
            name='首节点未命中流程',
            scope_mode=approval_models.ApprovalFlow.SCOPE_SELECTED_REGIONS,
            regions=[self.region_east],
            steps=[
                {
                    'name': '缺失角色',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_missing,
                },
                {
                    'name': '区域合伙人',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_partner,
                },
                {
                    'name': '区域负责人',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_manager,
                },
            ],
        )

        with self.captureOnCommitCallbacks(execute=True):
            instance = engine.start_approval(self.contract_east, self.submitter_east)
        instance.refresh_from_db()

        self.assertEqual(instance.current_step, 2)
        pending = self._pending_tasks(instance)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].assignee_id, self.partner_east.id)
        self.assertTrue(instance.action_logs.filter(extra__op='auto_skip_no_assignee', extra__step_order=1).exists())

        with self.captureOnCommitCallbacks(execute=True):
            engine.approve_task(pending[0], self.partner_east, approved=True, comment='同意')
        instance.refresh_from_db()
        self.assertEqual(instance.current_step, 3)
        step3_pending = self._pending_tasks(instance)
        self.assertEqual(len(step3_pending), 1)
        self.assertEqual(step3_pending[0].assignee_id, self.manager_east.id)

    def test_middle_step_missing_is_auto_skipped_on_advance(self):
        self._create_flow(
            name='中间节点未命中流程',
            scope_mode=approval_models.ApprovalFlow.SCOPE_SELECTED_REGIONS,
            regions=[self.region_east],
            steps=[
                {
                    'name': '区域合伙人',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_partner,
                },
                {
                    'name': '缺失角色',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_missing,
                },
                {
                    'name': '区域负责人',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_manager,
                },
            ],
        )

        with self.captureOnCommitCallbacks(execute=True):
            instance = engine.start_approval(self.contract_east, self.submitter_east)
        first_pending = self._pending_tasks(instance)[0]
        self.assertEqual(first_pending.assignee_id, self.partner_east.id)
        self.assertTrue(instance.action_logs.filter(extra__op='auto_skip_no_assignee', extra__step_order=2).exists())

        with self.captureOnCommitCallbacks(execute=True):
            engine.approve_task(first_pending, self.partner_east, approved=True, comment='同意')
        instance.refresh_from_db()
        self.assertEqual(instance.current_step, 3)
        step3_pending = self._pending_tasks(instance)
        self.assertEqual(len(step3_pending), 1)
        self.assertEqual(step3_pending[0].assignee_id, self.manager_east.id)

    def test_selected_scope_priority_over_all_regions(self):
        self._create_flow(
            name='合同全局流程',
            scope_mode=approval_models.ApprovalFlow.SCOPE_ALL_REGIONS,
            regions=[],
            steps=[
                {
                    'name': '总部审批',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_GLOBAL,
                    'approver_role': self.role_hq,
                },
            ],
        )
        self._create_flow(
            name='合同华东专属流程',
            scope_mode=approval_models.ApprovalFlow.SCOPE_SELECTED_REGIONS,
            regions=[self.region_east],
            steps=[
                {
                    'name': '华东合伙人',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_partner,
                },
            ],
        )

        with self.captureOnCommitCallbacks(execute=True):
            east_instance = engine.start_approval(self.contract_east, self.submitter_east)
        east_pending = self._pending_tasks(east_instance)
        self.assertEqual(len(east_pending), 1)
        self.assertEqual(east_pending[0].assignee_id, self.partner_east.id)

        with self.captureOnCommitCallbacks(execute=True):
            north_instance = engine.start_approval(self.contract_north, self.submitter_north)
        north_pending = self._pending_tasks(north_instance)
        self.assertEqual(len(north_pending), 1)
        self.assertEqual(north_pending[0].assignee_id, self.hq_owner.id)

    def test_higher_priority_flow_wins_when_multiple_selected_scope_flows_match(self):
        self._create_flow(
            name='华东低优先级流程',
            scope_mode=approval_models.ApprovalFlow.SCOPE_SELECTED_REGIONS,
            regions=[self.region_east],
            priority=50,
            steps=[
                {
                    'name': '低优先级节点',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_partner,
                },
            ],
        )
        self._create_flow(
            name='华东高优先级流程',
            scope_mode=approval_models.ApprovalFlow.SCOPE_SELECTED_REGIONS,
            regions=[self.region_east],
            priority=200,
            steps=[
                {
                    'name': '高优先级节点',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_manager,
                },
            ],
        )

        with self.captureOnCommitCallbacks(execute=True):
            instance = engine.start_approval(self.contract_east, self.submitter_east)
        pending = self._pending_tasks(instance)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].assignee_id, self.manager_east.id)

    def test_future_effective_flow_is_skipped(self):
        now = timezone.now()
        self._create_flow(
            name='未来生效流程',
            scope_mode=approval_models.ApprovalFlow.SCOPE_SELECTED_REGIONS,
            regions=[self.region_east],
            priority=300,
            effective_from=now + timedelta(days=1),
            steps=[
                {
                    'name': '未来节点',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_manager,
                },
            ],
        )
        self._create_flow(
            name='当前生效流程',
            scope_mode=approval_models.ApprovalFlow.SCOPE_SELECTED_REGIONS,
            regions=[self.region_east],
            priority=100,
            effective_from=now - timedelta(days=1),
            effective_to=now + timedelta(days=1),
            steps=[
                {
                    'name': '当前节点',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_partner,
                },
            ],
        )

        with self.captureOnCommitCallbacks(execute=True):
            instance = engine.start_approval(self.contract_east, self.submitter_east)
        pending = self._pending_tasks(instance)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].assignee_id, self.partner_east.id)

    def test_publish_returns_warnings_when_region_assignee_missing(self):
        flow = self._create_flow(
            name='待发布流程',
            scope_mode=approval_models.ApprovalFlow.SCOPE_SELECTED_REGIONS,
            regions=[self.region_east, self.region_north],
            steps=[
                {
                    'name': '区域负责人',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_manager,
                },
            ],
            is_active=False,
        )
        self.client.force_authenticate(self.admin)
        response = self.client.post(f'/api/approval-flow-configs/{flow.id}/publish/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        warnings = response.data.get('warnings') or []
        self.assertTrue(warnings)
        self.assertTrue(any(
            item.get('region_id') == self.region_north.id and item.get('step_order') == 1
            for item in warnings
        ))
        flow.refresh_from_db()
        self.assertTrue(flow.is_active)
        self.assertEqual(flow.status, approval_models.ApprovalFlow.STATUS_PUBLISHED)

    def test_preview_assignees_marks_will_auto_skip(self):
        flow = self._create_flow(
            name='预览流程',
            scope_mode=approval_models.ApprovalFlow.SCOPE_SELECTED_REGIONS,
            regions=[self.region_east, self.region_north],
            steps=[
                {
                    'name': '区域负责人',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_manager,
                },
            ],
            is_active=False,
        )
        self.client.force_authenticate(self.admin)

        north_resp = self.client.get(
            f'/api/approval-flow-configs/{flow.id}/preview-assignees/',
            {'region_id': str(self.region_north.id)},
            format='json',
        )
        self.assertEqual(north_resp.status_code, status.HTTP_200_OK)
        north_steps = north_resp.data.get('items', [])[0].get('steps', [])
        self.assertEqual(len(north_steps), 1)
        self.assertEqual(north_steps[0].get('matched_count'), 0)
        self.assertTrue(north_steps[0].get('will_auto_skip'))

        east_resp = self.client.get(
            f'/api/approval-flow-configs/{flow.id}/preview-assignees/',
            {'region_id': str(self.region_east.id)},
            format='json',
        )
        self.assertEqual(east_resp.status_code, status.HTTP_200_OK)
        east_steps = east_resp.data.get('items', [])[0].get('steps', [])
        self.assertEqual(len(east_steps), 1)
        self.assertEqual(east_steps[0].get('matched_count'), 1)
        self.assertFalse(east_steps[0].get('will_auto_skip'))

    def test_publish_success_sets_flow_active(self):
        flow = self._create_flow(
            name='可发布流程',
            scope_mode=approval_models.ApprovalFlow.SCOPE_SELECTED_REGIONS,
            regions=[self.region_east],
            steps=[
                {
                    'name': '区域合伙人',
                    'assignee_type': approval_models.ApprovalStep.ASSIGNEE_TYPE_ROLE,
                    'assignee_scope': approval_models.ApprovalStep.ASSIGNEE_SCOPE_REGION,
                    'approver_role': self.role_partner,
                },
            ],
            is_active=False,
            status=approval_models.ApprovalFlow.STATUS_DRAFT,
        )
        self.client.force_authenticate(self.admin)
        response = self.client.post(f'/api/approval-flow-configs/{flow.id}/publish/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        flow.refresh_from_db()
        self.assertTrue(flow.is_active)
        self.assertEqual(flow.status, approval_models.ApprovalFlow.STATUS_PUBLISHED)
