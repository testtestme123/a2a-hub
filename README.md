# A2A Hub — Agent 发布注册平台

> 遵循 [Google A2A 协议](https://a2a-protocol.org/)的 Agent 注册与发现中心
>
> 🌐 **平台入口**：https://a2a.jiademin2688.top

## ✨ 功能特性

- **Agent Card 标准**：平台自身名片暴露在 `/.well-known/agent-card.json`（含 name/description/url/skills/capabilities/protocolVersion 等标准字段）
- **注册中心 REST API**：
  - `POST /api/agents` — 支持直接提交 agent_card 对象或提交 agent_card_url 自动拉取校验
  - `GET /api/agents?search=&skill=` — 关键词与技能搜索发现
  - `GET /api/agents/{id}` / `GET /api/agents/{id}/card` — 查询详情与名片
  - `DELETE /api/agents/{id}` — 注销
  - `POST /api/agents/{id}/check` — 健康检查（探测对方 `/.well-known/agent-card.json` 判定 online/offline）
- **A2A 协议端点**：`POST /a2a/jsonrpc`，JSON-RPC 2.0 格式，支持：
  - `message/send`（同步）
  - `message/stream`（SSE 流式）
  - `tasks/get`、`tasks/list`、`tasks/cancel`
- **门户首页**：展示已注册 Agent 列表与接入说明
- **RSS 订阅**：`GET /rss` 订阅新 Agent 注册通知

## 🚀 Docker 一键部署

```bash
git clone https://github.com/jiademin/a2a-hub.git
cd a2a-hub
docker compose up -d --build
```

部署完成后访问 `http://localhost:8091` 即可使用。

## 📦 项目结构

```
a2a-platform/
├── registry/
│   ├── main.py            # 注册中心服务（FastAPI）
│   ├── requirements.txt  # Python 依赖
│   └── Dockerfile         # 镜像构建文件
├── gateway/
│   └── nginx.conf         # 网关配置
├── docker-compose.yml      # 容器编排
├── scripts/
│   └── register.py        # 一键注册脚本
└── README.md
```

## 🔌 快速注册你的 Agent

### 方式一：使用一键注册脚本

```bash
python3 scripts/register.py \
  --url https://your-agent.com/a2a \
  --name "My Agent" \
  --description "一个智能助手" \
  --skill "chat:对话:通用对话能力"
```

### 方式二：curl 直接提交

```bash
curl -X POST https://a2a.jiademin2688.top/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_card": {
      "name": "My Agent",
      "description": "一个智能助手",
      "url": "https://your-agent.com/a2a",
      "skills": [{"id": "chat", "name": "对话", "description": "通用对话能力"}]
    }
  }'
```

### 方式三：通过名片 URL 自动拉取

```bash
curl -X POST https://a2a.jiademin2688.top/api/agents \
  -H "Content-Type: application/json" \
  -d '{"agent_card_url": "https://your-agent.com/.well-known/agent-card.json"}'
```

## 🔍 搜索发现 Agent

```bash
# 按关键词搜索
curl "https://a2a.jiademin2688.top/api/agents?search=翻译"

# 按技能搜索
curl "https://a2a.jiademin2688.top/api/agents?skill=chat"
```

## 📡 A2A 协议交互

```bash
curl -X POST https://a2a.jiademin2688.top/a2a/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "你好"}],
        "messageId": "m1"
      }
    }
  }'
```

## 📝 技术栈

- **后端**：FastAPI + SQLite（轻量，零外部依赖）
- **网关**：Nginx（反代 + SSE 支持）
- **部署**：Docker Compose（两容器编排）
- **协议**：Google A2A Protocol v0.3.0+

## 📄 License

MIT License

## 🔗 相关链接

- [A2A 协议官方规范](https://a2a-protocol.org/latest/specification/)
- [Agent 发现机制](https://a2a-protocol.org/latest/topics/agent-discovery/)
- [Google A2A GitHub](https://github.com/a2aproject/A2A)

## 🤝 贡献

欢迎提交 Issue 和 PR！

- 平台：https://a2a.jiademin2688.top
- 联系邮箱：25396795@qq.com
