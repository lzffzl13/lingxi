# LingXi Service - 智能客服 Agent

基于 ReAct 循环的智能客服系统，支持多轮对话、工具调用和会话记忆。

## 功能特性

- 多轮对话管理
- 工具调用（订单查询、转人工等）
- 会话槽位和历史记录
- OpenAI 兼容接口（支持 DeepSeek、中转 GPT 等）

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填入你的配置：

```bash
cp .env.example .env
```

### 3. 启动 Redis

```bash
docker run -p 6379:6379 redis:7-alpine
```

### 4. 启动服务

```bash
uvicorn app.main:app --reload
```

### 5. 测试

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-001", "message": "你好"}'
```

## API 文档

启动服务后访问：http://localhost:8000/docs

## 项目结构

```
app/
├── main.py           # FastAPI 入口
├── config.py         # 配置管理
├── models/           # 数据模型
├── session/          # 会话管理
├── agent/            # ReAct 引擎
├── tools/            # 工具系统
├── api/              # API 端点
└── utils/            # 工具函数
```

## 开发

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
pytest tests/ -v

# 运行测试并查看覆盖率
pytest --cov=app tests/
```

## Docker 部署

```bash
docker-compose up -d
```
