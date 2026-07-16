from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from astrbot_stubs import LOGGER

del LOGGER
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
main = importlib.import_module("astrbot_plugin_xqa.main")
store_module = importlib.import_module("astrbot_plugin_xqa.core.store")
XQAPlugin = main.XQAPlugin
XQAStore = store_module.XQAStore


class StorageFilenameTests(unittest.IsolatedAsyncioTestCase):
    async def test_custom_filename_persists_reloads_and_isolates_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            custom_filename = "custom-xqa.json"
            with (
                patch.object(main.Star, "__init__", return_value=None),
                patch.object(
                    main.StarTools,
                    "get_data_dir",
                    return_value=data_dir,
                    create=True,
                ),
            ):
                plugin = XQAPlugin(object(), {"storage_filename": custom_filename})

            self.assertEqual(plugin.store.path, data_dir / custom_filename)
            await plugin.initialize()
            await plugin.store.set_question(
                "group-1",
                "user-1",
                "question",
                [[{"type": "text", "text": "answer"}]],
            )
            self.assertTrue((data_dir / custom_filename).is_file())

            reloaded = XQAStore(data_dir, filename=custom_filename)
            await reloaded.load()
            self.assertEqual(reloaded.list_questions("group-1", "user-1"), ["question"])

            isolated_filename = "isolated-xqa.json"
            isolated = XQAStore(data_dir, filename=isolated_filename)
            await isolated.load()
            self.assertTrue((data_dir / isolated_filename).is_file())
            self.assertEqual(isolated.count_questions("group-1", "user-1"), 0)
            self.assertEqual(reloaded.list_questions("group-1", "user-1"), ["question"])


if __name__ == "__main__":
    unittest.main()
