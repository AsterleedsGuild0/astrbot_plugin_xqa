from __future__ import annotations

import hashlib
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from astrbot_stubs import LOGGER, Plain, Reply, Video

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
MESSAGE_CODEC = importlib.import_module("astrbot_plugin_xqa.core.message_codec")


class VideoStorageLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        LOGGER.reset_mock()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.video_dir = self.root / "videos"
        self.video_dir.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def persist(self, source: Path, *, storage_limit_mb: int):
        return MESSAGE_CODEC._persist_video_path(
            source,
            video_dir=self.video_dir,
            max_video_size_mb=10,
            max_video_storage_mb=storage_limit_mb,
        )

    def test_new_file_within_storage_limit_succeeds(self):
        (self.video_dir / "existing.mp4").write_bytes(b"x" * (400 * 1024))
        source = self.root / "source.mp4"
        source.write_bytes(b"y" * (500 * 1024))

        segment = self.persist(source, storage_limit_mb=1)

        self.assertEqual(segment["type"], "video")
        self.assertTrue((self.root / segment["value"]).is_file())

    def test_new_file_exceeding_storage_limit_is_rejected(self):
        (self.video_dir / "existing.mp4").write_bytes(b"x" * (600 * 1024))
        source = self.root / "source.mp4"
        source.write_bytes(b"y" * (500 * 1024))

        with self.assertRaisesRegex(ValueError, "视频存储空间已达到上限（1 MB）"):
            self.persist(source, storage_limit_mb=1)

    def test_zero_storage_limit_is_unlimited(self):
        (self.video_dir / "existing.mp4").write_bytes(b"x" * (2 * 1024 * 1024))
        source = self.root / "source.mp4"
        source.write_bytes(b"y" * (500 * 1024))

        segment = self.persist(source, storage_limit_mb=0)

        self.assertTrue((self.root / segment["value"]).is_file())

    def test_duplicate_sha_succeeds_when_storage_is_full(self):
        source = self.root / "source.mp4"
        source.write_bytes(b"same video")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        existing = self.video_dir / f"{digest}.mp4"
        existing.write_bytes(source.read_bytes())
        (self.video_dir / "filler.mp4").write_bytes(b"x" * (1024 * 1024))

        segment = self.persist(source, storage_limit_mb=1)

        self.assertEqual(segment["value"], f"videos/{existing.name}")

    def test_directories_do_not_count_toward_storage_limit(self):
        nested = self.video_dir / "not-a-video-file"
        nested.mkdir()
        (nested / "large.bin").write_bytes(b"x" * (2 * 1024 * 1024))
        source = self.root / "source.mp4"
        source.write_bytes(b"y" * (500 * 1024))

        segment = self.persist(source, storage_limit_mb=1)

        self.assertTrue((self.root / segment["value"]).is_file())


class VideoDirectoryBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_reply_video_is_not_downloaded_when_video_dir_is_none(self):
        video = Video("https://example.invalid/reply.mp4")
        converter = AsyncMock(
            side_effect=AssertionError("video download must not be attempted")
        )
        setattr(video, "convert_to_file_path", converter)
        event = Mock()
        event.get_messages.return_value = [Plain("我问A你答"), Reply([video])]
        persister = AsyncMock(
            side_effect=AssertionError("video persistence must not be attempted")
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(MESSAGE_CODEC, "_persist_video", new=persister):
                result = await MESSAGE_CODEC.parse_set_command_from_event(
                    event,
                    video_dir=None,
                )

            self.assertEqual(result, ("我", "A", []))
            self.assertEqual(list(Path(temp_dir).iterdir()), [])
        converter.assert_not_awaited()
        persister.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
