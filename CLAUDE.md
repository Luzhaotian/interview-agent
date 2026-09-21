# CLAUDE.md — interview-agent

@AGENTS.md

## Claude Code 补充

- 共享约束以根目录 `AGENTS.md` 为准；本文件只做 Claude Code 入口，避免与 Cursor / 其他 Agent 维护两套正文。
- 改业务规则优先编辑 `backend/rules/*.md`；改题库优先编辑 `backend/kb/`，需要时再 `python main.py ingest`。
- 前端新组件：`web/src/components/IG*.vue`。
- 提交前在相关目录跑通：`web` 下 `npm run type-check` / 相关 Vitest；后端改动至少保证能 `serve` / 相关脚本不炸。
- 不要把 `DEEPSEEK_API_KEY` 或真实简历内容写进回复、测试夹具或提交。
