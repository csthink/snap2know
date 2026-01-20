# Day 6：Device Agent 状态机 + LCD 渲染

> **目标**：实现完整的设备状态机，包含按键交互、LED 状态同步和 LCD 界面渲染

## 前置要求

- ✅ Day 5 完成（硬件封装模块就绪）
- Device Agent 在 Pi 上可正常启动
- 所有硬件模块测试通过

---

## 交付内容

- 完整状态机实现（Idle → Recording → Processing → Answering → Done）
- 按键事件处理（短按/长按/超长按）
- LCD UI 渲染（PIL/Pillow 绘制）
- LED 颜色状态同步

---

## 项目结构

```
device_agent/
├── services/
│   ├── __init__.py
│   ├── state_machine.py     # 状态机核心
│   ├── button_handler.py    # 按键事件处理
│   └── lcd_renderer.py      # LCD 渲染器
└── main.py                  # 更新：集成状态机
```

---

## 状态定义

| 状态 | LED | LCD | 说明 |
|------|-----|-----|------|
| **Idle** | 🔵 蓝色 | 待机 + 提示 | 空闲 |
| **Pre-Hold** | 🔵 闪烁 | "继续按住..." | 按下 300ms |
| **Recording** | 🔴 红色 | 🎤 + 时长 | 录音中 |
| **Processing** | 🟡 黄色 | ⏳ + 处理中 | STT/OCR |
| **Answering** | 🟢 绿色 | 💬 + 回答 | TTS 播放 |
| **Done** | 🔵 蓝色 | ✅ 完成 | 短暂显示 |
| **Menu** | 🟣 紫色 | 菜单选项 | 超长按 |
| **Error** | 🔴 闪烁 | ❌ 错误 | 异常 |
| **Busy** | 🟡 黄色 | 📷 拍照中 | 短按拍照 |

---

## 按键时间阈值

| 事件 | 时长 | 动作 |
|------|------|------|
| **短按** | < 300ms | 拍照入库 |
| **预按住** | 300-600ms | 显示预反馈 |
| **长按** | ≥ 600ms | 开始录音 |
| **超长按** | ≥ 3000ms | 进入菜单 |
| **取消** | ≥ 1200ms（在特定状态） | 取消操作 |

---

## 代码同步

```bash
# MBP 上已配置别名
sync-pi

# 或手动执行
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude '.env' \
  ~/sourceCode/personal/ai/Snap2Know/device_agent/ mars@raspberrypi:/opt/snap2know/device_agent/
```

---

## 验收测试

### 状态机测试

```bash
ssh mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && cd device_agent && python -c \"
from services import StateMachine, LCDRenderer, State, RenderData

sm = StateMachine()
lcd = LCDRenderer()

sm.set_callbacks(
    on_state_change=lambda o, n, d: print(f'State: {o.name} -> {n.name}'),
    on_lcd_update=lambda s, d: lcd.render(s.name.lower(), RenderData())
)

sm.transition_to(State.IDLE)
sm.transition_to(State.RECORDING)
sm.transition_to(State.PROCESSING)
sm.transition_to(State.DONE)
print('Test passed!')
\""
```

**输出**：
```
State: IDLE -> RECORDING
State: RECORDING -> PROCESSING
State: PROCESSING -> DONE
Test passed!
```

### 按键事件测试

```bash
ssh mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && cd device_agent && python -c \"
from services import ButtonHandler
import time

handler = ButtonHandler()
events = []

handler.set_callbacks(
    on_tap=lambda: events.append('tap'),
    on_pre_hold=lambda: events.append('pre_hold'),
    on_hold_start=lambda: events.append('hold_start'),
    on_hold_end=lambda d: events.append(f'hold_end:{d:.1f}s'),
    on_long_hold=lambda: events.append('long_hold')
)

# 短按测试
handler.on_press(); time.sleep(0.2); handler.on_release()
print(f'Tap: {events}'); events.clear()

# 长按测试
handler.on_press(); time.sleep(2.0); handler.on_release()
print(f'Hold: {events}')
\""
```

**输出**：
```
Tap: ['tap']
Hold: ['pre_hold', 'hold_start', 'hold_end:1.4s']
```

### 完整流程测试

```bash
# 启动 Device Agent
ssh -t mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && cd device_agent && python main.py"
```

**物理测试**：
1. 启动后 LCD 显示 Idle 界面，LED 蓝色 ✅
2. 短按 → Busy 状态 → 回到 Idle ✅
3. 长按 600ms → Recording（LED 红色）→ 松开 → Processing → Done ✅
4. 超长按 3s → Menu 界面 ✅

---

## 验收清单

- [x] `services/state_machine.py` 状态机
- [x] `services/button_handler.py` 按键处理
- [x] `services/lcd_renderer.py` LCD 渲染
- [x] 状态转换事件回调
- [x] LED 颜色同步（含闪烁）
- [x] LCD 各状态界面渲染
- [x] 短按事件 (< 300ms)
- [x] 预按住事件 (300-600ms)
- [x] 长按事件 (≥ 600ms)
- [x] 超长按事件 (≥ 3s)
- [x] 按键松开事件

---

## 下一步

✅ Day 6 完成，继续 [Day 7：Device Agent MBP 通信](../Day7/Day7-Device-Agent-MBP通信.md)