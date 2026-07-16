# 更新日志

本项目的所有重要变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增

- 新增 `FSD.md`，固化 `v0.1.2` MVP 功能行为规格与后续 Issue/FSD 演进约定。
- 新增 Changelog 生成与版本章节提取脚本，并补充对应单元测试。

### 变更

- 精简 README 与 PRD，明确用户文档、产品基线和功能规格的职责边界。
- 收紧 MVP 用户可见命令面：移除全群问答预留配置说明，全群问答与批量清空字符串改按普通群消息处理（[#2]）。
- Release workflow 改为复用 CHANGELOG 版本章节生成 GitHub Release 正文。
- 插件发布包加入 PRD、FSD 与 CHANGELOG 文档。

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

[Unreleased]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/compare/v0.1.2...HEAD
[v0.1.2]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/compare/v0.1.1...v0.1.2
[v0.1.1]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/compare/v0.1.0...v0.1.1
[v0.1.0]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/releases/tag/v0.1.0
[#1]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/issues/1
[#2]: https://github.com/AsterleedsGuild0/astrbot_plugin_xqa/issues/2
