# 面试题推荐 Agent

上传简历后，选出 10 到 20 道面试题，按基础、框架、架构经验、过往经历排布。题库以前端为主，也包含 Agent 和后端。基础、框架和架构题只能用知识库或当次联网补到的题，不改题干。过往经历题根据简历来写。

一次可以上传多份简历，每份单独出题，也可以单独判断是否进入可约面试。

DeepSeek 负责读简历和从候选题里挑选。检索在本机用向量相似度完成，不依赖向量数据库。

## 目录

```text
interview-agent/
├── start.sh                 # 一键启动前后端
├── backend/                 # Python 服务与命令行
│   ├── main.py              # ingest / recommend / serve
│   ├── rules/               # 可编辑的规则与建议
│   ├── src/                 # 流程、检索、简历解析、HTTP 接口
│   ├── kb/                  # 前端、Agent、后端题库
│   ├── resumes/             # 放简历（命令行用法）
│   └── README.md            # 流程、环境变量、题库格式
└── web/                     # Vue 3 前端
```

## 规则与建议

面试门槛和出题建议写在 Markdown 里，改完保存即可，不用改代码。下次出题或判断会重新读取。

| 文件 | 作用 |
| --- | --- |
| `backend/rules/interview-gate.md` | 是否可约面试的规则和建议 |
| `backend/rules/suggestions.md` | 出题、开场说明、追问时的建议 |

题量限制和「只能从知识库选题、禁止编造新题」仍由程序保证。这里写的是额外规则和建议。

## 准备

- Python 3.9 或以上
- Node.js 26（根目录 `.nvmrc`；本机 shell 用 nvm 切换）
- DeepSeek API Key。只建索引可以不填；生成题目必须填

## 启动

依赖装好之后，在仓库根目录执行：

```bash
./start.sh
```

脚本会先等后端 `http://127.0.0.1:8000/api/health` 通过，再启动前端。浏览器打开 `http://127.0.0.1:5173`。按 Ctrl+C 会同时停掉两边。

第一次使用需要先准备环境。

后端：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

打开 `backend/.env`，填上 `DEEPSEEK_API_KEY`。

前端：

```bash
cd web
npm install
```

然后回到仓库根目录执行 `./start.sh`。开发服务器会把 `/api` 代理到后端。页面会显示知识库题量。上传 PDF、DOCX、Markdown 或 TXT 即可生成题目，也可以把文件拖进页面，一次最多 8 个，每个不超过 10MB。多份简历各自返回一份结果。Enter 发送，Shift + Enter 换行。数量限制在 10 到 20，生成大约需要一两分钟。索引不存在或比知识库旧时，后端会自动重建，不必先手动 `ingest`。

输入框下方有两条推荐文案：按基础到经历出 15 道题，以及判断是否进入可约面试。可约面试的标准写在 `backend/rules/interview-gate.md`。

也可以分开启动：`python main.py serve`（在 `backend` 目录，默认 `http://127.0.0.1:8000`）和 `npm run dev`（在 `web` 目录）。

## 命令行

不启动前端时，也可以直接出题。报告打到终端，并覆盖写入 `backend/output/questions.md`。

```bash
cd backend
python main.py recommend resumes/你的简历.pdf
python main.py recommend resumes/你的简历.md --count 12
```

`--count` 和 `.env` 里的 `QUESTION_COUNT` 一样，只接受 10 到 20。小于 10 按 10，大于 20 按 20。

## 接口

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/api/health` | 健康检查 |
| `GET` | `/api/kb` | 返回题库总数和分类计数 |
| `GET` | `/api/kb/questions` | 返回题目列表，供知识库页面查看 |
| `GET` | `/api/mcp` | 返回当前 MCP 服务和工具说明 |
| `POST` | `/api/chat` | 对话追问。JSON：`messages`、可选 `context`、`selected_ids`、`profile`、`count` |
| `POST` | `/api/chat/stream` | 同上，SSE：`thinking` / `token` / `question` / `decision` / `error` / `done` |
| `POST` | `/api/recommend` | 上传简历并选题。表单字段：`files`（可多个）、`count`。多份时看 `results`；只有一份时仍带顶层 `profile` 和 `questions` |
| `POST` | `/api/recommend/stream` | 同上，SSE：`resume` / `thinking` / `profile` / `question` / `token` / `error` / `done` |
| `POST` | `/api/screen/stream` | 判断是否可约面试。表单字段：`files`。SSE：`resume` / `thinking` / `profile` / `decision` / `token` / `error` / `done` |

每个简历不超过 10MB，一次最多 8 个。跨域只允许 `http://127.0.0.1:5173` 和 `http://localhost:5173`。

## 联网查题

上传简历出题时，先抽画像并检索本地知识库。若某项技能几乎没有对应题，推荐流程会直接调用 `search_interview_questions` 补候选，再选题。这是进程内函数调用，不读 `.cursor/mcp.json`。查到的题不写入本地知识库，页面会标成「联网」。

同一套检索另有一个 MCP 服务 `interview-web`（`backend/mcp_server.py`），只给 Cursor 对话里手动调用。`.cursor/mcp.json` 仅在这种情况下有用，网页出题不依赖它。依赖见 `backend/requirements.txt` 的 `mcp`。

## 更多

流程、环境变量、知识库 JSON / Markdown 格式，以及向量检索说明，见 [backend/README.md](backend/README.md)。
