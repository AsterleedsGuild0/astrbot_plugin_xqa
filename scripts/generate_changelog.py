#!/usr/bin/env python3
"""Generate and extract Keep a Changelog sections using only the standard library."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHANGELOG = ROOT / "CHANGELOG.md"
CATEGORY_ORDER = (
    "新增",
    "变更",
    "弃用",
    "移除",
    "修复",
    "安全",
    "文档",
    "测试",
    "内部",
    "其他",
)
ISSUE_PATTERN = re.compile(r"(?<![\w/])#(\d+)\b")
HEADING_PATTERN = re.compile(
    r"^##[ \t]+(?:\[(?P<bracketed>[^]\n]+)\]|(?P<plain>\S+))"
    r"(?:[ \t]+-[ \t]+[^\n]+)?[ \t]*$",
    re.MULTILINE,
)
LINK_REFERENCE_PATTERN = re.compile(r"^\[[^]\n]+\]:\s+\S+", re.MULTILINE)
LINK_DEFINITION_PATTERN = re.compile(
    r"^\[(?P<label>[^]\n]+)\]:\s+(?P<url>\S+)\s*$", re.MULTILINE
)


@dataclass(frozen=True)
class Commit:
    subject: str
    body: str = ""


def classify_commit(subject: str) -> str:
    """Map common Conventional Commit types and gitmoji to changelog categories."""
    lowered = subject.casefold().lstrip()
    conventional = re.match(r"([a-z]+)(?:\([^)]*\))?!?[^:\w]*:", lowered)
    commit_type = conventional.group(1) if conventional else ""

    rules = (
        ("安全", {"security"}, ("🔒", "🔐")),
        ("修复", {"fix", "bugfix", "hotfix"}, ("🐛", "🚑", "🩹")),
        ("移除", {"remove"}, ("🔥", "➖")),
        ("弃用", {"deprecate"}, ("🗑️",)),
        ("新增", {"feat", "feature"}, ("✨", "🎉", "➕")),
        ("文档", {"docs", "doc"}, ("📝",)),
        ("测试", {"test"}, ("✅", "🧪")),
        ("内部", {"chore", "build", "ci", "release"}, ("🔧", "💚", "📦", "🏗️")),
        ("变更", {"refactor", "perf", "style"}, ("♻️", "⚡", "🎨")),
    )
    for category, types, emojis in rules:
        if commit_type in types or any(emoji in subject for emoji in emojis):
            return category
    return "其他"


def extract_issue_references(text: str) -> list[str]:
    """Return unique local issue references in their first-seen order."""
    return list(dict.fromkeys(f"#{number}" for number in ISSUE_PATTERN.findall(text)))


def clean_subject(subject: str) -> str:
    """Remove Conventional Commit prefixes and leading/trailing gitmoji."""
    cleaned = re.sub(r"^[a-zA-Z]+(?:\([^)]*\))?!?[^:\w]*:\s*", "", subject).strip()
    emoji_tokens = "✨🐛🚑🩹🔥➖🗑️🎉➕📝🔒🔐🚀🖼️🔧♻️⚡️⚡✅🧪💚⬆️⬇️📦🏗️🎨"
    cleaned = cleaned.strip(emoji_tokens + " ")
    cleaned = re.sub(r"^[a-zA-Z]+\s*:\s*", "", cleaned).strip()
    return cleaned or subject.strip()


def parse_git_log(output: str) -> list[Commit]:
    commits: list[Commit] = []
    for record in output.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        fields = record.split("\x1f", 2)
        if len(fields) != 3:
            raise ValueError("Unexpected git log record")
        _commit_hash, subject, body = fields
        commits.append(Commit(subject=subject.strip(), body=body.strip()))
    return commits


def read_commits(from_ref: str | None, to_ref: str) -> list[Commit]:
    revision = f"{from_ref}..{to_ref}" if from_ref else to_ref
    result = subprocess.run(
        ["git", "log", "--format=%H%x1f%s%x1f%b%x1e", revision],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_git_log(result.stdout)


def generate_section(version: str, release_date: str, commits: list[Commit]) -> str:
    if not commits:
        raise ValueError("No commits found for the requested revision range")

    grouped: dict[str, list[str]] = {category: [] for category in CATEGORY_ORDER}
    for commit in commits:
        category = classify_commit(commit.subject)
        description = clean_subject(commit.subject)
        references = extract_issue_references(f"{commit.subject}\n{commit.body}")
        if references and not extract_issue_references(description):
            description = f"{description}（{', '.join(references)}）"
        grouped[category].append(f"- {description}")

    lines = [f"## [{version}] - {release_date}"]
    for category in CATEGORY_ORDER:
        entries = grouped[category]
        if entries:
            lines.extend(("", f"### {category}", "", *entries))
    return "\n".join(lines) + "\n"


def find_section(text: str, version: str) -> tuple[int, int, str]:
    matches = list(HEADING_PATTERN.finditer(text))
    for index, match in enumerate(matches):
        heading_version = match.group("bracketed") or match.group("plain")
        if heading_version != version:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        link_references = LINK_REFERENCE_PATTERN.search(text, match.end(), end)
        if link_references:
            end = link_references.start()
        body = text[match.end() : end].strip()
        if not body:
            raise ValueError(f"Changelog section {version!r} is empty")
        return match.start(), end, body
    raise ValueError(f"Changelog section {version!r} was not found")


def append_referenced_link_definitions(text: str, body: str) -> str:
    """Append link definitions referenced by an extracted section."""
    definitions: list[str] = []
    for match in LINK_DEFINITION_PATTERN.finditer(text):
        label = re.escape(match.group("label"))
        reference = re.compile(
            rf"(?<!\!)\[{label}\](?:\[\]|(?![\[(]))",
            re.IGNORECASE,
        )
        if reference.search(body):
            definitions.append(match.group(0))
    if not definitions:
        return body
    definition_block = "\n".join(definitions)
    return f"{body}\n\n{definition_block}"


def write_section(
    changelog_path: Path,
    version: str,
    section: str,
    from_ref: str | None = None,
) -> None:
    text = changelog_path.read_text(encoding="utf-8")
    matches = list(HEADING_PATTERN.finditer(text))
    if any(
        (match.group("bracketed") or match.group("plain")) == version
        for match in matches
    ):
        raise ValueError(f"Changelog section {version!r} already exists")

    link_definitions = list(LINK_DEFINITION_PATTERN.finditer(text))
    version_links = [
        match for match in link_definitions if match.group("label") == version
    ]
    if version_links:
        raise ValueError(f"Changelog link {version!r} already exists")

    unreleased_links = [
        match for match in link_definitions if match.group("label") == "Unreleased"
    ]
    if len(unreleased_links) != 1:
        raise ValueError("Changelog must contain exactly one [Unreleased] link")
    unreleased_link = unreleased_links[0]
    repository_match = re.fullmatch(
        r"(?P<base>.+)/compare/.+\.\.\.HEAD", unreleased_link.group("url")
    )
    if not repository_match:
        raise ValueError("Cannot derive repository URL from [Unreleased] link")
    repository_url = repository_match.group("base")

    new_unreleased = f"[Unreleased]: {repository_url}/compare/{version}...HEAD"
    if from_ref:
        version_url = f"{repository_url}/compare/{from_ref}...{version}"
    else:
        version_url = f"{repository_url}/releases/tag/{version}"
    new_version_link = f"[{version}]: {version_url}"
    text = (
        text[: unreleased_link.start()]
        + new_unreleased
        + "\n"
        + new_version_link
        + text[unreleased_link.end() :]
    )

    matches = list(HEADING_PATTERN.finditer(text))

    for index, match in enumerate(matches):
        heading_version = match.group("bracketed") or match.group("plain")
        if heading_version != "Unreleased":
            continue
        if index + 1 < len(matches):
            insert_at = matches[index + 1].start()
        else:
            link_references = LINK_REFERENCE_PATTERN.search(text, match.end())
            insert_at = link_references.start() if link_references else len(text)
        before = text[: match.end()].rstrip()
        after = text[insert_at:].lstrip()
        updated = f"{before}\n\n{section.strip()}\n\n{after}"
        changelog_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
        return
    raise ValueError("Changelog section 'Unreleased' was not found")


def command_generate(args: argparse.Namespace) -> int:
    commits = read_commits(args.from_ref, args.to_ref)
    section = generate_section(args.version, args.date, commits)
    if args.write:
        write_section(args.changelog, args.version, section, args.from_ref)
    elif args.output:
        args.output.write_text(section, encoding="utf-8")
    else:
        sys.stdout.write(section)
    return 0


def command_extract(args: argparse.Namespace) -> int:
    text = args.changelog.read_text(encoding="utf-8")
    _start, _end, body = find_section(text, args.version)
    body = append_referenced_link_definitions(text, body)
    output = body + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate a version section")
    generate.add_argument(
        "version_positional",
        nargs="?",
        metavar="VERSION",
        help="Version heading, for example v0.1.3 (or use --version)",
    )
    generate.add_argument(
        "--version", dest="version_option", help="Version heading, for example v0.1.3"
    )
    generate.add_argument("--from-ref", help="Exclusive lower Git revision")
    generate.add_argument(
        "--to-ref", default="HEAD", help="Inclusive upper Git revision"
    )
    generate.add_argument(
        "--date", default=date.today().isoformat(), help="Release date"
    )
    generate.add_argument("--changelog", type=Path, default=DEFAULT_CHANGELOG)
    generate_output = generate.add_mutually_exclusive_group()
    generate_output.add_argument(
        "--write", action="store_true", help="Update CHANGELOG.md and version links"
    )
    generate_output.add_argument(
        "--output", type=Path, help="Write the generated section to this file"
    )
    generate.set_defaults(handler=command_generate)

    extract = subparsers.add_parser("extract", help="Extract one exact version section")
    extract.add_argument(
        "version_positional",
        nargs="?",
        metavar="VERSION",
        help="Exact version heading to extract (or use --version)",
    )
    extract.add_argument(
        "--version", dest="version_option", help="Exact version heading to extract"
    )
    extract.add_argument("--changelog", type=Path, default=DEFAULT_CHANGELOG)
    extract.add_argument("--output", type=Path, help="Write release notes to this file")
    extract.set_defaults(handler=command_extract)
    return parser


def resolve_version(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    positional = args.version_positional
    option = args.version_option
    if positional and option:
        parser.error("VERSION and --version cannot be used together")
    if not positional and not option:
        parser.error("a version is required: provide VERSION or --version")
    args.version = positional or option


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    resolve_version(parser, args)
    try:
        return args.handler(args)
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
