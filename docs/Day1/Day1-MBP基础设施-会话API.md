# Day 1：MBP 基础设施 + 会话 API

> **目标**：搭建 MBP 后端基础设施，实现 Qdrant 向量数据库部署和基础会话管理 API

## 前置要求

- ✅ Day 0 完成（Pi 端硬件测试通过）
- Docker Desktop 已安装
- Python 3.11+ 环境就绪

---

## 步骤 1：Qdrant 向量数据库部署

### 1.1 拉取镜像并启动

```bash
# 拉取 Qdrant 镜像
docker pull qdrant/qdrant

# 创建持久化存储目录
mkdir -p ~/dc/devops/docker/qdrant_storage

# 启动容器
docker run -idt \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v ~/dc/devops/docker/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

> 💡 端口说明：`6333` = HTTP API，`6334` = gRPC API

### 1.2 验证部署

**方式一：命令行检查**

```bash
curl http://localhost:6333/healthz
# 预期输出：ok
```

![Qdrant Health Check From CLI](./images/qdrant_2.png)

**方式二：Web UI 检查**

访问 [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

![Qdrant Web UI](./images/qdrant_1.png)

![Qdrant Health Check From Web UI](./images/qdrant_3.png)

### 1.3 参考资料

- [Qdrant 官方安装指南](https://qdrant.tech/documentation/quickstart/)

---

## 步骤 2：FastAPI 项目骨架（待实现）

### 2.1 项目结构

```
mbp/
├── docker-compose.yml     # Qdrant + 其他服务
└── snap2know/
    ├── main.py            # FastAPI 入口
    ├── config.py          # 配置管理
    ├── session.py         # 会话管理
    └── requirements.txt   # Python 依赖
```

### 2.2 核心 API

| 端点 | 方法 | 功能 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/session` | POST | 创建新会话 |
| `/session/{id}` | GET | 获取会话详情 |
| `/session/{id}` | DELETE | 删除会话 |

### 2.3 验收条件

```bash
# 1. 启动 FastAPI
uvicorn main:app --host 0.0.0.0 --port 8000

# 2. 健康检查
curl http://localhost:8000/health
# 预期输出：{"status": "ok"}

# 3. 创建会话
curl -X POST http://localhost:8000/session
# 预期输出：{"session_id": "xxx", "created_at": "..."}

# 4. 删除会话
curl -X DELETE http://localhost:8000/session/{id}
# 预期输出：{"deleted": true}
```

---

## 验收清单

- [x] Qdrant Docker 容器运行正常
- [x] `curl http://localhost:6333/healthz` 返回 `ok`
- [x] Qdrant Web UI 可访问
- [ ] FastAPI 骨架实现
- [ ] 会话 API（POST/GET/DELETE）实现

---

## 下一步

✅ Qdrant 部署完成，继续实现 **FastAPI 会话 API**
