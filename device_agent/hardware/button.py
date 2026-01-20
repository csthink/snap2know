"""
Button Module - GPIO 按键监听封装（Pi 5 兼容 gpiod 版本）
"""
from typing import Callable, Optional
import threading


class Button:
    """按键监听封装类（使用 gpiod 支持 Pi 5）"""
    
    def __init__(self, pin: int = 17, chip: str = "/dev/gpiochip4"):
        """
        初始化按键模块
        
        Args:
            pin: GPIO 引脚编号
            chip: GPIO 芯片设备路径（Pi 5 使用 gpiochip4）
        """
        self.pin = pin
        self.chip_path = chip
        self._callback = None
        self._initialized = False
        self._chip = None
        self._line = None
        self._watch_thread = None
        self._running = False
    
    def _ensure_initialized(self):
        """确保 GPIO 已初始化"""
        if self._initialized:
            return
        
        try:
            import gpiod
            from gpiod.line import Direction, Bias, Edge
            
            self._gpiod = gpiod
            
            # 打开 GPIO 芯片
            self._chip = gpiod.Chip(self.chip_path)
            
            # 配置为输入，上拉，监听下降沿
            self._line = self._chip.request_lines(
                consumer="snap2know-button",
                config={
                    self.pin: gpiod.LineSettings(
                        direction=Direction.INPUT,
                        bias=Bias.PULL_UP,
                        edge_detection=Edge.FALLING
                    )
                }
            )
            
            self._initialized = True
        except ImportError:
            raise RuntimeError("gpiod not installed. Run: pip install gpiod")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize GPIO: {e}")
    
    def on_press(self, callback: Callable) -> None:
        """
        注册按键按下回调
        
        Args:
            callback: 按键按下时调用的函数
        """
        self._ensure_initialized()
        self._callback = callback
        
        # 启动监听线程
        self._running = True
        self._watch_thread = threading.Thread(target=self._watch_events, daemon=True)
        self._watch_thread.start()
    
    def _watch_events(self):
        """监听 GPIO 事件"""
        while self._running:
            try:
                # 等待事件，超时 1 秒
                if self._line.wait_edge_events(timeout=1.0):
                    events = self._line.read_edge_events()
                    for event in events:
                        if self._callback:
                            self._callback()
            except Exception as e:
                if self._running:
                    print(f"Button event error: {e}")
                break
    
    def wait_for_press(self, timeout: Optional[float] = None) -> bool:
        """
        阻塞等待按键按下
        
        Args:
            timeout: 超时时间（秒），None 表示永久等待
        
        Returns:
            是否检测到按键（超时返回 False）
        """
        self._ensure_initialized()
        
        try:
            if self._line.wait_edge_events(timeout=timeout):
                self._line.read_edge_events()  # 清除事件
                return True
            return False
        except Exception as e:
            print(f"wait_for_press error: {e}")
            return False
    
    def is_pressed(self) -> bool:
        """检查按键是否被按下"""
        self._ensure_initialized()
        try:
            value = self._line.get_value(self.pin)
            return value == self._gpiod.line.Value.INACTIVE  # 按下时为低电平
        except:
            return False
    
    def cleanup(self):
        """清理 GPIO 资源"""
        self._running = False
        if self._watch_thread:
            self._watch_thread.join(timeout=2)
        if self._line:
            try:
                self._line.release()
            except:
                pass
        self._initialized = False


# 模拟模式
class MockButton:
    """模拟按键（用于开发测试）"""
    
    def __init__(self, pin: int = 17, chip: str = ""):
        self.pin = pin
        self._callback = None
    
    def on_press(self, callback: Callable) -> None:
        print(f"[MockButton] Registered callback on pin {self.pin}")
        self._callback = callback
    
    def wait_for_press(self, timeout: Optional[float] = None) -> bool:
        print(f"[MockButton] Waiting for press (timeout={timeout})")
        import time
        time.sleep(timeout or 1)
        return True
    
    def is_pressed(self) -> bool:
        return False
    
    def simulate_press(self):
        """模拟按键按下（用于测试）"""
        if self._callback:
            self._callback()
    
    def cleanup(self):
        pass
