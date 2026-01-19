# Day 2：STT + TTS API

> **目标**：实现语音转文字（STT）和文字转语音（TTS）API

## 前置要求

- ✅ Day 1 完成（FastAPI 项目骨架就绪）
- OpenAI API Key（用于 STT）
- 网络连接（edge-tts 需要）

---

## 交付内容

- `POST /upload/audio` → OpenAI Whisper STT → 返回识别文本
- `POST /tts` → edge-tts/OpenAI TTS → 返回音频流
- `GET /tts/info` → TTS 配置信息

---

## 项目结构更新

```
mbp/snap2know/
├── main.py          # 更新：注册 STT/TTS 路由
├── stt.py           # 新增：STT API（OpenAI Whisper）
├── tts.py           # 新增：TTS API（edge-tts + OpenAI TTS）
├── config.py        # 更新：添加代理配置支持
├── session.py       # 会话管理
├── .env.example     # 更新：代理配置示例
└── requirements.txt # 依赖
```

---

## 配置说明

### 环境变量 (.env)

```bash
# OpenAI API Key
OPENAI_API_KEY=sk-xxx

# 自定义 API 地址（注意：需要包含 /v1 后缀）
OPENAI_BASE_URL=https://api.gptsapi.net/v1

# Anthropic API Key（Day 3 使用）
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_BASE_URL=https://api.gptsapi.net

# 代理配置（可选）
# HTTP_PROXY=http://127.0.0.1:7890
# HTTPS_PROXY=http://127.0.0.1:7890

# TTS 模式
TTS_MODE=auto
```

> ⚠️ **重要**：使用 API 代理服务时，`OPENAI_BASE_URL` 必须包含 `/v1` 后缀

---

## 文件功能说明

### stt.py - 语音转文字

| 端点 | 方法 | 功能 |
|------|------|------|
| `/upload/audio` | POST | 接收音频文件，调用 OpenAI Whisper API 转写 |

**请求参数**：
- `audio`: 音频文件（wav/mp3/webm）
- `session_id`: 会话 ID（query 参数）

**响应**：
```json
{
  "question_text": "识别的文本内容",
  "stt_ms": 1234,
  "session_id": "xxx"
}
```

**特性**：
- 支持代理配置
- 支持自定义 API 地址
- 默认中文识别

### tts.py - 文字转语音

| 端点 | 方法 | 功能 |
|------|------|------|
| `/tts` | POST | 文字转语音，返回 MP3 音频流 |
| `/tts/info` | GET | 获取 TTS 配置信息 |

**TTS 模式**：
- `auto`（默认）：edge-tts 优先，espeak-ng 降级
- `edge`：强制使用 edge-tts
- `cloud`：使用 OpenAI TTS

**可用语音**：
- **edge-tts**：zh-CN-XiaoxiaoNeural, zh-CN-YunxiNeural, zh-CN-YunjianNeural, zh-CN-XiaoyiNeural
- **OpenAI TTS**：alloy, echo, fable, onyx, nova, shimmer

---

## 验收测试

### 1. 启动服务

```bash
cd mbp/snap2know
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 2. TTS 测试

```bash
# 获取 TTS 配置信息
curl http://localhost:8000/tts/info
# {"available_modes":["auto","edge","cloud"],"current_mode":"auto",...}

# edge-tts 模式（默认）
curl -X POST -H "Content-Type: application/json" \
  -d '{"text": "你好，这是测试"}' \
  "http://localhost:8000/tts" --output test_edge.mp3
# 生成 ~13KB MP3 文件

# OpenAI TTS 模式
curl -X POST -H "Content-Type: application/json" \
  -d '{"text": "你好，这是一个测试", "mode": "cloud"}' \
  "http://localhost:8000/tts" --output test_cloud.mp3
# 生成 ~38KB MP3 文件
```

### 3. STT 测试

```bash
# 使用 TTS 生成的音频测试 STT
curl -X POST -F "audio=@test_cloud.mp3" \
  "http://localhost:8000/upload/audio?session_id=test123"

# 预期响应：
# {"question_text":"錄音測試 12345","stt_ms":3049,"session_id":"test123"}
```

---

## 验收清单

- [x] `stt.py` 模块创建
- [x] `tts.py` 模块创建
- [x] `main.py` 注册 STT/TTS 路由
- [x] 代理配置支持
- [x] `GET /tts/info` 返回配置信息 ✅
- [x] `POST /tts` (edge-tts) 生成语音 ✅
- [x] `POST /tts` (cloud/OpenAI) 生成语音 ✅ (38KB)
- [x] `POST /upload/audio` STT 识别成功 ✅ (3049ms)

---

## 测试截图

### TTS 验证

```
curl -X POST -d '{"text":"你好，这是一个测试","mode":"cloud"}' http://localhost:8000/tts
HTTP Status: 200
/tmp/test_tts_cloud.mp3: MPEG ADTS, layer III, v2, 160 kbps, 24 kHz, Monaural (38KB)
```

### STT 验证

```
curl -X POST -F "audio=@test.mp3" "http://localhost:8000/upload/audio?session_id=test"
{"question_text":"錄音測試 12345","stt_ms":3049,"session_id":"test123"}
```

---

## 下一步

✅ Day 2 完成，继续 **Day 3：OCR 入库（图片→切块→Qdrant）**