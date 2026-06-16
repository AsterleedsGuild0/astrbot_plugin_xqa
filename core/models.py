from __future__ import annotations

from dataclasses import dataclass, field
from time import time


@dataclass
class QuestionEntry:
    answers: list[str]
    updated_at: float = field(default_factory=time)

    @classmethod
    def from_raw(cls, raw: object) -> "QuestionEntry":
        if isinstance(raw, dict):
            answers = raw.get("answers", [])
            updated_at = raw.get("updated_at")
            return cls(
                answers=[str(item) for item in answers if str(item)],
                updated_at=float(updated_at) if updated_at else time(),
            )
        if isinstance(raw, list):
            return cls(answers=[str(item) for item in raw if str(item)])
        return cls(answers=[])

    def to_raw(self) -> dict[str, object]:
        return {"answers": self.answers, "updated_at": self.updated_at}


@dataclass
class MatchResult:
    question: str
    answer: str
    scope: str
