from __future__ import annotations

import re


QUESTION_PATTERN = re.compile(r"^(全群|有人|我)问([\s\S]*)你答([\s\S]*)$")
SHOW_PATTERN = re.compile(r"^看看(有人|我|全群)问([\s\S]*)$")
DELETE_PATTERN = re.compile(r"^(?:@([0-9]+)\s*)?(全群)?不要回答([\s\S]*)$")


def split_answers(raw: str, limit: int) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    escaped = False
    for ch in raw:
        if escaped:
            if ch == "#":
                buf.append("#")
            else:
                buf.append("\\")
                buf.append(ch)
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == "#":
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if escaped:
        buf.append("\\")
    parts.append("".join(buf))
    answers = [item for item in parts if item]
    return answers[:limit]


def replace_backrefs(answer: str, match: re.Match[str]) -> str:
    def repl(item: re.Match[str]) -> str:
        index = int(item.group(1))
        try:
            return match.group(index) or ""
        except IndexError:
            return item.group(0)

    return re.sub(r"\$(\d+)", repl, answer)


def is_empty_or_broad_regex(pattern: str) -> bool:
    if not pattern.strip():
        return True
    if pattern.strip() in {".*", ".*?", "[\\s\\S]*", "([\\s\\S]*)", "(.*)"}:
        return True
    try:
        return re.match(f"^(?:{pattern})$", "") is not None
    except re.error:
        return False


def looks_dangerous_regex(pattern: str) -> bool:
    # Conservative guard for common nested-quantifier ReDoS shapes.
    return re.search(r"\([^)]*[+*][^)]*\)[+*]", pattern) is not None
