# Snap2Know


## 项目简介

**Snap2Know** 是一个基于树莓派的智能问答设备，通过拍照识别说明书内容，语音提问获取操作指导。
**Snap2Know** 不仅仅是一个硬件 Demo，它是一个典型的端到端 AIoT（AI + IoT）全栈项目。

### 演示场景
拍摄路由器说明书 → 语音提问"如何登录管理后台" → 获得步骤化回答 + 语音播报

---

## 硬件设备

| 设备 | 规格 | 用途 |
|------|------|------|
| **Raspberry Pi 5** | 16GB RAM, 64GB TF | 控制面：Device Agent |
| **Whisplay HAT** | 240×280 LCD, WM8960, 双麦克风, 扬声器, LED, 按键 | 显示/音频/交互 |
| **Pi AI Camera** | 官方 AI 摄像头 | 拍照 |
| **Pi Active Cooler** | 官方主动散热器 | 防止过热 |
| **Pi 官方电源** | 官方45W USB-C 电源，官方原装 PD 5.1V/5A 电源线 | 供电 |
| **MacBook Pro M2 Max** | 96GB RAM | 数据面：后端服务 |

> Pi 5 和 MBP 在同一局域网内

### Whisplay HAT 规格

- **屏幕**: 1.69" IPS LCD, 240×280, SPI 直驱 (ST7789P3)
- **音频**: WM8960 编解码, 双麦克风, 8Ω1W 扬声器
- **交互**: 单个可编程按键, RGB LED
- **驱动**: [官方文档](https://docs.pisugar.com/docs/product-wiki/whisplay/overview)

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│  Pi 5 - Device Agent（Python 单进程）                             │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ UI Renderer │  │Input Handler│  │State Machine│              │
│  │ (LCD 渲染)  │  │ (按键识别)  │  │  (状态机)   │              │
│  │ PIL/Pillow  │  │短按/长按/超长按│  │ 7 状态+Busy │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│         └────────────────┴────────────────┘                      │
│                          ↓                                       │
│                    ┌─────────────┐                               │
│                    │   UIState   │  ← 单一真相源                  │
│                    └─────────────┘                               │
│                          ↓                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │Backend Client│ │Audio Pipeline│ │ LED Control │              │
│  │ HTTP/WS→MBP │  │录音/TTS/播放 │  │  RGB 状态   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└──────────────────────────────────────────────────────────────────┘
                          ↓ HTTP/WS (局域网)
┌──────────────────────────────────────────────────────────────────┐
│  MBP - FastAPI 后端                                              │
│  ├── 会话管理 (/session)                                         │
│  ├── STT (OpenAI Whisper)                                        │
│  ├── OCR (Claude Sonnet Vision（主）/ GPT-4o（备选）)                  │
│  ├── Embedding (OpenAI)                                          │
│  ├── 问答 (Claude Sonnet + RAG)                                  │
│  ├── TTS (/tts 可选，本地 edge-tts 为默认)                          │
│  └── 向量库 (Qdrant Docker)                                      │
└──────────────────────────────────────────────────────────────────┘
```

### 设计要点

- **Pi 端**: 纯 Python 单进程直绘 LCD（不使用浏览器，SPI 直驱）
- **UI 渲染**: PIL/Pillow + Whisplay 驱动，事件驱动刷新（10-15 FPS）
- **按键交互**: 单键 Push-to-Talk（短按拍照、长按录音、超长按3s菜单）
- **TTS**: edge-tts（默认）/ espeak-ng（降级）/ 云端 OpenAI TTS（TTS_MODE=cloud）

---

## 交互设计

### 单键 Push-to-Talk

| 状态 | 操作 | 功能 |
|------|------|------|
| 待机 | 短按 | 拍照 → OCR 入库 |
| 待机 | 长按（按住） | 开始录音 |
| 录音中 | 松开 | 结束录音 → STT → 问答 |
| 回答中 | 短按 | 静音/恢复 |
| 回答中 | 长按 1.2s | 停止播报 |
| 待机 | 超长按 ≥3s | 进入清库确认 |

### LCD 状态显示 (240×280)

```
┌────────────────────────┐
│ ● Snap2Know     12:30  │  ← 状态栏 (20px)
├────────────────────────┤
│                        │
│         📷            │
│   [状态图标/缩略图]    │  ← 主区域 (180px)
│                        │
│   "按住说话..."        │
│                        │
├────────────────────────┤
│ 待机                   │  ← 底部状态 (40px)
│ 会话: 3张              │
└────────────────────────┘
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| **Pi 端** | Python, PIL/Pillow, picamera2, arecord/aplay, edge-tts, espeak-ng, Whisplay Driver |
| **MBP 后端** | Python, FastAPI, Qdrant, httpx, websockets |
| **AI 服务** | OpenAI (STT/TTS/Embedding), Anthropic Claude (OCR/LLM) |
| **部署** | Docker (Qdrant), systemd (Device Agent) |

---

## 快速开始

### 1. MBP 端

```bash
# 启动 Qdrant
cd mbp/
docker-compose up -d

# 配置环境变量
export OPENAI_API_KEY=sk-xxx
export ANTHROPIC_API_KEY=sk-ant-xxx

# 启动后端
cd snap2know/
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 2. Pi 端

```bash
# 安装 Whisplay 驱动
git clone https://github.com/PiSugar/Whisplay.git
cd Whisplay/Driver && sudo bash install_wm8960_drive.sh
sudo reboot

# 安装系统依赖（picamera2, espeak-ng, ffmpeg）
sudo apt install -y python3-picamera2 espeak-ng ffmpeg

# 安装 Python 依赖
pip install edge-tts httpx websockets pillow qdrant-client --break-system-packages
# 注：Pi OS Bookworm 需要 --break-system-packages 或使用 venv

# 启动 Device Agent
cd device_agent/
export MBP_HOST=192.168.x.x:8000  # 替换为 MBP 的 IP
python main.py
```

---

## 项目结构

```
Snap2Know/
├── README.md              # 本文件
├── Design.md              # 详细设计文档
├── mbp/                   # MBP 后端
│   ├── docker-compose.yml # Qdrant 部署
│   └── snap2know/         # FastAPI 源码
│       ├── main.py
│       ├── session.py
│       ├── stt.py
│       ├── ocr.py
│       ├── embedding.py
│       ├── qa.py
│       └── tts.py
└── pi/                    # Pi 端
    ├── device_agent/      # Device Agent 源码
    │   ├── main.py
    │   ├── state_machine.py
    │   ├── ui_renderer.py
    │   ├── input_handler.py
    │   ├── backend_client.py
    │   ├── audio_pipeline.py
    │   └── hardware/
    └── assets/            # 图标 + 字体
```

---

## 两周开发计划

### Day 0：硬件准备（前置工作）

| 步骤 | 任务 | 验收 |
|------|------|------|
| 0.1 | Pi OS 安装（非 Lite 带桌面） | SSH 连接成功 |
| 0.2 | Whisplay 驱动 | `run_test.sh` 通过 |
| 0.3 | 摄像头驱动 | picamera2 拍照成功 |
| 0.4 | 最小硬件验收 | `hardware_test.py` 全部通过 |

### Week 1-2：开发计划

| Week | Day | 任务 |
|------|-----|------|
| 1 | 1 | MBP 基础设施 + 会话 API |
| 1 | 2 | STT + TTS API |
| 1 | 3 | OCR 入库 |
| 1 | 4 | WS 流式问答 |
| 1 | 5 | Pi Device Agent 骨架 + 硬件封装 |
| 1 | 6 | 状态机 + LCD 渲染 |
| 1 | 7 | MBP 通信 + 音频处理 |
| 2 | 8 | LCD 状态渲染完善 |
| 2 | 9-10 | 全链路集成测试 |
| 2 | 11 | 稳定性测试 |
| 2 | 12 | Demo 脚本 + Prompt |
| 2 | 13 | 文档 + 一键启动 |
| 2 | 14 | 最终验收 |

---

## 参考资料

- [Whisplay HAT 官方文档](https://docs.pisugar.com/docs/product-wiki/whisplay/overview)
- [Whisplay Driver GitHub](https://github.com/PiSugar/Whisplay)
- [详细设计文档](./Design.md)
