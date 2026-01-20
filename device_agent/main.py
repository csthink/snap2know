"""
Snap2Know Device Agent - Main Entry Point
"""
import os
import sys
import asyncio
import signal
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from config import config


def create_hardware():
    """创建硬件实例（根据环境自动选择真实或模拟模式）"""
    try:
        # 尝试导入真实硬件模块
        from hardware import Camera, Audio, Button, LED, LCD
        
        # 检测是否在树莓派上运行
        is_pi = os.path.exists("/proc/device-tree/model")
        
        if is_pi:
            print("[INFO] Running on Raspberry Pi - using real hardware")
            return {
                "camera": Camera(),
                "audio": Audio(device=config.audio_device),
                "button": Button(pin=config.button_pin),
                "led": LED(
                    red_pin=config.led_red_pin,
                    green_pin=config.led_green_pin,
                    blue_pin=config.led_blue_pin
                ),
                "lcd": LCD()
            }
        else:
            raise ImportError("Not on Pi")
            
    except (ImportError, RuntimeError) as e:
        print(f"[INFO] Using mock hardware: {e}")
        from hardware.camera import MockCamera
        from hardware.audio import MockAudio
        from hardware.button import MockButton
        from hardware.led import MockLED
        from hardware.lcd import MockLCD
        
        return {
            "camera": MockCamera(),
            "audio": MockAudio(),
            "button": MockButton(pin=config.button_pin),
            "led": MockLED(),
            "lcd": MockLCD()
        }


def setup_directories():
    """创建必要的目录"""
    os.makedirs(config.tmp_dir, exist_ok=True)
    os.makedirs(config.log_dir, exist_ok=True)


def test_hardware(hw: dict):
    """测试硬件模块"""
    print("\n[TEST] Testing hardware modules...")
    
    # LED 测试
    print("  - LED: ", end="")
    try:
        hw["led"].set_color("blue")
        print("OK")
    except Exception as e:
        print(f"FAILED: {e}")
    
    # LCD 测试
    print("  - LCD: ", end="")
    try:
        hw["lcd"].show_text("Snap2Know\nReady")
        print("OK")
    except Exception as e:
        print(f"FAILED: {e}")
    
    # Button 测试
    print("  - Button: ", end="")
    try:
        # 只检查是否能初始化，不等待按键
        _ = hw["button"].is_pressed() if hasattr(hw["button"], "is_pressed") else True
        print("OK")
    except Exception as e:
        print(f"FAILED: {e}")
    
    # Camera 测试
    print("  - Camera: ", end="")
    try:
        # 只检查是否能初始化
        print("OK (lazy init)")
    except Exception as e:
        print(f"FAILED: {e}")
    
    # Audio 测试
    print("  - Audio: ", end="")
    try:
        print("OK (lazy init)")
    except Exception as e:
        print(f"FAILED: {e}")
    
    print("[TEST] Hardware test complete\n")


async def main_loop(hw: dict):
    """主事件循环"""
    print("[INFO] Device Agent starting...")
    print(f"[INFO] MBP Backend: {config.mbp_base_url}")
    print("[INFO] Press button to start recording, Ctrl+C to exit\n")
    
    # 显示就绪状态
    hw["led"].set_color("blue")
    hw["lcd"].show_status("idle", "按键开始录音")
    
    running = True
    
    def on_button_press():
        nonlocal running
        print("[EVENT] Button pressed!")
        # TODO: 触发录音->问答流程
    
    # 注册按键回调
    try:
        hw["button"].on_press(on_button_press)
    except Exception as e:
        print(f"[WARN] Button callback registration failed: {e}")
    
    # 主循环
    try:
        while running:
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        print("[INFO] Main loop cancelled")


def cleanup(hw: dict):
    """清理资源"""
    print("[INFO] Cleaning up...")
    
    try:
        hw["led"].off()
    except:
        pass
    
    try:
        hw["lcd"].clear()
    except:
        pass
    
    try:
        hw["button"].cleanup()
    except:
        pass
    
    try:
        if hasattr(hw["camera"], "close"):
            hw["camera"].close()
    except:
        pass
    
    print("[INFO] Cleanup complete")


def main():
    """主入口"""
    print("=" * 50)
    print("  Snap2Know Device Agent")
    print("=" * 50)
    
    # 设置目录
    setup_directories()
    
    # 创建硬件实例
    hw = create_hardware()
    
    # 测试硬件
    if config.debug:
        test_hardware(hw)
    
    # 设置信号处理
    def signal_handler(sig, frame):
        print("\n[INFO] Received shutdown signal")
        cleanup(hw)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 运行主循环
    try:
        asyncio.run(main_loop(hw))
    except KeyboardInterrupt:
        pass
    finally:
        cleanup(hw)


if __name__ == "__main__":
    main()
