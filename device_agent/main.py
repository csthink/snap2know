"""
Snap2Know Device Agent - Main Entry Point (with MBP Communication)
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
        from hardware import Camera, Audio, Button, LED, LCD
        
        is_pi = os.path.exists("/proc/device-tree/model")
        
        if is_pi:
            print("[INFO] Running on Raspberry Pi - using real hardware")
            
            # LCD 先初始化（会创建 WhisplayBoard）
            lcd = LCD()
            
            # Button 使用 LCD 的 WhisplayBoard 实例
            button = Button(pin=config.button_pin)
            board = lcd.get_board()
            if board:
                button.set_board(board)
                print("[INFO] Button using shared WhisplayBoard")
            
            return {
                "camera": Camera(),
                "audio": Audio(device=config.audio_device),
                "button": button,
                "led": LED(
                    red_pin=config.led_red_pin,
                    green_pin=config.led_green_pin,
                    blue_pin=config.led_blue_pin
                ),
                "lcd": lcd
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
    from services import StateMachine, ButtonHandler, LCDRenderer, MBPClient, TTSPlayer
    
    state_machine = StateMachine()
    button_handler = ButtonHandler()
    lcd_renderer = LCDRenderer(lcd_driver=hw["lcd"])
    
    # MBP 客户端
    mbp_client = MBPClient(base_url=config.mbp_base_url)
    
    # TTS 播放器
    tts_player = TTSPlayer(
        audio_device=config.audio_device,
        mbp_client=mbp_client
    )
    
    return {
        "state_machine": state_machine,
        "button_handler": button_handler,
        "lcd_renderer": lcd_renderer,
        "mbp_client": mbp_client,
        "tts_player": tts_player
    }


def setup_callbacks(hw: dict, services: dict):
    """配置回调函数"""
    from services import State, RenderData
    
    state_machine = services["state_machine"]
    button_handler = services["button_handler"]
    lcd_renderer = services["lcd_renderer"]
    mbp_client = services["mbp_client"]
    tts_player = services["tts_player"]
    
    # 状态变更回调
    def on_state_change(old_state: State, new_state: State, data):
        print(f"[STATE] {old_state.name} -> {new_state.name}")
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
    
    # === 按键事件回调（集成 MBP 通信）===
    
    # 保存主事件循环引用（在 main_loop 中设置）
    main_loop_ref = {"loop": None}
    services["_main_loop_ref"] = main_loop_ref
    
    def on_tap():
        """短按 - 拍照入库 或 静音切换"""
        current_state = state_machine.state
        
        if current_state == State.IDLE:
            print("[BUTTON] Tap - Taking photo")
            state_machine.transition_to(State.BUSY)
            
            # 在线程中执行拍照和上传
            def do_photo_work():
                try:
                    from PIL import Image
                    import io
                    
                    # 拍照（同步）
                    image_data = hw["camera"].capture_bytes()
                    print(f"[PHOTO] Captured {len(image_data)} bytes")
                    
                    # 在 LCD 上显示拍摄的图片预览
                    try:
                        img = Image.open(io.BytesIO(image_data))
                        # 调整大小以适应 LCD（240x280）
                        img.thumbnail((240, 280), Image.Resampling.LANCZOS)
                        # 创建黑色背景
                        lcd_img = Image.new("RGB", (240, 280), (0, 0, 0))
                        # 居中放置
                        x = (240 - img.width) // 2
                        y = (280 - img.height) // 2
                        lcd_img.paste(img, (x, y))
                        # 显示
                        hw["lcd"].draw_image(lcd_img)
                        print("[PHOTO] Preview displayed on LCD")
                    except Exception as e:
                        print(f"[PHOTO] Preview error: {e}")
                    
                    # 上传（需要异步，使用 run_coroutine_threadsafe）
                    async def upload():
                        result = await mbp_client.upload_image(image_data)
                        return result
                    
                    loop = main_loop_ref.get("loop")
                    if loop:
                        future = asyncio.run_coroutine_threadsafe(upload(), loop)
                        result = future.result(timeout=30)
                        print(f"[PHOTO] Upload result: {result}")
                    
                    # 成功，继续显示图片 1.5 秒
                    state_machine.transition_to(State.DONE)
                    time.sleep(1.5)
                    state_machine.reset()
                    
                except Exception as e:
                    print(f"[PHOTO] Error: {e}")
                    state_machine.set_error(str(e)[:20])
            
            threading.Thread(target=do_photo_work, daemon=True).start()
            
        elif current_state == State.ANSWERING:
            # 静音切换
            is_muted = tts_player.toggle_mute()
            print(f"[BUTTON] Toggle mute: {is_muted}")
            
        elif current_state == State.ERROR:
            # 重试
            state_machine.reset()
        
        elif current_state == State.MENU:
            # 菜单中短按：循环选择
            current_selection = state_machine.data.menu_selection
            new_selection = (current_selection + 1) % 3  # 3 个菜单项
            state_machine._data.menu_selection = new_selection
            print(f"[MENU] Selection: {new_selection}")
            # 更新 LCD 显示
            if state_machine._on_lcd_update:
                state_machine._on_lcd_update(state_machine.state, state_machine.data)
    
    def on_pre_hold():
        """预按住 - 显示提示"""
        current_state = state_machine.state
        # 只在 IDLE 状态下响应
        if current_state == State.IDLE:
            print("[BUTTON] Pre-hold")
            state_machine.transition_to(State.PRE_HOLD)
        elif current_state == State.MENU:
            # 菜单中预按住：准备确认
            print("[BUTTON] Pre-hold in menu - preparing to confirm")
    
    def execute_menu_action(selection: int):
        """执行菜单操作"""
        print(f"[MENU] === Executing menu action, selection={selection} ===")
        
        if selection == 0:
            # 清除会话
            print("[MENU] Action: Clearing session...")
            
            async def clear_session():
                try:
                    new_session = await mbp_client.create_session()
                    print(f"[MENU] New session created: {new_session}")
                except Exception as e:
                    print(f"[MENU] Error creating session: {e}")
            
            loop = main_loop_ref.get("loop")
            if loop:
                asyncio.run_coroutine_threadsafe(clear_session(), loop)
            else:
                print("[MENU] Warning: No event loop available")
            
            state_machine.reset()
            
        elif selection == 1:
            # 网络设置（暂未实现）
            print("[MENU] Action: Network settings - not implemented")
            state_machine.reset()
            
        elif selection == 2:
            # 返回
            print("[MENU] Action: Return to idle")
            state_machine.reset()
        else:
            print(f"[MENU] Unknown selection: {selection}")
            state_machine.reset()
    
    # 录音数据（在线程间共享）
    recording_data = {"path": None, "task": None}
    
    def on_hold_start():
        """长按开始 - 开始录音 或 菜单确认"""
        current_state = state_machine.state
        
        if current_state == State.MENU:
            # 菜单中长按：确认选择
            selection = state_machine.data.menu_selection
            print(f"[BUTTON] Hold in menu - confirming selection {selection}")
            execute_menu_action(selection)
            return
        
        # 只在 PRE_HOLD 状态下响应录音
        if current_state != State.PRE_HOLD:
            return
        print("[BUTTON] Hold start - Recording")
        state_machine.transition_to(State.RECORDING)
        
        # 启动录音
        recording_path = os.path.join(config.tmp_dir, "recording.wav")
        recording_data["path"] = recording_path
        
        # 录音在后台线程
        def do_record():
            try:
                hw["audio"].record(
                    recording_path,
                    duration=config.record_duration,
                    sample_rate=config.record_sample_rate
                )
            except Exception as e:
                print(f"[RECORD] Error: {e}")
        
        recording_thread = threading.Thread(target=do_record, daemon=True)
        recording_thread.start()
        
        # 更新录音时长
        def update_duration():
            while state_machine.state == State.RECORDING:
                state_machine.update_recording_duration()
                time.sleep(0.5)
        
        threading.Thread(target=update_duration, daemon=True).start()
    
    def on_hold_end(duration: float):
        """长按结束 - 处理录音"""
        print(f"[BUTTON] Hold end - Duration: {duration:.1f}s")
        state_machine.transition_to(State.PROCESSING, processing_message="语音识别中...")
        
        def do_stt_and_qa_sync():
            try:
                # 读取录音
                recording_path = recording_data.get("path")
                if not recording_path or not os.path.exists(recording_path):
                    state_machine.set_error("录音失败")
                    return
                
                with open(recording_path, "rb") as f:
                    audio_data = f.read()
                print(f"[STT] Audio size: {len(audio_data)} bytes")
                
                loop = main_loop_ref.get("loop")
                if not loop:
                    state_machine.set_error("事件循环未就绪")
                    return
                
                # STT（异步）
                async def do_stt():
                    return await mbp_client.speech_to_text(audio_data)
                
                future = asyncio.run_coroutine_threadsafe(do_stt(), loop)
                text = future.result(timeout=30)
                print(f"[STT] Result: {text}")
                
                if not text:
                    state_machine.set_error("语音识别失败")
                    return
                
                # 问答（异步）
                state_machine.transition_to(State.ANSWERING)
                state_machine.set_answer("")
                
                async def do_qa():
                    await tts_player.start_playing()
                    
                    async def on_token_async(token_text):
                        state_machine.append_answer(token_text)
                        await tts_player.add_text(token_text)
                    
                    def on_token(token_text):
                        asyncio.run_coroutine_threadsafe(
                            on_token_async(token_text), loop
                        )
                    
                    def on_done(data):
                        print(f"[QA] Done: {data}")
                        asyncio.run_coroutine_threadsafe(tts_player.flush(), loop)
                        tts_player.mark_done()  # 标记没有更多内容
                    
                    await mbp_client.ask_question(
                        text,
                        on_token=on_token,
                        on_done=on_done
                    )
                    
                    await tts_player.wait_until_done()
                
                future = asyncio.run_coroutine_threadsafe(do_qa(), loop)
                future.result(timeout=120)
                
                # 完成
                state_machine.transition_to(State.DONE)
                time.sleep(2)
                state_machine.reset()
                
            except Exception as e:
                print(f"[QA] Error: {e}")
                state_machine.set_error(str(e)[:20])
        
        threading.Thread(target=do_stt_and_qa_sync, daemon=True).start()
    
    def on_long_hold():
        """超长按 - 进入菜单"""
        current_state = state_machine.state
        # 只在 RECORDING 状态下响应超长按
        if current_state != State.RECORDING:
            return
        print("[BUTTON] Long hold - Menu")
        state_machine.transition_to(State.MENU)
    
    def on_cancel():
        """取消操作"""
        # 只在可取消状态下响应
        if not state_machine.can_cancel():
            return
        print("[BUTTON] Cancel")
        tts_player.stop()
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
        # 使用 WhisplayBoard 的按钮回调
        hw["button"].on_press(button_handler.on_press)
        hw["button"].on_release(button_handler.on_release)
        print("[BUTTON] GPIO callbacks registered")
        
    except Exception as e:
        print(f"[BUTTON] GPIO setup failed: {e}")


async def init_mbp_connection(services: dict):
    """初始化 MBP 连接"""
    mbp_client = services["mbp_client"]
    
    print("[MBP] Checking connection...")
    if await mbp_client.health_check():
        print("[MBP] Connected!")
        session_id = await mbp_client.create_session()
        print(f"[MBP] Session: {session_id}")
        return True
    else:
        print("[MBP] Connection failed!")
        return False


async def main_loop(hw: dict, services: dict):
    """主事件循环"""
    from services import State
    
    state_machine = services["state_machine"]
    button_handler = services["button_handler"]
    
    # 设置事件循环引用（供按键回调使用）
    if "_main_loop_ref" in services:
        services["_main_loop_ref"]["loop"] = asyncio.get_event_loop()
    
    print("[INFO] Device Agent starting...")
    print(f"[INFO] MBP Backend: {config.mbp_base_url}")
    
    # 初始化 MBP 连接
    if not await init_mbp_connection(services):
        print("[WARN] MBP not available, some features disabled")
    
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


async def cleanup_async(services: dict):
    """异步清理"""
    if "mbp_client" in services:
        await services["mbp_client"].close()


def cleanup(hw: dict, services: dict):
    """清理资源"""
    print("[INFO] Cleaning up...")
    
    # 停止 TTS
    if "tts_player" in services:
        services["tts_player"].stop()
    
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
    
    for name in ["led", "lcd", "button"]:
        print(f"  - {name.upper()}: ", end="")
        try:
            if name == "led":
                hw["led"].set_color("blue")
            elif name == "lcd":
                hw["lcd"].show_status("idle", "测试中...")
            elif name == "button":
                hw["button"].is_pressed()
            print("OK")
        except Exception as e:
            print(f"FAILED: {e}")
    
    print("  - Camera: OK (lazy init)")
    print("  - Audio: OK (lazy init)")
    print("[TEST] Hardware test complete\n")


def main():
    """主入口"""
    print("=" * 50)
    print("  Snap2Know Device Agent v3.0 (MBP Integration)")
    print("=" * 50)
    
    setup_directories()
    hw = create_hardware()
    
    if config.debug:
        test_hardware(hw)
    
    services = create_services(hw)
    setup_callbacks(hw, services)
    
    def signal_handler(sig, frame):
        print("\n[INFO] Received shutdown signal")
        cleanup(hw, services)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(main_loop(hw, services))
    except KeyboardInterrupt:
        pass
    finally:
        cleanup(hw, services)


if __name__ == "__main__":
    main()
