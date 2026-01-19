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
├── config.py        # 配置管理
├── session.py       # 会话管理
└── requirements.txt # 依赖
```

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
# {"available_modes":["auto","edge","cloud"],"current_mode":"auto","edge_voices":[...],"openai_voices":[...]}

# 生成语音
curl -X POST -H "Content-Type: application/json" \
  -d '{"text": "你好，这是测试"}' \
  "http://localhost:8000/tts" --output test_tts.mp3

# 播放验证
afplay test_tts.mp3  # macOS
# 或 aplay test_tts.mp3  # Linux
```

**预期结果**：生成可播放的 MP3 文件（约 10-20KB）

### 3. STT 测试

> ⚠️ 需要先配置 `OPENAI_API_KEY`

```bash
# 配置环境变量
cd mbp/snap2know
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY

# 测试 STT
curl -X POST -F "audio=@test.wav" \
  "http://localhost:8000/upload/audio?session_id=test"
# {"question_text": "...", "stt_ms": 1234, "session_id": "test"}
```

---

## 验收清单

- [x] `stt.py` 模块创建
- [x] `tts.py` 模块创建
- [x] `main.py` 注册 STT/TTS 路由
- [x] `GET /tts/info` 返回配置信息
- [x] `POST /tts` 生成语音文件成功
- [ ] `POST /upload/audio` STT 识别成功（需配置 API Key）

---

## 下一步

✅ Day 2 完成，继续 **Day 3：OCR 入库（图片→切块→Qdrant）**