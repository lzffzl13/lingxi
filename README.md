<p align="center">
  <h1 align="center">LingXi Service</h1>
  <p align="center">面向智能客服场景的 FastAPI Agent 服务</p>
</p>

<p align="center">
  <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white"></a>
  <a href="https://fastapi.tiangolo.com/"><img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white"></a>
  <a href="https://redis.io/"><img alt="Redis" src="https://img.shields.io/badge/Redis-ready-DC382D?style=flat-square&logo=redis&logoColor=white"></a>
  <a href="https://docs.pytest.org/"><img alt="Tests" src="https://img.shields.io/badge/tests-151%20passed-2E7D32?style=flat-square"></a>
  <a href="./README.md"><img alt="Coverage" src="https://img.shields.io/badge/coverage-75%25-0F766E?style=flat-square"></a>
</p>

---

LingXi Service 是一个可运行、可测试、可观测的智能客服后端。它把 **多轮会话**、**ReAct 工具调用**、**知识库检索**、**Prompt 版本管理** 和 **监控指标** 组织成一套完整的服务，适合用来搭建客服问答、订单辅助、退换货流程和 FAQ 检索增强应用。

## Highlights

| 能力 | 说明 |
| --- | --- |
| 会话记忆 | 基于 `session_id` 管理多轮上下文、历史消息窗口和槽位信息。 |
| Agent 编排 | ReAct Agent 按需调用订单、退换货、FAQ、转人工等工具。 |
| 知识库增强 | 支持 FAQ 管理、关键词检索和 RAG 检索增强。 |
| Prompt 管理 | 支持 Prompt 版本、激活切换、回滚和 A/B 测试。 |
| 流式输出 | 同时提供普通聊天接口和 SSE 流式聊天接口。 |
| 运维可见 | 内置健康检查、缓存统计、性能统计和 Prometheus 指标。 |
| 基础防护 | 包含 XSS 清理、请求大小限制、限流和生产环境 API Key 认证。 |

## Architecture

```mermaid
flowchart LR
    Client["Web / API Client"] --> Middleware["Middleware<br/>CORS / Rate Limit / XSS / API Key"]
    Middleware --> API["FastAPI Routers"]

    API --> Chat["Chat API"]
    API --> Admin["Admin APIs"]
    API --> Ops["Health / Metrics / Performance"]

    Chat --> Agent["ReAct Agent"]
    Agent --> LLM["OpenAI-compatible LLM"]
    Agent --> Tools["Tool Registry"]
    Agent --> Session["Session Manager"]
    Agent --> Cache["Response Cache"]

    Tools --> Order["Order Tools"]
    Tools --> Return["Return Tools"]
    Tools --> FAQ["FAQ Search"]
    FAQ --> RAG["RAG Pipeline"]

    Session --> Redis[(Redis)]
    Admin --> MySQL[(MySQL)]
    RAG --> Vector["Vector Store"]
```

## Tech Stack

| 层级 | 技术 |
| --- | --- |
| API | FastAPI, Uvicorn, Pydantic |
| Agent | ReAct loop, OpenAI-compatible LLM client |
| Storage | Redis, MySQL, SQLAlchemy, Alembic |
| Knowledge | FAQ manager, RAG pipeline, vector search |
| Observability | Prometheus metrics, health checks, performance stats |
| Tests | pytest, pytest-asyncio, pytest-cov, fakeredis |
| Delivery | Dockerfile, Docker Compose |

## Quick Start

### 1. Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

使用 `uv` 也可以：

```bash
uv venv .venv
.venv\Scripts\activate
uv pip install -r requirements-dev.txt
```

### 2. Configure

```bash
copy .env.example .env
```

常用配置：

```env
APP_ENV=development
PORT=8002

LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

REDIS_URL=redis://localhost:6379/0
DATABASE_URL=mysql+pymysql://lingxi:lingxi_password@localhost:3306/lingxi
```

真实 `.env` 只放在本地或部署环境，不提交到仓库。

### 3. Start Dependencies

只启动 Redis：

```bash
docker run --rm -p 6379:6379 redis:7-alpine
```

或者直接启动完整服务栈：

```bash
docker compose up -d
```

### 4. Run

```bash
uvicorn app.main:app --reload --port 8002
```

| 入口 | 地址 |
| --- | --- |
| Chat UI | http://localhost:8002/ |
| Admin UI | http://localhost:8002/admin |
| API Docs | http://localhost:8002/docs |
| Health | http://localhost:8002/health |
| Metrics | http://localhost:8002/metrics |

生产环境下 `docs` 和 `redoc` 会自动关闭。

## API Preview

### Chat

```bash
curl -X POST http://localhost:8002/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"demo-session\",\"message\":\"你好，我想查询订单\"}"
```

### Streaming Chat

```bash
curl -N -X POST http://localhost:8002/chat/stream \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"demo-session\",\"message\":\"帮我看看退货流程\"}"
```

### Knowledge Search

```bash
curl -X POST http://localhost:8002/knowledge/search \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"退货需要多久\",\"top_k\":3}"
```

## Endpoint Map

| 模块 | 接口 |
| --- | --- |
| 页面 | `GET /`, `GET /admin` |
| 聊天 | `POST /chat`, `POST /chat/stream` |
| 健康与缓存 | `GET /health`, `GET /cache/stats`, `POST /cache/clear` |
| 监控与性能 | `GET /metrics`, `GET /performance/stats`, `GET /performance/summary` |
| 会话 | `GET /sessions`, `GET /sessions/{session_id}`, `DELETE /sessions/{session_id}`, `GET /sessions/{session_id}/slots` |
| 知识库 | `GET /knowledge/faq`, `GET /knowledge/faq/{faq_id}`, `POST /knowledge/faq`, `PUT /knowledge/faq/{faq_id}`, `DELETE /knowledge/faq/{faq_id}`, `POST /knowledge/search` |
| Prompt | `POST /prompt/versions`, `GET /prompt/versions/{name}`, `GET /prompt/active/{name}`, `POST /prompt/active/{name}/{version_id}`, `POST /prompt/rollback/{name}` |
| A/B 测试 | `POST /prompt/tests`, `GET /prompt/tests`, `GET /prompt/tests/{test_id}`, `POST /prompt/tests/{test_id}/pause`, `POST /prompt/tests/{test_id}/resume` |
| 分析 | `GET /analytics/stats`, `GET /analytics/conversations/{conversation_id}`, `GET /analytics/users/{user_id}/conversations` |

## Project Layout

```text
app/
  main.py          FastAPI 应用入口
  config.py        环境配置
  api/             HTTP 路由
  agent/           LLM 客户端和 ReAct Agent
  tools/           Agent 可调用工具
  session/         会话管理与 Redis 客户端
  knowledge/       FAQ 与 RAG 知识库管理
  rag/             文档切分、向量检索和 RAG Pipeline
  prompt/          Prompt 版本与 A/B 测试
  cache/           响应缓存
  monitoring/      Prometheus 指标
  security/        输入清理和 XSS 防护
  db/              数据库模型、连接和仓储
  models/          请求与响应模型
  utils/           日志和通用工具

tests/             单元测试和接口测试
docs/              设计文档
static/            Chat UI 和 Admin UI 静态资源
scripts/           初始化脚本
alembic/           数据库迁移
```

## Tests

```bash
pytest tests -q
```

```bash
pytest --cov=app --cov-report=term-missing tests
```

最近一次本地验证：

| 项目 | 结果 |
| --- | --- |
| 测试 | `151 passed` |
| 覆盖率 | `75%` |

## Docker

```bash
docker compose up -d --build
```

Compose 默认启动：

| 服务 | 地址 |
| --- | --- |
| LingXi Service | http://localhost:8002 |
| Redis | localhost:6379 |
| MySQL | localhost:3306 |

Compose 中应用容器会使用 `APP_ENV=production`，部署前请确认 `.env` 中的 `API_KEY`、LLM 和数据库配置可用。

## Production Notes

- 修改默认 `API_KEY`，不要使用模板值。
- 不要提交真实 `.env`、密钥和数据库密码。
- 设置明确的 `CORS_ORIGINS`，不要在生产环境继续使用 `["*"]`。
- 确认 `APP_ENV=production`，否则 API Key 中间件不会启用。
- 对外暴露服务时建议放在反向代理后，统一处理 TLS、访问日志和限流策略。

## More

- 架构设计：[docs/architecture.md](docs/architecture.md)
- 环境模板：[.env.example](.env.example)
- 开发依赖：[requirements-dev.txt](requirements-dev.txt)
