from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from astrbot_stubs import LOGGER

del LOGGER
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
main = importlib.import_module("astrbot_plugin_xqa.main")
store_module = importlib.import_module("astrbot_plugin_xqa.core.store")
XQAPlugin = main.XQAPlugin
XQAStore = store_module.XQAStore


class GroupPluginTogglePermissionTests(unittest.IsolatedAsyncioTestCase):
    def make_plugin(
        self, *, allow_group_admin: bool, plugin_admin: bool, group_admin: bool
    ):
        plugin = object.__new__(XQAPlugin)
        plugin.config = {
            "allow_group_admin_toggle_group_plugin": allow_group_admin,
            "permission_denied_notice": True,
        }
        plugin.store = Mock()
        plugin.store.set_group_enabled = AsyncMock()
        plugin._is_plugin_admin = AsyncMock(return_value=plugin_admin)
        plugin._is_group_admin = AsyncMock(return_value=group_admin)
        return plugin

    async def test_plugin_admin_is_always_allowed(self):
        plugin = self.make_plugin(
            allow_group_admin=False, plugin_admin=True, group_admin=False
        )

        result = await plugin._toggle_group_plugin(Mock(), "group-1", False)

        self.assertEqual(result, "本群已禁用 XQA。")
        plugin.store.set_group_enabled.assert_awaited_once_with("group-1", False)
        plugin._is_group_admin.assert_not_awaited()

    async def test_group_admin_is_allowed_when_config_enabled(self):
        plugin = self.make_plugin(
            allow_group_admin=True, plugin_admin=False, group_admin=True
        )

        result = await plugin._toggle_group_plugin(Mock(), "group-2", True)

        self.assertEqual(result, "本群已启用 XQA。")
        plugin.store.set_group_enabled.assert_awaited_once_with("group-2", True)

    async def test_group_admin_is_denied_when_config_disabled(self):
        plugin = self.make_plugin(
            allow_group_admin=False, plugin_admin=False, group_admin=True
        )

        result = await plugin._toggle_group_plugin(Mock(), "group-3", True)

        self.assertEqual(result, "权限不足：该命令仅限管理员使用。")
        plugin.store.set_group_enabled.assert_not_awaited()
        plugin._is_group_admin.assert_not_awaited()

    async def test_regular_member_is_denied(self):
        plugin = self.make_plugin(
            allow_group_admin=True, plugin_admin=False, group_admin=False
        )

        result = await plugin._toggle_group_plugin(Mock(), "group-4", True)

        self.assertEqual(result, "权限不足：该命令仅限管理员使用。")
        plugin.store.set_group_enabled.assert_not_awaited()


class DisabledGroupManagementTests(unittest.IsolatedAsyncioTestCase):
    def make_plugin(self):
        plugin = object.__new__(XQAPlugin)
        plugin.config = {"group_plugin_enabled_default": True}
        plugin.store = Mock()
        plugin.store.is_group_enabled.return_value = False
        plugin._toggle_group_plugin = AsyncMock(return_value="本群已启用 XQA。")
        return plugin

    async def test_regular_chat_is_silent(self):
        plugin = self.make_plugin()

        result = await plugin._handle_management_message(
            Mock(), "group-1", "user-1", "今天天气不错"
        )

        self.assertIsNone(result)

    async def test_setting_show_and_delete_commands_report_disabled(self):
        plugin = self.make_plugin()

        for message in ("我问A你答B", "看看我问", "不要回答A"):
            with self.subTest(message=message):
                result = await plugin._handle_management_message(
                    Mock(), "group-1", "user-1", message
                )
                self.assertEqual(result, "本群已禁用 XQA。发送“XQA启用本群”可恢复。")

    async def test_unimplemented_command_texts_are_silent(self):
        plugin = self.make_plugin()

        for message in (
            "全群问A你答B",
            "看看全群问",
            "全群不要回答A",
            "XQA清空本群所有我问",
            "XQA清空本群所有有人问",
        ):
            with self.subTest(message=message):
                result = await plugin._handle_management_message(
                    Mock(), "group-1", "user-1", message
                )
                self.assertIsNone(result)

    async def test_enable_command_still_uses_toggle_logic(self):
        plugin = self.make_plugin()
        event = Mock()

        result = await plugin._handle_management_message(
            event, "group-1", "user-1", "XQA启用本群"
        )

        self.assertEqual(result, "本群已启用 XQA。")
        plugin._toggle_group_plugin.assert_awaited_once_with(event, "group-1", True)


class DefaultDisabledGroupTests(unittest.IsolatedAsyncioTestCase):
    def make_plugin(self):
        plugin = object.__new__(XQAPlugin)
        plugin.config = {
            "self_question_enabled_default": True,
            "enable_regex_question": True,
            "cooldown_seconds": 0,
            "allow_group_admin_toggle_group_plugin": True,
            "permission_denied_notice": True,
        }
        plugin._cooldowns = {}
        plugin.store = Mock()
        plugin.store.is_group_enabled.return_value = False
        return plugin

    async def test_missing_default_keeps_regular_messages_silent(self):
        plugin = self.make_plugin()

        result = await plugin._handle_management_message(
            Mock(), "group-new", "user-1", "普通消息"
        )

        self.assertIsNone(result)
        plugin.store.is_group_enabled.assert_called_once_with("group-new", False)

    async def test_missing_default_does_not_match_questions(self):
        plugin = self.make_plugin()

        result = await plugin._match_reply("group-new", "user-1", "hello")

        self.assertIsNone(result)
        plugin.store.is_group_enabled.assert_called_once_with("group-new", False)
        plugin.store.match.assert_not_called()

    async def test_admin_can_enable_group_and_restore_matching(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin = object.__new__(XQAPlugin)
            plugin.config = {
                "self_question_enabled_default": True,
                "enable_regex_question": True,
                "cooldown_seconds": 0,
                "allow_group_admin_toggle_group_plugin": True,
                "permission_denied_notice": True,
            }
            plugin._cooldowns = {}
            plugin.store = XQAStore(temp_dir)
            await plugin.store.load()
            answer = [[{"type": "text", "text": "world"}]]
            await plugin.store.set_question("group-new", "admin-1", "hello", answer)
            plugin._is_plugin_admin = AsyncMock(return_value=True)

            self.assertIsNone(
                await plugin._match_reply("group-new", "admin-1", "hello")
            )
            result = await plugin._handle_management_message(
                Mock(), "group-new", "admin-1", "XQA启用本群"
            )

            self.assertEqual(result, "本群已启用 XQA。")
            self.assertEqual(
                await plugin._match_reply("group-new", "admin-1", "hello"),
                [{"type": "text", "text": "world"}],
            )


class GroupPluginMatchTests(unittest.IsolatedAsyncioTestCase):
    def make_plugin(self, *, enabled: bool):
        plugin = object.__new__(XQAPlugin)
        plugin.config = {
            "group_plugin_enabled_default": True,
            "self_question_enabled_default": True,
            "enable_regex_question": True,
            "cooldown_seconds": 0,
        }
        plugin._cooldowns = {}
        plugin.store = Mock()
        plugin.store.is_group_enabled.return_value = enabled
        plugin.store.is_self_enabled.return_value = True
        return plugin

    async def test_disabled_group_does_not_match(self):
        plugin = self.make_plugin(enabled=False)

        result = await plugin._match_reply("group-1", "user-1", "hello")

        self.assertIsNone(result)
        plugin.store.match.assert_not_called()

    async def test_reenabled_group_can_match_existing_data(self):
        plugin = self.make_plugin(enabled=True)
        answer = [{"type": "text", "value": "world"}]
        plugin.store.match.return_value = SimpleNamespace(answer=answer)

        result = await plugin._match_reply("group-1", "user-1", "hello")

        self.assertEqual(result, answer)
        plugin.store.match.assert_called_once_with(
            "group-1", "user-1", "hello", "self", True
        )


class GroupPluginStorePersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_group_state_overrides_false_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = XQAStore(temp_dir)
            await store.load()

            self.assertFalse(store.is_group_enabled("missing", False))
            await store.set_group_enabled("enabled", True)
            await store.set_group_enabled("disabled", False)

            self.assertTrue(store.is_group_enabled("enabled", False))
            self.assertFalse(store.is_group_enabled("disabled", True))

    async def test_group_toggle_survives_reload_without_losing_questions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = XQAStore(temp_dir)
            await store.load()
            answer = [[{"type": "text", "value": "answer"}]]
            await store.set_question("group-1", None, "public-question", answer)
            await store.set_question("group-1", "user-1", "self-question", answer)
            await store.set_group_enabled("group-1", False)

            reloaded = XQAStore(temp_dir)
            await reloaded.load()

            self.assertFalse(reloaded.is_group_enabled("group-1"))
            self.assertEqual(
                reloaded.list_questions("group-1", None), ["public-question"]
            )
            self.assertEqual(
                reloaded.list_questions("group-1", "user-1"), ["self-question"]
            )

            await reloaded.set_group_enabled("group-1", True)
            enabled = XQAStore(temp_dir)
            await enabled.load()
            self.assertTrue(enabled.is_group_enabled("group-1", False))
            self.assertEqual(enabled.count_questions("group-1", None), 1)
            self.assertEqual(enabled.count_questions("group-1", "user-1"), 1)


if __name__ == "__main__":
    unittest.main()
