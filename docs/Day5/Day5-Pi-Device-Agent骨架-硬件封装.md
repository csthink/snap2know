# Day 5：Pi Device Agent 骨架 + 硬件封装

> **目标**：创建运行于树莓派的 Device Agent 服务，实现硬件模块统一封装

## 前置要求

- ✅ Day 4 完成（WS 流式问答就绪）
- 树莓派已完成 Day 0 硬件配置
- Whisplay 套件驱动已安装（WM8960、LCD、LED）
- picamera2 库已安装

---

## 交付内容

- Device Agent Python 服务（运行于 Pi）
- 硬件封装模块：
  - `Camera` - picamera2 拍照
  - `Audio` - WM8960 录音/播放（arecord/aplay）
  - `Button` - 按键 GPIO 监听
  - `LED` - RGB LED 控制
  - `LCD` - SPI LCD 显示（Whisplay 驱动 + PIL/Pillow）

---

- 解决 Pi 上的 /opt 目录权限问题

```shell
ssh mars@raspberrypi "sudo mkdir -p /opt/snap2know && sudo chown mars:mars /opt/snap2know"
```

## 项目结构

```
device_agent/
├── main.py              # Device Agent 入口
├── config.py            # 配置管理
├── hardware/            # 硬件封装模块
│   ├── __init__.py
│   ├── camera.py        # 相机封装
│   ├── audio.py         # 音频录制/播放
│   ├── button.py        # 按键监听
│   ├── led.py           # LED 控制
│   └── lcd.py           # LCD 显示
├── services/            # 业务服务
│   ├── __init__.py
│   └── state_machine.py # 状态机
├── requirements.txt     # 依赖
└── .env.example         # 环境变量模板
```

---

## 硬件封装设计

### 1. Camera 模块

```python
# hardware/camera.py
from picamera2 import Picamera2

class Camera:
    def __init__(self):
        self.camera = Picamera2()
        self.camera.configure(self.camera.create_still_configuration())
    
    def capture(self, path: str) -> str:
        """拍照并保存到指定路径"""
        self.camera.start()
        self.camera.capture_file(path)
        self.camera.stop()
        return path
    
    def capture_bytes(self) -> bytes:
        """拍照并返回字节数据"""
        ...
```

### 2. Audio 模块

```python
# hardware/audio.py
import subprocess

class Audio:
    def __init__(self, device="plughw:0,0"):
        self.device = device
    
    def record(self, path: str, duration: int = 5) -> str:
        """录制音频"""
        subprocess.run([
            "arecord", "-D", self.device,
            "-f", "S16_LE", "-r", "16000", "-c", "1",
            "-d", str(duration), path
        ], check=True)
        return path
    
    def play(self, path: str) -> None:
        """播放音频"""
        subprocess.run(["aplay", "-D", self.device, path], check=True)
    
    def play_bytes(self, data: bytes) -> None:
        """播放音频字节数据"""
        ...
```

### 3. Button 模块

```python
# hardware/button.py
import RPi.GPIO as GPIO
from typing import Callable

class Button:
    def __init__(self, pin: int = 17):
        self.pin = pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self._callback = None
    
    def on_press(self, callback: Callable) -> None:
        """注册按键按下回调"""
        self._callback = callback
        GPIO.add_event_detect(
            self.pin,
            GPIO.FALLING,
            callback=self._handle_press,
            bouncetime=300
        )
    
    def _handle_press(self, channel):
        if self._callback:
            self._callback()
    
    def wait_for_press(self) -> None:
        """阻塞等待按键"""
        GPIO.wait_for_edge(self.pin, GPIO.FALLING)
```

### 4. LED 模块

```python
# hardware/led.py
import RPi.GPIO as GPIO

class LED:
    # RGB 引脚定义（根据 Whisplay 硬件）
    RED_PIN = 5
    GREEN_PIN = 6
    BLUE_PIN = 13
    
    COLORS = {
        "red": (1, 0, 0),
        "green": (0, 1, 0),
        "blue": (0, 0, 1),
        "yellow": (1, 1, 0),
        "cyan": (0, 1, 1),
        "magenta": (1, 0, 1),
        "white": (1, 1, 1),
        "off": (0, 0, 0)
    }
    
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        for pin in [self.RED_PIN, self.GREEN_PIN, self.BLUE_PIN]:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
    
    def set_color(self, color: str) -> None:
        """设置 LED 颜色"""
        r, g, b = self.COLORS.get(color, (0, 0, 0))
        GPIO.output(self.RED_PIN, r)
        GPIO.output(self.GREEN_PIN, g)
        GPIO.output(self.BLUE_PIN, b)
    
    def off(self) -> None:
        """关闭 LED"""
        self.set_color("off")
```

### 5. LCD 模块

```python
# hardware/lcd.py
from PIL import Image, ImageDraw, ImageFont
import spidev
import RPi.GPIO as GPIO

class LCD:
    # LCD 配置（Whisplay 1.3" SPI LCD）
    WIDTH = 240
    HEIGHT = 240
    
    def __init__(self):
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 40000000
        self._init_display()
    
    def show_text(self, text: str, size: int = 24) -> None:
        """显示文字"""
        image = Image.new("RGB", (self.WIDTH, self.HEIGHT), "black")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", size)
        draw.text((10, 10), text, font=font, fill="white")
        self._display_image(image)
    
    def show_image(self, path: str) -> None:
        """显示图片"""
        image = Image.open(path).resize((self.WIDTH, self.HEIGHT))
        self._display_image(image)
    
    def show_status(self, status: str) -> None:
        """显示状态图标"""
        # 预定义状态显示
        status_colors = {
            "idle": "blue",
            "recording": "red",
            "processing": "yellow",
            "speaking": "green"
        }
        ...
    
    def clear(self) -> None:
        """清屏"""
        image = Image.new("RGB", (self.WIDTH, self.HEIGHT), "black")
        self._display_image(image)
```

---

## 配置说明

### 环境变量 (.env)

```bash
# MBP 后端地址
MBP_HOST=192.168.1.100
MBP_PORT=8000

# 硬件配置
AUDIO_DEVICE=plughw:0,0
BUTTON_PIN=17
LED_RED_PIN=5
LED_GREEN_PIN=6
LED_BLUE_PIN=13

# 录音配置
RECORD_DURATION=5
RECORD_SAMPLE_RATE=16000

# 调试模式
DEBUG=true
```

---

## 验收测试

### 1. Camera 测试

```bash
python -c "from hardware import Camera; Camera().capture('/tmp/test.jpg')"
ls -la /tmp/test.jpg
# 应生成图片文件
```

### 2. Audio 测试

```bash
# 录音测试
python -c "from hardware import Audio; Audio().record('/tmp/test.wav', 3)"
# 播放测试
python -c "from hardware import Audio; Audio().play('/tmp/test.wav')"
```

### 3. Button 测试

```bash
python -c "
from hardware import Button
btn = Button()
print('等待按键...')
btn.wait_for_press()
print('按键已按下!')
"
```

### 4. LED 测试

```bash
python -c "from hardware import LED; led = LED(); led.set_color('blue')"
python -c "from hardware import LED; led = LED(); led.set_color('red')"
python -c "from hardware import LED; led = LED(); led.off()"
```

### 5. LCD 测试

```bash
python -c "from hardware import LCD; LCD().show_text('Hello Snap2Know')"
python -c "from hardware import LCD; LCD().clear()"
```

### 6. Device Agent 启动

```bash
cd device_agent
python main.py

# 预期输出：
# [INFO] Device Agent starting...
# [INFO] Hardware initialized
# [INFO] Connected to MBP backend
# [INFO] Ready - Press button to start
```

---

## 验收清单

- [ ] `hardware/camera.py` 模块创建
- [ ] `hardware/audio.py` 模块创建
- [ ] `hardware/button.py` 模块创建
- [ ] `hardware/led.py` 模块创建
- [ ] `hardware/lcd.py` 模块创建
- [ ] `main.py` Device Agent 入口
- [ ] `config.py` 配置管理
- [ ] Camera 拍照测试通过
- [ ] Audio 录音/播放测试通过
- [ ] Button 按键检测测试通过
- [ ] LED 颜色控制测试通过
- [ ] LCD 文字显示测试通过

---

## 下一步

✅ Day 5 完成，继续 **Day 6：端到端集成（Pi↔MBP）**