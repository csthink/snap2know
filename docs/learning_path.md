# Snap2Know 学习路径与技术栈总结

> 本文档梳理 Snap2Know 项目涉及的核心技术、学习路径与实践价值。

---

## 项目定位

**Snap2Know** 是一个端到端的多模态 AI 应用：
- **输入**：图像（说明书拍照）+ 语音（问题）
- **处理**：OCR → Embedding → RAG 检索 → LLM 生成
- **输出**：流式文本 + TTS 语音播报

通过实现完整的 Pi 边缘设备 + MBP 后端架构，学习者可以深入理解 AI 应用从"API 调用"到"产品落地"的全过程。

---

## 技术栈一览

```
┌─────────────────────────────────────────────────────────────┐
│                        Snap2Know 技术栈                      │
├─────────────────────────────────────────────────────────────┤
│  硬件层                                                      │
│  ├── Raspberry Pi 5 (16GB)                                  │
│  ├── Whisplay HAT (LCD + WM8960 + 按键 + LED + 双麦克风)     │
│  └── Pi AI Camera                                           │
├─────────────────────────────────────────────────────────────┤
│  Pi 端 (Device Agent)                                       │
│  ├── Python 3.11+                                           │
│  ├── PIL/Pillow (LCD 渲染)                                  │
│  ├── picamera2 (摄像头)                                     │
│  ├── edge-tts / espeak-ng (TTS)                             │
│  ├── arecord / aplay (ALSA 音频)                            │
│  └── httpx / websockets (后端通信)                          │
├─────────────────────────────────────────────────────────────┤
│  MBP 后端                                                   │
│  ├── FastAPI (REST + WebSocket)                             │
│  ├── Qdrant (向量数据库, Docker)                            │
│  ├── OpenAI API (STT / Embedding / TTS)                     │
│  └── Anthropic Claude API (OCR / LLM)                       │
├─────────────────────────────────────────────────────────────┤
│  AI 能力                                                    │
│  ├── Vision OCR: Claude Sonnet / GPT-4o                     │
│  ├── STT: OpenAI Whisper                                    │
│  ├── Embedding: OpenAI text-embedding-3-small               │
│  ├── LLM: Claude Sonnet (流式生成)                          │
│  └── TTS: edge-tts (默认) / espeak-ng (降级) / OpenAI (云端) │
└─────────────────────────────────────────────────────────────┘
```

---

## 学习路径（按阶段）

### 阶段 1：硬件与环境 (Day 0)

| 主题 | 知识点 |
|------|--------|
| **Pi OS 配置** | 64-bit Bookworm, SSH, 网络配置 |
| **硬件驱动** | SPI LCD, I2C 音频编解码器, GPIO 按键 |
| **音频系统** | ALSA 声卡探测, asound.conf 配置 |
| **摄像头** | libcamera, picamera2 API |

### 阶段 2：后端服务 (Week 1 前半)

| 主题 | 知识点 |
|------|--------|
| **FastAPI** | REST API 设计, 异步处理, 错误处理 |
| **向量数据库** | Qdrant 部署, collection 管理, 过滤检索 |
| **AI API 集成** | OpenAI/Anthropic SDK, 超时/重试策略 |
| **流式响应** | WebSocket 协议, token 流推送 |

### 阶段 3：边缘设备开发 (Week 1 后半)

| 主题 | 知识点 |
|------|--------|
| **状态机设计** | 7 状态 + 子阶段, 事件驱动 |
| **单键交互** | 防误触, 阈值判定, 强反馈 |
| **LCD 渲染** | PIL 图像合成, SPI 推屏, 帧率控制 |
| **音频管道** | 录音/播放进程管理, 中断与清理 |

### 阶段 4：系统集成 (Week 2)

| 主题 | 知识点 |
|------|--------|
| **TTS 流式播放** | 分段合成, 队列背压, pop/click 缓解 |
| **降级策略** | OCR 主备切换, TTS 自动降级 |
| **可观测性** | trace_id, 耗时分解, 日志脱敏 |
| **稳定性测试** | 长时间运行, 异常恢复 |

---

## 核心设计模式

### 1. 分层架构
```
用户交互 → 状态机 → 后端通信 → AI 服务
    ↑          ↓
  UI 渲染 ← UIState (单一真相源)
```

### 2. 降级链路
```
edge-tts ──超时──→ espeak-ng (本地)
Claude Sonnet ──超时──→ GPT-4o (备选)
云端 TTS ──失败──→ 本地 TTS
```

### 3. 流式处理
```
WS token 流 → TTS Buffer → 分段 flush → 队列 → 播放
                  ↓
           背压控制 (合并尾段)
```

### 4. 硬件抽象
```
GPIO → Input Handler (去抖/阈值) → EVT_xxx 事件
LCD ← UI Renderer ← UIState 快照
LED ← State Machine (语义枚举映射)
```

---

## 关键挑战与解决方案

| 挑战 | 解决方案 |
|------|----------|
| OCR 延迟 10s+ | 换 Sonnet (快) + GPT-4o 备选 |
| TTS 机械音 | edge-tts 默认,体验优先 |
| WM8960 pop/click | v2 常驻流,避免频繁 open/close |
| 单键误触 | 阈值判定 + 强反馈 + 无延迟 tap |
| 流式断句 | 强标点 + 保护规则 + 时间上限 |
| 成本控制 | 图片去重 + 操作限流 |

---

## 学习收获

### 技术能力
- [x] 多模态 AI 应用全链路开发
- [x] 嵌入式设备与云端服务协同
- [x] 流式处理与实时系统设计
- [x] 硬件驱动与软件抽象

### 工程素养
- [x] MVP 范围控制与交付节奏
- [x] 配置管理与环境隔离
- [x] 可观测性与故障排查
- [x] 降级设计与容错机制

### AI 应用洞察
- [x] 不同 AI 服务的性能/成本权衡
- [x] 用户体验驱动的技术选型
- [x] 边缘计算与云端 AI 的边界

---

## 延伸学习资源

| 领域 | 推荐资源 |
|------|----------|
| **RAG** | LlamaIndex / LangChain 文档 |
| **嵌入式 AI** | Edge Impulse, TensorFlow Lite |
| **音频处理** | ALSA 官方文档, PulseAudio |
| **状态机** | python-statemachine, transitions |
| **流式系统** | AsyncIO 深入, WebSocket 协议 |

---

## 项目文件索引

| 文件 | 用途 |
|------|------|
| [Design.md](../Design.md) | 完整技术设计文档 |
| [README.md](../README.md) | 项目概览与快速开始 |
| `mbp/` | MBP 后端源码 |
| `pi/device_agent/` | Pi 端 Device Agent 源码 |
| `pi/assets/` | 图标与字体资源 |

---

*最后更新：2026-01-16*
