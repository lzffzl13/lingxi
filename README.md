# LingXi Service

LingXi Service 是一个基于 FastAPI 的智能客服 Agent 服务。项目围绕多轮对话、ReAct 工具调用、知识库检索、会话记忆、Prompt 管理、监控指标和基础安全防护构建，适合作为客服自动化、FAQ 检索增强、工单辅助处理等场景的后端服务。

## 核心能力

- 多轮对话：基于会话 ID 保存上下文，支持历史消息窗口和槽位信息管理。
- ReAct Agent：LLM 可以按需调用订单查询、退换货检查、创建退货、FAQ 搜索、转人工等工具。
- 知识库增强：支持 FAQ 管理、关键词检索和 RAG 检索增强。
- Prompt 工程：支持 Prompt 版本管理、激活版本切换、回滚和 A/B 测试。
- 流式响应：提供普通聊天接口和 SSE 流式聊天接口。
- 可观测性：内置健康检查、性能统计、缓存统计和 Prometheus 指标。
- 基础安全：包含 XSS 输入清理、请求大小限制、限流和生产环境 API Key 认证。

## 技术栈

- Python 3.11+
- FastAPI / Uvicorn
- Redis
- MySQL / SQLAlchemy / Alembic
- OpenAI-compatible LLM API
- pytest / pytest-asyncio / pytest-cov
- Docker Compose

## 快速启动

### 1. 创建环境并安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

如果你使用 `uv`：

```bash
uv venv .venv
.venv\Scripts\activate
uv pip install -r requirements-dev.txt
```

### 2. 准备配置

复制环境变量模板：

```bash
copy .env.example .env
```

至少需要确认这些配置：

```env
APP_ENV=development
PORT=8002
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=mysql+pymysql://lingxi:lingxi_password@localhost:3306/lingxi
```

`.env` 只用于本地环境，不要提交到仓库。

### 3. 启动依赖服务

只启动 Redis：

```bash
docker run --rm -p 6379:6379 redis:7-alpine
```

或者使用 Docker Compose 启动 Redis、MySQL 和应用：

```bash
docker compose up -d
```

### 4. 启动应用

```bash
uvicorn app.main:app --reload --port 8002
```

启动后可以访问：

- 聊天页面：http://localhost:8002/
- 管理页面：http://localhost:8002/admin
- API 文档：http://localhost:8002/docs
- 健康检查：http://localhost:8002/health

生产环境下 `docs` 和 `redoc` 会关闭。

## API 示例

普通聊天：

```bash
curl -X POST http://localhost:8002/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"demo-session\",\"message\":\"你好，我想查询订单\"}"
```

流式聊天：

```bash
curl -N -X POST http://localhost:8002/chat/stream \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"demo-session\",\"message\":\"帮我看看退货流程\"}"
```

知识库搜索：

```bash
curl -X POST http://localhost:8002/knowledge/search \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"退货需要多久\",\"top_k\":3}"
```

## 主要接口

| 模块 | 接口 |
| --- | --- |
| 页面 | `GET /`、`GET /admin` |
| 聊天 | `POST /chat`、`POST /chat/stream` |
| 健康与缓存 | `GET /health`、`GET /cache/stats`、`POST /cache/clear` |
| 监控 | `GET /metrics` |
| 性能 | `GET /performance/stats`、`GET /performance/summary` |
| 会话 | `GET /sessions`、`GET /sessions/{session_id}`、`DELETE /sessions/{session_id}`、`GET /sessions/{session_id}/slots` |
| 知识库 | `GET /knowledge/faq`、`GET /knowledge/faq/{faq_id}`、`POST /knowledge/faq`、`PUT /knowledge/faq/{faq_id}`、`DELETE /knowledge/faq/{faq_id}`、`POST /knowledge/search` |
| Prompt | `POST /prompt/versions`、`GET /prompt/versions/{name}`、`GET /prompt/active/{name}`、`POST /prompt/active/{name}/{version_id}`、`POST /prompt/rollback/{name}` |
| A/B 测试 | `POST /prompt/tests`、`GET /prompt/tests`、`GET /prompt/tests/{test_id}`、`POST /prompt/tests/{test_id}/pause`、`POST /prompt/tests/{test_id}/resume` |
| 分析 | `GET /analytics/stats`、`GET /analytics/conversations/{conversation_id}`、`GET /analytics/users/{user_id}/conversations` |

## 测试

运行全部测试：

```bash
pytest tests -q
```

查看覆盖率：

```bash
pytest --cov=app --cov-report=term-missing tests
```

最近一次本地验证结果：

- 测试：151 passed
- 覆盖率：75%

## 项目结构

```text
app/
  main.py              FastAPI 应用入口
  config.py            配置加载
  api/                 HTTP 接口
  agent/               LLM 客户端和 ReAct Agent
  tools/               Agent 可调用工具
  session/             会话管理和 Redis 客户端
  knowledge/           FAQ 与 RAG 知识库管理
  rag/                 文档切分、向量检索和 RAG Pipeline
  prompt/              Prompt 版本管理和 A/B 测试
  cache/               响应缓存
  monitoring/          Prometheus 指标
  security/            输入清理和 XSS 防护
  db/                  数据库模型、连接和仓储
  models/              请求与响应模型
  utils/               日志和通用工具

tests/                 单元测试和接口测试
docs/                  设计文档
static/                聊天页和管理页静态资源
scripts/               初始化脚本
alembic/               数据库迁移
```

## Docker 部署

```bash
docker compose up -d --build
```

Compose 会启动：

- Redis：`localhost:6379`
- MySQL：`localhost:3306`
- LingXi Service：`localhost:8002`

注意：Compose 中应用容器使用 `APP_ENV=production`，因此需要在 `.env` 中配置可用的 `API_KEY` 和 LLM 参数。

## 生产环境注意事项

- 修改默认 `API_KEY`，不要使用模板值。
- 不要把真实 `.env`、密钥、数据库密码提交到仓库。
- 设置明确的 `CORS_ORIGINS`，避免生产环境继续使用 `["*"]`。
- 确认 `APP_ENV=production`，否则 API Key 中间件不会启用。
- 为 Redis、MySQL 和 LLM API 配置稳定的网络、超时和重试策略。
- 对外暴露服务时建议放在反向代理后，并统一处理 TLS、访问日志和限流策略。

## 文档

更多架构设计可以查看 [docs/architecture.md](docs/architecture.md)。
