from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import generate_changelog as changelog


class GenerateChangelogTests(unittest.TestCase):
    def test_classifies_conventional_commits_and_gitmoji(self) -> None:
        cases = {
            "feat: add command": "新增",
            "fix🐛: repair parser": "修复",
            "docs📝: update guide": "文档",
            "security: reject unsafe path": "安全",
            "refactor: simplify store": "变更",
            "perf: speed up lookup": "变更",
            "style: format source": "变更",
            "test: cover parser": "测试",
            "chore: update tooling": "内部",
            "build: update package": "内部",
            "ci: update workflow": "内部",
            "release: prepare version": "内部",
            "unknown: keep this commit": "其他",
            "plain commit subject": "其他",
        }
        for subject, expected in cases.items():
            with self.subTest(subject=subject):
                self.assertEqual(changelog.classify_commit(subject), expected)

    def test_extracts_unique_issue_references(self) -> None:
        text = "Fixes #12, relates to #7 and closes #12; ignore owner/repo#99"
        self.assertEqual(changelog.extract_issue_references(text), ["#12", "#7"])

    def test_generates_grouped_section_with_chinese_and_issue(self) -> None:
        commits = [
            changelog.Commit("feat✨: 新增‘群问答’", "Closes #8"),
            changelog.Commit("fix: 修复中文＃符号处理"),
        ]
        section = changelog.generate_section("v0.2.0", "2026-07-16", commits)
        self.assertIn("## [v0.2.0] - 2026-07-16", section)
        self.assertIn("### 新增", section)
        self.assertIn("- 新增‘群问答’（#8）", section)
        self.assertIn("### 修复", section)
        self.assertIn("中文＃符号", section)

    def test_generate_reads_git_without_shell(self) -> None:
        completed = mock.Mock(stdout="abc\x1ffeat: 新功能\x1fCloses #3\x1e")
        with mock.patch.object(
            changelog.subprocess, "run", return_value=completed
        ) as run:
            commits = changelog.read_commits("v0.1.0", "HEAD")
        self.assertEqual(commits, [changelog.Commit("feat: 新功能", "Closes #3")])
        _args, kwargs = run.call_args
        self.assertNotIn("shell", kwargs)
        self.assertEqual(_args[0][-1], "v0.1.0..HEAD")

    def test_write_inserts_after_unreleased(self) -> None:
        original = "# 更新日志\n\n## [Unreleased]\n\n### 变更\n\n- 草稿\n\n## [v0.1.0] - 2026-01-01\n\n- 首发\n"
        section = "## [v0.2.0] - 2026-02-01\n\n### 新增\n\n- 新功能\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "CHANGELOG.md"
            original += (
                "\n[Unreleased]: https://example.test/project/compare/v0.1.0...HEAD\n"
                "[v0.1.0]: https://example.test/project/releases/tag/v0.1.0\n"
            )
            path.write_text(original, encoding="utf-8")
            changelog.write_section(path, "v0.2.0", section, "v0.1.0")
            updated = path.read_text(encoding="utf-8")
        self.assertLess(updated.index("## [Unreleased]"), updated.index("## [v0.2.0]"))
        self.assertLess(updated.index("## [v0.2.0]"), updated.index("## [v0.1.0]"))
        self.assertIn("## [Unreleased]\n\n## [v0.2.0]", updated)
        self.assertNotIn("### 变更", updated)
        self.assertNotIn("- 草稿", updated)
        self.assertIn("### 新增\n\n- 新功能", updated)
        self.assertIn("## [v0.1.0] - 2026-01-01\n\n- 首发", updated)
        self.assertIn(
            "[Unreleased]: https://example.test/project/compare/v0.2.0...HEAD",
            updated,
        )
        self.assertIn(
            "[v0.2.0]: https://example.test/project/compare/v0.1.0...v0.2.0",
            updated,
        )

    def test_write_rejects_duplicate_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "CHANGELOG.md"
            path.write_text(
                "## [Unreleased]\n\n- 草稿\n\n## [v0.2.0] - 2026-02-01\n\n- 已发布\n\n"
                "[Unreleased]: https://example.test/project/compare/v0.1.0...HEAD\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "already exists"):
                changelog.write_section(path, "v0.2.0", "unused")

    def test_write_without_from_ref_uses_release_link(self) -> None:
        original = (
            "## [Unreleased]\n\n- 草稿\n\n"
            "[Unreleased]: https://example.test/project/compare/v0.1.0...HEAD\n"
        )
        section = "## [v0.2.0] - 2026-02-01\n\n- 新功能\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "CHANGELOG.md"
            path.write_text(original, encoding="utf-8")
            changelog.write_section(path, "v0.2.0", section)
            updated = path.read_text(encoding="utf-8")
        self.assertIn(
            "[v0.2.0]: https://example.test/project/releases/tag/v0.2.0", updated
        )
        self.assertLess(updated.index("## [v0.2.0]"), updated.index("[Unreleased]:"))
        self.assertNotIn("- 草稿", updated)

    def test_write_handles_empty_unreleased_section(self) -> None:
        original = (
            "# 更新日志\n\n## [Unreleased]\n\n"
            "## [v0.1.0] - 2026-01-01\n\n- 首发\n\n"
            "[Unreleased]: https://example.test/project/compare/v0.1.0...HEAD\n"
            "[v0.1.0]: https://example.test/project/releases/tag/v0.1.0\n"
        )
        section = "## [v0.2.0] - 2026-02-01\n\n### 修复\n\n- 修复问题\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "CHANGELOG.md"
            path.write_text(original, encoding="utf-8")
            changelog.write_section(path, "v0.2.0", section, "v0.1.0")
            updated = path.read_text(encoding="utf-8")

        self.assertIn(
            "## [Unreleased]\n\n## [v0.2.0] - 2026-02-01\n\n"
            "### 修复\n\n- 修复问题\n\n"
            "## [v0.1.0] - 2026-01-01\n\n- 首发",
            updated,
        )
        self.assertIn(
            "[Unreleased]: https://example.test/project/compare/v0.2.0...HEAD",
            updated,
        )
        self.assertIn(
            "[v0.2.0]: https://example.test/project/compare/v0.1.0...v0.2.0",
            updated,
        )

    def test_unknown_commit_is_kept_in_other_category(self) -> None:
        section = changelog.generate_section(
            "v0.2.0", "2026-02-01", [changelog.Commit("untyped change")]
        )
        self.assertIn("### 其他", section)
        self.assertIn("- untyped change", section)

    def test_write_rejects_duplicate_version_link(self) -> None:
        original = (
            "## [Unreleased]\n\n- 草稿\n\n"
            "[Unreleased]: https://example.test/project/compare/v0.1.0...HEAD\n"
            "[v0.2.0]: https://example.test/project/releases/tag/v0.2.0\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "CHANGELOG.md"
            path.write_text(original, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "link.*already exists"):
                changelog.write_section(path, "v0.2.0", "unused")

    def test_generate_output_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "release.md"
            with mock.patch.object(
                changelog,
                "read_commits",
                return_value=[changelog.Commit("feat: 新功能")],
            ):
                result = changelog.main(
                    [
                        "generate",
                        "--version",
                        "v0.2.0",
                        "--date",
                        "2026-02-01",
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(result, 0)
            self.assertIn("## [v0.2.0] - 2026-02-01", output.read_text("utf-8"))

    def test_version_supports_positional_and_option(self) -> None:
        parser = changelog.build_parser()
        positional = parser.parse_args(["extract", "v0.1.2"])
        changelog.resolve_version(parser, positional)
        self.assertEqual(positional.version, "v0.1.2")

        option = parser.parse_args(["extract", "--version", "v0.1.2"])
        changelog.resolve_version(parser, option)
        self.assertEqual(option.version, "v0.1.2")

    def test_version_rejects_conflicting_forms(self) -> None:
        parser = changelog.build_parser()
        args = parser.parse_args(["extract", "v0.1.2", "--version", "v0.1.3"])
        with self.assertRaises(SystemExit):
            changelog.resolve_version(parser, args)

    def test_generate_rejects_write_with_output(self) -> None:
        parser = changelog.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                ["generate", "v0.2.0", "--write", "--output", "release.md"]
            )

    def test_extracts_exact_version_only(self) -> None:
        text = (
            "## [Unreleased]\n\n- 下一版\n\n"
            "## [v0.1.2] - 2026-07-15\n\n### 修复\n\n- 精确内容\n\n"
            "## [v0.1.20] - 2026-08-01\n\n- 不能混入\n"
        )
        _start, _end, body = changelog.find_section(text, "v0.1.2")
        self.assertEqual(body, "### 修复\n\n- 精确内容")

    def test_extract_last_version_excludes_link_definitions(self) -> None:
        text = (
            "## [v0.1.0] - 2026-06-16\n\n- 首发\n\n"
            "[v0.1.0]: https://example.test/releases/v0.1.0\n"
        )
        _start, _end, body = changelog.find_section(text, "v0.1.0")
        self.assertEqual(body, "- 首发")

    def test_extract_rejects_missing_and_empty_versions(self) -> None:
        with self.assertRaisesRegex(ValueError, "was not found"):
            changelog.find_section("## [v0.1.0]\n\n- 内容\n", "v9.9.9")
        with self.assertRaisesRegex(ValueError, "is empty"):
            changelog.find_section("## [v0.1.0]\n\n## [v0.0.9]\n\n- 内容\n", "v0.1.0")


if __name__ == "__main__":
    unittest.main()
