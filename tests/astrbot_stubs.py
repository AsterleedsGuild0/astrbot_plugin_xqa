from __future__ import annotations

import sys
import types
from unittest.mock import Mock


class _Component:
    def __init__(self, value: str = "", *, kind: str = "raw") -> None:
        self.value = value
        self.kind = kind
        self.file = value


class Plain(_Component):
    def __init__(self, text: str) -> None:
        super().__init__(text, kind="text")
        self.text = text


class Image(_Component):
    @classmethod
    def fromBase64(cls, value: str):
        return cls(value, kind="base64")

    @classmethod
    def fromURL(cls, value: str):
        return cls(value, kind="url")

    @classmethod
    def fromFileSystem(cls, value: str):
        return cls(value, kind="file")


class Video(_Component):
    @classmethod
    def fromURL(cls, value: str):
        return cls(value, kind="url")

    @classmethod
    def fromFileSystem(cls, value: str):
        return cls(value, kind="file")


class File(_Component):
    pass


class Reply(_Component):
    def __init__(self, chain=None) -> None:
        super().__init__()
        self.chain = chain


class At(_Component):
    def __init__(self, qq: str | int) -> None:
        super().__init__(str(qq), kind="at")
        self.qq = qq


def install_astrbot_stubs() -> Mock:
    def decorator(*args, **kwargs):
        del args, kwargs
        return lambda function: function

    logger = Mock()
    astrbot = types.ModuleType("astrbot")
    astrbot.__path__ = []
    api = types.ModuleType("astrbot.api")
    api.__path__ = []
    setattr(api, "AstrBotConfig", dict)
    setattr(api, "logger", logger)

    event = types.ModuleType("astrbot.api.event")
    setattr(event, "AstrMessageEvent", type("AstrMessageEvent", (), {}))
    setattr(event, "MessageChain", type("MessageChain", (), {}))
    setattr(
        event,
        "filter",
        types.SimpleNamespace(
            command=decorator,
            event_message_type=decorator,
            EventMessageType=types.SimpleNamespace(GROUP_MESSAGE=object()),
        ),
    )

    star = types.ModuleType("astrbot.api.star")
    setattr(star, "Context", type("Context", (), {}))
    setattr(star, "Star", type("Star", (), {}))
    setattr(star, "StarTools", type("StarTools", (), {}))

    components = types.ModuleType("astrbot.api.message_components")
    for component in (At, File, Image, Plain, Reply, Video):
        setattr(components, component.__name__, component)

    sys.modules.update(
        {
            "astrbot": astrbot,
            "astrbot.api": api,
            "astrbot.api.event": event,
            "astrbot.api.star": star,
            "astrbot.api.message_components": components,
        }
    )
    return logger


LOGGER = install_astrbot_stubs()
