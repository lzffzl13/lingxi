# LingXi Service - 项目说明

## 重要配置

- **端口：8002**（不是默认的 8000，避免与其他项目冲突）
- 启动命令：`uvicorn app.main:app --reload --port 8002`
- 访问地址：http://localhost:8002

## 项目概述

智能客服 Agent 系统，基于 ReAct 循环实现多轮对话和工具调用。

## 技术栈

- Python 3.11+ / FastAPI
- Redis（会话存储）
- MySQL（数据持久化）
- ChromaDB（向量数据库）

## 启动方式

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env

# 启动 Redis
docker run -p 6379:6379 redis:7-alpine

# 启动服务（注意端口是 8002）
uvicorn app.main:app --reload --port 8002
```

## API 端点

主要端点：
- `POST /chat` - 对话接口
- `POST /chat/stream` - 流式对话（SSE）
- `GET /health` - 健康检查
- `GET /docs` - API 文档

## 注意事项

1. 端口必须用 8002，不要用 8000
2. 需要先启动 Redis
3. 生产环境需要配置 `.env` 文件
