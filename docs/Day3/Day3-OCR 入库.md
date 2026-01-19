# Day 3：OCR 入库（图片→切块→Qdrant）

> **目标**：实现图片 OCR 识别、文本切块、向量化存储到 Qdrant

## 前置要求

- ✅ Day 2 完成（STT/TTS API 就绪）
- Qdrant 运行中（`docker-compose up -d`）
- Anthropic API Key（Claude Sonnet Vision OCR）
- OpenAI API Key（GPT-4o Vision 备选 + Embedding）

---

## 交付内容

- `POST /upload/image` → Claude Sonnet OCR（主）→ 切块 → Embedding → Qdrant
- 回退机制：OCR 超时/失败 → GPT-4o Vision OCR（备选）
- `GET /qdrant/stats` → Collection 统计信息

---

## 项目结构更新

```
mbp/snap2know/
├── main.py          # 更新：注册 OCR 路由
├── ocr.py           # 新增：OCR API（Claude + GPT-4o 回退）
├── embedding.py     # 新增：文本 Embedding（OpenAI）
├── qdrant_store.py  # 新增：Qdrant 客户端封装
├── chunking.py      # 新增：文本切块策略
├── config.py        # 更新：OCR 超时配置
└── ...
```

---

## 配置说明

### 环境变量 (.env)

```bash
# Anthropic API（OCR 主路径）
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_BASE_URL=https://api.gptsapi.net

# OpenAI API（OCR 回退 + Embedding）
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.gptsapi.net/v1

# OCR 超时配置（秒）
OCR_PRIMARY_TIMEOUT_SEC=30
OCR_FALLBACK_TIMEOUT_SEC=30

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

---

## API 说明

### POST /upload/image

**请求参数**：
- `image`: 图片文件（jpg/png/webp）
- `session_id`: 会话 ID（query 参数）

**响应**：
```json
{
  "image_id": "e3b0f86d",
  "num_chunks": 1,
  "ingest_ms": 15983,
  "ocr_provider": "claude_sonnet",
  "fallback_used": false,
  "text_preview": "识别到的文字前 200 字符..."
}
```

### GET /qdrant/stats

**响应**：
```json
{
  "name": "snap2know_chunks",
  "points_count": 1,
  "status": "green"
}
```

---

## 验收测试

### 1. 启动服务

```bash
# 确保 Qdrant 运行
cd mbp && docker-compose up -d

# 启动 FastAPI
cd snap2know
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 2. 上传图片测试

```bash
curl -X POST -F "image=@images/huawei.png" \
  "http://localhost:8000/upload/image?session_id=test123"

# 实际输出：
# {
#   "image_id": "e3b0f86d",
#   "num_chunks": 1,
#   "ingest_ms": 15983,
#   "ocr_provider": "claude_sonnet",
#   "fallback_used": false,
#   "text_preview": "华为商由路首次配置视频合集..."
# }
```

### 3. 验证 Qdrant 数据

```bash
curl http://localhost:8000/qdrant/stats
# {"name":"snap2know_chunks","points_count":1,"status":"green"}
```

---

## 验收清单

- [x] `chunking.py` 模块创建
- [x] `embedding.py` 模块创建
- [x] `qdrant_store.py` 模块创建
- [x] `ocr.py` 模块创建（Claude + GPT-4o 回退）
- [x] `config.py` 添加 OCR/Embedding 配置
- [x] `main.py` 注册 OCR 路由
- [x] Qdrant Collection 自动创建
- [x] `POST /upload/image` 主路径成功 ✅ (15983ms)
- [x] `GET /qdrant/stats` 返回正确统计 ✅ (points_count=1)
- [ ] 回退路径验证（可选）

---

## 测试结果截图

### OCR 识别结果
```
华为商由路首次配置视频合集

主要内容包括：
- 华为商由登录App/现场华为路由器登入上网配置
- 系统更新与路由设置
- WiFi设置相关选项
- 安全配置与防护
- 访问控制与网络配置
...
```

### Qdrant 存储验证
```json
{"name":"snap2know_chunks","points_count":1,"status":"green"}
```

---

## 下一步

✅ Day 3 完成，继续 [Day 4：WS 流式问答](../Day4/Day4-WS流式问答.md)