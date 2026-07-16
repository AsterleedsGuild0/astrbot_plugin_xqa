from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from astrbot_stubs import LOGGER

del LOGGER
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
XQAPlugin = importlib.import_module("astrbot_plugin_xqa.main").XQAPlugin


class PublicQuestionPermissionTests(unittest.IsolatedAsyncioTestCase):
    def make_plugin(
        self, *, allow_group_admin: bool, plugin_admin: bool, group_admin: bool
    ):
        plugin = object.__new__(XQAPlugin)
        plugin.config = {
            "allow_group_admin_manage_public_questions": allow_group_admin,
            "permission_denied_notice": True,
            "reject_empty_regex": True,
            "reject_dangerous_regex": True,
        }
        plugin.store = Mock()
        plugin.store.count_questions.return_value = 0
        plugin.store.set_question = AsyncMock()
        plugin._is_plugin_admin = AsyncMock(return_value=plugin_admin)
        plugin._is_group_admin = AsyncMock(return_value=group_admin)
        return plugin

    async def assert_permission(
        self,
        *,
        allow_group_admin: bool,
        plugin_admin: bool,
        group_admin: bool,
        allowed: bool,
    ):
        plugin = self.make_plugin(
            allow_group_admin=allow_group_admin,
            plugin_admin=plugin_admin,
            group_admin=group_admin,
        )
        answers = [{"type": "text", "text": "B"}]

        result = await plugin._set_question(
            Mock(), "group-1", "user-1", ("有人", "A", answers)
        )

        if allowed:
            self.assertEqual(result, "好的我记住了。")
            plugin.store.set_question.assert_awaited_once_with(
                "group-1", None, "A", [answers]
            )
        else:
            self.assertEqual(result, "权限不足：有人问只能群管理员设置。")
            plugin.store.set_question.assert_not_awaited()

    async def test_plugin_admin_is_allowed(self):
        await self.assert_permission(
            allow_group_admin=False,
            plugin_admin=True,
            group_admin=False,
            allowed=True,
        )

    async def test_group_admin_is_allowed_when_enabled(self):
        await self.assert_permission(
            allow_group_admin=True,
            plugin_admin=False,
            group_admin=True,
            allowed=True,
        )

    async def test_group_admin_is_denied_when_disabled(self):
        await self.assert_permission(
            allow_group_admin=False,
            plugin_admin=False,
            group_admin=True,
            allowed=False,
        )

    async def test_regular_member_is_denied(self):
        await self.assert_permission(
            allow_group_admin=True,
            plugin_admin=False,
            group_admin=False,
            allowed=False,
        )


if __name__ == "__main__":
    unittest.main()
