# CLAUDE.md

## 项目目标

金铲铲之战 AI 助手：规则引擎优先决策，LLM 兜底，跨平台适配（Mac PlayCover / Windows 模拟器）。

## 红线

- 不改业务逻辑，只做类型、测试、门禁相关改动
- 所有改动必须让 `make smoke` 全绿（ruff check + ruff format --check + mypy + pytest）
- 不调用真实 LLM、不依赖真实窗口

## 工作流

1. 先写/改测试
2. 实现代码
3. `make smoke` 全绿
4. 提交
