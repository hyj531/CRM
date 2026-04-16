from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings

from approval import models as approval_models
from approval.services import todo


class TodoApiCompleteTests(SimpleTestCase):
    def _make_user(self, union_id='union_demo', user_id=''):
        return SimpleNamespace(
            dingtalk_union_id=union_id,
            dingtalk_user_id=user_id,
        )

    @override_settings(
        DINGTALK={
            'TODO_ENABLED': '1',
            'TODO_COMPLETE_URL': 'https://api.dingtalk.com/v1.0/todo/users/{unionId}/tasks/{taskId}?operatorId={operatorUnionId}',
            'TODO_OPERATOR_UNION_ID': 'op_union',
        }
    )
    @patch('approval.services.todo.dingtalk_client._get_app_access_token_for_url', return_value='token_demo')
    @patch('approval.services.todo.requests.put')
    def test_complete_todo_uses_put_for_openapi(self, mocked_put, _mocked_token):
        mocked_response = Mock()
        mocked_response.raise_for_status.return_value = None
        mocked_response.content = b'{}'
        mocked_response.json.return_value = {}
        mocked_put.return_value = mocked_response

        result = todo.complete_todo_task_result(
            user=self._make_user(union_id='union_1'),
            source_id='approval-task-1',
            task_id='task_1',
            channel=approval_models.ApprovalTask.TODO_CHANNEL_TODO_API,
        )

        self.assertTrue(result.ok)
        mocked_put.assert_called_once_with(
            'https://api.dingtalk.com/v1.0/todo/users/union_1/tasks/task_1?operatorId=op_union',
            json={
                'done': True,
                'executorIds': ['union_1'],
            },
            headers={'x-acs-dingtalk-access-token': 'token_demo'},
            timeout=10,
        )

    @override_settings(
        DINGTALK={
            'TODO_ENABLED': '1',
            'TODO_COMPLETE_URL': 'https://api.dingtalk.com/v1.0/todo/users/{unionId}/tasks/{taskId}?operatorId={operatorUnionId}',
            'TODO_OPERATOR_UNION_ID': 'op_union',
        }
    )
    @patch('approval.services.todo.dingtalk_client._get_app_access_token_for_url')
    def test_complete_todo_missing_task_id_is_skipped(self, mocked_token):
        result = todo.complete_todo_task_result(
            user=self._make_user(union_id='union_1'),
            source_id='approval-task-1',
            task_id='',
            channel=approval_models.ApprovalTask.TODO_CHANNEL_TODO_API,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.raw.get('reason'), 'missing_task_id')
        mocked_token.assert_not_called()

    @override_settings(
        DINGTALK={
            'TODO_ENABLED': '1',
            'TODO_COMPLETE_URL': 'https://api.dingtalk.com/v1.0/todo/users/{unionId}/tasks/{taskId}?operatorId={operatorUnionId}',
            'TODO_OPERATOR_UNION_ID': 'op_union',
        }
    )
    @patch('approval.services.todo.dingtalk_client._get_app_access_token_for_url', return_value='token_demo')
    @patch('approval.services.todo.requests.put')
    def test_complete_todo_404_treated_as_success(self, mocked_put, _mocked_token):
        mocked_response = Mock()
        mocked_response.status_code = 404
        mocked_put.side_effect = requests.HTTPError(response=mocked_response)

        result = todo.complete_todo_task_result(
            user=self._make_user(union_id='union_1'),
            source_id='approval-task-1',
            task_id='task_not_exist',
            channel=approval_models.ApprovalTask.TODO_CHANNEL_TODO_API,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.raw.get('reason'), 'remote_task_not_found')

    @override_settings(
        DINGTALK={
            'TODO_ENABLED': '1',
            'TODO_CREATE_URL': 'https://api.dingtalk.com/v1.0/todo/users/{unionId}/tasks?operatorId={operatorUnionId}',
            'TODO_OPERATOR_UNION_ID': 'op_union',
        }
    )
    @patch('approval.services.todo._send_request', return_value={'id': 'task_123'})
    def test_create_todo_openapi_uses_app_url_and_executor_ids(self, mocked_send):
        result = todo.send_todo_task_result(
            user=self._make_user(union_id='union_1', user_id='legacy_user_id'),
            title='审批待办提醒',
            content='请审批',
            url='https://crm.example.com/app/approvals/tasks/1',
            source_id='approval-task-1',
        )

        self.assertTrue(result.ok)
        _, payload = mocked_send.call_args.args
        self.assertEqual(
            payload['detailUrl'],
            {
                'pcUrl': 'https://crm.example.com/app/approvals/tasks/1',
                'appUrl': 'https://crm.example.com/app/approvals/tasks/1',
            },
        )
        self.assertEqual(payload.get('executorIds'), ['union_1'])
        self.assertNotIn('executorId', payload)

    @override_settings(
        DINGTALK={
            'TODO_ENABLED': '1',
            'TODO_CREATE_URL': 'https://api.dingtalk.com/v1.0/todo/users/{unionId}/tasks?operatorId={operatorUnionId}',
            'TODO_OPERATOR_UNION_ID': 'op_union',
        }
    )
    @patch('approval.services.todo._send_request')
    def test_create_todo_with_unresolved_placeholder_returns_error(self, mocked_send):
        result = todo.send_todo_task_result(
            user=self._make_user(union_id='', user_id='legacy_user_id'),
            title='审批待办提醒',
            content='请审批',
            url='https://crm.example.com/app/approvals/tasks/1',
            source_id='approval-task-1',
        )

        self.assertFalse(result.ok)
        self.assertIn('unresolved placeholders', result.error)
        mocked_send.assert_not_called()
