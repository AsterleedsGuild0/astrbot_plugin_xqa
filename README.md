# astrbot_plugin_xqa

一个面向 AstrBot 的 XQA 风格群聊问答插件。群成员可以用自然语言设置个人问答，管理员可以设置本群公共问答；后续消息命中问题时，Bot 自动回复保存的答案。

```text
我问A你答B
有人问A你答B
```

当前版本：`v1.0.0`。

---

## 安装

软件要求：

- AstrBot `>= 4.11.2`
- Python 跟随 AstrBot 运行环境
- 无额外第三方依赖

当前插件尚未发布到 AstrBot 插件市场。可将仓库放入 AstrBot 插件目录，或在 AstrBot WebUI 的插件管理页面上传插件 zip。运行数据会写入 AstrBot 插件数据目录，请勿将运行时数据提交到源码仓库。

安装后，新群默认关闭 XQA。请先由管理员在群内明确 @ 当前 Bot 并发送 `@Bot XQA启用本群`，再设置或触发问答；其中 `@Bot` 表示平台消息中对当前 AstrBot 实例的真实 At，而不是手工输入的普通文本。

---

## 核心特性

- 个人问答：`我问A你答B`，仅设置者本人可触发。
- 公共问答：`有人问A你答B`，本群成员均可触发。
- 完全匹配优先，正则表达式匹配作为后备。
- 回答支持 `$1`、`$2` 等正则捕获组回流。
- 纯文本回答支持用 `#` 分隔随机候选，用 `\#` 表示普通井号。
- 支持图片回答及文本与图片复合回答。
- 支持通过回复视频消息或视频文件设置 video-only 回答。
- 支持查看、搜索、删除问答，以及群级总开关和个人问答开关。
- 问答和群开关持久化保存，插件重启后继续生效。

---

## 使用示例

### 个人问答

```text
我问菜单你答今天吃黄焖鸡
```

同一用户在同一群发送 `菜单` 后，Bot 回复 `今天吃黄焖鸡`；其他用户不会触发这条个人问答。

### 公共问答

```text
有人问群规你答禁止刷屏，禁止攻击他人
```

设置成功后，本群任意成员发送 `群规` 均可触发。设置公共问答需要相应管理权限。

### 正则、回流与随机回答

```text
我问你好(.*)你答你也好$1
有人问吃什么你答火锅#烧烤#黄焖鸡
我问井号你答A\#B
```

- 发送 `你好呀` 可得到 `你也好呀`。
- 多次触发 `吃什么` 时，会随机返回一个候选答案。
- 触发 `井号` 时回复 `A#B`。

### 图片回答

在 `你答` 后直接附带图片，可保存纯图片或文本与图片复合回答：

```text
有人问攻略你答先看这张图：[图片]
```

插件会按配置尽量持久化图片。保存较慢时，可能先发送 QQ 表情回应或处理提示。

### 视频回答

先发送视频消息，或以文件形式发送 `.mp4`、`.mov`、`.m4v`、`.webm`，再回复该消息：

```text
有人问意志图鉴你答
```

也可使用 `我问意志图鉴你答` 设置个人视频回答。视频回答当前仅支持 video-only，不支持文字与视频混合。

---

## 命令表

| 命令 | 说明 |
| --- | --- |
| `我问A你答B` | 设置或覆盖自己的个人问答 |
| `有人问A你答B` | 设置或覆盖本群公共问答 |
| `看看我问` / `看看我问X` | 查看或搜索自己的个人问题 |
| `看看有人问` / `看看有人问X` | 查看或搜索本群公共问题 |
| `不要回答A` | 优先删除自己的个人问答；管理员可据此删除公共问答 |
| `@用户 不要回答A` | 插件管理员删除指定成员的个人问答；实际识别依赖平台提供用户 ID |
| `@Bot XQA禁用本群` / `@Bot XQA启用本群` | 明确 @ 当前 Bot 后切换本群总开关；禁用时仍保留定向帮助、禁用提示和恢复命令 |
| `XQA禁用我问` / `XQA启用我问` | 禁用或启用本群个人问答 |
| `问答帮助` / `XQA帮助` | 查看插件帮助 |

---

## 群开关与多 Bot 场景

- 群级总开关只接受明确 @ 当前 Bot 的 `@Bot XQA启用本群` 和 `@Bot XQA禁用本群`。
- 不带 At、At 其他用户或 Bot、At 全体成员时，当前 Bot 对上述群开关命令保持静默且不执行本次写操作。
- 本群 XQA 禁用后，未 @ 当前 Bot 的普通消息及 XQA 管理命令均静默处理。
- 禁用期间明确 @ 当前 Bot 时，启用命令可恢复本群 XQA；其他受支持的管理命令可返回禁用提示，`@Bot XQA帮助` 可显示帮助和恢复说明。
- 本群启用后，设置、查看、删除及个人问答开关等其他命令无需 @ 当前 Bot，自动问答行为也保持不变。
- 同一群存在多个 Bot 时，应 @ 需要操作的具体 Bot；At 约束只隔离本次群级总开关命令的消息目标和处理路由，非目标 Bot 不回复、也不执行本次写操作。
- 插件不提供 Bot、platform 或 AstrBot 实例维度的数据与状态隔离；多个 Bot 或实例共享同一插件数据目录和 `storage_filename` 时，会读写同一份问答与群开关状态。

---

## 管理权限

- 普通成员可管理自己的个人问答，并可查看本群公共问题。
- QQ 群主、群管理员是否可设置公共问答和操作群级开关，由相应配置控制；当前可删除本群公共问答。
- AstrBot 管理员和 `admin_users` 中的插件管理员可管理公共问答、删除指定成员问答并操作群级开关。
- `permission_denied_notice` 关闭后，部分权限不足场景会静默处理。

---

## 配置摘要

插件配置通过 AstrBot 插件配置界面管理。默认值及字段定义以 [`_conf_schema.json`](_conf_schema.json) 为准。

| 功能组 | 主要配置 | 用途 |
| --- | --- | --- |
| 群开关 | `group_plugin_enabled_default`、`self_question_enabled_default` | 新群 XQA 默认关闭；启用本群后，个人问答默认开启 |
| 权限 | `admin_users`、`allow_group_admin_*`、`permission_denied_notice` | 配置管理员来源、群管理员能力和拒绝提示 |
| 匹配 | `enable_regex_question`、`reject_empty_regex`、`reject_dangerous_regex`、`cooldown_seconds` | 控制正则、安全拦截和同群回复冷却 |
| 媒体 | `enable_image_message`、`enable_video_message`、`persist_image_as_base64`、`enable_processing_feedback` | 控制图片、视频及保存反馈 |
| 限额 | `max_question_length`、`max_answer_length`、`max_answers_per_question`、`max_*_questions_*` | 限制内容长度、随机候选和问答数量 |
| 视频限额 | `max_videos_per_answer`、`max_video_size_mb`、`max_video_storage_mb`、`video_download_timeout_seconds` | 限制视频数量、大小、总量和处理时间 |
| 展示与存储 | `list_page_size`、`storage_filename` | 控制列表显示数量和数据文件名 |

当前 `group_plugin_enabled_default=false`、`self_question_enabled_default=true`。已有显式群开关状态继续按保存的状态执行。

---

## 当前限制

- 仅处理群聊；不支持私聊问答。
- 不支持图片或视频作为问题。
- 不支持语音作为问题或回答。
- 视频回答仅支持 video-only。
- 不支持全群问答、跨群复制、批量清空、数据导入导出或 WebUI / Pages 管理。
- 视频文件受单文件大小和视频目录总量限制；删除问答不会自动清理已保存的视频文件。
- 正则使用安全规则进行保守拦截，但仍不建议在同一群同时启用多个自动问答 Bot。

---

## 开发验证与发布

可运行最小开发验证：

```bash
python -m unittest discover -s tests -v
```

版本变化见 [`CHANGELOG.md`](CHANGELOG.md)；维护者可通过 [`DESIGN.md`](DESIGN.md) 了解实现结构与技术边界；发布自动化见 [GitHub Actions](https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/blob/main/.github/workflows/release.yml)。

---

## 相关文档

- [产品基线 PRD](PRD.md)
- [MVP 功能行为规格 FSD](FSD.md)
- [实现设计与技术边界 DESIGN](DESIGN.md)
- [版本变化 CHANGELOG](CHANGELOG.md)
- [配置权威定义](./_conf_schema.json)

---

## 许可证

本仓库使用 GNU General Public License v3.0，详见 [`LICENSE`](LICENSE)。

---

## 致谢

本项目是 AstrBot 插件实现，产品思路、自然语言问答交互与部分行为设计参考了：

- [`azmiao/YuiChyanBot`](https://github.com/azmiao/YuiChyanBot)
- XQA 模块及其 `我问A你答B`、`有人问A你答B` 交互设计

插件 logo 使用来自参考项目的 `yuiChyan.jpg`，并以 AstrBot 常用的 `logo.png` 文件名随插件发布。感谢原项目作者 [AZMIAO](https://github.com/azmiao) 的工作。
