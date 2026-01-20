# Day 5：Pi Device Agent 骨架 + 硬件封装

> **目标**：创建运行于树莓派的 Device Agent 服务，实现硬件模块统一封装

## 前置要求

- ✅ Day 4 完成（WS 流式问答就绪）
- ✅ Pi OS 已安装，SSH 免密登录配置完成
- ✅ Whisplay HAT 驱动已安装（WM8960、LCD、LED）
- ✅ picamera2 驱动已安装

---

## 交付内容

- Device Agent Python 服务（运行于 Pi）
- 硬件封装模块：
  - `Camera` - picamera2 拍照
  - `Audio` - WM8960 录音/播放（arecord/aplay）
  - `Button` - 按键 GPIO 监听（gpiod）
  - `LED` - RGB LED 控制（gpiod）
  - `LCD` - SPI LCD 显示（PIL/Pillow）

---

## 环境配置

### Pi 端目录权限

```bash
# 在 MBP 上执行，创建 Pi 端目录
ssh mars@raspberrypi "sudo mkdir -p /opt/snap2know && sudo chown mars:mars /opt/snap2know"
```

### 网络信息

| 设备 | IP 地址 | 说明 |
|------|---------|------|
| MBP | 192.168.1.38 | 后端服务运行 |
| Pi | 192.168.1.55 | Device Agent 运行 |

---

## 项目结构

```
device_agent/                    # 本地开发目录
├── main.py                      # Device Agent 入口
├── config.py                    # 配置管理
├── .env.example                 # 环境变量模板
├── requirements.txt             # Python 依赖
├── hardware/                    # 硬件封装模块
│   ├── __init__.py
│   ├── camera.py                # 相机（picamera2）
│   ├── audio.py                 # 音频（arecord/aplay）
│   ├── button.py                # 按键（gpiod）
│   ├── led.py                   # LED（gpiod）
│   └── lcd.py                   # LCD（PIL）
├── services/                    # 业务服务
│   └── __init__.py
└── utils/                       # 工具模块
    └── __init__.py

# Pi 端部署目录
/opt/snap2know/
├── device_agent/                # 同步的代码
├── tmp/                         # 临时文件
├── logs/                        # 日志文件
└── .venv/                       # Python 虚拟环境
```

---

## 代码同步（MBP → Pi）

### 首次同步

```bash
# 在 MBP 项目根目录执行
cd /Users/mars/sourceCode/personal/ai/Snap2Know

# 同步代码到 Pi
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude '.env' \
  device_agent/ mars@raspberrypi:/opt/snap2know/device_agent/
```

### 更新同步

```bash
# 开发过程中修改代码后，执行同步
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude '.env' \
  device_agent/ mars@raspberrypi:/opt/snap2know/device_agent/

# 仅同步硬件模块
rsync -avz device_agent/hardware/ mars@raspberrypi:/opt/snap2know/device_agent/hardware/
```

### 快捷命令（可添加到 ~/.zshrc）

```bash
# 添加别名
alias sync-pi="rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude '.env' \
  ~/sourceCode/personal/ai/Snap2Know/device_agent/ mars@raspberrypi:/opt/snap2know/device_agent/"
```

---

## Pi 端环境配置

### 1. 创建虚拟环境

```bash
ssh mars@raspberrypi

cd /opt/snap2know
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 安装系统依赖

```bash
# libcap 开发库（python-prctl 需要）
sudo apt-get install -y libcap-dev

# libgpiod 开发库（gpiod 需要）
sudo apt-get install -y libgpiod-dev python3-libgpiod
```

### 3. 安装 Python 依赖

```bash
cd /opt/snap2know
source .venv/bin/activate

# 核心依赖
pip install python-dotenv pillow gpiod

# 硬件依赖
pip install picamera2 websockets httpx aiofiles
```

### 4. 配置环境变量

```bash
# 创建 .env 文件
cat > /opt/snap2know/device_agent/.env << 'EOF'
# Snap2Know Device Agent Environment Variables

# MBP 后端地址
MBP_HOST=192.168.1.38
MBP_PORT=8000

# 硬件配置（Whisplay HAT）
AUDIO_DEVICE=plughw:wm8960
BUTTON_PIN=17
LED_RED_PIN=5
LED_GREEN_PIN=6
LED_BLUE_PIN=13

# 录音配置
RECORD_DURATION=5
RECORD_SAMPLE_RATE=16000

# 临时文件目录
TMP_DIR=/opt/snap2know/tmp

# 日志目录
LOG_DIR=/opt/snap2know/logs

# 调试模式
DEBUG=true
EOF
```

---

## 测试命令

### 在 Pi 上启动 Device Agent

```bash
# SSH 登录 Pi
ssh mars@raspberrypi

# 激活虚拟环境并运行
cd /opt/snap2know
source .venv/bin/activate
cd device_agent
python main.py
```

### 从 MBP 远程启动测试

```bash
# 运行 10 秒后自动退出
ssh -t mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && cd device_agent && timeout 10 python main.py"
```

### 单独测试硬件模块

```bash
# LED 测试
ssh mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && python -c \"
from device_agent.hardware import LED
led = LED()
led.set_color('blue')
import time; time.sleep(2)
led.set_color('red')
time.sleep(2)
led.off()
led.cleanup()
print('LED test passed')
\""

# 按键测试
ssh mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && python -c \"
from device_agent.hardware import Button
btn = Button()
print('Waiting for button press (5s timeout)...')
if btn.wait_for_press(timeout=5):
    print('Button pressed!')
else:
    print('Timeout')
btn.cleanup()
\""

# 音频录制测试
ssh mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && python -c \"
from device_agent.hardware import Audio
audio = Audio(device='plughw:wm8960')
print('Recording 3 seconds...')
audio.record('/tmp/test.wav', duration=3)
print('Playing back...')
audio.play('/tmp/test.wav')
print('Audio test passed')
\""

# 相机测试
ssh mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && python -c \"
from device_agent.hardware import Camera
cam = Camera()
path = cam.capture('/tmp/test.jpg')
print(f'Photo saved to {path}')
cam.close()
\""

# LCD 测试
ssh mars@raspberrypi "cd /opt/snap2know && source .venv/bin/activate && python -c \"
from device_agent.hardware import LCD
lcd = LCD()
lcd.show_text('Hello\\nSnap2Know')
import time; time.sleep(3)
lcd.clear()
print('LCD test passed')
\""
```

---

## 技术说明

### Pi 5 GPIO 兼容性

Pi 5 使用新的 GPIO 控制器，不兼容 `RPi.GPIO` 库。解决方案：

| 库 | Pi 4 | Pi 5 | 说明 |
|----|------|------|------|
| `RPi.GPIO` | ✅ | ❌ | Legacy，不支持 Pi 5 |
| `gpiod` | ✅ | ✅ | 推荐，使用 libgpiod |
| `lgpio` | ✅ | ✅ | 需要编译 |

本项目使用 `gpiod` 库，代码示例：

```python
import gpiod
from gpiod.line import Direction, Value

chip = gpiod.Chip("/dev/gpiochip4")  # Pi 5: gpiochip4 -> gpiochip0
lines = chip.request_lines(
    consumer="snap2know",
    config={
        5: gpiod.LineSettings(direction=Direction.OUTPUT)
    }
)
lines.set_value(5, Value.ACTIVE)
```

### 音频设备

Whisplay HAT 使用 WM8960 音频编解码器：

```bash
# 查看声卡
aplay -l
# card 2: wm8960soundcard

# 使用设备名（推荐）
AUDIO_DEVICE=plughw:wm8960

# 使用设备号
AUDIO_DEVICE=plughw:2,0
```

---

## 验收测试结果

```
==================================================
  Snap2Know Device Agent
==================================================
[INFO] Running on Raspberry Pi - using real hardware

[TEST] Testing hardware modules...
  - LED: OK ✅
  - LCD: OK ✅
  - Button: OK ✅
  - Camera: OK (lazy init) ✅
  - Audio: OK (lazy init) ✅
[TEST] Hardware test complete

[INFO] Device Agent starting...
[INFO] MBP Backend: http://192.168.1.38:8000
[INFO] Press button to start recording, Ctrl+C to exit
```

---

## 验收清单

- [x] `hardware/camera.py` 模块创建
- [x] `hardware/audio.py` 模块创建
- [x] `hardware/button.py` 模块创建（gpiod）
- [x] `hardware/led.py` 模块创建（gpiod）
- [x] `hardware/lcd.py` 模块创建
- [x] `main.py` Device Agent 入口
- [x] `config.py` 配置管理
- [x] Pi 端虚拟环境配置
- [x] 代码同步流程验证
- [x] 所有硬件模块测试通过

---

## 常见问题

### GPIO 设备忙（Errno 16）

```bash
# 检查占用进程
ps aux | grep python

# 终止占用进程
pkill -f "python main.py"
```

### 权限问题

```bash
# 将用户添加到 gpio 组
sudo usermod -aG gpio mars

# 重新登录后生效
```

---

## 下一步

✅ Day 5 完成，继续 [Day 6：端到端集成（Pi↔MBP）](../Day6/Day6-端到端集成.md)