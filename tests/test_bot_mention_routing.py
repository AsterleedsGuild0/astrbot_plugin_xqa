from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from astrbot_stubs import At, LOGGER, Plain

del LOGGER
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
XQAPlugin = importlib.import_module("astrbot_plugin_xqa.main").XQAPlugin


class AtAll:
    pass


def event_for(
    message: str,
    *,
    self_id: str | int | None = "bot-1",
    components: Sequence[object] | None = None,
):
    event = Mock()
    event.get_self_id.return_value = self_id
    event.get_messages.return_value = components or [Plain(message)]
    event.get_group_id.return_value = "group-1"
    event.get_sender_id.return_value = "user-1"
    event.get_message_str.return_value = message
    event.plain_result.side_effect = lambda text: text
    event.chain_result.side_effect = lambda components: components
    return event


async def collect(async_generator):
    return [item async for item in async_generator]


class CurrentBotMentionTests(unittest.TestCase):
    def test_matches_current_self_id_with_string_conversion(self):
        event = event_for("command", self_id=123, components=[At("123")])
        self.assertTrue(XQAPlugin._is_at_current_bot(event))

    def test_rejects_other_self_id(self):
        event = event_for("command", self_id="bot-2", components=[At("bot-1")])
        self.assertFalse(XQAPlugin._is_at_current_bot(event))

    def test_rejects_missing_at(self):
        self.assertFalse(XQAPlugin._is_at_current_bot(event_for("command")))

    def test_rejects_at_all(self):
        event = event_for("command", components=[AtAll(), Plain("command")])
        self.assertFalse(XQAPlugin._is_at_current_bot(event))

    def test_missing_self_id_fails_closed(self):
        event = event_for("command", self_id=None, components=[At("bot-1")])
        self.assertFalse(XQAPlugin._is_at_current_bot(event))


class MentionRoutingTests(unittest.IsolatedAsyncioTestCase):
    def make_plugin(self, *, enabled: bool):
        plugin = object.__new__(XQAPlugin)
        plugin.config = {
            "group_plugin_enabled_default": True,
            "enable_processing_feedback": False,
        }
        plugin.data_dir = tempfile.gettempdir()
        plugin.store = Mock()
        plugin.store.is_group_enabled.return_value = enabled
        plugin.store.set_group_enabled = AsyncMock()
        plugin._can_toggle_group_plugin = AsyncMock(return_value=True)
        plugin._set_question = AsyncMock(return_value="set")
        plugin._show_questions = AsyncMock(return_value="show")
        plugin._delete_question = AsyncMock(return_value="delete")
        return plugin

    async def test_toggle_without_current_bot_mention_is_silent_and_does_not_stop(
        self,
    ):
        for message in ("XQA禁用本群", "XQA启用本群"):
            for components in (
                [Plain(message)],
                [At("other-bot"), Plain(message)],
                [AtAll(), Plain(message)],
            ):
                with self.subTest(message=message, components=components):
                    plugin = self.make_plugin(enabled=True)
                    plugin._match_reply = AsyncMock(return_value=[{"type": "text"}])
                    event = event_for(message, components=components)

                    result = await collect(plugin.on_group_message(event))

                    self.assertEqual(result, [])
                    event.stop_event.assert_not_called()
                    plugin._match_reply.assert_not_awaited()
                    plugin._can_toggle_group_plugin.assert_not_awaited()
                    plugin.store.set_group_enabled.assert_not_awaited()

    async def test_toggle_with_current_bot_mention_executes(self):
        for message, expected, enabled in (
            ("XQA禁用本群", "本群已禁用 XQA。", False),
            ("XQA启用本群", "本群已启用 XQA。", True),
        ):
            with self.subTest(message=message):
                plugin = self.make_plugin(enabled=not enabled)
                plugin._match_reply = AsyncMock()
                event = event_for(message, components=[At("bot-1"), Plain(message)])

                result = await collect(plugin.on_group_message(event))

                self.assertEqual(result, [expected])
                event.stop_event.assert_called_once_with()
                plugin._match_reply.assert_not_awaited()
                plugin._can_toggle_group_plugin.assert_awaited_once_with(event)
                plugin.store.set_group_enabled.assert_awaited_once_with(
                    "group-1", enabled
                )

    async def test_toggle_permission_denial_is_preserved_after_current_mention(self):
        plugin = self.make_plugin(enabled=True)
        plugin._can_toggle_group_plugin.return_value = False
        plugin.config["permission_denied_notice"] = True
        event = event_for("XQA启用本群", components=[At("bot-1"), Plain("XQA启用本群")])

        result = await plugin._handle_management_message(
            event, "group-1", "user-1", "XQA启用本群"
        )

        self.assertEqual(result, "权限不足：该命令仅限管理员使用。")
        plugin.store.set_group_enabled.assert_not_awaited()

    async def test_disabled_commands_without_current_mention_are_silent(self):
        plugin = self.make_plugin(enabled=False)
        for message in ("我问A你答B", "看看我问", "不要回答A"):
            with self.subTest(message=message):
                result = await plugin._handle_management_message(
                    event_for(message), "group-1", "user-1", message
                )
                self.assertIsNone(result)
        plugin._set_question.assert_not_awaited()
        plugin._show_questions.assert_not_awaited()
        plugin._delete_question.assert_not_awaited()

    async def test_disabled_commands_with_current_mention_report_disabled(self):
        plugin = self.make_plugin(enabled=False)
        for message in ("我问A你答B", "看看我问", "不要回答A"):
            with self.subTest(message=message):
                result = await plugin._handle_management_message(
                    event_for(message, components=[At("bot-1"), Plain(message)]),
                    "group-1",
                    "user-1",
                    message,
                )
                self.assertEqual(
                    result,
                    "本群已禁用 XQA。请明确 @ 当前 Bot 后发送“XQA启用本群”恢复。",
                )

    async def test_disabled_group_mentioned_regular_message_is_silent_without_stopping(
        self,
    ):
        plugin = self.make_plugin(enabled=False)
        event = event_for("普通消息", components=[At("bot-1"), Plain("普通消息")])

        result = await collect(plugin.on_group_message(event))

        self.assertEqual(result, [])
        event.stop_event.assert_not_called()
        plugin.store.match.assert_not_called()

    async def test_disabled_help_requires_current_mention(self):
        plugin = self.make_plugin(enabled=False)
        silent = await collect(plugin.xqa_help(event_for("XQA帮助")))
        for alias in ("问答帮助", "XQA帮助", "xqa帮助"):
            with self.subTest(alias=alias):
                shown = await collect(
                    plugin.xqa_help(
                        event_for(alias, components=[At("bot-1"), Plain(alias)])
                    )
                )
                self.assertEqual(shown, [plugin._disabled_help_text()])
                self.assertIn("本群当前已禁用 XQA", shown[0])
                self.assertIn("@Bot XQA启用本群", shown[0])
                self.assertIn(plugin._help_text(), shown[0])

        self.assertEqual(silent, [])

    async def test_disabled_help_mentioned_other_bot_is_silent(self):
        plugin = self.make_plugin(enabled=False)
        result = await collect(
            plugin.xqa_help(
                event_for("XQA帮助", components=[At("other-bot"), Plain("XQA帮助")])
            )
        )
        self.assertEqual(result, [])

    async def test_disabled_directed_help_has_only_one_observable_reply(self):
        plugin = self.make_plugin(enabled=False)
        event = event_for("XQA帮助", components=[At("bot-1"), Plain("XQA帮助")])

        command_outputs = await collect(plugin.xqa_help(event))
        group_outputs = await collect(plugin.on_group_message(event))

        self.assertEqual(
            command_outputs + group_outputs, [plugin._disabled_help_text()]
        )
        event.stop_event.assert_not_called()

    async def test_disabled_group_can_be_reenabled_when_current_bot_is_mentioned(self):
        plugin = self.make_plugin(enabled=False)
        event = event_for("XQA启用本群", components=[At("bot-1"), Plain("XQA启用本群")])

        result = await plugin._handle_management_message(
            event, "group-1", "user-1", "XQA启用本群"
        )

        self.assertEqual(result, "本群已启用 XQA。")
        plugin.store.set_group_enabled.assert_awaited_once_with("group-1", True)

    async def test_enabled_management_commands_do_not_require_mentions(self):
        plugin = self.make_plugin(enabled=True)
        for message, expected in (
            ("我问A你答B", "set"),
            ("看看我问", "show"),
            ("不要回答A", "delete"),
        ):
            with self.subTest(message=message):
                result = await plugin._handle_management_message(
                    event_for(message), "group-1", "user-1", message
                )
                self.assertEqual(result, expected)

    async def test_enabled_help_keeps_existing_no_mention_behavior(self):
        plugin = self.make_plugin(enabled=True)
        result = await collect(plugin.xqa_help(event_for("XQA帮助")))
        self.assertEqual(result, [plugin._help_text()])
        self.assertNotIn("本群当前已禁用 XQA", result[0])

    async def test_only_target_bot_instance_handles_toggle(self):
        event_for_a = event_for(
            "XQA禁用本群",
            self_id="bot-a",
            components=[At("bot-a"), Plain("XQA禁用本群")],
        )
        event_for_b = event_for(
            "XQA禁用本群",
            self_id="bot-b",
            components=[At("bot-a"), Plain("XQA禁用本群")],
        )
        plugin_a = self.make_plugin(enabled=True)
        plugin_b = self.make_plugin(enabled=True)

        result_a = await collect(plugin_a.on_group_message(event_for_a))
        result_b = await collect(plugin_b.on_group_message(event_for_b))

        self.assertEqual(result_a, ["本群已禁用 XQA。"])
        self.assertEqual(result_b, [])
        event_for_a.stop_event.assert_called_once_with()
        event_for_b.stop_event.assert_not_called()
        plugin_a.store.set_group_enabled.assert_awaited_once()
        plugin_b.store.set_group_enabled.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
