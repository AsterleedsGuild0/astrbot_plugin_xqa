from __future__ import annotations

import json
import os
import random
import re
from collections.abc import Iterable
from pathlib import Path
from time import time
from typing import cast

from astrbot.api import logger

from .models import MatchResult, QuestionEntry
from .text import replace_backrefs


class XQAStore:
    def __init__(self, data_dir: str | Path, filename: str = "xqa_data.json") -> None:
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / filename
        self.data: dict[str, object] = {"config": {}, "groups": {}}

    async def load(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            await self.save()
            return
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            self.data.setdefault("config", {})
            self.data.setdefault("groups", {})
        except Exception as exc:
            logger.error(f"[XQA] 读取数据失败，将使用空数据: {exc}")
            self.data = {"config": {}, "groups": {}}

    async def save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp, self.path)

    def is_self_enabled(self, group_id: str, default: bool = True) -> bool:
        config = self.data.setdefault("config", {})
        assert isinstance(config, dict)
        group_config = config.get(group_id, {})
        if not isinstance(group_config, dict):
            return default
        return bool(group_config.get("self_enabled", default))

    async def set_self_enabled(self, group_id: str, enabled: bool) -> None:
        config = self.data.setdefault("config", {})
        assert isinstance(config, dict)
        group_config = config.get(group_id, {})
        if not isinstance(group_config, dict):
            group_config = {}
        group_config["self_enabled"] = enabled
        config[group_id] = group_config
        await self.save()

    def _group(self, group_id: str) -> dict[str, object]:
        groups = self.data.setdefault("groups", {})
        assert isinstance(groups, dict)
        raw_group = groups.get(group_id)
        if isinstance(raw_group, dict):
            group = cast(dict[str, object], raw_group)
        else:
            group: dict[str, object] = {"all": {}, "users": {}}
            groups[group_id] = group
        group.setdefault("all", {})
        group.setdefault("users", {})
        return group

    def _scope_dict(self, group_id: str, user_id: str | None) -> dict[str, object]:
        group = self._group(group_id)
        if user_id is None:
            public = group.setdefault("all", {})
            assert isinstance(public, dict)
            return cast(dict[str, object], public)
        users = group.setdefault("users", {})
        assert isinstance(users, dict)
        user = users.get(user_id)
        if not isinstance(user, dict):
            user = {}
            users[user_id] = user
        return cast(dict[str, object], user)

    def count_questions(self, group_id: str, user_id: str | None) -> int:
        return len(self._scope_dict(group_id, user_id))

    async def set_question(
        self, group_id: str, user_id: str | None, question: str, answers: list[str]
    ) -> None:
        scope = self._scope_dict(group_id, user_id)
        scope[question] = QuestionEntry(answers=answers, updated_at=time()).to_raw()
        await self.save()

    async def delete_question(
        self, group_id: str, user_id: str | None, question: str
    ) -> bool:
        scope = self._scope_dict(group_id, user_id)
        if question not in scope:
            return False
        scope.pop(question, None)
        await self.save()
        return True

    def list_questions(
        self, group_id: str, user_id: str | None, search: str = ""
    ) -> list[str]:
        scope = self._scope_dict(group_id, user_id)
        entries = [
            (question, QuestionEntry.from_raw(raw).updated_at)
            for question, raw in scope.items()
        ]
        entries.sort(key=lambda item: item[1])
        if search:
            return [question for question, _ in entries if search in question]
        return [question for question, _ in entries]

    def _iter_match_candidates(
        self, group_id: str, user_id: str | None
    ) -> Iterable[tuple[str, QuestionEntry]]:
        scope = self._scope_dict(group_id, user_id)
        entries = [
            (question, QuestionEntry.from_raw(raw)) for question, raw in scope.items()
        ]
        entries.sort(key=lambda item: item[1].updated_at, reverse=True)
        return entries

    def match(
        self,
        group_id: str,
        user_id: str | None,
        message: str,
        scope_name: str,
        enable_regex: bool = True,
    ) -> MatchResult | None:
        candidates = list(self._iter_match_candidates(group_id, user_id))
        for question, entry in candidates:
            if question == message and entry.answers:
                return MatchResult(
                    question=question,
                    answer=random.choice(entry.answers),
                    scope=scope_name,
                )
        if not enable_regex:
            return None
        for question, entry in candidates:
            if not entry.answers:
                continue
            try:
                match = re.match(f"^(?:{question})$", message)
            except re.error:
                continue
            if match:
                answer = replace_backrefs(random.choice(entry.answers), match)
                return MatchResult(question=question, answer=answer, scope=scope_name)
        return None
