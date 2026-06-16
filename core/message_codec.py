from __future__ import annotations

import re
from typing import Any, TypeAlias

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import Image, Plain

from .text import split_answers

AnswerSegment: TypeAlias = dict[str, str]
AnswerChain: TypeAlias = list[AnswerSegment]


def normalize_answer_chain(raw: object) -> AnswerChain:
    if isinstance(raw, str):
        return [{"type": "text", "text": raw}]
    if not isinstance(raw, list):
        return []
    # New format: [{"type": "text", ...}, {"type": "image", ...}]
    if all(isinstance(item, dict) for item in raw):
        result: AnswerChain = []
        for item in raw:
            seg = _normalize_segment(item)
            if seg:
                result.append(seg)
        return result
    # Legacy format may be a list of strings.
    text = "".join(str(item) for item in raw if str(item))
    return [{"type": "text", "text": text}] if text else []


def chain_to_plain_text(chain: AnswerChain) -> str:
    parts: list[str] = []
    for seg in chain:
        if seg.get("type") == "text":
            parts.append(seg.get("text", ""))
        elif seg.get("type") == "image":
            parts.append("[图片]")
    return "".join(parts)


def chain_text_length(chain: AnswerChain) -> int:
    return sum(len(seg.get("text", "")) for seg in chain if seg.get("type") == "text")


def chain_image_count(chain: AnswerChain) -> int:
    return sum(1 for seg in chain if seg.get("type") == "image")


def has_answer_content(chain: AnswerChain) -> bool:
    for seg in chain:
        if seg.get("type") == "image":
            return True
        if seg.get("type") == "text" and seg.get("text", "").strip():
            return True
    return False


def split_text_only_answer(chain: AnswerChain, limit: int) -> list[AnswerChain]:
    if len(chain) != 1 or chain[0].get("type") != "text":
        return [chain]
    return [
        [{"type": "text", "text": answer}]
        for answer in split_answers(chain[0].get("text", ""), limit)
    ]


async def parse_set_command_from_event(
    event: AstrMessageEvent, *, persist_image_as_base64: bool = True
) -> tuple[str, str, AnswerChain] | None:
    before_text, answer_chain = await _split_set_command_components(
        event, persist_image_as_base64=persist_image_as_base64
    )
    if before_text is None:
        return None
    matched = re.match(r"^(全群|有人|我)问([\s\S]*)$", before_text)
    if not matched:
        return None
    return matched.group(1), matched.group(2), answer_chain


def build_components(chain: AnswerChain) -> list[Any]:
    components: list[Any] = []
    for seg in chain:
        if seg.get("type") == "text":
            text = seg.get("text", "")
            if text:
                components.append(Plain(text))
        elif seg.get("type") == "image":
            source = seg.get("source", "")
            value = seg.get("value", "")
            if not value:
                continue
            if source == "base64":
                components.append(Image.fromBase64(value))
            elif source == "url":
                components.append(Image.fromURL(value))
            elif source == "file":
                components.append(Image.fromFileSystem(value))
            else:
                components.append(Image(file=value))
    return components


def has_image_after_answer_delimiter(event: AstrMessageEvent) -> bool:
    found_delimiter = False
    for comp in event.get_messages():
        if isinstance(comp, Plain):
            text = comp.text or ""
            if not found_delimiter and "你答" in text:
                found_delimiter = True
        elif isinstance(comp, Image) and found_delimiter:
            return True
    return False


async def _split_set_command_components(
    event: AstrMessageEvent, *, persist_image_as_base64: bool
) -> tuple[str | None, AnswerChain]:
    before_parts: list[str] = []
    answer_chain: AnswerChain = []
    found_delimiter = False

    for comp in event.get_messages():
        if isinstance(comp, Plain):
            text = comp.text or ""
            if not found_delimiter:
                index = text.find("你答")
                if index < 0:
                    before_parts.append(text)
                    continue
                found_delimiter = True
                before_parts.append(text[:index])
                tail = text[index + len("你答") :]
                if tail:
                    answer_chain.append({"type": "text", "text": tail})
                continue
            if text:
                answer_chain.append({"type": "text", "text": text})
        elif isinstance(comp, Image) and found_delimiter:
            image_segment = await _serialize_image(
                comp, persist_as_base64=persist_image_as_base64
            )
            if image_segment:
                answer_chain.append(image_segment)

    if not found_delimiter:
        return None, []
    return "".join(before_parts), answer_chain


async def _serialize_image(
    image: Image, *, persist_as_base64: bool
) -> AnswerSegment | None:
    if persist_as_base64:
        try:
            base64_data = await image.convert_to_base64()
            if base64_data:
                return {"type": "image", "source": "base64", "value": base64_data}
        except Exception as exc:
            logger.warning(f"[XQA] 图片转 base64 失败，尝试保存引用: {exc}")

    url = str(getattr(image, "url", "") or "")
    if url.startswith(("http://", "https://")):
        return {"type": "image", "source": "url", "value": url}

    file = str(getattr(image, "file", "") or "")
    if file.startswith(("http://", "https://")):
        return {"type": "image", "source": "url", "value": file}
    if file.startswith("file://"):
        return {
            "type": "image",
            "source": "file",
            "value": file.removeprefix("file://"),
        }
    if file.startswith("base64://"):
        return {
            "type": "image",
            "source": "base64",
            "value": file.removeprefix("base64://"),
        }
    if file:
        return {"type": "image", "source": "raw", "value": file}
    return None


def _normalize_segment(raw: dict[Any, Any]) -> AnswerSegment | None:
    seg_type = str(raw.get("type", ""))
    if seg_type == "text":
        text = str(raw.get("text", ""))
        return {"type": "text", "text": text} if text else None
    if seg_type == "image":
        value = str(raw.get("value", ""))
        if not value:
            return None
        return {
            "type": "image",
            "source": str(raw.get("source", "raw")),
            "value": value,
        }
    return None
