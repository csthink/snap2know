"""
Button Module - 使用 WhisplayBoard 按钮回调
共享 LCD 的 WhisplayBoard 实例避免 GPIO 冲突
"""
from typing import Callable, Optional
import threading
import time


class Button:
    """按键监听封装类（使用 WhisplayBoard 共享 GPIO）"""
    
    def __init__(self, pin: int = 17, chip: str = "", whisplay_board=None):
        """
        初始化按键模块
        
        Args:
            pin: GPIO 引脚编号（忽略，使用 WhisplayBoard 内置按钮）
            chip: GPIO 芯片设备路径（忽略）
            whisplay_board: 共享的 WhisplayBoard 实例
        """
        self.pin = pin
        self._callback = None
        self._release_callback = None
        self._board = whisplay_board
        self._initialized = False
        self._simulated_pressed = False
    
    def set_board(self, board):
        """设置 WhisplayBoard 实例（LCD 初始化后调用）"""
        self._board = board
        self._initialized = True
    
    def on_press(self, callback: Callable) -> None:
        """
        注册按键按下回调
        
        Args:
            callback: 按键按下时调用的函数
        """
        self._callback = callback
        
        if self._board:
            # 使用 WhisplayBoard 的按钮回调
            def on_button_press():
                if self._callback:
                    self._callback()
            
            self._board.on_button_press(on_button_press)
            self._initialized = True
    
    def on_release(self, callback: Callable) -> None:
        """
        注册按键松开回调
        
        Args:
            callback: 按键松开时调用的函数
        """
        self._release_callback = callback
        
        if self._board:
            def on_button_release():
                if self._release_callback:
                    self._release_callback()
            
            self._board.on_button_release(on_button_release)
    
    def wait_for_press(self, timeout: Optional[float] = None) -> bool:
        """
        阻塞等待按键按下
        
        Args:
            timeout: 超时时间（秒），None 表示永久等待
        
        Returns:
            是否检测到按键（超时返回 False）
        """
        if not self._board:
            time.sleep(timeout or 1)
            return False
        
        start = time.time()
        while True:
            if self._board.button_pressed():
                return True
            if timeout and (time.time() - start) >= timeout:
                return False
            time.sleep(0.05)
    
    def is_pressed(self) -> bool:
        """检查按键是否被按下"""
        if self._board:
            return self._board.button_pressed()
        return self._simulated_pressed
    
    def cleanup(self):
        """清理资源（由 WhisplayBoard 统一管理）"""
        self._initialized = False


# 模拟模式
class MockButton:
    """模拟按键（用于开发测试）"""
    
    def __init__(self, pin: int = 17, chip: str = "", whisplay_board=None):
        self.pin = pin
        self._callback = None
        self._release_callback = None
        self._pressed = False
    
    def set_board(self, board):
        pass
    
    def on_press(self, callback: Callable) -> None:
        print(f"[MockButton] Registered press callback on pin {self.pin}")
        self._callback = callback
    
    def on_release(self, callback: Callable) -> None:
        print(f"[MockButton] Registered release callback on pin {self.pin}")
        self._release_callback = callback
    
    def wait_for_press(self, timeout: Optional[float] = None) -> bool:
        print(f"[MockButton] Waiting for press (timeout={timeout})")
        import time
        time.sleep(timeout or 1)
        return True
    
    def is_pressed(self) -> bool:
        return self._pressed
    
    def simulate_press(self):
        """模拟按键按下（用于测试）"""
        self._pressed = True
        if self._callback:
            self._callback()
    
    def simulate_release(self):
        """模拟按键松开（用于测试）"""
        self._pressed = False
        if self._release_callback:
            self._release_callback()
    
    def cleanup(self):
        pass
