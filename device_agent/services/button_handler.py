"""
Snap2Know Button Handler
按键事件处理（短按/长按/超长按检测）
"""
import time
import threading
from typing import Callable, Optional
from enum import Enum, auto


class PressType(Enum):
    """按键类型"""
    TAP = auto()           # 短按 < 300ms
    PRE_HOLD = auto()      # 预按住 300-600ms
    HOLD = auto()          # 长按 ≥ 600ms
    LONG_HOLD = auto()     # 超长按 ≥ 3000ms
    CANCEL_HOLD = auto()   # 取消长按 ≥ 1200ms（在特定状态）


class ButtonHandler:
    """按键事件处理器"""
    
    # 时间阈值（毫秒）
    THRESHOLD_TAP = 300        # 短按阈值
    THRESHOLD_HOLD = 600       # 长按阈值
    THRESHOLD_LONG_HOLD = 3000  # 超长按阈值
    THRESHOLD_CANCEL = 1200    # 取消阈值
    
    def __init__(self):
        self._press_start: float = 0
        self._is_pressed = False
        self._timer_thread: Optional[threading.Thread] = None
        self._timer_running = False
        
        # 回调函数
        self._on_tap: Optional[Callable[[], None]] = None
        self._on_pre_hold: Optional[Callable[[], None]] = None
        self._on_hold_start: Optional[Callable[[], None]] = None
        self._on_hold_end: Optional[Callable[[float], None]] = None  # 传入录音时长
        self._on_long_hold: Optional[Callable[[], None]] = None
        self._on_cancel: Optional[Callable[[], None]] = None
        
        # 状态标记
        self._pre_hold_triggered = False
        self._hold_triggered = False
        self._long_hold_triggered = False
        self._cancel_triggered = False
        
        # 是否可取消（由外部设置）
        self._can_cancel = False
    
    def set_callbacks(
        self,
        on_tap: Callable[[], None] = None,
        on_pre_hold: Callable[[], None] = None,
        on_hold_start: Callable[[], None] = None,
        on_hold_end: Callable[[float], None] = None,
        on_long_hold: Callable[[], None] = None,
        on_cancel: Callable[[], None] = None
    ):
        """设置回调函数"""
        self._on_tap = on_tap
        self._on_pre_hold = on_pre_hold
        self._on_hold_start = on_hold_start
        self._on_hold_end = on_hold_end
        self._on_long_hold = on_long_hold
        self._on_cancel = on_cancel
    
    def set_can_cancel(self, can_cancel: bool):
        """设置是否可取消"""
        self._can_cancel = can_cancel
    
    def on_press(self):
        """按键按下"""
        self._press_start = time.time()
        self._is_pressed = True
        self._pre_hold_triggered = False
        self._hold_triggered = False
        self._long_hold_triggered = False
        self._cancel_triggered = False
        
        # 启动定时器
        self._start_timer()
    
    def on_release(self):
        """按键松开"""
        if not self._is_pressed:
            return
        
        self._is_pressed = False
        self._stop_timer()
        
        press_duration_ms = (time.time() - self._press_start) * 1000
        
        # 根据按压时长判断类型
        if self._cancel_triggered:
            # 取消操作已在定时器中触发
            pass
        elif self._long_hold_triggered:
            # 超长按已在定时器中触发
            pass
        elif self._hold_triggered:
            # 长按结束
            recording_duration = time.time() - self._press_start - (self.THRESHOLD_HOLD / 1000)
            if recording_duration > 0.5:  # 至少录音 0.5 秒才有效
                if self._on_hold_end:
                    self._on_hold_end(recording_duration)
            else:
                # 录音太短，取消
                if self._on_cancel:
                    self._on_cancel()
        elif self._pre_hold_triggered:
            # 预按住状态松开，不触发任何操作
            pass
        elif press_duration_ms < self.THRESHOLD_TAP:
            # 短按
            if self._on_tap:
                self._on_tap()
    
    def _start_timer(self):
        """启动按键计时器"""
        self._timer_running = True
        self._timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self._timer_thread.start()
    
    def _stop_timer(self):
        """停止按键计时器"""
        self._timer_running = False
        if self._timer_thread:
            self._timer_thread.join(timeout=0.5)
            self._timer_thread = None
    
    def _timer_loop(self):
        """计时器循环，检测各阈值"""
        while self._timer_running and self._is_pressed:
            elapsed_ms = (time.time() - self._press_start) * 1000
            
            # 取消检测（在可取消状态下）
            if self._can_cancel and elapsed_ms >= self.THRESHOLD_CANCEL and not self._cancel_triggered:
                self._cancel_triggered = True
                if self._on_cancel:
                    self._on_cancel()
                break
            
            # 超长按检测
            if elapsed_ms >= self.THRESHOLD_LONG_HOLD and not self._long_hold_triggered:
                self._long_hold_triggered = True
                if self._on_long_hold:
                    self._on_long_hold()
                break
            
            # 长按检测
            if elapsed_ms >= self.THRESHOLD_HOLD and not self._hold_triggered:
                self._hold_triggered = True
                if self._on_hold_start:
                    self._on_hold_start()
            
            # 预按住检测
            elif elapsed_ms >= self.THRESHOLD_TAP and not self._pre_hold_triggered:
                self._pre_hold_triggered = True
                if self._on_pre_hold:
                    self._on_pre_hold()
            
            time.sleep(0.05)  # 50ms 检测间隔
    
    def is_pressed(self) -> bool:
        """是否正在按下"""
        return self._is_pressed
    
    def get_press_duration(self) -> float:
        """获取当前按压时长（秒）"""
        if self._is_pressed:
            return time.time() - self._press_start
        return 0
