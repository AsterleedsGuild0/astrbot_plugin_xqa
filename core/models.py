from __future__ import annotations

from dataclasses import dataclass, field
from time import time

from .message_codec import AnswerChain, normalize_answer_chain


@dataclass
class QuestionEntry:
    answers: list[AnswerChain]
    updated_at: float = field(default_factory=time)

    @classmethod
    def from_raw(cls, raw: object) -> "QuestionEntry":
        if isinstance(raw, dict):
            answers = raw.get("answers", [])
            updated_at = raw.get("updated_at")
            return cls(
                answers=[
                    chain for item in answers if (chain := normalize_answer_chain(item))
                ],
                updated_at=float(updated_at) if updated_at else time(),
            )
        if isinstance(raw, list):
            return cls(
                answers=[
                    chain for item in raw if (chain := normalize_answer_chain(item))
                ]
            )
        return cls(answers=[])

    def to_raw(self) -> dict[str, object]:
        return {"answers": self.answers, "updated_at": self.updated_at}


@dataclass
class MatchResult:
    question: str
    answer: AnswerChain
    scope: str
