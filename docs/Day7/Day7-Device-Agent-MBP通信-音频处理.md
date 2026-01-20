# Day 7：Device Agent MBP 通信 + 音频处理

> **目标**：实现 Pi 与 MBP 后端的完整通信，包括 HTTP 上传和 WebSocket 问答

## 前置要求

- ✅ Day 6 完成（状态机 + LCD 渲染就绪）
- ✅ MBP 后端服务运行中（port 8000）
- Pi 可访问 MBP（`ping 192.168.1.38`）

---

## 交付内容

- **Backend Client**：HTTP 上传图片/音频、WebSocket 问答
- **TTS 分段播报**：buffer → flush → 播放队列
- **静音切换**：短按切换
- **长按停止**：立即停止播放 + 清空队列
- **错误处理**：网络断开、API 失败等

---

## 项目结构

```
device_agent/
├── services/
│   ├── __init__.py
│   ├── state_machine.py
│   ├── button_handler.py
│   ├── lcd_renderer.py
│   ├── mbp_client.py          # 新增：MBP 通信客户端
│   └── tts_player.py          # 新增：TTS 播放器
└── main.py                     # 更新：集成 MBP 通信
```

---

## MBP Client 设计

### API 接口

| 功能 | 端点 | 方法 | 说明 |
|------|------|------|------|
| 创建会话 | `/session` | POST | 获取 session_id |
| 上传图片 | `/upload/image` | POST | OCR 入库 |
| 上传音频 | `/stt` | POST | 语音转文字 |
| TTS | `/tts` | POST | 文字转语音 |
| WS 问答 | `/ws/chat` | WebSocket | 流式问答 |
| 健康检查 | `/health` | GET | 检查连接 |

### 代码示例

```python
class MBPClient:
    def __init__(self, base_url: str, session_id: str = None):
        self.base_url = base_url
        self.session_id = session_id
        self.ws_url = base_url.replace("http", "ws")
    
    async def create_session(self) -> str:
        """创建会话"""
        ...
    
    async def upload_image(self, image_data: bytes) -> dict:
        """上传图片进行 OCR 入库"""
        ...
    
    async def speech_to_text(self, audio_data: bytes) -> str:
        """语音转文字"""
        ...
    
    async def ask_question(
        self,
        question: str,
        on_token: Callable[[str], None],
        on_done: Callable[[], None]
    ):
        """WebSocket 流式问答"""
        ...
```

---

## TTS 播放器设计

### 播放队列

```
Token Stream → Buffer → Sentence Split → TTS API → Audio Queue → Play
```

### 分段策略

1. **Token 缓冲**：累积 tokens 直到遇到句号/问号/感叹号
2. **句子分割**：按标点符号分段
3. **TTS 请求**：每个句子单独请求 TTS
4. **队列播放**：音频加入队列，顺序播放

### 代码示例

```python
class TTSPlayer:
    def __init__(self, audio_device: str, mbp_client: MBPClient):
        self.audio = Audio(device=audio_device)
        self.mbp_client = mbp_client
        self.queue = asyncio.Queue()
        self.is_playing = False
        self.is_muted = False
    
    async def add_text(self, text: str):
        """添加文本到播放队列"""
        ...
    
    async def flush(self):
        """刷新缓冲区，发送剩余文本"""
        ...
    
    def toggle_mute(self):
        """切换静音"""
        ...
    
    def stop(self):
        """停止播放并清空队列"""
        ...
```

---

## 完整流程

### 短按拍照入库

```
[Idle] → 短按 → [Busy]
        ↓
    Camera.capture()
        ↓
    MBPClient.upload_image()
        ↓
    成功/失败 → [Idle]
```

### 长按录音问答

```
[Idle] → 长按600ms → [Recording]
        ↓
    Audio.record() (持续到松开)
        ↓
    松开 → [Processing]
        ↓
    MBPClient.speech_to_text()
        ↓
    MBPClient.ask_question()
        ↓
    [Answering] + TTSPlayer.play()
        ↓
    播放完成 → [Done] → [Idle]
```

---

## 配置说明

### 新增环境变量

```bash
# MBP 通信
MBP_REQUEST_TIMEOUT=30
MBP_WS_TIMEOUT=60

# TTS 播放
TTS_BUFFER_SIZE=50
TTS_SENTENCE_SEPARATORS=。！？.!?

# 重试配置
MAX_RETRIES=3
RETRY_DELAY=1
```

---

## 验收测试

### 1. 网络连通性测试

```bash
ssh mars@raspberrypi "ping -c 3 192.168.1.38"
```

### 2. MBP Client 测试

```bash
ssh mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && python -c \"
import asyncio
from device_agent.services import MBPClient

async def test():
    client = MBPClient('http://192.168.1.38:8000')
    
    # 健康检查
    ok = await client.health_check()
    print(f'Health check: {ok}')
    
    # 创建会话
    session_id = await client.create_session()
    print(f'Session: {session_id}')

asyncio.run(test())
\""
```

### 3. 上传图片测试

```bash
ssh mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && python -c \"
import asyncio
from device_agent.services import MBPClient
from device_agent.hardware import Camera

async def test():
    client = MBPClient('http://192.168.1.38:8000')
    await client.create_session()
    
    # 拍照并上传
    camera = Camera()
    image_data = camera.capture_bytes()
    camera.close()
    
    result = await client.upload_image(image_data)
    print(f'Upload result: {result}')

asyncio.run(test())
\""
```

### 4. STT 测试

```bash
ssh mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && python -c \"
import asyncio
from device_agent.services import MBPClient
from device_agent.hardware import Audio

async def test():
    client = MBPClient('http://192.168.1.38:8000')
    await client.create_session()
    
    # 录音并转文字
    audio = Audio(device='plughw:wm8960')
    print('Recording 3 seconds...')
    audio_data = audio.record_bytes(duration=3)
    
    text = await client.speech_to_text(audio_data)
    print(f'STT result: {text}')

asyncio.run(test())
\""
```

### 5. WebSocket 问答测试

```bash
ssh mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && python -c \"
import asyncio
from device_agent.services import MBPClient

async def test():
    client = MBPClient('http://192.168.1.38:8000')
    await client.create_session()
    
    answer = ''
    async def on_token(text):
        global answer
        answer += text
        print(text, end='', flush=True)
    
    await client.ask_question('如何登录管理后台', on_token, lambda: None)
    print(f'\\n\\nTotal: {len(answer)} chars')

asyncio.run(test())
\""
```

### 6. 完整流程测试

```bash
# 启动 Device Agent
ssh -t mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && cd device_agent && python main.py"

# 物理测试：
# 1. 短按 → 拍照 → LCD 显示结果
# 2. 长按 → 录音 → 松开 → 识别 → 回答 → 播放
```

---

## 验收清单

- [ ] `services/mbp_client.py` MBP 通信客户端
- [ ] `services/tts_player.py` TTS 播放器
- [ ] `main.py` 集成 MBP 通信
- [ ] 健康检查接口
- [ ] 创建会话接口
- [ ] 上传图片 → OCR 入库
- [ ] 上传音频 → STT 转写
- [ ] WebSocket 流式问答
- [ ] TTS 分段播报（不是每 token 一声）
- [ ] 短按静音切换
- [ ] 长按停止播放
- [ ] 网络错误处理

---

## 下一步

✅ Day 7 完成，继续 [Day 8：LCD 状态渲染完善](../Day8/Day8-LCD状态渲染完善.md)