# AGENTS.md — interview-agent

给编码 Agent 的项目约束。人类说明以根目录 `README.md`、`backend/README.md` 为准；这里只写 Agent 容易踩坑的约定。

## 项目概览

- **做什么**：上传简历 → 从本地知识库（必要时联网补候选）选题 → 前端 SSE 流式展示；也可对话追问、可约面试判断。
- **结构**：
  - `backend/`：Python（FastAPI 风格 HTTP、`graph` 出题流程、`kb` 检索、简历解析）
  - `web/`：Vue 3 + Vite + Pinia + UnoCSS
  - `backend/rules/*.md`：可编辑业务规则（面试门槛、出题建议），**改规则优先改这些文件，不要硬编码进图逻辑**
  - `backend/kb/`：题库源文件；索引在 `backend/data/index.json`

## 启动与命令

```bash
# 根目录一键前后端
./start.sh

# 后端
cd backend && source .venv/bin/activate
python main.py serve          # :8000
python main.py ingest         # 重建题库索引
python main.py recommend resumes/某简历.pdf --count 15

# 前端
cd web
npm run dev                   # :5173，/api 代理到后端
npm run build
npm run test:unit
npm run type-check
```

Node 版本见根目录 `.nvmrc`。密钥只放 `backend/.env`（参考 `.env.example`），**禁止提交密钥或把 Key 写进代码/文档示例。**

## 领域硬约束

1. **不能编造题干**：基础 / 框架 / 架构题只能来自知识库或当次联网补到的候选；过往经历题可按简历写。
2. **题量**：推荐题数仅允许 **10–20**（小于 10 按 10，大于 20 按 20）。
3. **规则文件**：`backend/rules/interview-gate.md`、`suggestions.md` 改完即生效（下次请求重读），不要为改文案去大改 `graph.py`，除非改的是程序保证的不变量。
4. **记忆**：后端不做长期记忆落库；前端可本机缓存画像。`context` / `messages` 随请求带上、请求结束即丢。
5. **MCP**：网页出题走进程内联网检索，**不依赖** `.cursor/mcp.json`；该文件只服务 Cursor 里手动调 MCP。

## 前端约定（web/）

- **组件前缀**：可复用 UI 放 `web/src/components/`，命名 **`IG*`**（如 `IGButton`、`IGDrawer`、`IGFilterChip`、`IGTagChip`）。新建组件沿用此前缀。
- **样式**：优先 UnoCSS 工具类 / `uno.config.ts` shortcuts；全局与伪元素、滚动条、Vue Transition、`.md` 内容样式放 `styles.css`。
- **Uno 坑**：
  - 不要用 `bg-[linear-gradient(...)]`（会生成无效 `background-color`）；复杂背景用 `uno.config.ts` 的 `rules`。
  - 主题色用实色 + `/10` 这类透明度，避免 rgba 主题色被拆坏。
  - `h1`–`h6` 已 blocklist，勿当 height 工具类。
- **知识库 UI**：分面筛选逻辑在 `web/src/lib/kbFilter.ts`（分类单选、难度 OR、标签 AND、条件计数）；列表+详情布局在 `KnowledgeView.vue`。
- **文案**：产品界面默认中文。
- **测试**：纯函数优先单测（Vitest）；改过滤/transcript 等逻辑时补或更新 `web/src/__tests__/`。

## 后端约定（backend/）

- 题库分类仅 `frontend` / `agent` / `backend`；难度仅 `easy` / `medium` / `hard`。
- 检索以本机 BM25 / 规则加权为主，不要默认引入向量库或新外部服务，除非需求明确要求。
- API 路由与 SSE 事件名保持与 `README.md` 一致；改协议时同步前端 `sse.ts` / store。

## Git 与协作

- **只有用户明确要求时才 commit / push**；不要擅自改 git config、不要 `--force` 推 main/master。
- Commit message 简洁说明「为什么」，用 HEREDOC 传 `-m`。
- 不要提交：`.env`、密钥、大体量生成物、无必要的 lockfile 大翻（除非依赖变更本身是目标）。
- 改动范围对准需求；不做无关重构、不顺手扩文档（用户没要就别加 markdown）。

## 回复与改代码的习惯

- 先读再改；用工具核实，不臆造文件路径或 API。
- 保持现有命名与目录习惯；复用 `IG*` 组件与 `lib/` 纯函数。
- 用户要计划时再出方案；已确认执行就直接改，少客套。
