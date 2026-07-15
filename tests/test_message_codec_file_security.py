from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path

from astrbot_stubs import Image, LOGGER, Video

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
MESSAGE_CODEC = importlib.import_module("astrbot_plugin_xqa.core.message_codec")


class MessageCodecFileSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        LOGGER.reset_mock()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "data"
        self.root.mkdir()
        (self.root / "videos").mkdir()
        self.image = self.root / "image.png"
        self.video = self.root / "videos" / "video.mp4"
        self.image.write_bytes(b"image")
        self.video.write_bytes(b"video")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def build_file(self, media_type: str, value: str, data_dir=None):
        return MESSAGE_CODEC.build_components(
            [{"type": media_type, "source": "file", "value": value}],
            data_dir=self.root if data_dir is None else data_dir,
        )

    def test_relative_path_inside_data_dir_is_allowed(self):
        components = self.build_file("video", "videos/video.mp4")

        self.assertEqual(len(components), 1)
        self.assertIsInstance(components[0], Video)
        self.assertEqual(components[0].value, str(self.video.resolve()))

    def test_absolute_path_inside_data_dir_is_allowed(self):
        components = self.build_file("image", str(self.image.resolve()))

        self.assertEqual(len(components), 1)
        self.assertIsInstance(components[0], Image)
        self.assertEqual(components[0].value, str(self.image.resolve()))

    def test_parent_traversal_is_rejected(self):
        outside = self.root.parent / "outside.png"
        outside.write_bytes(b"outside")

        self.assertEqual(self.build_file("image", "../outside.png"), [])
        LOGGER.warning.assert_called_once()

    def test_absolute_path_outside_data_dir_is_rejected(self):
        outside = self.root.parent / "outside.mp4"
        outside.write_bytes(b"outside")

        self.assertEqual(self.build_file("video", str(outside.resolve())), [])
        LOGGER.warning.assert_called_once()

    def test_symlink_escape_is_rejected(self):
        outside = self.root.parent / "outside.png"
        outside.write_bytes(b"outside")
        link = self.root / "linked.png"
        try:
            link.symlink_to(outside)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"symlink is unavailable: {exc}")

        self.assertEqual(self.build_file("image", "linked.png"), [])
        LOGGER.warning.assert_called_once()

    def test_missing_file_is_skipped(self):
        self.assertEqual(self.build_file("image", "missing.png"), [])
        LOGGER.warning.assert_called_once()

    def test_valid_image_and_video_are_built(self):
        components = MESSAGE_CODEC.build_components(
            [
                {"type": "image", "source": "file", "value": "image.png"},
                {
                    "type": "video",
                    "source": "file",
                    "value": "videos/video.mp4",
                },
            ],
            data_dir=self.root,
        )

        self.assertEqual([type(item) for item in components], [Image, Video])
        self.assertTrue(all(item.kind == "file" for item in components))

    def test_file_source_without_data_dir_is_skipped(self):
        components = MESSAGE_CODEC.build_components(
            [
                {
                    "type": "image",
                    "source": "file",
                    "value": str(self.image.resolve()),
                }
            ],
            data_dir=None,
        )

        self.assertEqual(components, [])
        LOGGER.warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
