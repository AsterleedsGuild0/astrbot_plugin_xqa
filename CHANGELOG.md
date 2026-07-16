# 更新日志

本项目的所有重要变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

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

[Unreleased]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/compare/v0.1.3...HEAD
[v0.1.3]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/compare/v0.1.2...v0.1.3
[v0.1.2]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/compare/v0.1.1...v0.1.2
[v0.1.1]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/compare/v0.1.0...v0.1.1
[v0.1.0]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/releases/tag/v0.1.0
[#1]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/issues/1
[#2]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/issues/2
