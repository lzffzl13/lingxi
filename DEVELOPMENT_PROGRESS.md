# 灵犀智能客服系统 - 开发进度

## 项目概述

基于 FastAPI + Redis + LLM 的智能客服系统，采用 ReAct 模式实现多轮对话。

---

## 版本进度

### ✅ v1.2.0 - AI 能力增强 (已完成)

- RAG 检索增强生成 (向量语义搜索)
- Prompt 工程化 (版本管理、A/B 测试)
- 文档可视化 (架构图、流程图)
- 性能指标展示 (统计 API)

### ✅ v1.1.0 - 系统优化 (已完成)

- Prometheus 监控指标
- 响应缓存优化 (LRU + TTL)
- 安全性增强 (输入验证、XSS 防护)
- 新增 `/metrics`、`/cache/stats`、`/cache/clear` 端点

### ✅ v0.1.0 - 基础框架 (已完成)

- FastAPI 应用框架
- ReAct 循环引擎
- 工具注册系统 (装饰器模式)
- Redis 会话存储
- Mock 工具实现

### ✅ v0.2.0 - 知识库 (已完成)

- FAQ 知识库管理器
- 关键词匹配搜索 (替代 ChromaDB，因模型下载慢)
- 知识库 API 端点

### ✅ v0.3.0 - 更多工具 (已完成)

- `check_order` - 查询订单 (支持数据库 + Mock 双模式)
- `search_faq` - 搜索 FAQ
- `check_return` - 检查退换货资格
- `create_return` - 创建退换货工单
- `transfer_human` - 转人工

### ❌ v0.4.0 - QA Agent (已跳过)

用户要求跳过此版本。

### ✅ v0.5.0 - 前端界面 (已完成)

- 现代化紫色渐变设计
- 快捷操作按钮
- 打字指示器
- 响应式布局

### ✅ 生产级改造 (已完成)

#### Phase 1: MySQL 数据层
- `app/db/database.py` - 数据库连接管理 (可选，支持优雅降级)
- `app/db/models.py` - ORM 模型 (Order, ReturnOrder, FAQ)
- `app/db/repositories.py` - Repository 模式数据访问层
- 工具函数更新为数据库优先 + Mock 回退

#### Phase 2: API 认证
- `app/api/middleware.py` - API Key 认证中间件
- 生产环境自动启用认证
- 请求日志中间件

#### Phase 3: 管理 API
- `app/api/sessions.py` - 会话管理 (列表、详情、删除、槽位)
- `app/api/knowledge.py` - 知识库管理 (FAQ CRUD + 搜索)

#### Phase 4: 架构优化
- `app/api/deps.py` - 依赖注入 (Redis, Agent, SessionManager, KnowledgeManager)
- `app/exceptions.py` - 自定义异常类 (LingXiError, SessionNotFoundError, etc.)
- SSE 流式响应 `/chat/stream` 端点
- 前端支持流式输出显示

---

## 技术栈

| 组件 | 技术选型 |
|------|----------|
| Web 框架 | FastAPI |
| 会话存储 | Redis (aioredis) |
| 数据库 | MySQL (可选，aiomysql + SQLAlchemy) |
| 配置管理 | pydantic-settings |
| 认证 | API Key (X-API-Key header) |
| 监控 | Prometheus (prometheus-client) |
| 缓存 | LRU 内存缓存 |
| 安全 | XSS 防护、CSP、输入验证 |
| RAG | 向量检索 (FAISS/NumPy) |
| Embedding | OpenAI/本地模型 |
| Prompt 管理 | 版本控制、A/B 测试 |
| 前端 | 纯 HTML/CSS/JS |

---

## 文件结构

```
lingxi_service/
├── app/
│   ├── agent/
│   │   ├── llm.py           # LLM 客户端 (支持流式)
│   │   ├── react.py         # ReAct 循环引擎 (支持流式)
│   │   └── prompts.py       # 系统提示词
│   ├── api/
│   │   ├── analytics.py     # 数据统计 API
│   │   ├── chat.py          # 聊天 API (含 SSE 流式)
│   │   ├── deps.py          # 依赖注入
│   │   ├── health.py        # 健康检查 + 缓存统计
│   │   ├── knowledge.py     # 知识库管理 API
│   │   ├── metrics.py       # Prometheus 指标端点
│   │   ├── middleware.py     # 认证 + 日志中间件
│   │   ├── router.py        # 路由聚合
│   │   └── sessions.py      # 会话管理 API
│   ├── cache/
│   │   ├── __init__.py
│   │   └── response_cache.py # LRU 响应缓存
│   ├── config.py            # 配置中心
│   ├── db/
│   │   ├── conversation_repo.py # 对话记录仓库
│   │   ├── database.py      # 数据库连接
│   │   ├── models.py        # ORM 模型
│   │   └── repositories.py  # 数据访问层
│   ├── exceptions.py        # 自定义异常类
│   ├── knowledge/
│   │   └── manager.py       # FAQ 管理器
│   ├── main.py              # 应用入口
│   ├── monitoring/
│   │   ├── __init__.py
│   │   └── metrics.py       # Prometheus 指标收集
│   ├── security/
│   │   ├── __init__.py
│   │   ├── input_sanitizer.py # 输入清理验证
│   │   └── xss_protection.py # XSS 防护中间件
│   ├── session/
│   │   ├── manager.py       # 会话管理器
│   │   └── redis_client.py  # Redis 客户端
│   ├── models/
│   │   ├── message.py       # 消息模型
│   │   └── schemas.py       # Pydantic 模型
│   └── tools/
│       ├── base.py          # 工具注册表
│       ├── check_order.py   # 查询订单
│       ├── check_return.py  # 检查退换货
│       ├── create_return.py # 创建退换货
│       ├── search_faq.py    # 搜索 FAQ
│       └── transfer_human.py # 转人工
├── scripts/
│   └── init_db.py           # 数据库初始化脚本
├── static/
│   └── index.html           # 前端界面 (支持流式显示)
├── tests/                   # 测试文件
├── .env                     # 环境变量
├── requirements.txt         # 依赖列表
└── README.md                # 项目说明
```

---

## 测试状态

```
18 passed, 1 warning
```

所有核心功能测试通过。

---

## 配置说明

### 环境变量 (.env)

```env
# 应用
APP_ENV=development
APP_DEBUG=true

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM
LLM_API_KEY=your-api-key
LLM_BASE_URL=http://model.mify.ai.srv/v1
LLM_MODEL=anthropic/claude-sonnet-4-20250514

# 数据库 (可选，不配置则使用 Mock 数据)
# DATABASE_URL=mysql+pymysql://user:password@localhost:3306/lingxi

# 安全 (生产环境)
API_KEY=your-secure-api-key
```

---

## API 端点

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/` | 聊天界面 | 否 |
| POST | `/chat` | 对话 | 否 |
| POST | `/chat/stream` | 对话 (SSE 流式) | 否 |
| GET | `/health` | 健康检查 | 否 |
| GET | `/sessions` | 列出会话 | 是 |
| GET | `/sessions/{id}` | 会话详情 | 是 |
| DELETE | `/sessions/{id}` | 删除会话 | 是 |
| GET | `/sessions/{id}/slots` | 会话槽位 | 是 |
| GET | `/knowledge/faq` | 列出 FAQ | 是 |
| POST | `/knowledge/faq` | 添加 FAQ | 是 |
| PUT | `/knowledge/faq/{id}` | 更新 FAQ | 是 |
| DELETE | `/knowledge/faq/{id}` | 删除 FAQ | 是 |
| POST | `/knowledge/search` | 搜索 FAQ | 否 |

---

## 启动方式

### 开发环境

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 Redis
redis-server

# 启动应用
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 生产环境

```bash
export APP_ENV=production
export API_KEY=your-secure-key
export DATABASE_URL=mysql+pymysql://user:pass@host:3306/lingxi

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker 部署

```bash
# 复制环境变量文件
cp .env.example .env
# 编辑 .env 填入你的配置

# 启动所有服务 (应用 + Redis + MySQL)
docker-compose up -d

# 查看日志
docker-compose logs -f app

# 停止服务
docker-compose down
```

---

## 已完成 Phase 5: Docker 部署

- [x] 多阶段构建 Dockerfile
- [x] docker-compose.yml (应用 + Redis + MySQL)
- [x] MySQL 初始化脚本 `scripts/init.sql`
- [x] 健康检查配置
- [x] .dockerignore
- [x] .env.example 更新

---

## 已完成 Phase 6: 生产级优化

- [x] LLM 重试机制 (指数退避) `app/agent/llm.py`
- [x] 请求超时控制 (60s 默认)
- [x] 结构化日志 (JSON 格式，生产环境) `app/utils/logger.py`
- [x] Alembic 数据库迁移配置
- [x] FAQ 搜索缓存 (TTL 5分钟) `app/knowledge/manager.py`
- [x] Prompt 动态优化 (场景检测) `app/agent/prompts.py`
- [x] 限流中间件 (按 IP/API Key) `app/api/middleware.py`
- [x] 测试覆盖提升 (54 个测试)

## 已完成 Phase 7: 核心业务功能

- [x] 消息持久化 `app/db/conversation_repo.py`
  - Conversation, ChatMessage 数据库模型
  - 对话记录自动保存到数据库
- [x] 用户识别 `app/db/models.py`
  - User 模型，支持手机号/邮箱
  - 关联订单和对话历史
- [x] 数据统计 `app/api/analytics.py`
  - 对话量、解决率、满意度
  - 工具使用统计
- [x] 后台管理UI `static/admin.html`
  - 数据看板
  - FAQ 管理 (CRUD)
  - 对话查看

---

## 已知问题

1. **ChromaDB 未使用** - 因模型下载慢，改用关键词匹配
2. **数据库可选** - 未配置 DATABASE_URL 时使用 Mock 数据

---

## 已完成 Phase 8: 系统优化

- [x] Prometheus 监控指标 `app/monitoring/metrics.py`
  - HTTP 请求计数和延迟
  - LLM 调用统计 (次数、延迟、token 使用)
  - 工具调用统计
  - 会话消息统计
  - `/metrics` 端点
- [x] 响应缓存优化 `app/cache/response_cache.py`
  - LRU 缓存策略
  - TTL 过期机制
  - 缓存统计 API (`/cache/stats`, `/cache/clear`)
- [x] 安全性增强 `app/security/`
  - 输入清理和验证
  - XSS 防护中间件
  - CSP 安全策略头
  - 请求大小限制

---

## 更新日志

### 2026-05-30
- **完成系统优化 Phase 8** 🎉
- Prometheus 监控指标 (HTTP、LLM、工具、会话)
- 响应缓存优化 (LRU + TTL)
- 安全性增强 (输入验证、XSS 防护、CSP)
- 版本升级至 v1.1.0

### 2025-05-29
- **完成核心业务功能 Phase 7** 🎉
- 消息持久化 (对话记录存数据库)
- 用户识别 (User 模型，关联订单)
- 数据统计 API (对话量、解决率、满意度、工具使用)
- 后台管理UI (数据看板、FAQ管理、对话查看)
- **完成生产级优化 Phase 6** 🎉
- LLM 重试机制 (指数退避，3次重试)
- 请求超时控制 (60s 默认)
- 结构化日志 (JSON 格式，生产环境)
- Alembic 数据库迁移配置
- FAQ 搜索缓存 (TTL 5分钟)
- Prompt 动态优化 (场景检测)
- 限流中间件 (按 IP/API Key，60次/分钟)
- 测试覆盖提升至 54 个测试
- **完成生产级改造 Phase 1-5** 🎉
- Phase 4 架构优化:
  - SSE 流式响应 `/chat/stream`
  - 依赖注入优化 `app/api/deps.py`
  - 统一错误处理 `app/exceptions.py`
- Phase 5 Docker 部署:
  - 多阶段构建 Dockerfile
  - docker-compose.yml (应用 + Redis + MySQL)
  - MySQL 初始化脚本
  - 健康检查配置
- 前端支持流式输出显示

### 2025-05-29 (早期)
- 完成生产级改造 Phase 1-3
- 新增 MySQL 支持 (可选)
- 新增 API Key 认证
- 新增会话和知识库管理 API

### 2025-05-29 (更早)
- 完成 v0.1.0 - v0.3.0, v0.5.0
- 实现基础框架、工具系统、前端界面
- 解决 ChromaDB 兼容性问题
