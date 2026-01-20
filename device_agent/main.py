"""
Snap2Know Device Agent - Main Entry Point (with State Machine)
"""
import os
import sys
import asyncio
import signal
import time
import threading
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


def create_services(hw: dict):
    """创建服务实例"""
    from services import StateMachine, ButtonHandler, LCDRenderer, State, RenderData
    
    # 创建状态机
    state_machine = StateMachine()
    
    # 创建按键处理器
    button_handler = ButtonHandler()
    
    # 创建 LCD 渲染器
    lcd_renderer = LCDRenderer(lcd_driver=hw["lcd"])
    
    return {
        "state_machine": state_machine,
        "button_handler": button_handler,
        "lcd_renderer": lcd_renderer
    }


def setup_callbacks(hw: dict, services: dict):
    """配置回调函数"""
    from services import State, RenderData
    
    state_machine = services["state_machine"]
    button_handler = services["button_handler"]
    lcd_renderer = services["lcd_renderer"]
    
    # 状态变更回调
    def on_state_change(old_state: State, new_state: State, data):
        print(f"[STATE] {old_state.name} -> {new_state.name}")
        
        # 更新按键处理器的取消状态
        button_handler.set_can_cancel(state_machine.can_cancel())
    
    def on_led_change(color: str):
        try:
            hw["led"].set_color(color)
        except Exception as e:
            print(f"[LED] Error: {e}")
    
    def on_lcd_update(state: State, data):
        try:
            render_data = RenderData(
                duration=data.recording_duration,
                message=data.processing_message,
                answer_text=data.answer_text,
                error_message=data.error_message,
                menu_selection=data.menu_selection
            )
            lcd_renderer.render(state.name.lower(), render_data)
        except Exception as e:
            print(f"[LCD] Error: {e}")
    
    state_machine.set_callbacks(
        on_state_change=on_state_change,
        on_led_change=on_led_change,
        on_lcd_update=on_lcd_update
    )
    
    # 按键事件回调
    def on_tap():
        """短按 - 拍照入库"""
        print("[BUTTON] Tap - Taking photo")
        current_state = state_machine.state
        
        if current_state == State.IDLE:
            state_machine.transition_to(State.BUSY)
            # TODO: 执行拍照入库
            # 模拟处理
            threading.Timer(2.0, lambda: state_machine.transition_to(State.IDLE)).start()
        elif current_state == State.ANSWERING:
            # 静音切换
            print("[BUTTON] Toggle mute")
        elif current_state == State.ERROR:
            # 重试
            state_machine.reset()
    
    def on_pre_hold():
        """预按住 - 显示提示"""
        print("[BUTTON] Pre-hold")
        state_machine.transition_to(State.PRE_HOLD)
    
    def on_hold_start():
        """长按开始 - 开始录音"""
        print("[BUTTON] Hold start - Recording")
        state_machine.transition_to(State.RECORDING)
        
        # 启动录音时长更新
        def update_duration():
            while state_machine.state == State.RECORDING:
                state_machine.update_recording_duration()
                time.sleep(0.5)
        
        threading.Thread(target=update_duration, daemon=True).start()
    
    def on_hold_end(duration: float):
        """长按结束 - 处理录音"""
        print(f"[BUTTON] Hold end - Duration: {duration:.1f}s")
        state_machine.transition_to(State.PROCESSING, processing_message="语音识别中...")
        
        # TODO: 上传音频到 MBP STT
        # 模拟处理
        def simulate_processing():
            time.sleep(1.5)
            state_machine.transition_to(State.ANSWERING)
            state_machine.set_answer("这是一个模拟回答...")
            time.sleep(3)
            state_machine.transition_to(State.DONE)
            time.sleep(2)
            state_machine.reset()
        
        threading.Thread(target=simulate_processing, daemon=True).start()
    
    def on_long_hold():
        """超长按 - 进入菜单"""
        print("[BUTTON] Long hold - Menu")
        state_machine.transition_to(State.MENU)
    
    def on_cancel():
        """取消操作"""
        print("[BUTTON] Cancel")
        state_machine.cancel()
    
    button_handler.set_callbacks(
        on_tap=on_tap,
        on_pre_hold=on_pre_hold,
        on_hold_start=on_hold_start,
        on_hold_end=on_hold_end,
        on_long_hold=on_long_hold,
        on_cancel=on_cancel
    )


def setup_button_gpio(hw: dict, button_handler):
    """配置按键 GPIO 回调"""
    try:
        hw["button"].on_press(button_handler.on_press)
        
        # 对于 GPIO，需要单独处理松开事件
        # 这里使用轮询检测松开
        def poll_release():
            was_pressed = False
            while True:
                try:
                    is_pressed = hw["button"].is_pressed()
                    if was_pressed and not is_pressed:
                        button_handler.on_release()
                    was_pressed = is_pressed
                except:
                    pass
                time.sleep(0.02)
        
        threading.Thread(target=poll_release, daemon=True).start()
        
    except Exception as e:
        print(f"[BUTTON] GPIO setup failed: {e}")


async def main_loop(hw: dict, services: dict):
    """主事件循环"""
    from services import State
    
    state_machine = services["state_machine"]
    button_handler = services["button_handler"]
    
    print("[INFO] Device Agent starting...")
    print(f"[INFO] MBP Backend: {config.mbp_base_url}")
    print("[INFO] Press button to interact, Ctrl+C to exit\n")
    
    # 初始化为空闲状态
    state_machine.transition_to(State.IDLE)
    
    # 设置按键 GPIO
    setup_button_gpio(hw, button_handler)
    
    # 主循环
    try:
        while True:
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        print("[INFO] Main loop cancelled")


def cleanup(hw: dict, services: dict):
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
    
    try:
        if hasattr(hw["led"], "cleanup"):
            hw["led"].cleanup()
    except:
        pass
    
    print("[INFO] Cleanup complete")


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
        hw["lcd"].show_text("Test")
        print("OK")
    except Exception as e:
        print(f"FAILED: {e}")
    
    # Button 测试
    print("  - Button: ", end="")
    try:
        _ = hw["button"].is_pressed() if hasattr(hw["button"], "is_pressed") else True
        print("OK")
    except Exception as e:
        print(f"FAILED: {e}")
    
    # Camera 测试
    print("  - Camera: OK (lazy init)")
    
    # Audio 测试
    print("  - Audio: OK (lazy init)")
    
    print("[TEST] Hardware test complete\n")


def main():
    """主入口"""
    print("=" * 50)
    print("  Snap2Know Device Agent v2.0 (State Machine)")
    print("=" * 50)
    
    # 设置目录
    setup_directories()
    
    # 创建硬件实例
    hw = create_hardware()
    
    # 测试硬件
    if config.debug:
        test_hardware(hw)
    
    # 创建服务
    services = create_services(hw)
    
    # 配置回调
    setup_callbacks(hw, services)
    
    # 设置信号处理
    def signal_handler(sig, frame):
        print("\n[INFO] Received shutdown signal")
        cleanup(hw, services)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 运行主循环
    try:
        asyncio.run(main_loop(hw, services))
    except KeyboardInterrupt:
        pass
    finally:
        cleanup(hw, services)


if __name__ == "__main__":
    main()
