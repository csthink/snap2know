# Snap2Know

## 项目简介

**Snap2Know** 是一个基于树莓派的智能问答设备，通过拍照识别说明书内容，语音提问获取操作指导。
**Snap2Know** 不仅仅是一个硬件 Demo，它是一个典型的端到端 AIoT（AI + IoT）全栈项目。

### ✨ 核心特性
- **Wake-to-Photo**：唤醒即拍，无需手动按键
- **智能会话**：60秒内追问不重拍照
- **流式语音**：边生成边播报，响应更快

### 🎬 演示场景
```
唤醒 "小帮小帮" → 自动拍摄路由器说明书 → 
语音提问 "如何登录管理后台" → 获得步骤化回答 + 语音播报
```

---

## 硬件清单

| 设备 | 规格 | 用途 |
|------|------|------|
| **Raspberry Pi 5** | 16GB RAM, 64GB TF | 控制面：Device Agent |
| **Whisplay HAT** | 240×280 LCD, WM8960, 双麦克风, 扬声器, LED, 按键 | 显示/音频/交互 |
| **Pi AI Camera** | Sony IMX500 1200万像素 | 拍照 (定焦，30-50cm 最佳) |
| **Pi Active Cooler** | 官方主动散热器 | 防止过热 |
| **Pi 官方电源** | 45W USB-C PD | 供电 |
| **MacBook Pro M2 Max** | 96GB RAM | 数据面：后端服务 |

> Pi 5 和 MBP 需在同一局域网内

---

## 🚀 快速开始

### 1. MBP 后端

```bash
# 1. 启动 Qdrant 向量数据库
cd mbp/
docker-compose up -d

# 2. 配置环境变量
cd snap2know/
cp .env.example .env
# 编辑 .env，填入 API Keys

# 3. 启动后端服务
./start_server.sh
```

### 2. Pi 设备端

```bash
# 方式一：一键启动 (推荐)
cd /opt/snap2know/device_agent
./start_agent.sh

# 方式二：手动启动
cd /opt/snap2know
source .venv/bin/activate
python device_agent/main.py
```

### 3. 开机自启 (可选)

```bash
# 安装 systemd 服务
sudo cp /opt/snap2know/device_agent/snap2know.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable snap2know
sudo systemctl start snap2know

# 查看状态
sudo systemctl status snap2know
sudo journalctl -u snap2know -f
```

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│  Pi 5 - Device Agent（Python 单进程）                             │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Wake Word   │  │   Camera    │  │State Machine│              │
│  │ (Vosk 唤醒) │  │  (IMX500)   │  │  (状态机)   │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│         └────────────────┴────────────────┘                      │
│                          ↓                                       │
│                    Wake-to-Photo                                 │
│           (唤醒 → 自动拍照 → VAD录音 → 问答)                      │
└──────────────────────────────────────────────────────────────────┘
                          ↓ HTTP/WS (局域网)
┌──────────────────────────────────────────────────────────────────┐
│  MBP - FastAPI 后端                                              │
│  ├── 会话管理 (/session)                                         │
│  ├── STT (Groq Whisper / 本地 Faster-Whisper)                   │
│  ├── OCR (Claude Sonnet → GPT-4o fallback)                     │
│  ├── Embedding (OpenAI text-embedding-3-small)                  │
│  ├── 问答 (Claude Sonnet + RAG)                                 │
│  ├── TTS (edge-tts)                                            │
│  └── 向量库 (Qdrant Docker)                                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 交互流程

### 语音唤醒模式 (默认)

| 步骤 | 操作 | 响应 |
|------|------|------|
| 1 | 说 "小帮，小帮" | 自动拍照 + 开始聆听 |
| 2 | 提问 | STT → RAG → 流式回答 |
| 3 | 追问 (60s内) | 继续聆听 (不重拍) |
| 4 | 说 "拍一张" | 重新拍照 |

### 按键模式

| 状态 | 操作 | 功能 |
|------|------|------|
| 待机 | 短按 | 拍照 → OCR 入库 |
| 回答中 | 长按 1.2s | 停止播报 |
| 待机 | 超长按 ≥3s | 进入清库确认 |

---

## 项目结构

```
Snap2Know/
├── README.md                 # 本文件
├── design.md                 # 详细设计文档
├── docs/                     # 开发文档
│   ├── Day0/                 # 硬件准备
│   ├── Day1-13/              # 开发日志
│   └── camera-debug-guide.md # 摄像头调试指南
├── mbp/                      # MBP 后端
│   ├── docker-compose.yml    # Qdrant 部署
│   └── snap2know/            # FastAPI 源码
│       ├── main.py
│       ├── stt.py / tts.py
│       ├── ocr.py / rag.py
│       └── ...
└── device_agent/             # Pi 端
    ├── main.py               # 入口
    ├── start_agent.sh        # 一键启动脚本
    ├── snap2know.service     # Systemd 服务
    ├── hardware/             # 硬件封装
    ├── services/             # 业务服务
    └── tools/                # 调试工具
        ├── camera_stream.py  # 浏览器实时预览
        └── camera_focus_test.py
```

---

## 故障排查 (Troubleshooting)

### 📷 摄像头模糊
IMX500 是**定焦镜头**，无自动对焦。请调整设备到文档的距离 (30-50cm)。

调试工具：
```bash
# 启动浏览器实时预览
cd /opt/snap2know
source .venv/bin/activate
python device_agent/tools/camera_stream.py
# 在浏览器打开 http://<Pi-IP>:8080
```

### 🎤 唤醒不灵敏
- 检查麦克风增益：`alsamixer` → 调整 Capture 音量
- 环境噪音：远离空调/风扇

### 🔌 无法连接后端
- 检查 MBP IP：`ifconfig` 获取正确 IP
- 检查端口：MBP 后端运行在 8000 端口
- 测试连接：`curl http://<MBP-IP>:8000/health`

### 💥 服务崩溃
```bash
# 查看 systemd 日志
sudo journalctl -u snap2know -f

# 手动启动查看详细错误
./start_agent.sh
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| **Pi 端** | Python 3.11+, PIL/Pillow, picamera2, Vosk (唤醒词), arecord/aplay, edge-tts |
| **MBP 后端** | FastAPI, Qdrant (向量库), httpx, websockets |
| **AI 服务** | Groq Whisper (STT), Claude Sonnet (OCR/RAG), OpenAI (Embedding) |
| **部署** | Docker (Qdrant), systemd (Device Agent) |

---

## API 接口概览

| 接口 | 方法 | 用途 |
|------|------|------|
| `/session` | POST | 创建新会话 |
| `/session/{id}` | DELETE | 清理会话数据 |
| `/upload/image` | POST | 图片 OCR + 向量入库 |
| `/upload/audio` | POST | 音频 STT 转写 |
| `/ws/chat` | WS | 流式问答 |
| `/tts` | POST | 文本转语音 |

> 详细接口规格见 [design.md](./design.md#7-接口契约最终-mvp)

---

## 📊 项目状态

| 阶段 | 状态 | 说明 |
|------|------|------|
| Day 0-4 | ✅ | 硬件验证 + 后端基础 |
| Day 5-8 | ✅ | Device Agent 开发 |
| Day 9-10 | ✅ | 全链路集成测试 |
| Day 11 | ✅ | Wake-to-Photo + Prompt 固化 |
| Day 12 | ✅ | 一键启动 + 文档完善 |
| Day 13 | 🔜 | 最终验收 |

**完成度：约 92%**

> 详细进度见 [阶段性总结](./docs/stage-summary.md)

---

## 参考资料

- [详细设计文档](./design.md)
- [阶段性总结](./docs/stage-summary.md)
- [摄像头调试指南](./docs/camera-debug-guide.md)
- [Whisplay HAT 官方文档](https://docs.pisugar.com/docs/product-wiki/whisplay/overview)
- [Whisplay Driver GitHub](https://github.com/PiSugar/Whisplay)
