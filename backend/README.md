# 面试题推荐 Agent

扫描一份简历，从本地知识库里选出 10 到 20 道面试题。题库以前端为主，也包含 Agent 和后端。选题必须来自知识库，不会凭空编题。

DeepSeek 只负责读简历和从候选题里挑选。检索在本机完成，不需要向量模型。

## 目录

```text
interview-agent/
├── main.py                 # 命令行入口
├── src/
│   ├── graph.py            # LangGraph 流程
│   ├── kb.py               # 扫描知识库、BM25 检索
│   ├── resume.py           # 读取简历
│   └── llm.py              # DeepSeek 客户端
├── kb/
│   ├── frontend/           # 前端题
│   ├── agent/              # Agent 题
│   └── backend/            # 后端题
├── resumes/                # 放简历
├── data/index.json         # ingest 生成的索引，已忽略提交
├── output/questions.md     # 推荐结果
├── .env.example
└── requirements.txt
```

种子题大约为：前端 82、Agent 25、后端 30。

## 准备

需要 Python 3.9 或以上。

```bash
cd interview-agent
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

`ingest` 不调用模型，没有 Key 也能建索引。

## 使用

在项目目录下执行。

```bash
python main.py ingest
python main.py recommend resumes/你的简历.pdf
python main.py recommend resumes/你的简历.md --count 12
```

`ingest` 扫描 `kb/` 里的 JSON 和 Markdown，校验字段后写入 `data/index.json`。

`recommend` 读简历、检索、选题，把报告打到终端，并覆盖写入 `output/questions.md`。如果知识库比索引新，会先自动重新扫描，不必每次手动 `ingest`。

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
3. **检索**。用结巴分词和 BM25 从索引里取大约 40 道候选。方向匹配的题会加权。简历里出现 MySQL、LangGraph、RAG 这类技能时，会额外带上对应分类的题；纯前端简历则候选几乎都是前端题。
4. **选题**。DeepSeek 只能使用候选题的 id。无效 id 会被丢掉，数量不够时用检索结果补齐，仍然不会编新题。
5. **写报告**。每题包含分类、主题、难度、为什么问，以及答题要点。

报告示例：

```markdown
### 1. [前端 / Vue / 中等] Vue 3 的响应式和 Vue 2 有什么差别？

**为什么问：** 简历里的项目使用 Vue 3。

**答题要点：** Vue 3 用 Proxy 追踪新增和删除属性……
```

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

## 为什么不用向量检索

DeepSeek 的接口只有对话，没有 embedding。题库是几百道结构化题，用关键词和标签检索就够，也不用再配一套向量模型或第二个 Key。
