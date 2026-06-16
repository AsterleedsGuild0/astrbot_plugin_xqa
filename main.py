from __future__ import annotations

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools

from .core.store import XQAStore
from .core.text import (
    DELETE_PATTERN,
    QUESTION_PATTERN,
    SHOW_PATTERN,
    is_empty_or_broad_regex,
    looks_dangerous_regex,
    split_answers,
)


class XQAPlugin(Star):
    """XQA-style natural language Q&A plugin for AstrBot."""

    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.context = context
        self.config = config
        self.store = XQAStore(
            StarTools.get_data_dir("astrbot_plugin_xqa"),
            filename=str(config.get("storage_filename", "xqa_data.json")),
        )
        self._cooldowns: dict[str, float] = {}

    async def initialize(self) -> None:
        await self.store.load()
        logger.info("[XQA] 插件初始化完成")

    @filter.command("问答帮助", alias={"XQA帮助", "xqa帮助"})
    async def xqa_help(self, event: AstrMessageEvent):
        yield event.plain_result(self._help_text())

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        message = (event.get_message_str() or "").strip()
        if not message:
            return

        group_id = str(event.get_group_id() or "")
        user_id = str(event.get_sender_id() or "")
        if not group_id or not user_id:
            return

        reply = await self._handle_management_message(event, group_id, user_id, message)
        if reply is not None:
            event.stop_event()
            if reply == "":
                return
            yield event.plain_result(reply)
            return

        reply = await self._match_reply(group_id, user_id, message)
        if reply is not None:
            event.stop_event()
            yield event.plain_result(reply)

    async def _handle_management_message(
        self, event: AstrMessageEvent, group_id: str, user_id: str, message: str
    ) -> str | None:
        if message in {"XQA禁用我问", "XQA启用我问"}:
            return await self._toggle_self_question(
                event, group_id, message.endswith("启用我问")
            )
        if message == "XQA清空本群所有我问" or message == "XQA清空本群所有有人问":
            return "暂未实现清空命令。请先使用“不要回答A”逐条删除。"

        set_match = QUESTION_PATTERN.match(message)
        if set_match:
            question_type, question, answer = set_match.groups()
            return await self._set_question(
                event, group_id, user_id, (question_type, question, answer)
            )

        show_match = SHOW_PATTERN.match(message)
        if show_match:
            question_type, search = show_match.groups()
            return await self._show_questions(
                group_id, user_id, (question_type, search)
            )

        delete_match = DELETE_PATTERN.match(message)
        if delete_match:
            at_user_id, is_global, question = delete_match.groups()
            return await self._delete_question(
                event, group_id, user_id, (at_user_id, is_global, question)
            )

        return None

    async def _set_question(
        self,
        event: AstrMessageEvent,
        group_id: str,
        user_id: str,
        groups: tuple[str, str, str],
    ) -> str:
        question_type, question, raw_answer = groups
        question = question.strip()
        raw_answer = raw_answer.strip()

        if not question or not raw_answer:
            return f"发送“{question_type}问XXX你答XXX”我才记得住~"

        if len(question) > int(self.config.get("max_question_length", 200)):
            return "问题太长了，无法保存。"
        if len(raw_answer) > int(self.config.get("max_answer_length", 1000)):
            return "回答太长了，无法保存。"

        max_answers = int(self.config.get("max_answers_per_question", 20))
        answers = split_answers(raw_answer, max_answers)
        if not answers:
            return "回答内容不能为空。"

        if self.config.get("reject_empty_regex", True) and is_empty_or_broad_regex(
            question
        ):
            return "不可设置空匹配或泛匹配问题。"
        if self.config.get("reject_dangerous_regex", True) and looks_dangerous_regex(
            question
        ):
            return "该问题看起来像危险正则，已拒绝保存。"

        if question_type == "我":
            if not self.store.is_self_enabled(
                group_id, bool(self.config.get("self_question_enabled_default", True))
            ):
                return "本群已禁用个人问答功能。"
            limit = int(self.config.get("max_questions_per_user_per_group", 100))
            if self.store.count_questions(group_id, user_id) >= limit:
                return f"你的个人问答数量已达到上限（{limit}）。"
            await self.store.set_question(group_id, user_id, question, answers)
            return "好的我记住了。"

        if question_type == "有人":
            if not await self._is_plugin_admin(event):
                return self._permission_denied("有人问只能管理员设置。")
            limit = int(self.config.get("max_public_questions_per_group", 300))
            if self.store.count_questions(group_id, None) >= limit:
                return f"本群公共问答数量已达到上限（{limit}）。"
            await self.store.set_question(group_id, None, question, answers)
            return "好的我记住了。"

        if question_type == "全群":
            if not self.config.get("enable_global_question", False):
                return "全群问功能当前未启用。"
            return "暂未实现全群问写入。"

        return "未知问答类型。"

    async def _show_questions(
        self, group_id: str, user_id: str, groups: tuple[str, str]
    ) -> str:
        question_type, search = groups
        search = search.strip()
        if question_type == "我":
            if not self.store.is_self_enabled(
                group_id, bool(self.config.get("self_question_enabled_default", True))
            ):
                return "本群已禁用个人问答功能。"
            questions = self.store.list_questions(group_id, user_id, search)
            title = "你在本群设置的问题"
        elif question_type == "有人":
            questions = self.store.list_questions(group_id, None, search)
            title = "本群公共问题"
        else:
            return "看看全群问暂未实现。"

        if not questions:
            return f"没有找到相关{title}。"
        page_size = int(self.config.get("list_page_size", 30))
        lines = questions[:page_size]
        suffix = (
            ""
            if len(questions) <= page_size
            else f"\n……还有 {len(questions) - page_size} 条未显示"
        )
        header = f"查询“{search}”相关结果：\n" if search else ""
        return f"{header}{title}有：\n" + "\n".join(lines) + suffix

    async def _delete_question(
        self,
        event: AstrMessageEvent,
        group_id: str,
        user_id: str,
        groups: tuple[str | None, str | None, str],
    ) -> str:
        at_user_id, is_global, question = groups
        question = question.strip()
        if not question:
            return "删除问答请带上删除内容。"
        if is_global:
            if not self.config.get("enable_global_question", False):
                return "全群不要回答功能当前未启用。"
            return "暂未实现全群删除。"
        if at_user_id:
            if not await self._is_plugin_admin(event):
                return self._permission_denied("删除他人问答仅限管理员。")
            deleted = await self.store.delete_question(group_id, at_user_id, question)
            return "已删除该成员的问答。" if deleted else "没有找到该成员的这个问答。"

        deleted_self = await self.store.delete_question(group_id, user_id, question)
        if deleted_self:
            return "已删除你的问答。"
        if await self._is_plugin_admin(event):
            deleted_public = await self.store.delete_question(group_id, None, question)
            return "已删除公共问答。" if deleted_public else "没有找到该问题。"
        if question in self.store.list_questions(group_id, None):
            return self._permission_denied("你没有权限删除公共问答。")
        return "没有找到该问题。"

    async def _toggle_self_question(
        self, event: AstrMessageEvent, group_id: str, enabled: bool
    ) -> str:
        allow_admin = bool(
            self.config.get("allow_group_admin_toggle_self_question", False)
        )
        if not allow_admin and not await self._is_plugin_admin(event):
            return self._permission_denied("该命令仅限管理员使用。")
        if allow_admin and not await self._is_plugin_admin(event):
            return self._permission_denied("该命令仅限管理员使用。")
        await self.store.set_self_enabled(group_id, enabled)
        return "本群已启用个人问答功能。" if enabled else "本群已禁用个人问答功能。"

    async def _match_reply(
        self, group_id: str, user_id: str, message: str
    ) -> str | None:
        if self._is_in_cooldown(group_id):
            return None
        enable_regex = bool(self.config.get("enable_regex_question", True))
        if self.store.is_self_enabled(
            group_id, bool(self.config.get("self_question_enabled_default", True))
        ):
            matched = self.store.match(group_id, user_id, message, "self", enable_regex)
            if matched:
                self._mark_cooldown(group_id)
                return matched.answer
        matched = self.store.match(group_id, None, message, "public", enable_regex)
        if matched:
            self._mark_cooldown(group_id)
            return matched.answer
        return None

    def _is_in_cooldown(self, group_id: str) -> bool:
        cooldown = int(self.config.get("cooldown_seconds", 0))
        if cooldown <= 0:
            return False
        import time

        return time.time() - self._cooldowns.get(group_id, 0) < cooldown

    def _mark_cooldown(self, group_id: str) -> None:
        import time

        self._cooldowns[group_id] = time.time()

    async def _is_plugin_admin(self, event: AstrMessageEvent) -> bool:
        if event.is_admin():
            return True
        sender_id = str(event.get_sender_id() or "").strip()
        raw_admins = self.config.get("admin_users", []) or []
        if not isinstance(raw_admins, list):
            return False
        return sender_id in {
            str(item).strip() for item in raw_admins if str(item).strip()
        }

    def _permission_denied(self, text: str) -> str:
        if self.config.get("permission_denied_notice", True):
            return f"权限不足：{text}"
        return ""

    def _help_text(self) -> str:
        return """XQA 问答帮助

设置：
- 我问A你答B：设置个人问答
- 有人问A你答B：管理员设置本群公共问答

查看：
- 看看我问 / 看看我问关键词
- 看看有人问 / 看看有人问关键词

删除：
- 不要回答A：删除自己的问答；管理员可删除公共问答

高级：
- 支持正则问题与 $1、$2 回流
- 支持 # 分隔随机回答，\\# 表示普通井号
""".strip()
