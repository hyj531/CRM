from django.core.files.base import ContentFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core import models
from core.services import scoping


class MultiRoleSupportTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region_parent = models.Region.objects.create(name='华东', code='mr-east')
        cls.region_child = models.Region.objects.create(name='华东-杭州', code='mr-east-hz', parent=cls.region_parent)

        cls.role_self = models.Role.objects.create(
            name='仅本人-多角色',
            code='mr-self',
            data_scope=models.Role.SCOPE_SELF,
        )
        cls.role_region_children = models.Role.objects.create(
            name='区域及下级-多角色',
            code='mr-region-children',
            data_scope=models.Role.SCOPE_REGION_CHILDREN,
        )
        cls.role_opportunity_update = models.Role.objects.create(
            name='商机编辑-多角色',
            code='mr-opportunity-update',
            data_scope=models.Role.SCOPE_REGION,
        )
        cls.role_opportunity_delete = models.Role.objects.create(
            name='商机删除-多角色',
            code='mr-opportunity-delete',
            data_scope=models.Role.SCOPE_REGION,
        )
        cls.role_doc_view = models.Role.objects.create(
            name='文档查看-多角色',
            code='mr-doc-view',
            data_scope=models.Role.SCOPE_REGION,
        )
        cls.role_doc_download = models.Role.objects.create(
            name='文档下载-多角色',
            code='mr-doc-download',
            data_scope=models.Role.SCOPE_REGION,
        )

        models.RolePermission.objects.create(
            role=cls.role_opportunity_update,
            module=models.RolePermission.MODULE_OPPORTUNITY,
            can_create=False,
            can_update=True,
            can_delete=False,
            can_approve=False,
        )
        models.RolePermission.objects.create(
            role=cls.role_opportunity_delete,
            module=models.RolePermission.MODULE_OPPORTUNITY,
            can_create=False,
            can_update=False,
            can_delete=True,
            can_approve=False,
        )

        cls.user = models.User.objects.create_user(
            username='multi_role_user',
            password='pass1234',
            region=cls.region_parent,
            role=cls.role_opportunity_update,
        )
        cls.user.roles.set([cls.role_opportunity_update, cls.role_opportunity_delete])

        cls.scope_user = models.User.objects.create_user(
            username='multi_role_scope_user',
            password='pass1234',
            region=cls.region_parent,
            role=cls.role_self,
        )
        cls.scope_user.roles.set([cls.role_self, cls.role_region_children])

        cls.doc_user = models.User.objects.create_user(
            username='multi_role_doc_user',
            password='pass1234',
            region=cls.region_parent,
            role=cls.role_doc_view,
        )
        cls.doc_user.roles.set([cls.role_doc_view, cls.role_doc_download])

        cls.directory = models.CommonDocDirectory.objects.create(name='多角色文档目录')
        models.CommonDocDirectoryPermission.objects.create(
            directory=cls.directory,
            role=cls.role_doc_view,
            can_view=True,
        )
        models.CommonDocDirectoryPermission.objects.create(
            directory=cls.directory,
            role=cls.role_doc_download,
            can_download=True,
        )
        cls.document = models.CommonDocument.objects.create(
            directory=cls.directory,
            title='多角色文档',
            file=ContentFile(b'hello', name='multi-role.txt'),
            original_name='multi-role.txt',
        )

        cls.admin_user = models.User.objects.create_user(
            username='multi_role_admin',
            password='pass1234',
            is_staff=True,
            region=cls.region_parent,
        )

    def test_auth_me_returns_roles_and_union_permissions(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('current_user'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data.get('roles', [])), {self.role_opportunity_update.id, self.role_opportunity_delete.id})
        self.assertIn(response.data.get('role'), response.data.get('roles', []))

        permission = response.data.get('permissions', {}).get(models.RolePermission.MODULE_OPPORTUNITY, {})
        self.assertTrue(permission.get('update'))
        self.assertTrue(permission.get('delete'))
        self.assertFalse(permission.get('create'))

    def test_scoping_uses_max_scope_among_roles(self):
        region_ids = scoping.get_region_scope_ids(self.scope_user)
        self.assertEqual(set(region_ids), {self.region_parent.id, self.region_child.id})

    def test_common_doc_permissions_union_across_roles(self):
        self.client.force_authenticate(user=self.doc_user)

        list_resp = self.client.get(reverse('common-doc-directory-list'))
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        payload = list_resp.data.get('results', list_resp.data)
        directory_ids = {item['id'] for item in payload}
        self.assertIn(self.directory.id, directory_ids)

        download_resp = self.client.get(reverse('common-document-download', args=[self.document.id]))
        self.assertEqual(download_resp.status_code, status.HTTP_200_OK)

    def test_user_patch_roles_syncs_primary_role(self):
        target = models.User.objects.create_user(
            username='multi_role_target',
            password='pass1234',
            region=self.region_parent,
            role=self.role_self,
        )
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(
            reverse('user-detail', args=[target.id]),
            {'roles': [self.role_doc_download.id, self.role_doc_view.id]},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        target.refresh_from_db()
        self.assertEqual(target.role_id, self.role_doc_download.id)
        self.assertEqual(
            set(target.roles.values_list('id', flat=True)),
            {self.role_doc_download.id, self.role_doc_view.id},
        )
