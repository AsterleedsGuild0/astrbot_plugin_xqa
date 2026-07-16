# 更新日志

本项目的所有重要变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 文档

- 新增面向维护者的 `DESIGN.md`，记录 v1.0.0 实现结构、数据与媒体边界、已知限制和测试索引，并纳入发布包；同步明确 At 只提供当前 Bot 的消息目标与路由隔离，不提供 Bot / platform 数据或状态隔离（[#5]）。

### 修复

- 修复禁用群帮助缺少明确恢复提示，以及无效媒体样式消息错误触发处理反馈的问题（[#4]）。
- 修正个人问答默认开关的配置说明，并补充自定义存储文件名与无视频目录边界测试（[#6]）。

## [v1.0.0] - 2026-07-16

### 新增

- 补充插件市场短描述、标签和 `aiocqhttp` 支持平台声明。

### 变更

- 出于安全考虑，新群 XQA 默认关闭，需要管理员显式启用。
- 群级启停必须明确 @ 当前 Bot；禁用群中未 @ 当前 Bot 的消息保持静默，并提供帮助恢复入口和多 Bot 消息目标 / 路由隔离行为，不承诺 Bot / platform 数据或状态隔离（[#3]）。

### 修复

- 修复静默跳过消息时错误调用 `stop_event`、可能阻断后续消息处理的安全问题。
- 修正 Changelog 引用链接过滤。
- 补全 Release notes 引用链接。

## [v0.1.3] - 2026-07-16

### 新增

- 收口未实现的全群问答、批量清空命令及 WebUI 配置，只保留真实可用的 MVP 发布面（[#2]）。
- 补充文本处理、公共问答权限与命令发布面测试，单元测试总数提升至 66 项。
- 新增 MVP `FSD.md`、`CHANGELOG.md` 及 Changelog 生成/提取工具，建立文档生命周期边界。

### 修复

- 修复 `generate --write` 发布版本后未清空 `[Unreleased]` 正文的问题。

### 文档

- 精简 README 与 PRD，并同步 `v0.1.3` MVP 功能和配置边界。

## [v0.1.2] - 2026-07-15

### 新增

- 新增群内启用、禁用 XQA 功能，并补充核心逻辑与安全边界的单元测试（[#1]）。

### 修复

- 修复个人问答开关的群管理员权限判断。

### 安全

- 加固本地媒体路径安全校验，并增加视频存储总量限制。

## [v0.1.1] - 2026-06-30

### 新增

- 支持引用 MP4、MOV、M4V、WebM 文件作为视频回答，并提供视频大小、数量与下载超时配置。

### 修复

- 允许群管理员管理公共问答。

### 文档

- 更新 README 使用说明。

## [v0.1.0] - 2026-06-16

### 新增

- 实现文本问答 MVP，支持个人与群公共问答、完全匹配、正则匹配、随机回答、查询、搜索、删除及权限控制。
- 支持图片问答与处理反馈。
- 添加标准插件 Logo。
- 添加 GitHub Release 发布流程。

### 变更

- 添加本地插件打包测试工具与仓库基础文件。

[Unreleased]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/compare/v1.0.0...HEAD
[v1.0.0]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/compare/v0.1.3...v1.0.0
[v0.1.3]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/compare/v0.1.2...v0.1.3
[v0.1.2]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/compare/v0.1.1...v0.1.2
[v0.1.1]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/compare/v0.1.0...v0.1.1
[v0.1.0]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/releases/tag/v0.1.0
[#1]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/issues/1
[#2]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/issues/2
[#3]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/issues/3
[#4]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/issues/4
[#5]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/issues/5
[#6]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/issues/6
