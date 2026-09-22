# 面试题推荐 Agent

扫描简历，选出 10 到 20 道面试题。题库以前端为主，也包含 Agent 和后端。基础、框架和架构题只能用知识库或当次联网补到的题，不改题干。过往经历题根据简历来写。

DeepSeek 负责读简历和从候选题里挑选。检索在本机用向量相似度完成，不依赖向量数据库。

## 目录

以下路径都相对 `backend/`。

```text
backend/
├── main.py                 # ingest / recommend / serve
├── mcp_server.py           # 给 Cursor 手动调用的联网查题服务
├── run_mcp.sh
├── src/
│   ├── api.py              # HTTP 接口
│   ├── graph.py            # LangGraph 流程
│   ├── kb.py               # 扫描知识库、向量检索
│   ├── embeddings.py       # fastembed 编码 + numpy 余弦相似度
│   ├── rules.py            # 读取 rules/ 里的规则和建议
│   ├── web_questions.py    # 联网查题（推荐流程直接调用）
│   ├── resume.py           # 读取简历
│   ├── llm.py              # DeepSeek 客户端
│   └── mcp_catalog.py      # MCP 工具说明
├── rules/                  # 可编辑的规则与建议
├── kb/
│   ├── frontend/           # 前端题
│   ├── agent/              # Agent 题
│   └── backend/            # 后端题
├── resumes/                # 放简历
├── data/index.json         # ingest 生成的题目索引，已忽略提交
├── data/embeddings.npz     # ingest 生成的题向量，已忽略提交
├── output/questions.md     # 推荐结果
├── .env.example
└── requirements.txt
```

种子题大约为：前端 120、Agent 45、后端 50。

## 准备

需要 Python 3.9 或以上。

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

打开 `.env`，填上 DeepSeek 的 Key：

```bash
DEEPSEEK_API_KEY=sk-你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
QUESTION_COUNT=15
```

| 变量 | 作用 |
| --- | --- |
| `DEEPSEEK_API_KEY` | 必填。不填时 `recommend` 会直接退出 |
| `DEEPSEEK_BASE_URL` | 默认 `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 默认 `deepseek-chat` |
| `QUESTION_COUNT` | 默认 15。小于 10 会按 10，大于 20 会按 20 |

`ingest` 不调用 DeepSeek，但会下载 / 加载本机 embedding 模型并生成向量。

## 使用

在 `backend` 目录下执行。

```bash
python main.py ingest
python main.py recommend resumes/你的简历.pdf
python main.py recommend resumes/你的简历.md --count 12
```

`ingest` 扫描 `kb/` 里的 JSON 和 Markdown，校验字段后写入 `data/index.json`，并为每道题生成向量（默认 TF-IDF+SVD），写入 `data/embeddings.npz`。

`recommend` 读简历、向量检索、选题，把报告打到终端，并覆盖写入 `output/questions.md`。如果知识库比索引新，或向量文件缺失 / 与题目 id 对不上，会先自动重新扫描并重建向量。

简历支持：

| 后缀 | 说明 |
| --- | --- |
| `.pdf` | 抽取每页文字。扫描件如果没有文字层，读出来会是空的 |
| `.docx` | 读段落文字，不读文本框 |
| `.md` / `.markdown` / `.txt` | 按 UTF-8 读取 |

`--count` 和 `QUESTION_COUNT` 一样，只接受 10 到 20。

## 流程

```text
扫描简历 → 抽取画像 → 检索候选题 → 选出 10-20 道 → 写报告
```

1. **扫描简历**。抽出纯文本，最多取前 12000 字送给模型。
2. **抽取画像**。DeepSeek 返回年限、方向（`frontend` / `backend` / `agent`）、技能、项目和两句摘要。方向无法识别时按前端处理。
3. **检索**。用本机 embedding 模型把简历画像和每道题编成向量，按余弦相似度取大约 40 道候选；再乘分类权重，并给技能 / 标签重合加分。简历里出现 MySQL、LangGraph、RAG 这类技能时，会额外带上对应分类的题；纯前端简历则候选几乎都是前端题。若某项技能几乎没有对应题，会在进程内调用 `search_interview_questions` 补候选，不经过 `.cursor/mcp.json`。
4. **选题**。知识库题和联网补题只能使用候选 id，无效 id 会被丢掉，数量不够时用检索结果补齐，不改题干。过往经历题另根据简历生成，并点名具体项目。选题和措辞还会读 `rules/suggestions.md`。
5. **写报告**。每题包含分类、主题、难度、为什么问，以及答题要点。

网页上的「是否可约面试」走 `POST /api/screen/stream`，标准来自 `rules/interview-gate.md`。多份简历会逐份判断，不是合成一份结论。命令行没有单独的筛选命令。

报告示例：

```markdown
### 1. [框架 / 前端 / Vue / 中等] Vue 3 的响应式和 Vue 2 有什么差别？

**为什么问：** 简历里的项目使用 Vue 3。

**回答方向：** 先讲 Proxy 相对 defineProperty 的差异，再举项目里新增属性的例子。

**参考答案：** Vue 3 用 Proxy 追踪新增和删除属性……
```

题目会按 `foundation`（基础）→ `framework`（框架）→ `architecture`（架构经验）→ `experience`（过往经历）排序。

难度在文件里写成 `easy` / `medium` / `hard`，报告里显示为简单 / 中等 / 困难。

## 往知识库加题

把文件放到对应目录：

- `kb/frontend`
- `kb/agent`
- `kb/backend`

然后执行 `python main.py ingest`。`id` 不能重复。分类必须是 `frontend`、`agent`、`backend` 之一；如果 JSON 里没写分类，会用所在目录名。

### JSON

文件内容是题目数组：

```json
[
  {
    "id": "fe-css-011",
    "category": "frontend",
    "topic": "CSS",
    "tags": ["css", "flex"],
    "difficulty": "medium",
    "question": "flex: 1 展开后分别代表什么？",
    "answer_outline": "等同于 flex-grow: 1、flex-shrink: 1、flex-basis: 0%。"
  }
]
```

`tags` 用来和简历技能对齐，尽量写简历里会出现的词，例如 `vue`、`react`、`mysql`、`langgraph`。

### Markdown

一个文件可以放多道题，用二级标题分开：

```markdown
## custom-001
category: frontend
topic: CSS
tags: css, flex
difficulty: medium

题目：flex: 1 展开后分别代表什么？
要点：等同于 flex-grow: 1、flex-shrink: 1、flex-basis: 0%。
```

标题文字就是 `id`。`题目：` 和 `要点：` 必填。

## 规则与建议

可编辑的规则写在 `rules/`，出题和「是否可约面试」都会读进去：

- `rules/interview-gate.md`：是否进入可约面试
- `rules/suggestions.md`：选题、经历题、追问和措辞

直接改这两份 Markdown。题量配额，以及基础、框架、架构题必须来自候选题，仍由程序保证。`.cursor/mcp.json` 不参与出题，只给 Cursor 对话手动调用 `interview-web`。

## 向量检索怎么做的

DeepSeek 只有对话接口，没有 embedding，所以向量在本机做，**不依赖向量数据库**。

1. **默认 backend=`local`**：`TF-IDF（字级 n-gram）→ TruncatedSVD(256)` 得到稠密向量，写入 `data/embeddings.npz`，编码器写入 `data/vectorizer.joblib`。纯本机，适合对照余弦公式学习。
2. **可选 backend=`neural`**：环境变量 `EMBEDDING_BACKEND=neural`，用 `fastembed` 加载 `BAAI/bge-small-zh-v1.5`（语义向量；首次需下载，默认走 `HF_ENDPOINT` 镜像）。
3. **查询**：简历 skills / projects / summary / focus → 查询向量，与题库矩阵做**余弦相似度**（向量已 L2 归一化，点积即可）。
4. **重排**：相似度 × 分类权重 + 技能标签重合加分，再按 focus 优先取约 40 道候选。

前端知识库页面仍是全量拉取后本地分面过滤，不走这套向量检索。

```bash
# 默认本地稠密向量
python main.py ingest

# 改用语义向量（需能下载模型）
EMBEDDING_BACKEND=neural python main.py ingest
```

