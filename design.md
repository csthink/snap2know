# Snap2Know 设计文档

---

## 1. 项目目标与交付范围

### 1.1 两周内必须交付的 MVP（最终形态）

**Snap2Know（路由器说明书场景）** 实现以下闭环：

**Pi 5 端：Device Agent（Python 单进程直绘 LCD）**

1. **拍照问答流程（Snap）**
   - 用户 **短按** → picamera2 拍照 → LCD 显示缩略图 → 上传入库
   - 用户 **长按（Push-to-Talk）** → WM8960 录音 → 松开结束
   - 音频上传后端 → STT → 显示问题文字
   - WS 接收流式回答 → LCD 显示进度 → 本地 TTS 语音播报

2. **会话管理**
   - 用户 **双击** → 进入清库确认界面
   - **长按确认** → DELETE + POST /session → 清理 Qdrant 数据 + Pi 本地缓存

---

## 2. 总体架构设计

### 2.1 硬件约束（Whisplay HAT）

**屏幕规格**
- 1.69" IPS，240×280 像素，SPI 接口，驱动 ST7789P3
- **非触摸屏**，不适合传统网页聊天布局

**集成组件**
- WM8960 音频编解码器
- 双麦克风
- 板载扬声器
- RGB LED
- 可编程物理按键

**设计约束**
- 必须做 **超简 UI**：大按钮、少信息
- 交互主要依赖 **语音 + 物理按键**
- 文字信息以滚动状态行或极简提示为主

---

### 2.2 Pi 端架构（纯 Python 单进程直绘 LCD）

> **架构选择说明**：Whisplay 的 240×280 LCD 是 **SPI 直驱**，不走标准显示栈，
> 因此不能使用 Chromium Kiosk。采用 Python 单进程直接控制 LCD + 硬件的方案更简单、更稳定。

```
┌──────────────────────────────────────────────────────────────────┐
│  Device Agent（Python 单进程）                                    │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ UI Renderer │  │Input Handler│  │State Machine│              │
│  │ (LCD 渲染)  │  │ (按键识别)  │  │  (状态机)   │              │
│  │ PIL/Pillow  │  │短按/长按/双击│  │ 7 状态+Busy │              │
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
                          ↓ HTTP/WS
┌──────────────────────────────────────────────────────────────────┐
│  MBP（FastAPI + Qdrant）                                         │
│  OCR / Embedding / RAG / LLM / TTS                               │
└──────────────────────────────────────────────────────────────────┘
```

### 2.3 五个内部模块职责

#### 1. UI Renderer（LCD 渲染）
- **输入**：UIState 数据结构
- **输出**：通过 SPI 推送到 LCD（使用 Whisplay 驱动或 ST7789 封装）
- **实现**：
  - 使用 PIL/Pillow 在内存中生成 240×280 RGB 画面
  - **事件驱动刷新**：仅在状态变化时刷新，上限 10-15 FPS
  - 使用 **PNG 图标**（不依赖 emoji 字体）+ **固定 TTF 字体**（如 Noto Sans CJK）

#### 2. Input Handler（按键识别）
- **输入**：GPIO 原始事件（按下/释放）
- **输出**：手势事件（`EVT_SHORT_PRESS`, `EVT_LONG_PRESS_START`, `EVT_LONG_PRESS_END`, `EVT_DOUBLE_CLICK`）
- **实现**：
  - 短按：< 300ms
  - 长按并保持：≥ 600ms
  - 长按释放后：≥ 1.2s（确认/取消）
  - 双击：两次短按间隔 80-250ms
  - 双击判定延迟 250ms（避免误拆）

#### 3. State Machine（状态机）
- **维护**：idle / recording / busy(stt|ingest|qa) / answering / done / menu / error
- **职责**：
  - Busy 子阶段优先级与 800ms 最小驻留时间
  - 错误恢复逻辑
  - 取消逻辑（长按取消）
- **输出**：更新 UIState + LED 状态 + TTS 行为

#### 4. Backend Client（MBP 通信）
- **HTTP**：`/session`, `/upload/image`, `/upload/audio`, `/tts`
- **WS**：`/ws/chat` 接收 token 流
- **回调**：把 token、耗时、错误事件反馈给状态机

#### 5. Audio Pipeline（音频处理）
- **Recording**：arecord 指定 WM8960 声卡（启动时探测 card 编号）
- **Playback**：aplay 指定 WM8960 声卡
- **TTS（默认）**：本地 espeak-ng 合成 → 播放队列（低延迟、离线可用）
- **TTS（可选开关）**：请求 MBP `/tts`（云端 OpenAI TTS，音质更优）
- **可中断**：长按停止时 `kill aplay` + `kill arecord` + 清空队列

### 2.4 UIState 数据结构（单一真相源）

```python
from dataclasses import dataclass
from typing import Optional, Literal
from enum import Enum

class State(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    BUSY = "busy"
    ANSWERING = "answering"
    DONE = "done"
    MENU = "menu"
    ERROR = "error"

class BusyStage(Enum):
    STT = "stt"
    QA = "qa"
    INGEST = "ingest"

@dataclass
class UIState:
    state: State
    busy_stage: Optional[BusyStage] = None
    line1: str = ""
    line2: str = ""
    progress: Optional[dict] = None  # {"current": 5, "total": 12}
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    error_code: Optional[str] = None
    flags: Optional[dict] = None  # {"tts_enabled": True, "muted": False}
    led: str = "idle"  # 语义枚举
    thumbnail_path: Optional[str] = None  # 最近拍照缩略图
```

### 2.5 关键工程注意事项

#### 刷屏与 WS/TTS 不可互相阻塞
- UI Renderer 独立线程，接收 UIState 快照进行绘制
- WS 接收线程与播放线程分离

#### 取消语义（单键设备生死线）
| 场景 | 取消行为 |
|------|----------|
| Busy/Answering 长按取消 | 关闭 WS + 清空 TTS 队列 + 停止 aplay + 返回 idle |
| 入库任务 | 可继续后台进行，但用户表现为"已取消等待" |

#### SPI 推屏性能
- 控制刷新频率：10-15 FPS 上限
- 状态变化时才刷新
- 可做分层合成（MVP 不强制）

#### 资源约定
- **图标**：本地 PNG（64-96px），不依赖 emoji 字体
- **字体**：固定 TTF（Noto Sans CJK），确保中文稳定显示

### 2.6 企业级雏形设计原则
- **会话隔离**：所有数据都必须挂在 session_id 下
- **可销毁**：新建会话必须可验证清理旧数据
- **可观测**：每次问答有 trace_id 与耗时分解
- **可扩展**：未来替换 Pi UI/拆分服务不破坏接口契约

### 2.7 安全与合规（MVP 最小集）

**密钥管理**
- OpenAI/Anthropic API Key **只放 MBP**，通过环境变量加载
- **Pi 端不保存任何云端密钥**，所有 API 调用通过 MBP 代理

**MBP API 鉴权（可选）**
- MVP 阶段：局域网内信任，无鉴权
- 生产建议：简单 Token 或白名单 IP

**日志脱敏**
- 不打印完整说明书 OCR 文本（仅打印 chunk 数、字符数）
- 不打印完整 STT 转写内容（仅打印长度）
- 不打印 API 响应原文（仅打印状态码、耗时）

### 2.8 Device Agent 并发模型

> **硬约束**：状态机主循环只处理事件队列，不做耗时 IO

```
┌─────────────────────────────────────────────────────────────┐
│  Device Agent 进程                                          │
│                                                             │
│  ┌─────────────┐   事件    ┌─────────────────────────┐     │
│  │ Input Handler│ ───────→ │  State Machine (主循环) │     │
│  │ (GPIO 线程) │   队列    │  - 状态转换             │     │
│  └─────────────┘           │  - 更新 UIState         │     │
│                            │  - 触发 LED/TTS 行为    │     │
│                            └───────────┬─────────────┘     │
│                                        │                   │
│                      ┌─────────────────┼─────────────────┐ │
│                      ↓                 ↓                 ↓ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │ UI Renderer │  │ WS Receiver │  │ TTS Player  │       │
│  │ (独立线程)  │  │ (asyncio)   │  │ (独立进程)  │       │
│  │ 事件驱动刷新│  │ token→分段器│  │ 可被 kill   │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

**线程/任务边界**
| 组件 | 运行方式 | 阻塞策略 |
|------|----------|----------|
| State Machine | 主线程事件循环 | 非阻塞，仅处理事件 |
| UI Renderer | 独立线程 | 事件驱动 + 100ms 节流 |
| WS Receiver | asyncio task | 非阻塞，token 入队 |
| TTS Player | subprocess (aplay) | 可被 SIGTERM 终止 |
| Recording | subprocess (arecord) | 可被 SIGTERM 终止 |

### 2.9 取消与中断语义（硬约束）

> **核心原则**：用户看到"取消/停止"后，所有底层进程必须真正终止

**长按取消（Busy/Recording 状态）**

```python
def on_long_press_cancel():
    # 1. 终止录音（若在进行）
    if recording_process:
        recording_process.terminate()
        recording_process.wait()
    
    # 2. 关闭 WS 连接（若在进行）
    if ws_connection:
        await ws_connection.close()
    
    # 3. 丢弃未处理的音频/响应
    # 4. 状态转为 idle
```

**长按停止播报（Answering 状态）**

```python
def on_long_press_stop():
    # 1. 终止当前播放
    if aplay_process:
        aplay_process.terminate()
        aplay_process.wait()
    
    # 2. 清空 TTS 队列
    while not tts_queue.empty():
        tts_queue.get_nowait()
    
    # 3. 关闭 WS（不再接收 token）
    if ws_connection:
        await ws_connection.close()
    
    # 4. 状态转为 done（或 idle）
```

**验收标准**
- [ ] 取消后 1 秒内必须无声音
- [ ] 取消后 UI 立即显示 idle/done
- [ ] 后台无残留 aplay/arecord 进程

### 2.10 成本控制与限流（MVP 规则）

**图片去重（会话内）**

```python
import hashlib

def image_hash(image_bytes):
    return hashlib.md5(image_bytes).hexdigest()

# 上传前检查
if image_hash(new_image) in session_image_hashes:
    # 跳过 OCR/Embedding，返回 {dedup_skipped: true}
    return {"dedup_skipped": True}
else:
    session_image_hashes.add(image_hash(new_image))
    # 执行 OCR/Embedding
```

**操作限流（防误触）**

| 操作 | 限流规则 |
|------|----------|
| 拍照 | 2 秒内忽略重复短按 |
| 录音 | 录音结束后 1 秒内不响应新的长按 |
| 问答 | 上一轮未完成时忽略新问题 |
| 清库 | 需二次确认，5 秒超时自动取消 |

**成本估算提示**
- Claude Opus OCR：约 $0.01-0.03/张图
- OpenAI Embedding：约 $0.0001/chunk
- Claude Sonnet：约 $0.003/千 token
- OpenAI TTS（备选）：约 $0.015/千字符


## 3. UI 状态机规格（240×280 极简仪表盘）

### 3.1 屏幕三块区域固定语义

```
┌────────────────────────┐
│ ● Snap2Know     12:30  │  ← 状态栏 (20px)
├────────────────────────┤
│                        │
│         📷            │
│   [拍照预览/状态图标]   │  ← 主区域 (180px)
│                        │
│   "按住说话..."        │
│                        │
├────────────────────────┤
│ 待机                   │  ← 底部状态 (40px)
│ 会话: 3张              │     第一行=阶段 第二行=指标
└────────────────────────┘
```

| 区域 | 高度 | 内容 |
|------|------|------|
| **状态栏** | 20px | 左：● 点颜色=全局状态；右：时间；中：异常时显示网络图标/"MBP×" |
| **主区域** | 180px | 大图标 + 1 行动作提示 +（可选）拍照缩略图 |
| **底部状态** | 40px | 第一行=阶段+进度；第二行=阶段指标 |

### 3.2 按键手势定义

| 手势 | 定义 | 用途 |
|------|------|------|
| **短按** | Press < 300ms | 确认/继续/静音切换 |
| **长按并保持** | Press ≥ 600ms | 录音（Push-to-Talk） |
| **长按释放后** | 持续 ≥ 1.2s 后释放 | 取消/确认清库 |
| **双击** | 两次短按间隔 80–250ms | 进入菜单（不直接执行破坏性操作） |

> **双击判定**：必须延迟短按动作 250ms 以内（避免把双击拆成两次短按）

### 3.3 状态定义

#### S0 Idle（待机）
| 项目 | 值 |
|------|------|
| 主图标 | 📷（若有最近照片则显示缩略图） |
| 提示语 | 按住说话 / 短按拍照 |
| 底部第一行 | 待机 |
| 底部第二行 | 会话: N张（或 Ready） |
| LED | 🔵 蓝色常亮 |
| 短按 | 拍照 → 入库（转 Busy） |
| 长按保持 | 开始录音（转 S1） |
| 双击 | 进入 S6 菜单 |

#### S1 Recording（录音中）
| 项目 | 值 |
|------|------|
| 主图标 | 🎤 |
| 提示语 | 松开结束 |
| 底部第一行 | 录音中 |
| 底部第二行 | 00:SS（录音时长） |
| LED | 🟡 黄色常亮 |
| 松开 | 停止录音 → 上传 → STT（转 Busy） |

#### Busy（处理中：合并 S2 STT + S3 Ingest + 问答准备）
| 项目 | 值 |
|------|------|
| 主图标 | ⏳ |
| 提示语 | 处理中... 长按取消 |
| 底部第一行 | 语音识别... / 入库中... / 问答中...（按优先级显示） |
| 底部第二行 | 阶段指标（见下表） |
| LED | 🟣 紫色慢闪 |
| 长按 1.2s | 取消本轮 → 返回 S0 |

**Busy 子阶段显示优先级（高→低）**
| 优先级 | 子阶段 | 第一行文案 | 第二行指标 |
|--------|--------|------------|------------|
| 1 | STT | 语音识别... | STT 1.3s / 上传... |
| 2 | QA 准备 | 问答中... | 检索 6 / 生成中... |
| 3 | Ingest | 入库中... | chunks 12 / OCR.../Embed... |

**Busy 显示规则**
- 同一子阶段至少展示 **800ms**（最小驻留时间，避免闪烁）
- 只有当更高优先级子阶段开始时，才切换第一行文案
- 当收到第一条 WS token → 切换到 S4 Answering

#### S4 Answering（回答播报中）
| 项目 | 值 |
|------|------|
| 主图标 | ▶ |
| 提示语 | 短按静音 / 长按停止 |
| 底部第一行 | 正在回答... i/j |
| 底部第二行 | 播报队列: q（或 已播: k段） |
| LED | 🟢 绿色常亮（或绿慢闪） |
| 短按 | 切换静音/恢复（仅影响 TTS，不影响文本） |
| 长按 1.2s | 停止本轮（关闭 WS、清空 TTS 队列）→ 返回 S0 |

#### S5 Done（完成）
| 项目 | 值 |
|------|------|
| 主图标 | ✅ |
| 提示语 | 短按拍照 / 按住说话 |
| 底部第一行 | 完成 |
| 底部第二行 | 耗时: T秒 |
| LED | 🔵 蓝色常亮 |
| 短按 | 拍照入库（转 Busy） |
| 长按保持 | 开始录音（转 S1） |
| 双击 | 进入 S6 菜单 |

#### S6 MenuConfirm（新会话/清理确认）
| 项目 | 值 |
|------|------|
| 主图标 | 🧹 |
| 提示语 | 长按确认 / 短按取消 |
| 底部第一行 | 新建会话? |
| 底部第二行 | 将清理本次数据 |
| LED | ⚪ 白色慢闪 |
| 短按 | 取消 → 返回 S0 |
| 长按 1.2s | 确认 → DELETE + POST /session → 返回 S0 |
| 超时 5s | 自动取消 → 返回 S0 |

#### S7 Error（错误）
| 项目 | 值 |
|------|------|
| 主图标 | ⚠ |
| 提示语 | 短按重试 / 长按取消 |
| 底部第一行 | 错误: CODE |
| 底部第二行 | 提示: NET/MIC/API |
| LED | 🔴 红色常亮 |
| 短按 | 重试上一步 |
| 长按 1.2s | 取消 → 返回 S0 |

### 3.4 状态转换图

```
                    ┌─────────────────────────────────────────┐
                    ↓                                         │
┌────────┐ 短按  ┌──────┐ 完成  ┌──────┐ token流 ┌──────────┐ │
│ S0     │──────→│ Busy │──────→│ Busy │────────→│ S4       │ │
│ Idle   │       │入库中│       │问答中│         │Answering │ │
└────────┘       └──────┘       └──────┘         └──────────┘ │
    │                                                  │      │
    │ 长按保持                                     done│      │
    ↓                                                  ↓      │
┌────────┐ 松开  ┌──────┐ STT完成 ┌──────┐      ┌──────┐     │
│ S1     │──────→│ Busy │────────→│ Busy │      │ S5   │─────┘
│录音中  │       │STT中 │         │问答中│      │ Done │
└────────┘       └──────┘         └──────┘      └──────┘

[任意状态] ─双击→ [S6 MenuConfirm] ─长按1.2s→ [清库] → [S0]
                       │
                  短按/超时5s
                       ↓
                     [S0]

[任意处理中] ─错误→ [S7 Error] ─短按重试→ [上一步]
                        │
                   长按1.2s
                        ↓
                      [S0]
```

---

## 4. 端到端时序（并行 + 流式 + 语音播报）

### 4.1 拍照问答时序

```
┌─────────────────────────────────────────────────────────────────────┐
│  用户操作                  Pi Device Agent              MBP 后端    │
├─────────────────────────────────────────────────────────────────────┤
│  短按                                                               │
│    │                                                                │
│    ↓                                                                │
│  ┌─────────────────┐                                               │
│  │ 1. picamera2 拍照│                                               │
│  │ 2. LCD 显示缩略图│                                               │
│  │ 3. 状态→busy     │                                               │
│  └────────┬────────┘                                               │
│           │ POST /upload/image ──────────────────→ 4. OCR+切块+入库 │
│           │ ←───────────────── {num_chunks}                        │
│           ↓                                                         │
│  长按（按住）                                                        │
│    │                                                                │
│    ↓                                                                │
│  ┌─────────────────┐                                               │
│  │ 5. arecord 录音  │                                               │
│  │ 6. LCD 显示时长  │                                               │
│  │ 7. 状态→recording│                                               │
│  └────────┬────────┘                                               │
│  松开     │                                                         │
│           │ POST /upload/audio ──────────────────→ 8. STT          │
│           │ ←───────────────── {question_text}                     │
│           │                                                         │
│           │ WS /ws/chat ─────────────────────────→ 9. RAG+LLM 流式 │
│           │ ←───────────────── {token...}                          │
│           ↓                                                         │
│  ┌─────────────────┐                                               │
│  │ 10. LCD 显示进度 │                                               │
│  │ 11. TTS 分段播放 │ ← 本地 espeak-ng 或请求 /tts                   │
│  │ 12. 状态→answering│                                              │
│  └────────┬────────┘                                               │
│           │ {type:"done"} ←─────────────────────                   │
│           ↓                                                         │
│  ┌─────────────────┐                                               │
│  │ 13. flush TTS   │                                               │
│  │ 14. 状态→done    │                                               │
│  └─────────────────┘                                               │
└─────────────────────────────────────────────────────────────────────┘
```

**详细步骤**
1. 用户 **短按** → picamera2 拍照 → LCD 显示缩略图
2. Device Agent → MBP：`POST /upload/image?session_id=...`
   - MBP：Claude Opus OCR → 切块 → Embedding → Qdrant upsert
3. 用户 **长按（Push-to-Talk）** → arecord 开始录音 → LCD 显示录音时长
4. 用户 **松开** → 录音结束
5. Device Agent → MBP：`POST /upload/audio?session_id=...`
   - MBP：OpenAI STT 返回 question_text
6. Device Agent → MBP：连接 `WS /ws/chat?session_id=...`
   - 发送 `{question_text, top_k}`
7. MBP：Qdrant TopK → Claude Sonnet 流式生成 → token 流推送
8. Device Agent：对每个 token：
   - 更新 UIState 进度 → UI Renderer 刷新 LCD
   - 累积到 TTS buffer → 满足 flush 条件时请求 TTS 并播放
9. 收到 `{type:"done"}`：
   - flush 剩余 buffer 播报
   - 状态转为 done → LCD 显示完成

### 4.2 新建会话

1. 用户 **双击** → 状态转为 menu → LCD 显示"新建会话？长按确认"
2. 用户 **长按 1.2s** → 确认清库
3. Device Agent → MBP：`DELETE /session/{session_id}`
   - MBP：Qdrant filter delete + 缓存清理
   - 响应：`{deleted: true, qdrant_deleted: 12, cache_deleted: 3}`
4. Device Agent → MBP：`POST /session` → 获取新 session_id
5. Device Agent：清理本地缓存（照片、音频、TTS wav）
6. 状态转为 idle → LCD 显示待机

---

## 5. 语音播报（TTS）验收规格

### 5.1 分段触发条件（Device Agent 负责）

触发一次播报（flush）满足**任一**：
- 命中句末标点：`。！？；\n`
- buffer ≥ **80 字符**
- 距离上次 flush ≥ **1.2s**
- WS `done` 强制 flush 剩余

### 5.2 队列与中断

| 配置项 | 值 | 说明 |
|--------|------|------|
| tts_queue 最大长度 | 20 | 超限则合并末尾（保证连贯） |
| 长按停止 | 必须实现 | 立刻停止播放 + 清空队列 + 关闭 WS |

---

## 6. 内部状态管理与可观测性

> **架构说明**：Device Agent 单进程内，UIState 是单一真相源，UI Renderer 直接消费 UIState 绘制 LCD。
> 不存在外部 Web UI，也不需要本地 WebSocket 推送状态。
> 
> **可选**：可开放 `/debug/state`（HTTP GET）或 `/debug/ws`（WebSocket）用于远程调试观察。

### 6.1 UIState 数据结构（内部使用）

```json
{
  "type": "state",
  "state": "busy",                              // 主状态枚举
  "busy_stage": "stt",                          // 仅 state=busy 时有效
  "line1": "语音识别...",                        // Agent 产出，UI 直接渲染
  "line2": "STT 1.3s",                          // Agent 产出
  "progress": { "current": 0, "total": 0 },     // 可选，用于 "5/12" 进度
  "session_id": "uuid",                         // 强烈建议
  "trace_id": "uuid",                           // 强烈建议
  "flags": { "tts_enabled": true, "muted": false },  // 可选，UI 按钮状态
  "led": "busy",                                // 语义枚举，Agent 内部映射到硬件
  "timestamp": 1705289756
}
```

### 6.2 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | 固定为 `"state"` |
| `state` | enum | ✅ | 主状态：`idle` \| `recording` \| `busy` \| `answering` \| `done` \| `menu` \| `error` |
| `busy_stage` | enum | 仅 busy | 子阶段：`stt` \| `qa` \| `ingest` |
| `line1` | string | ✅ | 底部第一行文案，Agent 产出 |
| `line2` | string | ✅ | 底部第二行指标，Agent 产出 |
| `progress` | object | ❌ | `{ current, total }` 用于显示 "5/12" |
| `session_id` | string | 建议 | 当前会话 ID，排障用 |
| `trace_id` | string | 建议 | 本轮问答 trace ID，排障用 |
| `flags` | object | ❌ | UI 状态标志，如 `tts_enabled`, `muted` |
| `led` | enum | ✅ | LED 语义枚举 |
| `error_code` | string | 仅 error | 错误码，如 `NET`, `API_STT`, `MIC` |
| `timestamp` | number | ✅ | Unix 时间戳 |

### 6.3 state 枚举

| 值 | 说明 | LED |
|------|------|------|
| `idle` | 待机 | 🔵 blue_solid |
| `recording` | 录音中 | 🟡 yellow_solid |
| `busy` | 处理中 | 🟣 purple_slow |
| `answering` | 回答播报中 | 🟢 green_solid |
| `done` | 完成 | 🔵 blue_solid |
| `menu` | 菜单确认 | ⚪ white_slow |
| `error` | 错误 | 🔴 red_solid |

### 6.4 busy_stage 枚举与优先级

| 优先级 | 值 | 第一行文案 | 典型 line2 |
|--------|------|------------|------------|
| 1 (最高) | `stt` | 语音识别... | STT 2.1s / 上传... |
| 2 | `qa` | 问答中... | 检索 6 / 生成中... |
| 3 (最低) | `ingest` | 入库中... | chunks 12 / OCR... |

**显示规则（Agent 侧实现）**
- 同一子阶段至少展示 **800ms**（最小驻留时间）
- 只有当更高优先级子阶段开始时，才切换 `line1`
- 当收到第一条 WS token → 切换到 `answering`

### 6.5 LED 语义枚举映射（Agent 内部）

| 语义枚举 | 硬件实现 |
|----------|----------|
| `idle` / `done` | 蓝色常亮 |
| `recording` | 黄色常亮 |
| `busy` | 紫色慢闪 |
| `answering` | 绿色常亮 |
| `menu` | 白色慢闪 |
| `error` | 红色常亮 |

### 6.6 错误消息示例

```json
{
  "type": "state",
  "state": "error",
  "error_code": "API_STT",
  "line1": "出错",
  "line2": "STT 调用失败",
  "session_id": "...",
  "trace_id": "...",
  "led": "error",
  "timestamp": 1705289756
}
```

**error_code 枚举**
| 值 | 说明 |
|------|------|
| `NET` | 网络连接失败 |
| `MIC` | 麦克风错误 |
| `CAM` | 摄像头错误 |
| `API_STT` | STT API 调用失败 |
| `API_CLAUDE` | Claude API 调用失败 |
| `API_TTS` | TTS API 调用失败 |
| `QDRANT` | 向量库错误 |

---


## 7. 接口契约（最终 MVP）

### 7.1 Session

**POST /session**
- Resp: {session_id, created_at}

**DELETE /session/{session_id}**
- Resp（建议）：{deleted, qdrant_deleted, cache_deleted}

### 7.2 Upload

**POST /upload/image?session_id=…（multipart）**
- Resp：{image_id, num_chunks, ingest_ms, dedup_skipped?}

**POST /upload/audio?session_id=…（multipart）**
- Resp：{question_text, stt_ms}

### 7.3 WebSocket

**WS /ws/chat?session_id=…**
- Client → {question_text, top_k}
- Server → 流式：
  - {type:"meta", trace_id, retrieved}
  - 多条 {type:"token", text}
  - {type:"done", total_ms}

### 7.4 TTS（语音合成）

> **TTS 路径选择**（P1 明确）：
> - **主路径（推荐）**：Pi 本地离线 TTS（espeak-ng），低延迟、免费、离线可用
> - **备选路径**：MBP 云端 TTS（OpenAI TTS），音质更自然，但有延迟和成本
> 
> MVP 阶段建议使用 **本地 TTS 为主**，在需要更好音质的演示场景可切换到云端 TTS。

**POST /tts（备选路径，用于高质量语音）**

用于云端 TTS，Pi 请求 MBP 合成语音并返回音频。

**请求**
```json
{
  "text": "要合成的文本（必填，最大 1000 字符）",
  "voice": "alloy",           // 可选，OpenAI voice: alloy/echo/fable/onyx/nova/shimmer
  "format": "wav",            // 可选，wav（默认）或 mp3
  "sample_rate": 24000        // 可选，默认 24000
}
```

**响应**
| 字段 | 说明 |
|------|------|
| **成功** | 音频二进制流，`Content-Type: audio/wav` 或 `audio/mp3` |
| **失败** | `{"error": "API_TTS", "message": "..."}`, HTTP 500 |

**使用限制**
- 单次请求最大 1000 字符
- 建议分段请求（80 字符/段）以降低延迟
- 网络失败时自动降级到本地 TTS

**最小契约约束（固定值）**
| 参数 | 固定值 | 说明 |
|------|--------|------|
| **响应格式** | `audio/wav` | MVP 阶段只支持 WAV |
| **采样率** | 24000 Hz | OpenAI TTS 默认值 |
| **声道** | 单声道 (mono) | 降低带宽 |
| **位深** | 16-bit PCM | 标准格式 |

**错误处理与重试**
| 错误码 | 含义 | 重试策略 |
|--------|------|----------|
| `API_TTS` | OpenAI API 调用失败 | 不重试，降级本地 TTS |
| `RATE_LIMIT` | 请求过于频繁 | 等待 1 秒后重试 1 次 |
| `TEXT_TOO_LONG` | 文本超过 1000 字符 | 不重试，返回错误 |

**示例**
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"text": "你好，欢迎使用 Snap2Know"}' \
  "http://mbp-ip:8000/tts" --output response.wav
```

**本地 TTS（主路径）**

Pi 端直接使用 espeak-ng 合成（启动时已探测 AUDIO_DEVICE）：
```bash
espeak-ng -v zh -w /tmp/tts.wav "要合成的文本"
aplay -D ${AUDIO_DEVICE} /tmp/tts.wav
```

---

### 7.5 配置与服务发现

**MBP 地址配置**

Device Agent 需要知道 MBP 后端地址，支持以下方式：

| 方式 | 配置 | 适用场景 |
|------|------|----------|
| 环境变量 | `MBP_HOST=192.168.1.100:8000` | 开发 |
| 配置文件 | `config.toml` 中 `[backend] host = "..."` | 生产 |
| mDNS | `snap2know-mbp.local:8000` | 自动发现 |

**断线重连策略**

| 阶段 | 行为 |
|------|------|
| 连接失败 | 5s 后重试，最多 3 次 |
| 重试失败 | 进入 Error 状态，显示 NET 错误码 |
| 用户操作 | 短按重试，长按取消 |

**TTS 模式配置**

| 配置项 | 值 | 说明 |
|--------|------|------|
| `TTS_MODE` | `local` | **默认**，使用本地 espeak-ng |
| `TTS_MODE` | `cloud` | 使用 MBP `/tts`（OpenAI TTS） |

```bash
# 环境变量方式
export TTS_MODE=local  # 默认，低延迟
export TTS_MODE=cloud  # 演示场景，高音质

# 或 config.toml
[tts]
mode = "local"  # local | cloud
```

**降级策略**
- `TTS_MODE=cloud` 时，若 `/tts` 请求失败（`API_TTS` 错误），**自动降级到本地 TTS**
- 降级后本轮问答继续使用本地 TTS，下一轮恢复尝试云端

---

### 7.6 MBP 后端职责详细

**FastAPI 单体服务，监听 0.0.0.0:8000**
- 会话管理：POST /session、DELETE /session/{id}
- 图片入库（OCR/RAG ingestion）：
  - Claude Opus 视觉抽取文字块 → block 切块（200–500 chars）→ OpenAI Embedding → Qdrant upsert
- 音频 STT：
  - OpenAI audio/transcriptions → question_text
- 问答编排：
  - Qdrant TopK → 组 prompt → Claude Sonnet 流式生成 → WS token 回推
- 可观测性：trace_id、耗时分解、错误码

**Qdrant（Docker 独立服务）**
- collection：snap2know_chunks
- session_id 过滤检索与过滤删除

---

## 8. 数据与算法设计

### 8.1 Qdrant payload
- session_id, image_id, chunk_index, text, created_at

### 8.2 切块策略（block）
- Opus 输出 block（段落/块）
- 二次切分到 200–500 chars
- embedding 入库

### 8.3 检索策略
- TopK=6（默认）
- 仅取 text 进 prompt（暂不返回引用）

### 8.4 回答模板（步骤化）

输出必须满足：
- 操作步骤（编号）
- 前置条件/注意事项/风险提示 至少一项

### 8.5 Pi 端 TTS 分段与播放（Device Agent）

**目标：** 流式体验 + 连贯语音

**触发 flush 条件**（任一满足）：
- 命中句末标点：。！？； 或换行
- buffer ≥ 80 字符
- 距上次 flush ≥ 1.2 秒
- WS 收到 `{type:"done"}` 强制 flush 剩余

**实现机制**（主路径：本地 TTS）：
```python
# 分段缓冲
tts_buffer = ""
tts_queue = queue.Queue(maxsize=20)

def on_token(token):
    global tts_buffer
    tts_buffer += token
    if should_flush(tts_buffer):
        segment = tts_buffer
        tts_buffer = ""
        tts_queue.put(segment)

def tts_worker():
    while True:
        segment = tts_queue.get()
        # 本地 TTS（主路径）
        subprocess.run(["espeak-ng", "-v", "zh", "-w", "/tmp/tts.wav", segment])
        subprocess.run(["aplay", "-D", AUDIO_DEVICE, "/tmp/tts.wav"])
```

**取消/停止语义**：
| 场景 | 行为 |
|------|------|
| 长按停止播报 | `kill aplay` + 清空 `tts_queue` |
| 长按取消录音 | `kill arecord` + 丢弃音频 |
| 长按取消问答 | 关闭 WS + 停止播报 + 返回 idle |

---

## 9. 运行与部署设计

### 9.1 MBP
- Qdrant：Docker
- FastAPI：本机运行，监听 0.0.0.0:8000
- Key：环境变量（Anthropic/OpenAI）

### 9.2 Pi（Device Agent）

**运行方式**：Python 单进程 + systemd 自启动

**依赖**：
- Python 3.11+
- Pillow（LCD 渲染）
- picamera2（摄像头）
- Whisplay Driver（LCD/LED/按键）
- arecord/aplay（ALSA 音频）
- espeak-ng（本地 TTS，主路径）
- httpx, websockets（后端通信）

**音频设备配置**：
```bash
# 启动时探测 WM8960 声卡号
CARD_NUM=$(aplay -l | grep -i wm8960 | head -1 | sed 's/card \([0-9]*\):.*/\1/')
export AUDIO_DEVICE="plughw:${CARD_NUM},0"
```

**可选**：
- `/debug/state`（HTTP GET）或 `/debug/ws`（WebSocket）用于远程调试观察
- 云端 TTS（调用 MBP `/tts`）用于需要更好音质的演示场景

---

## 10. 可观测性与故障处理

### 10.1 trace_id
- 每次问答生成 trace_id，贯穿 upload 与 ws

### 10.2 耗时分解（必须）
- ocr_ms/embed_ms/qdrant_ms/stt_ms/search_ms/llm_ms/total_ms

### 10.3 关键异常与处理
- 图片 OCR 失败：UI 显示错误提示，允许重试
- STT 失败：提示检查网络/麦克风，允许重试
- WS 断开：提示并终止生成/播放
- TTS 播报失败：降级为纯文字显示

---

## 11. 两周验收计划（新架构版）

每个里程碑都有「验收条件」；所有验收都要求「可重复执行」。

> **新架构要点**：
> - Pi 端：纯 Python 单进程直绘 LCD
> - 单键 Push-to-Talk 交互
> - TTS：本地 espeak-ng（主）/ 云端 OpenAI（备选，TTS_MODE=cloud）
> - 状态协议：UIState dataclass

---

### Day 0：硬件准备 + 最小硬件验收（前置工作）

> ⚠️ **必须在 Day 1 之前完成**，确保硬件环境就绪

---

#### Day 0.1：Pi 操作系统安装

**交付**
- Raspberry Pi OS (64-bit, 最新版本，必须是非 Lite 带桌面环境的官方 OS) 烧录到 TF 卡
- 基础配置（WiFi、SSH、时区、中文环境）

**验收**
```bash
# 1. 烧录系统
# 使用 Raspberry Pi Imager 烧录最新 Pi OS (64-bit)

# 2. 首次启动配置
# - 连接显示器完成初始设置
# - 配置 WiFi 连接到局域网
# - 启用 SSH

# 3. 验证
ssh pi@raspberrypi.local
uname -a  # 确认 aarch64
cat /etc/os-release  # 确认 Bookworm 或更新版本
```

---

#### Day 0.2：Whisplay HAT 驱动安装

**交付**
- 硬件安装：Whisplay HAT 插到 Pi GPIO
- WM8960 音频驱动安装
- Whisplay Python 驱动安装

**验收**
```bash
# 1. 安装 Whisplay 驱动
git clone https://github.com/PiSugar/Whisplay.git --depth 1
cd Whisplay/Driver
sudo bash install_wm8960_drive.sh
sudo reboot

# 2. 验证声卡
aplay -l  # 应显示 wm8960 声卡
arecord -l  # 应显示 wm8960 输入

# 3. 测试音频
cd ~/Whisplay/example
sudo bash run_test.sh  # LCD 显示测试图片，按键切换颜色
sudo bash mic_test.sh  # 录音 10 秒并回放
```

---

#### Day 0.3：摄像头驱动安装

**交付**
- Pi AI Camera 连接到 CSI 接口
- picamera2 库安装

**验收**
```bash
# 1. 启用摄像头
sudo raspi-config  # Interface Options → Camera → Enable
sudo reboot

# 2. 安装 picamera2
sudo apt update
sudo apt install -y python3-picamera2

# 3. 验证拍照
python3 -c "from picamera2 import Picamera2; cam = Picamera2(); cam.start(); cam.capture_file('/tmp/test.jpg')"
ls -la /tmp/test.jpg  # 确认图片存在
```

---

#### Day 0.4：最小硬件验收（Python 脚本）

> **目标**：用单个 Python 脚本验证所有硬件功能正常

**交付**
- `hardware_test.py` 验收脚本
- 所有硬件功能测试通过

**验收脚本内容**
```python
#!/usr/bin/env python3
# import 路径与类名以实际 Driver 仓库为准
"""最小硬件验收脚本"""
import time
import subprocess
from pathlib import Path

# 假设 Whisplay 驱动已正确安装
import sys
sys.path.insert(0, '/home/pi/Whisplay/Driver')
from Whisplay import Whisplay

def test_led():
    """测试 RGB LED"""
    print("=== 测试 LED ===")
    ws = Whisplay()
    colors = [
        ("红", (255, 0, 0)),
        ("绿", (0, 255, 0)),
        ("蓝", (0, 0, 255)),
        ("白", (255, 255, 255)),
    ]
    for name, rgb in colors:
        print(f"  LED → {name}")
        ws.set_led(*rgb)
        time.sleep(0.5)
    ws.set_led(0, 0, 255)  # 回到蓝色
    print("  ✅ LED 测试通过")

def test_lcd():
    """测试 LCD 显示"""
    print("=== 测试 LCD ===")
    ws = Whisplay()
    # 显示纯色
    ws.fill_screen(0, 0, 255)  # 蓝色
    time.sleep(1)
    ws.fill_screen(0, 255, 0)  # 绿色
    time.sleep(1)
    # 显示图标/文字（如果驱动支持）
    print("  ✅ LCD 测试通过")

def test_button():
    """测试按键"""
    print("=== 测试按键 ===")
    print("  请在 5 秒内按下按键...")
    ws = Whisplay()
    start = time.time()
    pressed = False
    while time.time() - start < 5:
        if ws.is_button_pressed():
            pressed = True
            print("  检测到按键按下！")
            ws.set_led(0, 255, 0)  # 绿色反馈
            time.sleep(0.3)
            ws.set_led(0, 0, 255)
            break
        time.sleep(0.05)
    if pressed:
        print("  ✅ 按键测试通过")
    else:
        print("  ⚠️ 未检测到按键，请手动验证")

def test_audio():
    """测试录音和播放"""
    print("=== 测试音频 ===")
    wav_path = "/tmp/test_audio.wav"
    
    # 探测 WM8960 声卡号
    import re
    result = subprocess.run(["aplay", "-l"], capture_output=True, text=True)
    match = re.search(r"card (\d+):.*wm8960", result.stdout, re.IGNORECASE)
    card_num = match.group(1) if match else "0"
    audio_device = f"plughw:{card_num},0"
    print(f"  使用音频设备: {audio_device}")
    
    print("  录音 3 秒...")
    subprocess.run([
        "arecord", "-D", audio_device, "-f", "S16_LE", 
        "-r", "16000", "-c", "1", "-d", "3", wav_path
    ], check=True)
    
    print("  播放录音...")
    subprocess.run(["aplay", "-D", audio_device, wav_path], check=True)
    
    Path(wav_path).unlink()
    print("  ✅ 音频测试通过")

def test_camera():
    """测试摄像头"""
    print("=== 测试摄像头 ===")
    from picamera2 import Picamera2
    
    cam = Picamera2()
    cam.start()
    time.sleep(1)
    
    img_path = "/tmp/test_camera.jpg"
    cam.capture_file(img_path)
    cam.stop()
    
    size = Path(img_path).stat().st_size
    print(f"  拍照成功: {img_path} ({size} bytes)")
    
    if size > 10000:  # 至少 10KB
        print("  ✅ 摄像头测试通过")
    else:
        print("  ⚠️ 图片过小，请检查")

if __name__ == "__main__":
    print("\n🔧 Snap2Know 硬件验收测试\n")
    
    try:
        test_led()
        test_lcd()
        test_button()
        test_audio()
        test_camera()
        
        print("\n✅ 所有硬件测试通过！可以开始 Day 1 开发。\n")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}\n")
        raise
```

**验收条件**
```bash
python3 hardware_test.py

# 预期输出：
# 🔧 Snap2Know 硬件验收测试
# === 测试 LED ===
#   LED → 红
#   LED → 绿
#   LED → 蓝
#   LED → 白
#   ✅ LED 测试通过
# === 测试 LCD ===
#   ✅ LCD 测试通过
# === 测试按键 ===
#   请在 5 秒内按下按键...
#   检测到按键按下！
#   ✅ 按键测试通过
# === 测试音频 ===
#   录音 3 秒...
#   播放录音...
#   ✅ 音频测试通过
# === 测试摄像头 ===
#   拍照成功: /tmp/test_camera.jpg (xxx bytes)
#   ✅ 摄像头测试通过
# ✅ 所有硬件测试通过！可以开始 Day 1 开发。
```

---

### Week 1：后端 + Device Agent 核心链路

---

#### Day 1：MBP 基础设施 + 会话 API

**交付**
- Qdrant Docker Compose
- FastAPI 骨架：/health、POST/DELETE /session

**验收**
```bash
# 1. Qdrant 启动
docker-compose up -d
curl http://localhost:6333/health  # 返回 ok

# 2. FastAPI 启动
uvicorn main:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/health  # 返回 ok

# 3. 会话管理
curl -X POST http://localhost:8000/session  # 返回 {session_id, created_at}
curl -X DELETE http://localhost:8000/session/{id}  # 返回 {deleted: true}
```

---

#### Day 2：STT + TTS API

**交付**
- POST /upload/audio → OpenAI STT → question_text
- POST /tts → OpenAI TTS → 音频流返回

**验收**
```bash
# 1. STT
curl -X POST -F "audio=@test.wav" "http://localhost:8000/upload/audio?session_id=xxx"
# 返回 {question_text: "...", stt_ms: 1234}

# 2. TTS
curl -X POST -H "Content-Type: application/json" \
  -d '{"text": "你好，这是测试"}' \
  "http://localhost:8000/tts" --output test_tts.mp3
# 播放 test_tts.mp3 验证音质
```

---

#### Day 3：OCR 入库（图片→切块→Qdrant）

**交付**
- POST /upload/image → Claude Opus OCR → 切块 → Embedding → Qdrant

**验收**
```bash
# 1. 上传路由器说明书照片
curl -X POST -F "image=@router_manual.jpg" \
  "http://localhost:8000/upload/image?session_id=xxx"
# 返回 {image_id, num_chunks: 12, ingest_ms: 3456}

# 2. 验证 Qdrant 数据
curl "http://localhost:6333/collections/snap2know_chunks/points/count?filter=..."
# count > 0
```

---

#### Day 4：WS 流式问答

**交付**
- WS /ws/chat：检索 → Claude Sonnet → token 流
- 返回 meta/token/done 三种消息

**验收**
```python
# 使用 Python websockets 测试
import websockets, asyncio, json

async def test():
    async with websockets.connect("ws://localhost:8000/ws/chat?session_id=xxx") as ws:
        await ws.send(json.dumps({"question_text": "如何登录管理后台", "top_k": 6}))
        async for msg in ws:
            print(json.loads(msg))  # 验证 meta → token... → done

asyncio.run(test())
```
- [ ] 收到 `{type: "meta", trace_id, retrieved}` 
- [ ] 收到多条 `{type: "token", text}`
- [ ] 最后收到 `{type: "done", total_ms}`

---

#### Day 5：Pi Device Agent 骨架 + 硬件封装

**交付**
- Device Agent Python 服务（运行于 Pi）
- 硬件封装模块：
  - picamera2 拍照
  - WM8960 录音/播放（arecord/aplay）
  - 按键 GPIO 监听
  - LED RGB 控制
  - LCD SPI 显示（Whisplay 驱动 + PIL/Pillow）

**验收**
```bash
# 1. 在 Pi 上启动 Device Agent
python device_agent.py

# 2. 测试硬件封装
python -c "from hardware import Camera; Camera().capture('/tmp/test.jpg')"
python -c "from hardware import LED; LED().set_color('blue')"
python -c "from hardware import LCD; LCD().show_text('Hello')"

# 3. 验证 LCD 显示
# LCD 应显示 "Hello" 文字
```

---

#### Day 6：Device Agent 状态机 + LCD 渲染

**交付**
- 完整状态机实现（S0-S7 + Busy）
- 按键事件 → 状态转换
- **LCD UI 渲染**（PIL/Pillow 绘制 → SPI 推屏）
- LED 状态同步

**验收**
```bash
# 在 Pi 上进行物理测试
# 1. 启动 Device Agent，LCD 显示 idle 界面
# 2. 短按 → LCD 显示 busy + ingest → 返回 idle
# 3. 长按 → LCD 显示 recording + 录音时长滚动 → 松开
# 4. 双击 → LCD 显示 menu 确认界面

# 验证 LED 颜色与状态同步
```

---

#### Day 7：Device Agent MBP 通信 + 音频处理

**交付**
- Backend Client：HTTP 上传图片/音频、WS 问答
- TTS 分段播报（buffer → flush → 播放队列 → WM8960 扬声器）
- 静音切换、长按停止
- 错误状态处理（网络断开、API 失败等）

**验收**
- [ ] 上传图片 → MBP OCR 入库成功
- [ ] 上传音频 → MBP STT 返回文字
- [ ] WS 问答 → 流式 token 到达
- [ ] TTS 分段播报，不是"每 token 一声"
- [ ] 短按可静音/恢复
- [ ] 长按停止：立即停止播放 + 清空队列
- [ ] 断网时进入 Error 状态，短按可重试

---

### Week 2：集成 + Demo + 文档

---

#### Day 8：LCD 状态渲染完善

**交付**
- 所有状态的 LCD 渲染（idle/recording/busy/answering/done/menu/error）
- 图标资源（PNG 格式，64-96px）
- 中文字体（Noto Sans CJK TTF）
- 进度显示（录音时长、chunks 数、播报队列）

**验收**
- [ ] idle：📷 图标 + 蓝色 LED + "按住说话 / 短按拍照"
- [ ] recording：🎤 图标 + 黄色 LED + 录音时长滚动 "00:05"
- [ ] busy：⏳ 图标 + 紫色闪烁 + 子阶段文案切换（800ms 驻留）
- [ ] answering：▶ 图标 + 绿色 LED + 进度 "5/12"
- [ ] error：⚠ 图标 + 红色 LED + 错误码显示

---

#### Day 9：全链路集成测试

**验收**
- [ ] idle：📷 图标 + 蓝色 LED
- [ ] recording：🎤 图标 + 黄色 LED + 录音时长滚动
- [ ] busy：⏳ 图标 + 紫色闪烁 + 子阶段文案切换
- [ ] answering：▶ 图标 + 绿色 LED + 进度 "5/12"
- [ ] error：⚠ 图标 + 红色 LED + 错误码显示

---

#### Day 10：全链路集成测试

**交付**
- 完整问答链路：拍照 → 录音 → STT → OCR → 问答 → TTS
- 新建会话功能

**验收**
```
1. 启动所有服务：Qdrant + FastAPI + Device Agent（Pi 上 LCD 自动显示 UI）
2. 短按拍照路由器说明书 → LCD 显示 busy → 入库完成
3. 长按录音 "如何登录管理后台" → LCD 显示录音时长 → 松开
4. 观察：LCD 显示 STT → 问答 → 流式回答 → 扬声器语音播报
5. 双击 → LCD 显示清库确认 → 长按确认 → 新建会话
```

---

#### Day 11：稳定性 + 边界情况

**交付**
- 连续 10 次问答测试
- 异常场景处理（断网、API 超时、麦克风故障）
- 资源清理（临时文件、内存泄漏检查）

**验收**
- [ ] 连续 10 次问答成功率 ≥ 90%
- [ ] 断网时 5s 内显示错误状态
- [ ] 重连后可恢复正常工作
- [ ] 无内存泄漏（htop 监控）

---

#### Day 12：Demo 脚本 + Prompt 固化

**交付**
- 路由器说明书 Demo 脚本（3 个标准问题）
- Prompt 固化（步骤化 + 风险提示模板）
- 语音播报优化（语速、分段）

**验收**
Demo 脚本：
1. "如何登录管理后台" → 返回步骤 + 默认密码提示
2. "如何修改 WiFi 名称和密码" → 返回步骤
3. "如何恢复出厂设置" → 返回步骤 + ⚠ 风险提示

---

#### Day 13：文档 + 一键启动

**交付**
- README.md：部署指南、一键启动脚本、故障排查
- 启动脚本：`./start.sh` 一键启动所有服务
- 开机自启配置（可选）

**验收**
```bash
# 在干净环境测试
git clone ...
cd Snap2Know
./start.sh  # 一键启动所有服务
# 等待 30s 后即可使用
```

---

#### Day 14：最终验收 + Buffer

**交付**
- 完整演示视频录制
- Bug 修复 + 体验优化

**最终验收（演示级）**
```
从零启动 → 3 次完整问答演示：
1. 登录管理后台 ✓
2. 修改 Wi-Fi 名称/密码 ✓
3. 恢复出厂设置（含风险提示）✓

每次验证：
- [ ] 拍照成功（LED 闪烁）
- [ ] 录音 → STT 正确
- [ ] 流式回答 + 语音播报
- [ ] 新建会话清理可验证
```

---

## 12. 交付物清单（最终必须具备）

**MBP 端**
- `snap2know/` FastAPI 源码
  - 会话管理、STT、OCR、Embedding、问答、TTS 接口
- `qdrant-compose.yml` 向量库部署

**Pi 端**
- `device_agent/` Python 源码
  - `main.py` - 入口
  - `state_machine.py` - 状态机
  - `ui_renderer.py` - LCD 渲染（PIL/Pillow）
  - `input_handler.py` - 按键识别
  - `backend_client.py` - MBP 通信
  - `audio_pipeline.py` - 录音/播放
  - `hardware/` - 硬件封装（LED、LCD、Camera）
- `assets/` - 图标 PNG + 字体 TTF

**文档**
- `README.md` - 部署指南、一键启动、故障排查
- （可选）`ops.md` - 指标、日志、成本估算

---

## 13. 设计决策总结

| 项目 | 决策 | 备注 |
|------|------|------|
| **Pi 端架构** | ✅ 纯 Python 单进程直绘 LCD | 不使用 Chromium，SPI 直驱 |
| **UI 渲染** | ✅ PIL/Pillow + Whisplay 驱动 | 事件驱动刷新，10-15 FPS 上限 |
| **摄像头** | ✅ picamera2 | Pi 官方 AI Camera |
| **音频** | ✅ WM8960 arecord/aplay | Whisplay HAT 内置 |
| **TTS** | ✅ 本地 espeak-ng（主）/ 云端 OpenAI（备选） | 低延迟、离线可用 |
| **按键交互** | ✅ 单键 Push-to-Talk | 短按/长按/双击 |
| **状态机** | ✅ 7 状态（含 Busy 子阶段） | 优先级显示 + 800ms 驻留 |
| **状态协议** | ✅ UIState dataclass | 单一真相源 |

