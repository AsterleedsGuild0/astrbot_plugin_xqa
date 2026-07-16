from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from astrbot_stubs import File, Image, LOGGER, Plain, Reply, Video

del LOGGER
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
main_module = importlib.import_module("astrbot_plugin_xqa.main")
XQAPlugin = main_module.XQAPlugin


def event_for(message: str, components: list[object]):
    event = Mock()
    event.get_messages.return_value = components
    event.get_message_str.return_value = message
    return event


class ProcessingFeedbackTests(unittest.IsolatedAsyncioTestCase):
    def make_plugin(self):
        plugin = object.__new__(XQAPlugin)
        plugin.config = {
            "group_plugin_enabled_default": True,
            "enable_processing_feedback": True,
            "persist_image_as_base64": False,
        }
        plugin.data_dir = tempfile.gettempdir()
        plugin.store = Mock()
        plugin.store.is_group_enabled.return_value = True
        plugin.store.set_question = AsyncMock()
        plugin._send_slow_media_save_ack = AsyncMock()
        plugin._set_question = AsyncMock(return_value="set")
        return plugin

    async def test_invalid_media_style_message_has_no_feedback_or_write(self):
        plugin = self.make_plugin()
        message = "看看你答"
        event = event_for(message, [Plain(message), Image("base64://image")])

        result = await plugin._handle_management_message(
            event, "group-1", "user-1", message
        )

        self.assertIsNone(result)
        plugin._send_slow_media_save_ack.assert_not_awaited()
        plugin._set_question.assert_not_awaited()
        plugin.store.set_question.assert_not_awaited()

    async def test_valid_image_setting_still_sends_feedback(self):
        plugin = self.make_plugin()
        message = "我问A你答"
        event = event_for(message, [Plain(message), Image("base64://image")])

        result = await plugin._handle_management_message(
            event, "group-1", "user-1", message
        )

        self.assertEqual(result, "set")
        plugin._send_slow_media_save_ack.assert_awaited_once_with(event)
        plugin._set_question.assert_awaited_once()

    async def test_valid_media_setting_has_no_feedback_when_disabled(self):
        plugin = self.make_plugin()
        plugin.config["enable_processing_feedback"] = False
        message = "我问A你答"
        event = event_for(message, [Plain(message), Image("base64://image")])

        result = await plugin._handle_management_message(
            event, "group-1", "user-1", message
        )

        self.assertEqual(result, "set")
        plugin._send_slow_media_save_ack.assert_not_awaited()
        plugin._set_question.assert_awaited_once()

    async def test_valid_text_setting_has_no_feedback(self):
        plugin = self.make_plugin()
        message = "我问A你答B"
        event = event_for(message, [Plain(message)])

        result = await plugin._handle_management_message(
            event, "group-1", "user-1", message
        )

        self.assertEqual(result, "set")
        plugin._send_slow_media_save_ack.assert_not_awaited()

    async def test_replied_video_feedback_happens_before_parse(self):
        for replied_media in (Video("answer.mp4"), self._video_file()):
            with self.subTest(media=type(replied_media).__name__):
                plugin = self.make_plugin()
                message = "有人问A你答"
                event = event_for(message, [Plain(message), Reply([replied_media])])
                calls: list[str] = []

                async def send_feedback(_event):
                    calls.append("feedback")

                async def parse_event(_event, **_kwargs):
                    calls.append("parse")
                    return (
                        "有人",
                        "A",
                        [{"type": "video", "value": "saved.mp4"}],
                    )

                plugin._send_slow_media_save_ack.side_effect = send_feedback
                with patch.object(
                    main_module,
                    "parse_set_command_from_event",
                    side_effect=parse_event,
                ):
                    result = await plugin._handle_management_message(
                        event, "group-1", "user-1", message
                    )

                self.assertEqual(result, "set")
                self.assertEqual(calls, ["feedback", "parse"])

    @staticmethod
    def _video_file():
        file = File("/tmp/answer.mp4")
        setattr(file, "file_", "/tmp/answer.mp4")
        return file


if __name__ == "__main__":
    unittest.main()
