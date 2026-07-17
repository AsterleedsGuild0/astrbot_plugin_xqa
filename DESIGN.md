# AstrBot XQA 插件设计说明

## 文档定位

- 本文面向插件维护者，记录 `astrbot_plugin_xqa` 的实现方式与技术边界，即 HOW。
- [`PRD.md`](PRD.md) 说明产品为什么存在以及范围，即 WHY / SCOPE。
- [`FSD.md`](FSD.md) 说明用户和平台可观察到的功能行为。
- [`README.md`](README.md) 是安装、配置和使用指南。
- 本文以 `v1.0.1` 稳定基线及其当前实现为准，不用设计描述反向扩大 PRD 或 FSD 的承诺范围。
- 配置字段、类型和默认值的权威入口是 [`_conf_schema.json`](_conf_schema.json)。

---

## 模块职责与依赖

- `main.py`：AstrBot 插件入口，负责生命周期、事件路由、管理命令、权限、业务限额、冷却和回复发送。
- `core/store.py`：负责内存数据树、JSON 读写、作用域选择、问题增删查和匹配。
- `core/models.py`：定义 `QuestionEntry`、`MatchResult`，并把读取到的回答数据转换为当前内存表示。
- `core/message_codec.py`：负责 AstrBot 消息组件与 `AnswerChain` 之间的解析、归一化、图片序列化、回复视频持久化和发送组件构造。
- `core/text.py`：负责命令正则、随机文本候选拆分、捕获组回流和保守的正则安全判断。

内部依赖保持单向：

```text
main -> store / message_codec / text
store -> models / message_codec / text
models -> message_codec
message_codec -> text
```

这是一组按职责拆分的插件模块，不包装成 DDD、Repository 或其他未实际采用的架构模式。

---

## 生命周期与事件入口

- `XQAPlugin.__init__` 获取插件数据目录，读取当时的 `storage_filename`，构造 `XQAStore`，并创建仅存在于当前进程的 `_cooldowns` 字典。
- `initialize()` 调用 `store.load()`；数据文件不存在时会先写入空数据文件。
- 帮助通过 `@filter.command("问答帮助", alias={"XQA帮助", "xqa帮助"})` 进入独立 command handler。
- 其余群聊处理通过 `@filter.event_message_type(GROUP_MESSAGE)` 进入 GROUP_MESSAGE handler。
- 插件保留双入口：command handler 专门提供 AstrBot 帮助命令发布面；GROUP_MESSAGE handler 负责管理消息和自动匹配的主流程。
- 当前没有额外的关闭钩子、后台任务或定时维护流程。

---

## 群消息路由与停止传播

GROUP_MESSAGE handler 先清理文本并确认 `group_id`、`user_id`，然后按以下顺序执行：

1. 调用 `_handle_management_message()`，管理命令优先。
2. 管理分支未处理时，调用 `_match_reply()`，自动匹配后置。
3. 只有管理消息得到真实处理结果，或自动问答真实命中时，才调用 `event.stop_event()`。

管理分支使用三态返回值：

- `str` 或 `AnswerChain`：消息已被管理流程处理；停止事件并发送文本或回答链。
- `None`：当前管理流程未处理；允许继续尝试自动匹配。
- `_SILENT_SKIP`：有意静默跳过并立即返回，不调用 `stop_event()`，因此不阻断其他插件。

群级总开关命令未明确 At 当前 Bot 时使用 `_SILENT_SKIP`。禁用群中的普通未 At 消息通常返回 `None`，随后自动匹配也因群禁用而不命中，同样不会停止事件。权限提示关闭时可能返回空字符串；这仍表示管理命令已完成权限判定，不代表授权成功。

---

## 状态模型

持久化 JSON 的核心形状是：

```text
config[group_id].group_enabled
config[group_id].self_enabled
groups[group_id].all[question]
groups[group_id].users[user_id][question]
```

- `groups[group_id].all` 是本群公共问答。
- `groups[group_id].users[user_id]` 是用户在本群的个人问答。
- 没有公共问答独立开关；`self_enabled` 只控制个人问答。`group_enabled` 禁用后停止自动问答和原管理操作，但明确 At 当前 Bot 的定向帮助、禁用提示与恢复命令仍可用。
- 缺少显式开关字段时，由调用方传入 `_conf_schema.json` 对应默认值。
- 冷却状态不写入 JSON，只保存在插件实例的 `_cooldowns: dict[group_id, timestamp]` 中，并且仅按 `group_id` 共享个人和公共命中冷却。
- 状态键不包含 Bot ID、平台 ID 或 AstrBot 实例 ID。

---

## 问答模型与匹配

- `AnswerChain` 是消息段字典组成的列表，当前段类型包括 `text`、`image` 和 `video`。
- `QuestionEntry` 保存 `answers: list[AnswerChain]` 与 `updated_at`；覆盖同名问题会写入新的时间戳。
- 文本-only 回答在写入前按未转义的 `#` 拆成多个 `AnswerChain` 候选；复合媒体回答保持为单个候选。
- `QuestionEntry.from_raw()` 只接受问题映射中可解析的条目对象或回答列表；裸字符串问题条目会得到空回答，不属于兼容形状。
- 对可解析条目中的回答值，`normalize_answer_chain()` 接受字符串、当前消息段列表和字符串列表等源码明确支持的形态并做有限归一化；这不是任意旧格式兼容承诺。
- 单个作用域内先遍历完全匹配，再遍历正则匹配；两轮候选都按 `updated_at` 从新到旧排列。
- 正则使用整条消息锚定匹配；非法正则在运行时跳过。
- 命中条目后通过 `random.choice()` 从其回答候选中选择一个，正则命中再对文本段执行 `$1`、`$2` 等捕获组替换。
- `main.py` 先匹配当前用户个人作用域，未命中后再匹配本群公共作用域。

---

## JSON 持久化边界

- `load()` 读取整份 JSON，并补齐顶层 `config`、`groups`；群、作用域和问答条目的进一步归一化在访问时完成。
- `save()` 将完整内存数据写到同目录的 `.tmp` 文件，再通过 `os.replace()` 替换目标文件，避免直接覆盖过程中留下半份 JSON。
- 该实现没有 schema version、显式迁移器、进程内或跨进程写锁、`fsync`、自动备份和并发写保护。
- 因此只能描述为“全量临时文件写入后原子替换目标路径”，不能称为完整事务写入；并发插件实例或外部写入者可能互相覆盖。
- JSON 读取失败时当前运行使用空数据并记录错误，不会自动修复、迁移或恢复原文件。
- `storage_filename` 在 `XQAPlugin.__init__` 构造 `XQAStore` 时绑定到 `store.path`；运行中修改配置不会让既有实例自动切换文件，需要重新初始化插件。
- `storage_filename` 是管理员配置的存储路径组成部分，未复用本地媒体发送时的 `source=file` 路径限制，不应与媒体路径安全边界混为一谈。

---

## 图片与回复视频管线

图片设置管线：

- 解析 `你答` 之后的 `Plain` 与 `Image` 组件，保持段顺序形成 `AnswerChain`。
- 配置允许时优先调用图片组件转换为 base64；失败后按 URL、`file://`、`base64://` 或 raw 引用降级保存。
- 图片数量、文本长度、功能开关等业务校验在回答链形成后由 `main.py` 执行。

回复视频设置管线：

- 仅当 `你答` 后没有有效文本或图片回答时，才检查 `Reply` 中的 `Video` 或受支持后缀的 `File`。
- 视频组件先转换或下载为本地文件，再检查单文件大小并计算 SHA256。
- 目标文件名为“SHA256 + 最终后缀”，最终后缀依次取来源文件后缀、文件组件后缀提示或 `.mp4`；只有 SHA256 与最终后缀形成的目标文件名相同时才直接复用，不重复计入新增容量。
- 新文件写入前检查视频目录普通文件总量，最终使用 `shutil.copy2()` 保存。
- 删除或覆盖问答不会删除视频文件；当前没有未引用媒体自动 GC、引用计数或定时清理。
- `parse_set_command_from_event()` 在 `_set_question()` 的角色权限、问答数量、视频功能开关和部分业务限额检查之前执行，因此视频可能在后续权限或业务校验拒绝该设置之前已经落盘。

---

## 媒体发送与路径边界

- 构造图片发送组件时，`source=base64` 使用 `Image.fromBase64()`，`source=url` 使用 `Image.fromURL()`。
- 图片或视频的 `source=file` 会先进入 `_resolve_file_value()`：解析后的路径必须位于插件 `data_dir` 内且是现存普通文件，再使用对应的本地文件组件。
- 视频的 `source=url` 使用 `Video.fromURL()`；图片或视频的其他 source（包括 raw）直接作为组件 `file` 值交给框架。
- 因而不能宣称所有媒体来源都经过同一套本地路径安全检查；当前路径限制只覆盖发送本地媒体的 `source=file` 分支。
- `storage_filename` 控制 JSON 数据文件位置，属于受信管理员配置边界，也不经过 `_resolve_file_value()`。

---

## 权限与 At 当前 Bot

完整角色能力和用户可见拒绝行为见 [`FSD.md`](FSD.md#用户角色与权限行为)。实现侧关键来源与例外如下：

- 插件管理员由 AstrBot `event.is_admin()` 与配置 `admin_users` 共同判定。
- QQ 群角色来自平台 `get_group()` 返回的群主和管理员列表；平台能力缺失或查询失败时不授予该角色权限。
- 群管理员能力由对应 `allow_group_admin_*` 配置分别控制；删除本群公共问答是当前不受这些开关控制的关键例外。
- `permission_denied_notice` 只控制是否返回拒绝文本，不改变授权结果。
- At 当前 Bot 的识别检查消息组件中的 `At.qq` 是否等于当前事件 `self_id`。
- At 约束只隔离群总开关命令的消息目标和处理路由，以及禁用群中的定向帮助、禁用提示与恢复入口；At 路由隔离不等于数据或状态隔离。
- 同一数据目录和 `storage_filename` 被多个 Bot 或实例共享时，当前设计不提供 Bot、platform 或 AstrBot 实例维度的数据隔离、写入协调或独立命名空间。

---

## 配置入口与初始化绑定

- [`_conf_schema.json`](_conf_schema.json) 是配置字段、类型、默认值和界面提示的权威入口。
- `main.py` 通过 `config.get()` 在处理时读取大多数开关和限额。
- `storage_filename` 是例外：它只在插件实例初始化、构造 `XQAStore` 时读取并绑定路径。
- 设计文档、README、PRD 和 FSD 可解释配置效果，但不应复制出另一套默认值权威来源。

---

## 已知限制

- 仅处理群聊问答，依赖平台提供群 ID、发送者 ID、At、Reply、群角色和媒体组件能力。
- 数据模型没有 schema version 和迁移框架，只对代码中明确处理的回答形态做归一化。
- 全量 JSON 写入没有锁和并发冲突检测，不适合多个写入实例共享同一数据文件。
- 冷却为进程内状态，重启后清空，也不跨实例同步。
- 没有公共问答独立开关；At 消息目标与路由隔离不构成 Bot / platform 数据或状态隔离。
- `source=file` 的插件数据目录沙箱不覆盖 URL、raw 和配置的 `storage_filename`，不能外推为所有媒体来源安全。
- 媒体持久化与业务校验不是统一提交过程；视频可能在权限、开关、问答数量等校验前落盘，后续被拒绝时留下未引用文件。
- 删除或覆盖问答不回收媒体，没有自动 GC、备份恢复和存储整理工具。

---

## 实现范围外能力

产品级非目标和未实现功能以 [`PRD.md`](PRD.md#非目标) 与 [`FSD.md`](FSD.md#未实现与-out-of-scope) 为准。本文只保留直接影响实现判断的技术边界：

- 不提供多写入者事务、分布式锁、自动备份、崩溃恢复或媒体自动 GC。
- 不提供通用数据迁移器、任意旧格式兼容或跨实例写入协调。
- 不对 URL、raw 平台引用或管理员配置路径提供与 `source=file` 相同的插件数据目录沙箱。

---

## 扩展原则与文档生命周期

- 新行为先在 Issue 中明确 WHY、SCOPE、可观察行为和兼容策略，再决定是否更新 PRD 或新增 FSD。
- 修改模块依赖时保持入口层到基础模块的单向关系，避免 `core` 反向依赖 `main.py`。
- 修改数据形状前应先设计 schema version、迁移失败策略和回滚边界，不能继续依赖隐式猜测实现无限兼容。
- 引入并发写入、媒体回收或多 Bot 隔离时，应分别明确锁粒度、引用归属和命名空间，不以 At 路由替代数据隔离。
- `_conf_schema.json` 变化需同步用户文档；可观察行为变化需同步 FSD；实现边界或模块职责变化需同步本文；版本变化需写入 CHANGELOG。
- `v1.0.0` 稳定基线冻结后，本文只记录已实现设计和已确认限制，不把候选方案写成现有能力。

---

## 测试索引

- 命令与处理入口：[`tests/test_command_surface.py`](tests/test_command_surface.py)、[`tests/test_processing_feedback.py`](tests/test_processing_feedback.py)
- 群总开关、At 路由与 silent skip：[`tests/test_group_plugin_toggle.py`](tests/test_group_plugin_toggle.py)、[`tests/test_bot_mention_routing.py`](tests/test_bot_mention_routing.py)
- 个人与公共权限：[`tests/test_self_question_permissions.py`](tests/test_self_question_permissions.py)、[`tests/test_public_question_permissions.py`](tests/test_public_question_permissions.py)
- 文本拆分、捕获组和正则辅助：[`tests/test_text.py`](tests/test_text.py)
- 本地媒体发送边界：[`tests/test_message_codec_file_security.py`](tests/test_message_codec_file_security.py)
- 视频存储容量与复用：[`tests/test_video_storage_limit.py`](tests/test_video_storage_limit.py)
- 打包文档完整性：[`tests/test_package_plugin.py`](tests/test_package_plugin.py)
- Changelog 工具：[`tests/test_generate_changelog.py`](tests/test_generate_changelog.py)

测试索引只指向行为证据和回归入口，不在设计文档中复制测试代码。
