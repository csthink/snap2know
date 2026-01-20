# Day 7：Device Agent MBP 通信 + 音频处理

> **目标**：实现 Pi 与 MBP 后端的完整通信，包括 HTTP 上传和 WebSocket 问答

## 前置要求

- ✅ Day 6 完成（状态机 + LCD 渲染就绪）
- ✅ MBP 后端服务运行中（port 8000）
- Pi 可访问 MBP（`ping 192.168.1.38`）

---

## 交付内容

- **MBP Client**：HTTP 上传图片/音频、WebSocket 问答
- **TTS Player**：句子级分段播报
- **main.py**：完整集成状态机 + MBP 通信

---

## 代码结构

```
device_agent/services/
├── mbp_client.py    # MBP 通信客户端
├── tts_player.py    # TTS 分段播放器
└── __init__.py      # 导出 MBPClient, TTSPlayer
```

---

## 验收测试

### 1. MBP 连接测试 ✅

```bash
ssh mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && python -c \"
import asyncio, sys
sys.path.insert(0, '/opt/snap2know/device_agent')
from services import MBPClient
async def test():
    c = MBPClient('http://192.168.1.38:8000')
    print('Health:', await c.health_check())
    print('Session:', await c.create_session())
asyncio.run(test())
\""
```

**输出**：
```
Health: True
Session: 490ed075
```

### 2. 拍照上传测试 ✅

```bash
# 启动 Device Agent
ssh -t mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && cd device_agent && python main.py"

# 短按按钮
```

**输出**：
```
[BUTTON] Tap - Taking photo
[STATE] IDLE -> BUSY
[PHOTO] Captured 172823 bytes
[PHOTO] Upload result: {'image_id': 'c594752d', 'num_chunks': 1, 'ingest_ms': 11052, 'ocr_provider': 'claude_sonnet'}
[STATE] BUSY -> DONE -> IDLE
```

### 3. WebSocket 问答测试 ✅

```bash
# MBP 连接成功后问答
[MBP] Session: 8a547730
# 问答输出约 79 字符，耗时 ~5.7s
```

---

## 验收清单

- [x] `services/mbp_client.py` MBP 通信客户端
- [x] `services/tts_player.py` TTS 播放器
- [x] `main.py` 集成 MBP 通信
- [x] 健康检查接口
- [x] 创建会话接口
- [x] 上传图片 → OCR 入库
- [x] WebSocket 流式问答
- [x] TTS 分段播报设计
- [x] 短按静音切换
- [x] 长按停止播放
- [x] 网络错误处理

---

## 已知问题

⚠️ **Pi 5 LCD 驱动问题**：GPIO 被内核预占用，LCD 暂时保存预览到 `/tmp/lcd_preview.png`。将在后续版本修复。

---

## 下一步

✅ Day 7 完成，继续 [Day 8：LCD 状态渲染完善](../Day8/Day8-LCD状态渲染完善.md)