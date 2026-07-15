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


class ToggleSelfQuestionPermissionTests(unittest.IsolatedAsyncioTestCase):
    def make_plugin(
        self, *, allow_group_admin: bool, plugin_admin: bool, group_admin: bool
    ):
        plugin = object.__new__(XQAPlugin)
        plugin.config = {
            "allow_group_admin_toggle_self_question": allow_group_admin,
            "permission_denied_notice": True,
        }
        plugin.store = Mock()
        plugin.store.set_self_enabled = AsyncMock()
        plugin._is_plugin_admin = AsyncMock(return_value=plugin_admin)
        plugin._is_group_admin = AsyncMock(return_value=group_admin)
        return plugin

    async def test_plugin_admin_is_allowed_when_group_admin_toggle_disabled(self):
        plugin = self.make_plugin(
            allow_group_admin=False, plugin_admin=True, group_admin=False
        )

        result = await plugin._toggle_self_question(Mock(), "group-1", True)

        self.assertEqual(result, "本群已启用个人问答功能。")
        plugin.store.set_self_enabled.assert_awaited_once_with("group-1", True)
        plugin._is_group_admin.assert_not_awaited()

    async def test_group_admin_is_allowed_when_config_enabled(self):
        plugin = self.make_plugin(
            allow_group_admin=True, plugin_admin=False, group_admin=True
        )

        result = await plugin._toggle_self_question(Mock(), "group-2", False)

        self.assertEqual(result, "本群已禁用个人问答功能。")
        plugin.store.set_self_enabled.assert_awaited_once_with("group-2", False)

    async def test_group_admin_is_denied_when_config_disabled(self):
        plugin = self.make_plugin(
            allow_group_admin=False, plugin_admin=False, group_admin=True
        )

        result = await plugin._toggle_self_question(Mock(), "group-3", True)

        self.assertEqual(result, "权限不足：该命令仅限管理员使用。")
        plugin.store.set_self_enabled.assert_not_awaited()
        plugin._is_group_admin.assert_not_awaited()

    async def test_regular_member_is_always_denied(self):
        plugin = self.make_plugin(
            allow_group_admin=True, plugin_admin=False, group_admin=False
        )

        result = await plugin._toggle_self_question(Mock(), "group-4", True)

        self.assertEqual(result, "权限不足：该命令仅限管理员使用。")
        plugin.store.set_self_enabled.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
