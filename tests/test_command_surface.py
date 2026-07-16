from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, AsyncMock, Mock

from astrbot_stubs import LOGGER, Plain

del LOGGER
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
main = importlib.import_module("astrbot_plugin_xqa.main")
codec = importlib.import_module("astrbot_plugin_xqa.core.message_codec")
XQAPlugin = main.XQAPlugin


def event_for(message: str):
    event = Mock()
    event.get_messages.return_value = [Plain(message)]
    return event


class SetCommandSurfaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_self_and_public_set_commands_parse(self):
        for message, expected_type in (("我问A你答B", "我"), ("有人问A你答B", "有人")):
            with self.subTest(message=message):
                result = await codec.parse_set_command_from_event(event_for(message))
                self.assertEqual(
                    result, (expected_type, "A", [{"type": "text", "text": "B"}])
                )

    async def test_global_set_command_does_not_parse(self):
        result = await codec.parse_set_command_from_event(event_for("全群问A你答B"))
        self.assertIsNone(result)


class ManagementSurfaceTests(unittest.IsolatedAsyncioTestCase):
    def make_plugin(self):
        plugin = object.__new__(XQAPlugin)
        plugin.config = {
            "group_plugin_enabled_default": True,
            "enable_processing_feedback": False,
        }
        plugin.data_dir = tempfile.gettempdir()
        plugin.store = Mock()
        plugin.store.is_group_enabled.return_value = True
        plugin._set_question = AsyncMock(return_value="set")
        plugin._show_questions = AsyncMock(return_value="show")
        plugin._delete_question = AsyncMock(return_value="delete")
        return plugin

    async def test_planned_commands_do_not_hit_management_branches(self):
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
                    event_for(message), "group-1", "user-1", message
                )
                self.assertIsNone(result)
        plugin._set_question.assert_not_awaited()
        plugin._show_questions.assert_not_awaited()
        plugin._delete_question.assert_not_awaited()

    async def test_supported_commands_still_hit_management_branches(self):
        cases = (
            ("我问A你答B", "set"),
            ("有人问A你答B", "set"),
            ("看看我问", "show"),
            ("看看有人问", "show"),
            ("不要回答A", "delete"),
            ("@123 不要回答A", "delete"),
        )
        for message, expected in cases:
            with self.subTest(message=message):
                plugin = self.make_plugin()
                result = await plugin._handle_management_message(
                    event_for(message), "group-1", "user-1", message
                )
                self.assertEqual(result, expected)

    async def test_delete_arguments_keep_self_and_at_forms(self):
        plugin = self.make_plugin()
        await plugin._handle_management_message(
            event_for("不要回答A"), "group-1", "user-1", "不要回答A"
        )
        plugin._delete_question.assert_awaited_once_with(
            ANY, "group-1", "user-1", (None, "A")
        )

        plugin = self.make_plugin()
        await plugin._handle_management_message(
            event_for("@123 不要回答A"), "group-1", "user-1", "@123 不要回答A"
        )
        plugin._delete_question.assert_awaited_once_with(
            ANY, "group-1", "user-1", ("123", "A")
        )


class ConfigurationSurfaceTests(unittest.TestCase):
    def read_schema(self):
        schema_path = Path(__file__).resolve().parents[1] / "_conf_schema.json"
        return json.loads(schema_path.read_text(encoding="utf-8"))

    def test_global_question_switch_is_not_public(self):
        schema = self.read_schema()
        self.assertNotIn("enable_global_question", schema)

    def test_group_plugin_defaults_disabled_but_self_questions_default_enabled(self):
        schema = self.read_schema()
        self.assertFalse(schema["group_plugin_enabled_default"]["default"])
        self.assertTrue(schema["self_question_enabled_default"]["default"])
        self.assertEqual(
            schema["self_question_enabled_default"]["description"],
            "启用群后个人问答的默认状态",
        )
        self.assertIn("XQA启用本群", schema["group_plugin_enabled_default"]["hint"])


if __name__ == "__main__":
    unittest.main()
