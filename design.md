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
   - 用户 **超长按 ≥3s** → 进入清库确认界面
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
                          ↓ HTTP/WS
┌──────────────────────────────────────────────────────────────────┐
│  MBP（FastAPI + Qdrant）                                         │
│  OCR / Embedding / RAG / LLM / TTS                               │
└──────────────────────────────────────────────────────────────────┘
```

### 2.3 内部模块职责

#### 1. UI Renderer（LCD 渲染）
- **输入**：UIState 数据结构
- **输出**：通过 SPI 推送到 LCD（使用 Whisplay 驱动或 ST7789 封装）
- **实现**：
  - 使用 PIL/Pillow 在内存中生成 240×280 RGB 画面
  - **事件驱动刷新**：仅在状态变化时刷新，上限 10-15 FPS
  - 使用 **PNG 图标**（不依赖 emoji 字体）+ **固定 TTF 字体**（如 Noto Sans CJK）

#### 2. Input Handler（按键识别）
- **输入**：GPIO 原始事件（按下/释放）
- **输出**：手势/阈值事件（建议统一为阈值到达触发，避免“释放时机”误触发）
  - `EVT_TAP`（短按确认，松开后**立即执行**，无延迟）
  - `EVT_HOLD_RECORD_REACHED`（按住达到 600ms，进入录音态）
  - `EVT_HOLD_CANCEL_REACHED`（按住达到 1200ms，取消/确认在到达时立即触发，不依赖松开）
  - `EVT_HOLD_MENU_REACHED`（Idle 超长按达到 3000ms，进入菜单确认）
- **实现要点**：
  - 去抖：`T_DEBOUNCE_MS=50`
  - Tap 判定窗口：`T_TAP_MIN_MS=80`，`T_TAP_MAX_MS=300`（<80ms 视为抖动忽略；>300ms 不算 tap）
  - Tap **立即执行**：松开后满足窗口即刻触发，不等待（确保拍照即时响应）
  - Hold-to-record：`T_HOLD_TO_RECORD_MS=600`（到达即强反馈，进入 Recording）
  - Hold-to-cancel/confirm：`T_HOLD_TO_CANCEL_MS=1200`（到达即执行取消/确认）
  - Hold-to-menu：`T_HOLD_MENU_MS=3000`（仅 Idle 有效；一旦进入 Recording，本次按压不再触发菜单）
  
  > 实现提示：Pre-hold 的 UI/LED 更新应走同一套 UIState 更新链路，并做节流（例如 100ms 更新一次计时文本），避免 SPI 推屏频率过高。

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
- **录音有效门槛（MVP 防误触）**：松开结束录音后，先做本地快速校验，再决定是否提交到 STT
  - `MIN_AUDIO_DURATION_MS = 1000`：录音时长 < 1s → 视为“取消/无效”，不调用 STT，不进入 Busy(stt)
  - （可选增强）`MAX_SILENCE_RATIO = 0.8`：静音占比过高 → 视为无效录音
  - UI 行为：提示“录音过短/未检测到语音，未提交”，回 Idle
- **Playback**：aplay 指定 WM8960 声卡
- **TTS（默认）**：edge-tts 合成 → 播放队列（自然语音、免费）
- **TTS（降级）**：espeak-ng 离线合成（网络不可用/超时时自动降级）
- **TTS（可选）**：请求 MBP `/tts`（云端 OpenAI TTS，最高音质）
- **可中断**：长按停止时 `kill aplay` + `kill arecord` + 清空队列

#### 6. TTS Provider 策略（体验优先 + 可用性降级）

> **设计目标**：避免"高智商回答（Claude Sonnet）+ 机械语音（espeak-ng）"的体验违和感

**Provider 优先级**
1. **edge-tts（默认）**：自然语音、免费、无需 API Key
2. **espeak-ng（降级）**：离线兜底，断网/限流时仍可播报
3. **OpenAI TTS（可选）**：最高音质，需 API 调用（成本较高）

**配置项**
| 变量 | 值 | 说明 |
|------|------|------|
| `TTS_MODE` | `auto` | **默认**，优先 edge-tts，失败降级 espeak-ng |
| `TTS_MODE` | `edge` | 强制 edge-tts，失败报错 |
| `TTS_MODE` | `local` | 强制 espeak-ng（离线演示/稳定性测试） |
| `TTS_MODE` | `cloud` | 使用 MBP `/tts`（OpenAI TTS） |

**降级策略（`TTS_MODE=auto` 时生效）**
| 参数 | 值 | 说明 |
|------|------|------|
| `EDGE_TTS_TIMEOUT_SEC` | 2.0 | 单段合成超过 2s 视为失败 |
| `EDGE_TTS_FAIL_THRESHOLD` | 3 | 连续失败 3 次进入降级锁定 |
| `EDGE_TTS_LOCK_SEC` | 300 | 降级锁定 5 分钟，期间直接走 espeak-ng |

**降级流程**
```python
if tts_mode == "auto":
    try:
        audio = await asyncio.wait_for(
            edge_tts.synthesize(text),
            timeout=EDGE_TTS_TIMEOUT_SEC
        )
        edge_fail_count = 0
    except (TimeoutError, NetworkError):
        edge_fail_count += 1
        if edge_fail_count >= EDGE_TTS_FAIL_THRESHOLD:
            enter_degradation_lock()
        audio = espeak_ng.synthesize(text)  # 降级
```

**edge-tts 缓存（可选增强）**

> 目的：降低常见短句/提示语的合成延迟，减少网络抖动

| 配置 | 值 | 说明 |
|------|------|------|
| **缓存 Key** | `(voice, text_normalized)` | text 去首尾空白、折叠连续空白 |
| **缓存 Value** | 音频字节/文件路径 | 合成后的音频 |
| `MAX_CACHE_ITEMS` | 64 | LRU 淘汰 |
| `MAX_TEXT_LENGTH` | 80 | 仅缓存短句（提示语命中率高） |

**命中场景示例**
- "正在识别…"、"正在回答…"、"已取消"、"未提交"
- 常见操作步骤短句（如"请打开浏览器"）

> 注意：缓存不影响降级链路；edge-tts 失败仍按既定策略降级到 espeak-ng

---

#### 7. 文本分段（TTS Buffer）与队列背压

**分段 Flush 规则（满足任一即切段）**
| 条件 | 阈值 | 说明 |
|------|------|------|
| **强标点** | `。！？；\n` 或 `.?!;\n` | 立即切段 |
| **弱标点 + 最小长度** | `，、,:` 且 buffer ≥ 30 字 | 切段（避免断句过短） |
| **最大长度** | buffer ≥ 100 字 | 强制切段（避免等待过久） |
| **时间上限** | 距上次 flush ≥ 1.2s | 保证持续出声 |
| **流结束** | WS `done` | 强制 flush 剩余内容 |

**强标点 `.` 最小保护规则（可选增强）**

> 目的：避免英文缩写、版本号、URL 等场景被句点错误切分

命中强标点 `.` 时，若满足以下任一条件，**不触发 flush**：

| 保护类型 | 匹配规则 |
|----------|----------|
| **缩写白名单** | `e.g.` / `i.e.` / `etc.` / `vs.` / `Mr.` / `Mrs.` / `Ms.` / `Dr.` / `Prof.` |
| **版本号/数字** | 句点前后均为数字（如 `1.2`、`v1.2.3`） |
| **URL/域名** | buffer 含 `http://`/`https://`/`www.` 或 `.com`/`.net`/`.org` 附近的句点 |

> 实现提示：MVP 用简单正则/子串判断即可，目标是"减少明显误切"

**清洗规则**
- 连续空白/换行/标点折叠
- flush 后段文本若为空/仅标点 → 丢弃

**TTS 队列背压**
| 参数 | 值 | 说明 |
|------|------|------|
| `TTS_QUEUE_MAX` | 15 | 队列上限 |
| **超限策略** | 合并尾部未合成段 | 减少合成请求次数 |

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

**外部服务依赖（edge-tts）**
- edge-tts 使用 Microsoft Edge 在线 TTS 服务，语音内容会出网
- 企业环境需评估数据处理与合规要求
- 可通过 `TTS_MODE=local` 强制使用 espeak-ng 离线播报

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
- Claude Sonnet OCR（Vision）：约 $0.003-0.01/张图（比 Opus 便宜）
- GPT-4o OCR（备选）：约 $0.005-0.02/张图
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

### 3.2 按键手势定义（防误触版）

> **设计目标**：把复杂度从用户手势迁移到系统判定与容错，降低高压力/不熟练误触发概率。

#### 3.2.1 阈值参数（建议默认）
- `T_DEBOUNCE_MS = 50`（去抖）
- `T_TAP_MIN_MS = 80`（小于此按压视为抖动，忽略）
- `T_TAP_MAX_MS = 300`（tap 上限）
- `T_PREHOLD_MS = 300`（按住预备态提示阈值）
- `T_HOLD_TO_RECORD_MS = 600`（到达即进入录音态并强反馈）
- `T_HOLD_TO_CANCEL_MS = 1200`（到达即取消/确认，不依赖松开）
- `T_HOLD_MENU_MS = 3000`（仅 Idle 有效，超长按进入菜单确认）

#### 3.2.2 触发规则（关键）
- **Tap（短按）**：松开后若 `80–300ms` → **立即触发**短按动作（Idle=拍照；Answering=静音切换；MenuConfirm=取消），**无延迟**
- **Pre-hold（按住预备态）**：按住达到 300ms 进入预备态（只反馈、无副作用），松开在 300–600ms 仍然无动作（但用户已看到提示）
- **Hold-to-talk（按住说话）**：按住达到 `600ms` → 立即进入 Recording（强反馈）；松开 → 结束录音并进入“有效性判定”（通过才走 STT）
- **Hold-to-cancel/confirm（长按取消/确认）**：在 Busy/Answering/MenuConfirm 中，按住达到 `1200ms` 即立刻执行取消/确认（**不等待松开**）
- **Menu（Idle 超长按进入菜单确认）**：仅在 Idle 且未进入 Recording 前有效；按住达到 `3000ms` 即进入 MenuConfirm（不执行清库，仅进入确认态）。进入 Recording（600ms）后，本次按压不再触发菜单

#### 3.2.3 强反馈（必须）
- 到达 300ms：LED 蓝色变亮/轻呼吸 + LCD line2 显示“继续按住…”
- 到达 `600ms`（进入录音态）：
  - LED：蓝 → 黄（常亮）
  - LCD：主图标切换 🎤，提示语切为“松开结束”
  - 可选：提示音“滴”一次（≤100ms）
- 到达 `1200ms`（取消/确认）：
  - 在到达瞬间立即执行动作（取消/确认）
  - LCD 给出“已取消/已确认”提示，保持 800ms 后回 Idle

### 3.3 状态定义

#### S0 Idle（待机）
| 项目 | 值 |
|------|------|
| 主图标 | 📷（若有最近照片则显示缩略图） |
| 提示语 | 短按拍照 / 按住说话 / 超长按3s菜单 |
| 底部第一行 | 待机 |
| 底部第二行 | 会话: N张（或 Ready） |
| LED | 🔵 蓝色常亮 |
| 短按 | 拍照 → 入库（转 Busy） |
| 长按保持 | 开始录音（转 S1） |
| 超长按 ≥3s | 进入 S6 菜单 |

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
| 超长按 ≥3s | 进入 S6 菜单 |

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

[Idle] ─超长按≥3s→ [S6 MenuConfirm] ─长按1.2s→ [清库] → [S0]
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

### 3.5 事件与触发点（防误触规则）

| 事件 | 触发点 | 适用状态 | 说明 |
|------|--------|----------|------|
| `EVT_TAP` | 松开后判定 80–300ms **立即触发** | Idle/Answering/MenuConfirm | Idle=拍照；Answering=静音切换；MenuConfirm=取消（**无延迟**） |
| `EVT_HOLD_RECORD_REACHED` | 按住达到 600ms | Idle → Recording | **到达即切换录音态**（强反馈），避免用户犹豫松手误触发 |
| `EVT_HOLD_CANCEL_REACHED` | 按住达到 1200ms | Busy/Answering/MenuConfirm | **到达即取消/确认，不依赖释放时机** |
| `EVT_HOLD_MENU_REACHED` | 按住达到 3000ms | Idle → MenuConfirm | 仅 Idle 有效；进入 Recording 后本次按压不触发菜单 |

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
   - MBP：**Claude Sonnet（Vision）OCR（主）** → 切块 → Embedding → Qdrant upsert
   - **回退策略**：若 OCR 超时/失败 → **GPT-4o Vision OCR（备选）** → 切块 → Embedding → Qdrant upsert
3. 用户 **长按（Push-to-Talk）** → arecord 开始录音 → LCD 显示录音时长
4. 用户 **松开** → 录音结束  
4.1 Device Agent **本地有效性判定**（防误触）：录音时长 < 1s（或静音占比过高）→ 不提交 STT/问答，提示“未提交”，回 Idle  
5. Device Agent → MBP：`POST /upload/audio?session_id=...`（仅在有效录音时触发）
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

1. 用户 **超长按 ≥3s** → 状态转为 menu → LCD 显示"新建会话？长按确认"
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

**统一错误分类（UI 映射表）**

| 错误码 (Enum) | 触发场景 | LCD line1 | LCD line2 示例 | 交互建议 |
|---|---|---|---|---|
| **NET** | 后端不可达 / WS 断线 / API 超时 | 网络错误 | 检查连接/MBP | 短按重试 |
| **STT** | 录音过短 / 静音 / 识别空 | 无法识别 | 请大声一点 | 长按重录 |
| **OCR** | 拍照失败 / 入库超时 / 识别失败 | 识别失败 | 请靠近重拍 | 短按重拍 |
| **AUDIO** | 麦克风/扬声器故障 / 驱动丢失 | 设备故障 | 检查声卡 | 长按取消 |

> **LED 行为**：所有错误状态下均为 🔴 红色常亮。

---


## 7. 接口契约（最终 MVP）

### 7.1 Session

**POST /session**
- Resp: {session_id, created_at}

**DELETE /session/{session_id}**
- Resp（建议）：{deleted, qdrant_deleted, cache_deleted}

### 7.2 Upload

**POST /upload/image?session_id=…（multipart）**
- Resp：{image_id, num_chunks, ingest_ms, dedup_skipped?, ocr_provider, fallback_used, ocr_ms}

**POST /upload/audio?session_id=…（multipart）**
- Resp：{question_text, stt_ms}

### 7.2.1 OCR Provider 策略（即拍即问优先）

> **设计目标**：避免拍照后等待 10 秒的 Opus 延迟，确保即拍即问体验

**默认策略**
- **主 OCR**：Claude Sonnet（Vision）— 快速、成本适中
- **备选 OCR**：GPT-4o（Vision）— 超时/失败回退

**超时与回退（必须）**
| 参数 | 值 | 说明 |
|------|------|------|
| `OCR_PRIMARY_TIMEOUT_SEC` | 4.0 | 超过 4s 未完成，触发回退 |
| `OCR_FALLBACK_TIMEOUT_SEC` | 6.0 | 备选仍失败，返回 error |

**返回结构增强（用于可观测性与验收）**
| 字段 | 说明 |
|------|------|
| `ocr_provider` | `"claude_sonnet"` / `"gpt4o"` |
| `fallback_used` | `true` / `false` |
| `ocr_ms` / `chunk_ms` / `embed_ms` / `qdrant_ms` | 各阶段耗时 |

> 说明：超时阈值可根据实测调整，但必须在设计中固化为 SLA

### 7.3 WebSocket

**WS /ws/chat?session_id=…**
- Client → {question_text, top_k}
- Server → 流式：
  - {type:"meta", trace_id, retrieved}
  - 多条 {type:"token", text}
  - {type:"done", total_ms}

### 7.4 TTS（语音合成）

> **TTS 路径选择**（P1 明确）：
> - **默认策略**：混合模式（Auto），优先使用 edge-tts，失败自动降级到 espeak-ng
> - **云端模式**：TTS_MODE=cloud，强制使用 OpenAI TTS

**TTS 模式配置**

> 模式配置详见下方《TTS 模式配置（以本表为准）》。

> MVP 阶段默认使用 **edge-tts**（Pi 端，自然语音、免费），失败自动降级到 espeak-ng。在需要最高音质的演示场景可切换到云端 OpenAI TTS。

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

**本地 TTS（降级/离线路径）**

> Auto 默认优先 edge-tts；以下示例用于降级/离线模式验证音频链路。

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

> **说明**：
> - mDNS 需 Pi 启用 `avahi-daemon` 服务
> - 若 mDNS 不可用，则回退到 `config.toml` 或默认 IP
> - **优先级**：`MBP_HOST` (env) > `config.toml` > mDNS > 默认 (localhost)

**断线重连策略**

| 阶段 | 行为 |
|------|------|
| 连接失败 | 5s 后重试，最多 3 次 |
| 重试失败 | 进入 Error 状态，显示 NET 错误码 |
| 用户操作 | 短按重试，长按取消 |

**TTS 模式配置（以本表为准）**

| 配置项 | 值 | 说明 |
|--------|------|------|
| `TTS_MODE` | `auto` | **默认**，优先 edge-tts，失败降级 espeak-ng |
| `TTS_MODE` | `edge` | 强制 edge-tts，失败报错（调试/对比用） |
| `TTS_MODE` | `local` | 强制本地 espeak-ng（调试/离线用） |
| `TTS_MODE` | `cloud` | 使用 MBP `/tts`（OpenAI TTS，高音质演示用） |

```bash
# 环境变量方式
export TTS_MODE=auto   # 默认：edge-tts 优先，失败降级 espeak-ng
export TTS_MODE=cloud  # 演示场景：OpenAI TTS
export TTS_MODE=local  # 调试/离线：强制 espeak-ng
# export TTS_MODE=edge # 调试：强制 edge-tts（失败报错）
```
```toml
# 或 config.toml
[tts]
mode = "auto"  # auto | edge | local | cloud
```

**降级策略**
- `TTS_MODE=cloud` 时，若 `/tts` 请求失败（`API_TTS` 错误），**自动降级到本地 TTS**
- 降级后本轮问答继续使用本地 TTS，下一轮恢复尝试云端

---

### 7.6 MBP 后端职责详细

**FastAPI 单体服务，监听 0.0.0.0:8000**
- 会话管理：POST /session、DELETE /session/{id}
- 图片入库（OCR/RAG ingestion）：
  - **Claude Sonnet（Vision）OCR（主）** → block 切块（200–500 chars）→ OpenAI Embedding → Qdrant upsert
  - **备选**：GPT-4o Vision OCR（超时回退）
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
- Vision OCR 输出 block（段落/块）（主：Claude Sonnet；备：GPT-4o）
- 二次切分到 200–500 chars
- embedding 入库

### 8.3 检索策略
- TopK=6（默认）
- 仅取 text 进 prompt（暂不返回引用）

### 8.4 回答模板（步骤化）

输出必须满足：
- 操作步骤（编号）
- 前置条件/注意事项/风险提示 至少一项

### 8.5 本地缓存策略（文件与存储）

- **统一路径**: `/tmp/snap2know_cache/`
  - 使用 RAM disk (tmpfs) 避免 SD 卡损耗
  - 重启自动清理（依赖 OS 机制）
- **文件管理**:
  - 结构：`/tmp/snap2know_cache/{session_id}/{type}_{timestamp}.{ext}`
  - 类型：`images/`, `audio/`, `tts/`
- **清理策略**:
  - **启动时**: 强制清空 `/tmp/snap2know_cache/`
  - **新会话/结束会话**: 递归删除旧 `session_id` 目录
  - **运行时保护**: 单个会话内每类文件保留最近 **20** 个（FIFO），防止长会话爆内存

### 8.6 Pi 端 TTS 分段与播放（Device Agent）

**目标：** 流式体验 + 连贯语音（支持中断、可降级）

- 分段/清洗/背压规则遵循《文本分段（TTS Buffer）与队列背压（必须）》章节（含 `.` 断句保护与队列背压策略）
- Pi 端实现仅负责：token → buffer → 按规则 flush → tts_queue → 播放  
- **重要语义区分**：
  - **停止播报（Stop Playback）**：仅停止当前发声与清空播放队列，不影响 WS 是否继续接收文本
  - **取消问答（Cancel Round）**：关闭/忽略 WS 后续 token + 停止播报 + 回 Idle

---

#### 实现机制（v1 示例：本地 TTS/调试用）

> 说明：本代码块是“机制示例”。真正的 flush 判定应调用统一分段器（实现于《文本分段…》章节），其中包含 `.` 断句保护（缩写/版本号/URL）与背压合并策略。

```python
import queue, time, subprocess, tempfile, os
from threading import Event, Lock

# === 全局配置（与文档前文章节保持一致） ===
TTS_QUEUE_MAX = 15
AUDIO_DEVICE = "plughw:1,0"  # 示例：实际由启动探测/配置注入
FLUSH_TIME_LIMIT_SEC = 1.2
FLUSH_MAX_CHARS = 100

# === 状态与同步 ===
tts_buffer = ""
tts_queue = queue.Queue(maxsize=TTS_QUEUE_MAX)
last_flush_ts = 0.0

# cancel_round_event：代表“取消本轮问答”（忽略后续 token）；stop_playback 不应 set 它
cancel_round_event = Event()

# 进程句柄（用于可中断播放）
proc_lock = Lock()
current_aplay = None
current_tts_proc = None  # 可选：用于终止正在合成的 TTS

def segmenter_should_flush(buffer: str, now: float, last_flush: float, is_done: bool=False) -> bool:
    """
    统一分段器入口（示例最小实现）：
    - done 强制 flush
    - 时间上限 flush
    - 强标点 flush（实际实现需含 '.' 保护：缩写/版本号/URL 等）
    - 最大长度 flush
    """
    if is_done and buffer.strip():
        return True
    if now - last_flush >= FLUSH_TIME_LIMIT_SEC and buffer.strip():
        return True

    # 强标点（示例）：实际版本应在 '.' 处做保护判断
    strong_punct = ["。", "！", "？", "；", "\n", ".", "!", "?", ";"]
    if any(p in buffer for p in strong_punct) and len(buffer.strip()) >= 6:
        return True

    if len(buffer) >= FLUSH_MAX_CHARS:
        return True

    return False

def flush_segment(is_done: bool=False):
    global tts_buffer, last_flush_ts
    now = time.time()
    if segmenter_should_flush(tts_buffer, now, last_flush_ts, is_done=is_done):
        segment = tts_buffer.strip()
        tts_buffer = ""
        last_flush_ts = now
        if segment:
            # 背压：队列满时可选择“合并尾段”而非丢弃（详见前文章节）
            tts_queue.put(segment)

def on_token(token: str):
    global tts_buffer
    if cancel_round_event.is_set():
        return
    tts_buffer += token
    flush_segment(is_done=False)

def on_done():
    flush_segment(is_done=True)

def stop_playback():
    """
    停止播报：只影响“发声”，不取消本轮问答（WS 仍可继续接收并累计文本/或继续显示 UI）。
    """
    # 清空播放队列
    while not tts_queue.empty():
        try:
            tts_queue.get_nowait()
        except Exception:
            break

    # 终止当前播放进程
    with proc_lock:
        if current_aplay and current_aplay.poll() is None:
            # terminate 不一定立刻停，必要时可 kill
            current_aplay.terminate()

def cancel_round():
    """
    取消本轮问答：忽略后续 token + 停止播报（用于 Busy/Answering 的长按取消）。
    """
    cancel_round_event.set()
    stop_playback()

def start_new_round():
    """
    新一轮问答开始前调用：清除“取消本轮”标志，使后续 token 可进入 buffer/队列。
    """
    cancel_round_event.clear()

def tts_worker():
    global current_aplay, current_tts_proc
    while True:
        segment = tts_queue.get()

        # 如果已取消本轮，丢弃队列段
        if cancel_round_event.is_set():
            continue

        # 生成临时 wav，避免覆盖
        fd, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        try:
            # v1（oneshot，调试用）：espeak-ng → wav → aplay
            # 若你需要“可终止合成”，可用 Popen 保存 current_tts_proc 并在 stop/cancel 时 kill
            current_tts_proc = subprocess.Popen(["espeak-ng", "-v", "zh", "-w", wav_path, segment])
            current_tts_proc.wait()

            with proc_lock:
                current_aplay = subprocess.Popen(["aplay", "-D", AUDIO_DEVICE, wav_path])

            current_aplay.wait()

        finally:
            try:
                os.remove(wav_path)
            except Exception:
                pass

```
                
**取消/停止语义**：
| 场景 | 行为 |
|------|------|
| 长按停止播报 | 终止当前 aplay 进程（terminate/kill）+ 清空队列；（可选）终止当前 TTS 合成进程 |
| 长按取消录音 | `kill arecord` + 丢弃音频 |
| 长按取消问答 | 关闭 WS + 停止播报 + 返回 idle |

---

#### WM8960 Pop/Click 风险（已知硬件特性）与缓解策略

**风险说明：**
- WM8960 在 Linux ALSA 下，当 PCM 流频繁 open/close、mute/unmute、或功放使能切换时，硬件侧可能产生瞬态 **pop/click（“啪”声）**。
- 当前若采用“每段 TTS 都启动一次 `aplay` 播放并退出”的机制，将导致 PCM 流频繁开关，pop/click 风险显著升高，尤其在流式分段较碎时会被放大为“每段一句啪一下”。

**MVP 缓解策略（优先级从高到低）：**
1) **首选：播放流常驻（推荐）**  
   - 使用“`aplay` 常驻 + pipe 喂 raw PCM”或“Python 持久 PCM stream write”的方式：一次打开 PCM，持续写入音频，避免频繁 open/close。
2) **段间淡入淡出（可选）**  
   - 对每段音频增加 5–10ms fade-in/fade-out，并在段间插入 20–50ms 静音 padding，减少波形突变引发的 click（对 open/close pop 缓解有限）。
3) **减少段数量（可选）**  
   - 增大弱标点切分最小长度、提高 flush 时间上限、启用队列背压的尾段合并，降低播放段数。
4) **Mixer/驱动层尝试（可选）**  
   - 检查 `amixer` 是否提供 soft-mute/anti-pop 控件；若存在可在初始化时开启（视驱动暴露情况而定）。

> 现象提示：若出现“每段/每句稳定啪一下”的 pop/click，优先确认是否走 v2 常驻流；若仍存在，再考虑淡入淡出、减少段数或 amixer 控件等进一步缓解。

---

#### 推荐实现（v2）：`aplay` 常驻 + Pipe 喂 PCM（降低 pop/click）

> ⚠️ **v2 为默认启用**：默认配置必须走 v2，仅用于验证/调试时可临时切回 v1

**实现选择**
| 版本 | 机制 | 适用场景 |
|------|------|----------|
| **v2（默认）** | `aplay` 常驻 + pipe 喂 raw PCM | **生产默认**，Pop/Click 最小化 |
| v1 | 每段启动 `aplay` 播放后退出 | 仅用于快速验证/调试，**不作为默认** |

**配置项（推荐）**

- `PLAYBACK_MODE` = `persistent` (默认) | `oneshot` (调试)

```bash
# 环境变量
export PLAYBACK_MODE=persistent  # 生产默认：常驻流 (v2)
export PLAYBACK_MODE=oneshot     # 调试：单次播放 (v1)
```

```toml
# config.toml
[audio]
playback_mode = "persistent"  # persistent | oneshot
```

> **验收要求**：生产环境必须配置为 `persistent` (v2)。

**语义约束（v2 路径）**
| 函数 | 行为 | 是否关闭 WS |
|------|------|-------------|
| `stop_playback_stream()` | 清空队列 + 写静音 padding，**仅停止发声** | ❌ 不关闭 |
| `cancel_round()` | 关闭/忽略 WS 后续 token + `stop_playback_stream()` + 回 Idle | ✅ 关闭 |

> 思路：只打开一次 ALSA PCM 流，后续把每段语音转换为统一格式的 raw PCM 并持续写入 `aplay` stdin，避免每段启动/退出导致的 pop/click。

**约定统一音频格式：**
- `SAMPLE_RATE = 16000`
- `CHANNELS = 1`
- `FORMAT = S16_LE`

> **Note**: 所有 TTS 输出（edge-tts/OpenAI/espeak）在写入常驻流前**必须**统一重采样到上述 FORMAT (16k/mono/s16le)，以避免 aplay 异常。

```python
import subprocess, queue, tempfile, os

SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = "S16_LE"

tts_queue = queue.Queue(maxsize=TTS_QUEUE_MAX)

# 1) 启动常驻 aplay（从 stdin 读取 raw PCM）
aplay_proc = subprocess.Popen(
    ["aplay", "-D", AUDIO_DEVICE, "-f", FORMAT, "-r", str(SAMPLE_RATE), "-c", str(CHANNELS)],
    stdin=subprocess.PIPE
)

def write_pcm(pcm_bytes: bytes):
    if aplay_proc.poll() is not None:
        raise RuntimeError("aplay exited")
    aplay_proc.stdin.write(pcm_bytes)
    aplay_proc.stdin.flush()

def tts_to_pcm_bytes(text: str) -> bytes:
    """
    示例：本地 TTS 先生成 wav，再用 ffmpeg 转 raw PCM。
    也可以直接使用支持输出 raw 的 TTS 或库。
    """
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    raw_path = wav_path.replace(".wav", ".raw")
    try:
        subprocess.run(["espeak-ng", "-v", "zh", "-w", wav_path, text], check=False)
        subprocess.run(
            ["ffmpeg", "-y", "-i", wav_path, "-f", "s16le", "-acodec", "pcm_s16le",
             "-ac", str(CHANNELS), "-ar", str(SAMPLE_RATE), raw_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
        )
        with open(raw_path, "rb") as f:
            return f.read()
    finally:
        for p in [wav_path, raw_path]:
            try: os.remove(p)
            except: pass

def tts_worker_streaming():
    while True:
        segment = tts_queue.get()
        pcm = tts_to_pcm_bytes(segment)
        write_pcm(pcm)

def stop_playback_stream():
    """
    停止播报（不取消问答）：不建议频繁重启 aplay（会把 pop 风险带回来）。
    推荐：清空队列 + 写入 50ms 静音 padding。
    """
    while not tts_queue.empty():
        try: tts_queue.get_nowait()
        except: break
    silence_50ms = b"\x00\x00" * int(SAMPLE_RATE * 0.05)  # 16-bit mono
    write_pcm(silence_50ms)
```

**验收建议**
- 连续播报 20 段以上分段语音，主观听感不应出现"每段都啪一下"的稳定 pop/click
- 若出现，优先切换到"播放流常驻"实现

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
- ffmpeg（用于音频转码：wav → s16le raw PCM，以支持 v2 常驻播放流；pop/click 的核心缓解来自"常驻流避免频繁 open/close"，非 ffmpeg 本身）
- Pillow（LCD 渲染）
- picamera2（摄像头）
- Whisplay Driver（LCD/LED/按键）
- arecord/aplay（ALSA 音频）
- edge-tts（TTS 默认，自然语音、免费）
- espeak-ng（TTS 降级/离线模式）
- httpx, websockets（后端通信）

**音频设备配置**：
```bash
# 启动时探测 WM8960 声卡号
CARD_NUM=$(aplay -l | grep -i wm8960 | head -1 | sed 's/card \([0-9]*\):.*/\1/')
export AUDIO_DEVICE="plughw:${CARD_NUM},0"
```

**全局默认声卡设置（推荐）**：

> 目的：防止 `espeak-ng` 等工具忽略 `-D` 参数而使用 HDMI/耳机孔

```bash
# /etc/asound.conf（安装驱动后配置一次）
cat > /etc/asound.conf << 'EOF'
pcm.!default {
    type plug
    slave.pcm "plughw:wm8960"
}

ctl.!default {
    type hw
    card wm8960
}
EOF
```

> 说明：如果 WM8960 声卡名称不固定，可改用动态 card 编号（如 `plughw:1,0`）

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
> - TTS：edge-tts（默认）/ espeak-ng（降级）/ 云端 OpenAI（可选，TTS_MODE=cloud）
> - 状态协议：UIState dataclass

---

### Day 0：硬件准备 + 最小硬件验收（前置工作）

> ⚠️ **必须在 Day 1 之前完成**，确保硬件环境就绪

| 步骤 | 任务 | 详细文档 |
|------|------|----------|
| **0.1** | Pi 操作系统安装 | [Day-0.1-Pi 操作系统安装.md](docs/Day0/Day-0.1-Pi%20操作系统安装.md) |
| **0.2** | Whisplay HAT 驱动安装 | [Day-0.2-Whisplay驱动安装.md](docs/Day0/Day-0.2-Whisplay驱动安装.md) |
| **0.3** | 摄像头驱动安装 | [Day-0.3-摄像头驱动安装.md](docs/Day0/Day-0.3-摄像头驱动安装.md) |
| **0.4** | 最小硬件验收 | [Day-0.4-最小硬件验收.md](docs/Day0/Day-0.4-最小硬件验收.md) |

**验收标准**

运行 `hardware_test.py`，所有测试通过：

```bash
sudo python3 /opt/script/hardware_test.py

# 预期输出：
# ✅ LED 测试通过
# ✅ LCD 测试通过
# ✅ 按键测试通过
# ✅ 音频测试通过
# ✅ 摄像头测试通过
# ✅ 所有硬件测试通过！可以开始 Day 1 开发。
```

---

### Week 1：后端 + Device Agent 核心链路

---

#### Day 1：MBP 基础设施 + 会话 API

> 详细步骤参见 [Day1-MBP基础设施-会话API.md](docs/Day1/Day1-MBP基础设施-会话API.md)

**交付**
- Qdrant Docker Compose 部署
- FastAPI 骨架：`/health`、会话 CRUD API

**验收**
```bash
curl http://localhost:6333/healthz        # Qdrant 健康检查
curl http://localhost:8000/health         # FastAPI 健康检查
curl -X POST http://localhost:8000/session  # 创建会话
```

---

#### Day 2：STT + TTS API

> 详细步骤参见 [Day2-STT-TTS.md](docs/Day2/Day2-STT-TTS.md)

**交付**
- `POST /upload/audio` → OpenAI Whisper STT → 返回识别文本
- `POST /tts` → edge-tts（默认）/ OpenAI TTS（cloud 模式）→ 音频流返回
- `GET /tts/info` → TTS 配置信息

**验收**
```bash
curl http://localhost:8000/tts/info                    # TTS 配置
curl -X POST -d '{"text":"测试"}' http://localhost:8000/tts --output test.mp3  # TTS
curl -X POST -F "audio=@test.mp3" "http://localhost:8000/upload/audio?session_id=xxx"  # STT
```

---

#### Day 3：OCR 入库（图片→切块→Qdrant）

**交付**
- POST /upload/image → **Claude Sonnet（Vision）OCR（主）** → 切块 → Embedding → Qdrant
- 回退：OCR 超时/失败 → **GPT-4o Vision OCR（备选）** → 切块 → Embedding → Qdrant

**验收**
```bash
# 1. 上传路由器说明书照片
curl -X POST -F "image=@router_manual.jpg" \
  "http://localhost:8000/upload/image?session_id=xxx"
# 返回 {image_id, num_chunks: 12, ingest_ms: 3456, ocr_provider: "claude_sonnet"}

# 2. 验证 Qdrant 数据
curl "http://localhost:6333/collections/snap2know_chunks/points/count?filter=..."
# count > 0

# 3. 体验型 SLA 验收（避免"拍照后等待 10 秒"）
# 期望：局域网正常、MBP 空闲时，ingest_ms 在多数情况下较短
# - p95 ingest_ms <= 4000ms（建议目标，可按实测调整）
# - 若 OCR 端超时/失败，应自动回退到备选模型，最终仍成功入库（count > 0）

# 4. 回退路径验收（故意触发主 OCR 超时/失败）
# 方法示例：临时把 OCR 主模型 timeout 配得很小（如 0.5s）或断开主模型出网
# 预期：返回中 fallback_used=true 且 ocr_provider="gpt4o"，并最终 num_chunks>0
```

---

#### Day 4：WS 流式问答

> 详细步骤参见 [Day4-WS流式问答.md](docs/Day4/Day4-WS流式问答.md)

**交付**
- `WS /ws/chat` → RAG 检索 → Claude Sonnet → 流式 token 返回
- 消息类型：`meta` / `token` / `done` / `error`

**验收**
```bash
python test_ws_chat.py
# [META] 检索到 N 条文档, 上下文 tokens
# [TOKEN] 流式输出回答...
# [DONE] 耗时 xxxms, tokens=xxx
```

---

#### Day 5：Pi Device Agent 骨架 + 硬件封装

> 详细步骤参见 [Day5-Pi-Device-Agent骨架-硬件封装.md](docs/Day5/Day5-Pi-Device-Agent骨架-硬件封装.md)

**交付**
- Device Agent Python 服务（运行于 Pi）
- 硬件封装模块：
  - `Camera` - picamera2 拍照
  - `Audio` - WM8960 录音/播放
  - `Button` - GPIO 按键监听（gpiod，Pi 5 兼容）
  - `LED` - RGB LED 控制（gpiod）
  - `LCD` - SPI 显示（PIL/Pillow）

**验收**
```bash
# 同步代码到 Pi
rsync -avz device_agent/ mars@raspberrypi:/opt/snap2know/device_agent/

# 远程测试
ssh -t mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && cd device_agent && python main.py"

# 预期输出：
# [TEST] LED: OK ✅
# [TEST] LCD: OK ✅
# [TEST] Button: OK ✅
# [TEST] Camera: OK ✅
# [TEST] Audio: OK ✅
```

---

#### Day 6：Device Agent 状态机 + LCD 渲染

> 详细步骤参见 [Day6-Device-Agent-状态机-LCD渲染.md](docs/Day6/Day6-Device-Agent-状态机-LCD%20渲染.md)

**交付**
- 状态机：Idle/Pre-Hold/Recording/Processing/Answering/Done/Menu/Error/Busy
- 按键事件：短按/预按住/长按/超长按
- LCD 渲染 + LED 同步

**验收**
```bash
# 同步代码到 Pi
sync-pi

# 启动 Device Agent
ssh -t mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && cd device_agent && python main.py"
# 短按→Busy→Idle, 长按→Recording→Processing→Done, 超长按→Menu

```

---

#### Day 7：Device Agent MBP 通信 + 音频处理

> 详细步骤参见 [Day7-Device-Agent-MBP通信-音频处理.md](docs/Day7/Day7-Device-Agent-MBP通信-音频处理.md)

**交付**
- `services/mbp_client.py`：HTTP/WebSocket 通信客户端
- `services/tts_player.py`：TTS 分段播放器
- `main.py`：集成 MBP 通信完整流程

**验收**
```bash
# 同步代码
sync-pi

# 启动 Device Agent
ssh -t mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && cd device_agent && python main.py"

# 短按 → 拍照入库，长按 → 录音问答
```

**测试结果**
- [x] 健康检查 + 会话创建
- [x] 上传图片 → OCR 入库成功
- [x] WebSocket 流式问答
- [x] TTS 分段播报设计
- ⚠️ LCD 显示：Pi 5 GPIO 问题，暂用预览模式

---

### Week 2：集成 + Demo + 文档

---

#### Day 8：LCD 状态渲染完善 + TTS 播放修复 ✅ 完成

> 详细步骤参见 [Day8-LCD状态渲染完善.md](docs/Day8/Day8-LCD%20状态渲染完善.md)

**交付**
- `hardware/lcd.py`：使用官方 WhisplayBoard 驱动
- `hardware/button.py`：WhisplayBoard 按钮回调集成
- `services/tts_player.py`：修复播放循环时序问题
- `hardware/audio.py`：修复 MP3 格式检测

**验收**
```bash
# 启动 Device Agent（需要 sudo 访问 GPIO）
ssh -t mars@raspberrypi "cd /opt/snap2know/device_agent && sudo /opt/snap2know/.venv/bin/python main.py"

# 短按 → 拍照入库
# 长按 2-4 秒 → 录音 → STT → Q&A → TTS 播放
```

**测试结果（2026-01-20）**
- [x] LCD 显示就绪状态：蓝色背景 + "就绪" + 中文正常
- [x] LCD 显示录音状态：红色背景 + "录音中..."
- [x] LCD 显示处理状态：黄色背景 + "处理中..."
- [x] 短按拍照：拍照 → 上传 → OCR 完成
- [x] 长按录音：录音 → STT → Q&A → TTS 播放
- [x] TTS 语音播放：清晰播放回复内容

---

#### Day 9：全链路集成测试 ✅ 完成

> 详细步骤参见 [Day9-全链路集成测试.md](docs/Day9/Day9-全链路集成测试.md)

**交付**
- 完整问答链路：拍照 → 录音 → STT → OCR → 问答 → TTS
- LCD 尺寸修复：240x240 → 240x280
- 所有状态 LCD 显示验证

**测试结果（2026-01-21）**
- [x] Test 1：启动与连接
- [x] Test 2：短按拍照入库
- [x] Test 3：长按录音问答
- [x] Test 4：上下文问答
- [x] Test 5：菜单显示（交互待开发）
- [ ] Test 6：新建会话（待开发）
- [x] Test 7：错误处理
- [x] Test 8：播放取消

**LCD 状态验收**
- [x] idle：📷 + 蓝色 LED + "就绪"
- [x] recording：🎤 + 红色 LED + 时长
- [x] busy：⏳ + 黄色 LED + "处理中..."
- [x] answering：▶ + 绿色 LED + "播放中..."
- [x] error：⚠ + 红色 LED + 错误信息
- [x] menu：☰ + 菜单选项

---

#### Day 10：稳定性 + 边界情况

**交付**
- 连续 10 次问答测试
- 异常场景处理（断网、API 超时、麦克风故障）
- 资源清理（临时文件、内存泄漏检查）

**验收**
- [ ] 连续 10 次问答成功率 ≥ 90%
- [ ] 断网时 5s 内显示错误状态
- [ ] 重连后可恢复正常工作
- [ ] 无内存泄漏（htop 监控）

**TTS 体验与降级验收**
- [ ] `TTS_MODE=auto`：edge-tts 可用时播报自然，无机械音
- [ ] 断网/限流模拟：单段 2s 超时后自动降级到 espeak-ng，整轮问答不中断
- [ ] 连续失败 3 次：触发 5 分钟降级锁定，期间直接走 espeak-ng
- [ ] 分段自然性：连续 10 句播报无"怪断句/空读/重复读"

**v2 常驻播放流默认启用验收（必须）**
- [ ] 默认配置（未显式切到 v1/调试模式）下，必须使用 **v2 常驻流**（`aplay` 常驻 + pipe 喂 PCM）
- [ ] **不得**出现"每个 segment 启动一次 `aplay` 并退出"及其引发的稳定 pop/click
- [ ] 验证：`ps -ef | grep aplay` 见长驻进程 或 日志 `audio_mode=v2` 持续

**断句保护验收（可选）**
- [ ] 句子含 `e.g.` / `v1.2.3` / URL 时，播报不在句点处产生不自然停顿

---

#### Day 11：Demo 脚本 + Prompt 固化

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

#### Day 12：文档 + 一键启动

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

#### Day 13：最终验收 + Buffer

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
| **TTS** | ✅ edge-tts（默认）/ espeak-ng（降级） | 自然语音、免费、离线可用 |
| **按键交互** | ✅ 单键 Push-to-Talk | 短按/长按/超长按 |
| **状态机** | ✅ 7 状态（含 Busy 子阶段） | 优先级显示 + 800ms 驻留 |
| **状态协议** | ✅ UIState dataclass | 单一真相源 |

