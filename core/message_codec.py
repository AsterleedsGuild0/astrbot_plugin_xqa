from __future__ import annotations

import asyncio
import hashlib
import re
import shutil
from pathlib import Path
from typing import Any, TypeAlias
from urllib.parse import urlparse

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import File, Image, Plain, Reply, Video

from .text import split_answers

AnswerSegment: TypeAlias = dict[str, str]
AnswerChain: TypeAlias = list[AnswerSegment]

VIDEO_FILE_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm"}


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
        elif seg.get("type") == "video":
            parts.append("[视频]")
    return "".join(parts)


def chain_text_length(chain: AnswerChain) -> int:
    return sum(len(seg.get("text", "")) for seg in chain if seg.get("type") == "text")


def chain_image_count(chain: AnswerChain) -> int:
    return sum(1 for seg in chain if seg.get("type") == "image")


def chain_video_count(chain: AnswerChain) -> int:
    return sum(1 for seg in chain if seg.get("type") == "video")


def has_answer_content(chain: AnswerChain) -> bool:
    for seg in chain:
        if seg.get("type") == "image":
            return True
        if seg.get("type") == "video":
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
    event: AstrMessageEvent,
    *,
    persist_image_as_base64: bool = True,
    video_dir: str | Path | None = None,
    max_video_size_mb: int = 50,
    max_video_storage_mb: int = 1024,
    video_download_timeout_seconds: int = 30,
) -> tuple[str, str, AnswerChain] | None:
    before_text, answer_chain = await _split_set_command_components(
        event, persist_image_as_base64=persist_image_as_base64
    )
    if before_text is None:
        return None
    matched = re.match(r"^(全群|有人|我)问([\s\S]*)$", before_text)
    if not matched:
        return None
    if not has_answer_content(answer_chain):
        video_chain = await _extract_replied_video_answer(
            event,
            video_dir=video_dir,
            max_video_size_mb=max_video_size_mb,
            max_video_storage_mb=max_video_storage_mb,
            timeout_seconds=video_download_timeout_seconds,
        )
        if video_chain:
            answer_chain = video_chain
    return matched.group(1), matched.group(2), answer_chain


def build_components(
    chain: AnswerChain, *, data_dir: str | Path | None = None
) -> list[Any]:
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
                path = _resolve_file_value(value, data_dir)
                if path is None:
                    logger.warning(f"[XQA] 跳过不安全或不存在的本地图片: {value}")
                    continue
                components.append(Image.fromFileSystem(path))
            else:
                components.append(Image(file=value))
        elif seg.get("type") == "video":
            source = seg.get("source", "")
            value = seg.get("value", "")
            if not value:
                continue
            if source == "url":
                components.append(Video.fromURL(value))
            elif source == "file":
                path = _resolve_file_value(value, data_dir)
                if path is None:
                    logger.warning(f"[XQA] 跳过不安全或不存在的本地视频: {value}")
                    continue
                components.append(Video.fromFileSystem(path))
            else:
                components.append(Video(file=value))
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


def has_replied_video_answer(event: AstrMessageEvent) -> bool:
    for comp in event.get_messages():
        if isinstance(comp, Reply):
            return any(
                isinstance(item, Video)
                or (isinstance(item, File) and _is_video_file_component(item))
                for item in (comp.chain or [])
            )
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
    if seg_type == "video":
        value = str(raw.get("value", ""))
        if not value:
            return None
        return {
            "type": "video",
            "source": str(raw.get("source", "file")),
            "value": value,
        }
    return None


async def _extract_replied_video_answer(
    event: AstrMessageEvent,
    *,
    video_dir: str | Path | None,
    max_video_size_mb: int,
    max_video_storage_mb: int,
    timeout_seconds: int,
) -> AnswerChain:
    if video_dir is None:
        return []
    for comp in event.get_messages():
        if not isinstance(comp, Reply):
            continue
        for item in comp.chain or []:
            if isinstance(item, Video):
                segment = await _persist_video(
                    item,
                    video_dir=Path(video_dir),
                    max_video_size_mb=max_video_size_mb,
                    max_video_storage_mb=max_video_storage_mb,
                    timeout_seconds=timeout_seconds,
                )
                return [segment] if segment else []
            if isinstance(item, File) and _is_video_file_component(item):
                segment = await _persist_video_file(
                    item,
                    video_dir=Path(video_dir),
                    max_video_size_mb=max_video_size_mb,
                    max_video_storage_mb=max_video_storage_mb,
                    timeout_seconds=timeout_seconds,
                )
                return [segment] if segment else []
    return []


async def _persist_video(
    video: Video,
    *,
    video_dir: Path,
    max_video_size_mb: int,
    max_video_storage_mb: int,
    timeout_seconds: int,
) -> AnswerSegment | None:
    video_dir.mkdir(parents=True, exist_ok=True)
    try:
        source_path = await asyncio.wait_for(
            video.convert_to_file_path(), timeout=max(1, timeout_seconds)
        )
    except TimeoutError as exc:
        raise ValueError("视频下载/转换超时，请稍后重试。") from exc
    except Exception as exc:
        raise ValueError(f"视频保存失败：{type(exc).__name__}") from exc

    return _persist_video_path(
        Path(source_path),
        video_dir=video_dir,
        max_video_size_mb=max_video_size_mb,
        max_video_storage_mb=max_video_storage_mb,
    )


async def _persist_video_file(
    file: File,
    *,
    video_dir: Path,
    max_video_size_mb: int,
    max_video_storage_mb: int,
    timeout_seconds: int,
) -> AnswerSegment | None:
    try:
        source_path = await asyncio.wait_for(
            file.get_file(), timeout=max(1, timeout_seconds)
        )
    except TimeoutError as exc:
        raise ValueError("视频文件下载超时，请稍后重试。") from exc
    except Exception as exc:
        raise ValueError(f"视频文件保存失败：{type(exc).__name__}") from exc

    source = Path(source_path) if source_path else Path()
    suffix_hint = _video_file_suffix(file)
    return _persist_video_path(
        source,
        video_dir=video_dir,
        max_video_size_mb=max_video_size_mb,
        max_video_storage_mb=max_video_storage_mb,
        suffix_hint=suffix_hint,
    )


def _persist_video_path(
    source: Path,
    *,
    video_dir: Path,
    max_video_size_mb: int,
    max_video_storage_mb: int = 1024,
    suffix_hint: str = "",
) -> AnswerSegment | None:
    video_dir.mkdir(parents=True, exist_ok=True)
    if not source.is_file():
        raise ValueError("视频保存失败：未找到视频文件。")

    max_bytes = max_video_size_mb * 1024 * 1024
    file_size = source.stat().st_size
    if max_bytes > 0 and file_size > max_bytes:
        raise ValueError(f"视频过大，当前上限为 {max_video_size_mb} MB。")

    digest = _file_sha256(source)
    suffix = source.suffix or suffix_hint or ".mp4"
    target = video_dir / f"{digest}{suffix}"
    if target.exists():
        return {
            "type": "video",
            "source": "file",
            "value": str(Path("videos") / target.name),
        }

    storage_limit_bytes = max_video_storage_mb * 1024 * 1024
    if storage_limit_bytes > 0:
        current_size = _video_storage_size(video_dir)
        if current_size + file_size > storage_limit_bytes:
            raise ValueError(
                "视频存储空间已达到上限"
                f"（{max_video_storage_mb} MB），请清理旧视频或调整配置。"
            )

    shutil.copy2(source, target)
    logger.info(f"[XQA] 视频回答已保存 path={target} size={file_size}")
    return {
        "type": "video",
        "source": "file",
        "value": str(Path("videos") / target.name),
    }


def _video_storage_size(video_dir: Path) -> int:
    total_size = 0
    for entry in video_dir.iterdir():
        try:
            if entry.is_symlink() or not entry.is_file():
                continue
            total_size += entry.stat().st_size
        except OSError as exc:
            logger.warning(
                "[XQA] 统计视频存储空间时跳过不可访问文件 "
                f"path={entry} error={type(exc).__name__}: {exc}"
            )
    return total_size


def _is_video_file_component(file: File) -> bool:
    return _video_file_suffix(file) in VIDEO_FILE_SUFFIXES


def _video_file_suffix(file: File) -> str:
    for value in (
        getattr(file, "name", ""),
        getattr(file, "file_", ""),
        getattr(file, "url", ""),
    ):
        suffix = _suffix_from_value(str(value or ""))
        if suffix:
            return suffix
    return ""


def _suffix_from_value(value: str) -> str:
    if not value:
        return ""
    parsed_path = urlparse(value).path if "://" in value else value
    return Path(parsed_path).suffix.lower()


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _resolve_file_value(value: str, data_dir: str | Path | None) -> str | None:
    if data_dir is None:
        return None
    try:
        root = Path(data_dir).resolve()
        path = Path(value)
        resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
        resolved.relative_to(root)
        return str(resolved) if resolved.is_file() else None
    except (OSError, RuntimeError, ValueError):
        return None
