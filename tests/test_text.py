from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from astrbot_plugin_xqa.core.text import (  # noqa: E402
    is_empty_or_broad_regex,
    looks_dangerous_regex,
    replace_backrefs,
    split_answers,
)


class SplitAnswersTests(unittest.TestCase):
    def test_plain_split(self):
        self.assertEqual(split_answers("A#B#C", 10), ["A", "B", "C"])

    def test_escaped_hash(self):
        self.assertEqual(split_answers(r"A\#B#C", 10), ["A#B", "C"])

    def test_trailing_backslash(self):
        self.assertEqual(split_answers("A\\", 10), ["A\\"])

    def test_limit(self):
        self.assertEqual(split_answers("A#B#C", 2), ["A", "B"])

    def test_empty_candidates_are_removed(self):
        self.assertEqual(split_answers("#A##B#", 10), ["A", "B"])
        self.assertEqual(split_answers("###", 10), [])


class ReplaceBackrefsTests(unittest.TestCase):
    def test_existing_groups_are_replaced(self):
        match = re.fullmatch(r"(A)(B)", "AB")
        self.assertIsNotNone(match)
        self.assertEqual(replace_backrefs("$2-$1", match), "B-A")

    def test_missing_group_is_preserved(self):
        match = re.fullmatch(r"(A)", "A")
        self.assertIsNotNone(match)
        self.assertEqual(replace_backrefs("$2-$1", match), "$2-A")


class RegexGuardTests(unittest.TestCase):
    def test_empty_and_broad_patterns(self):
        for pattern in ("", "   ", ".*", ".*?", r"[\s\S]*", r"([\s\S]*)", "(.*)"):
            with self.subTest(pattern=pattern):
                self.assertTrue(is_empty_or_broad_regex(pattern))
        self.assertFalse(is_empty_or_broad_regex("hello"))

    def test_invalid_regex_is_not_reported_as_broad(self):
        self.assertFalse(is_empty_or_broad_regex("("))

    def test_dangerous_nested_quantifiers(self):
        for pattern in ("(a+)+", "(a*)*", "(ab+)*"):
            with self.subTest(pattern=pattern):
                self.assertTrue(looks_dangerous_regex(pattern))

    def test_ordinary_regex_is_not_dangerous(self):
        for pattern in (r"a+", r"(ab)+", r"^hello\s+world$"):
            with self.subTest(pattern=pattern):
                self.assertFalse(looks_dangerous_regex(pattern))


if __name__ == "__main__":
    unittest.main()
