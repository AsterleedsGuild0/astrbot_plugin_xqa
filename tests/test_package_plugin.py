from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts import package_plugin


class PackagePluginTests(unittest.TestCase):
    def test_archive_contains_linked_project_documents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "plugin.zip"
            package_plugin.build_archive(output, flat=False)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())

        plugin_name = package_plugin.read_plugin_name()
        for document in ("PRD.md", "FSD.md", "DESIGN.md", "CHANGELOG.md"):
            with self.subTest(document=document):
                self.assertIn(f"{plugin_name}/{document}", names)


if __name__ == "__main__":
    unittest.main()
