# Day 5：Pi Device Agent 骨架 + 硬件封装

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