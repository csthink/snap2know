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
- LCD UI 渲染（PIL/Pillow 绘制 → SPI 推屏）
- LED 颜色状态同步

---

## 状态机设计

### 状态定义

| 状态 | 代码 | LED | LCD 显示 | 说明 |
|------|------|-----|----------|------|
| **Idle** | `S_IDLE` | 🔵 蓝色 | 待机图标 + 提示 | 空闲状态 |
| **Pre-Hold** | `S_PRE_HOLD` | 🔵 蓝色闪烁 | "继续按住..." | 按下 300ms 后 |
| **Recording** | `S_RECORDING` | 🔴 红色 | 🎤 + 录音时长 | 录音中 |
| **Processing** | `S_PROCESSING` | 🟡 黄色 | ⏳ + "处理中" | STT/OCR 处理 |
| **Answering** | `S_ANSWERING` | 🟢 绿色 | 💬 + 回答文字 | TTS 播放中 |
| **Done** | `S_DONE` | 🔵 蓝色 | ✅ + "完成" | 短暂显示后回 Idle |
| **Menu** | `S_MENU` | 🟣 紫色 | 菜单选项 | 超长按 3s 进入 |
| **Error** | `S_ERROR` | 🔴 红色闪烁 | ❌ + 错误信息 | 错误状态 |
| **Busy** | `S_BUSY` | 🟡 黄色 | 📷 + "拍照中" | 短按拍照入库 |

### 状态转换图

```
                    ┌─────────────────────────────────────┐
                    │                                     │
                    ▼                                     │
              ┌─────────┐                                 │
              │  Idle   │◀────────────────────────────────┤
              └────┬────┘                                 │
                   │                                      │
         ┌─────────┼─────────┐                           │
         │ 短按    │ 长按600ms│                           │
         ▼         ▼         │                           │
    ┌─────────┐ ┌─────────┐  │                           │
    │  Busy   │ │Pre-Hold │  │ 超长按3s                   │
    │ (拍照)  │ └────┬────┘  │                           │
    └────┬────┘      │       ▼                           │
         │           │  ┌─────────┐                      │
         │           │  │  Menu   │                      │
         │           │  └────┬────┘                      │
         │           │       │ 确认/取消                  │
         │           │       └───────────────────────────┤
         │           ▼                                   │
         │    ┌───────────┐                              │
         │    │ Recording │──── 松开按键                  │
         │    └─────┬─────┘                              │
         │          │                                    │
         │          ▼                                    │
         │    ┌───────────┐                              │
         └───▶│Processing │                              │
              └─────┬─────┘                              │
                    │                                    │
                    ▼                                    │
              ┌───────────┐                              │
              │ Answering │──── 播放完成/长按停止          │
              └─────┬─────┘                              │
                    │                                    │
                    ▼                                    │
              ┌───────────┐                              │
              │   Done    │──── 2s 后自动                 │
              └───────────┘─────────────────────────────┘
```

### 按键事件定义

| 事件 | 时长 | 触发动作 |
|------|------|----------|
| **短按** | < 300ms | 拍照入库（Idle→Busy）或 静音切换（Answering） |
| **预按住** | 300-600ms | 显示预反馈（Pre-Hold） |
| **长按** | ≥ 600ms | 开始录音（Recording） |
| **超长按** | ≥ 3000ms | 进入菜单（Menu） |
| **松开** | - | 结束录音/确认操作 |
| **取消长按** | 1200ms（在 Busy/Answering） | 取消/停止当前操作 |

---

## 项目结构

```
device_agent/
├── services/
│   ├── __init__.py
│   ├── state_machine.py     # 状态机核心
│   ├── button_handler.py    # 按键事件处理
│   └── lcd_renderer.py      # LCD 渲染器
├── assets/                   # 资源文件
│   ├── fonts/
│   │   └── NotoSansSC.ttf   # 中文字体
│   └── icons/               # 状态图标
│       ├── idle.png
│       ├── recording.png
│       ├── processing.png
│       └── ...
└── main.py                  # 更新：集成状态机
```

---

## LCD 渲染设计

### 屏幕布局（240x240）

```
┌──────────────────────────────┐
│     状态图标区 (60px)         │
│        [🎤]                   │
├──────────────────────────────┤
│                              │
│     主文本区 (120px)          │
│     "正在录音..."             │
│     "00:05"                   │
│                              │
├──────────────────────────────┤
│     底部提示区 (60px)         │
│     "松开结束录音"            │
└──────────────────────────────┘
```

### 渲染方法

```python
class LCDRenderer:
    def render_state(self, state: str, data: dict = None):
        """根据状态渲染 LCD"""
        image = self._create_background(state)
        
        if state == "idle":
            self._draw_idle(image)
        elif state == "recording":
            self._draw_recording(image, data.get("duration", 0))
        elif state == "processing":
            self._draw_processing(image, data.get("message", ""))
        # ...
        
        self._push_to_display(image)
```

---

## 配置说明

### 新增环境变量

```bash
# 按键时间阈值（毫秒）
PRESS_SHORT_MS=300
PRESS_LONG_MS=600
PRESS_MENU_MS=3000
PRESS_CANCEL_MS=1200

# LCD 刷新率
LCD_FPS=10

# 录音最大时长（秒）
RECORD_MAX_DURATION=30
```

---

## 验收测试

### 基础流程测试

```bash
# 在 Pi 上启动 Device Agent
ssh -t mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && cd device_agent && python main.py"
```

1. **启动验证**
   - LCD 显示 Idle 界面
   - LED 蓝色常亮

2. **短按测试**（< 300ms）
   - LCD 显示 "拍照中..."
   - LED 黄色
   - 完成后回到 Idle

3. **长按测试**（≥ 600ms）
   - 300ms: Pre-Hold 反馈
   - 600ms: 进入 Recording，LED 红色
   - 松开: 进入 Processing
   - 完成: Answering → Done → Idle

4. **超长按测试**（≥ 3s）
   - LCD 显示菜单
   - LED 紫色

### 防误触测试

| 测试用例 | 操作 | 预期结果 |
|----------|------|----------|
| 按住 350ms | 按下后松开 | Pre-Hold 反馈，松开后回 Idle |
| 按住 550ms | 按下后松开 | 仍在 Pre-Hold，不进入录音 |
| 按住 300-600ms 松开 | 快速松开 | 不触发任何操作，保持 Idle |
| 达到 600ms 立即松开 | 刚进入录音就松开 | 录音无效，回 Idle |
| Answering 中按住 1.2s | 播放时长按 | 立即停止播放，清空队列 |

---

## 实现步骤

### 步骤 1：状态机核心

创建 `services/state_machine.py`：
- 定义状态枚举
- 实现状态转换逻辑
- 状态变更事件回调

### 步骤 2：按键事件处理

创建 `services/button_handler.py`：
- 监听按键按下/松开
- 计时器实现
- 触发状态转换

### 步骤 3：LCD 渲染器

创建 `services/lcd_renderer.py`：
- 各状态的渲染方法
- 动画效果（录音时长、进度等）
- 字体和图标加载

### 步骤 4：主程序集成

更新 `main.py`：
- 初始化状态机
- 绑定按键回调
- 状态变更时更新 LCD 和 LED

---

## 验收清单

- [ ] `services/state_machine.py` 状态机实现
- [ ] `services/button_handler.py` 按键处理
- [ ] `services/lcd_renderer.py` LCD 渲染
- [ ] 所有状态的 LED 颜色正确
- [ ] 所有状态的 LCD 显示正确
- [ ] 短按拍照流程
- [ ] 长按录音流程
- [ ] 超长按菜单流程
- [ ] 防误触机制验证
- [ ] 长按取消/停止功能

---

## 下一步

✅ Day 6 完成，继续 [Day 7：Device Agent MBP 通信](../Day7/Day7-Device-Agent-MBP通信-音频处理.md)