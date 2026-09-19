# 面试题推荐 Agent

上传一份简历，从本地知识库里选出 10 到 20 道面试题。题库以前端为主，也包含 Agent 和后端。选题必须来自知识库，不会凭空编题。

DeepSeek 只负责读简历和从候选题里挑选。检索在本机完成，不需要向量模型。

## 目录

```text
interview-agent/
├── start.sh                 # 一键启动前后端
├── backend/                 # Python 服务与命令行
│   ├── main.py              # ingest / recommend / serve
│   ├── src/                 # 流程、检索、简历解析、HTTP 接口
│   ├── kb/                  # 前端、Agent、后端题库
│   ├── resumes/             # 放简历（命令行用法）
│   └── README.md            # 流程、环境变量、题库格式
└── web/                     # Vue 3 前端
```

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

然后回到仓库根目录执行 `./start.sh`。开发服务器会把 `/api` 代理到后端。页面会显示知识库题量；上传 PDF、DOCX、Markdown 或 TXT 后即可生成题目。数量限制在 10 到 20，生成大约需要一两分钟。索引不存在或比知识库旧时，后端会自动重建，不必先手动 `ingest`。

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
| `POST` | `/api/recommend` | 上传简历并选题。表单字段：`file`、`count` |

简历不超过 10MB。跨域只允许 `http://127.0.0.1:5173` 和 `http://localhost:5173`。

## 联网查题

项目带了一个 MCP 服务 `interview-web`，工具名是 `search_interview_questions`。给一个技术主题，它会到网上检索公开面试题，并带回出处链接。查到的题不会写入本地知识库。

配置在 `.cursor/mcp.json`。在 Cursor 里启用 `interview-web` 后即可调用。依赖已经写在 `backend/requirements.txt` 的 `mcp` 里，虚拟环境需要装过这份依赖。

## 更多

流程、环境变量、知识库 JSON / Markdown 格式，以及为什么不用向量检索，见 [backend/README.md](backend/README.md)。
