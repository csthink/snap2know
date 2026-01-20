"""
Snap2Know State Machine
Device Agent 状态机核心实现
"""
from enum import Enum, auto
from typing import Callable, Dict, Optional, Any
from dataclasses import dataclass, field
import time
import threading


class State(Enum):
    """设备状态枚举"""
    IDLE = auto()          # 空闲
    PRE_HOLD = auto()      # 预按住（300ms）
    RECORDING = auto()     # 录音中
    PROCESSING = auto()    # 处理中（STT/OCR）
    ANSWERING = auto()     # 回答中（TTS播放）
    DONE = auto()          # 完成
    MENU = auto()          # 菜单
    ERROR = auto()         # 错误
    BUSY = auto()          # 拍照入库中


# 状态对应的 LED 颜色
STATE_LED_COLORS = {
    State.IDLE: "blue",
    State.PRE_HOLD: "blue",  # 闪烁
    State.RECORDING: "red",
    State.PROCESSING: "yellow",
    State.ANSWERING: "green",
    State.DONE: "blue",
    State.MENU: "magenta",
    State.ERROR: "red",  # 闪烁
    State.BUSY: "yellow",
}


@dataclass
class StateData:
    """状态相关数据"""
    recording_start_time: float = 0
    recording_duration: float = 0
    error_message: str = ""
    answer_text: str = ""
    menu_selection: int = 0
    processing_message: str = ""


class StateMachine:
    """设备状态机"""
    
    def __init__(self):
        self._state = State.IDLE
        self._data = StateData()
        self._lock = threading.Lock()
        
        # 回调函数
        self._on_state_change: Optional[Callable[[State, State, StateData], None]] = None
        self._on_led_change: Optional[Callable[[str], None]] = None
        self._on_lcd_update: Optional[Callable[[State, StateData], None]] = None
        
        # 闪烁控制
        self._blink_thread: Optional[threading.Thread] = None
        self._blink_running = False
    
    @property
    def state(self) -> State:
        """获取当前状态"""
        return self._state
    
    @property
    def data(self) -> StateData:
        """获取状态数据"""
        return self._data
    
    def set_callbacks(
        self,
        on_state_change: Callable[[State, State, StateData], None] = None,
        on_led_change: Callable[[str], None] = None,
        on_lcd_update: Callable[[State, StateData], None] = None
    ):
        """设置回调函数"""
        self._on_state_change = on_state_change
        self._on_led_change = on_led_change
        self._on_lcd_update = on_lcd_update
    
    def transition_to(self, new_state: State, **kwargs):
        """
        状态转换
        
        Args:
            new_state: 目标状态
            **kwargs: 状态数据
        """
        with self._lock:
            old_state = self._state
            
            if old_state == new_state:
                return
            
            # 停止闪烁
            self._stop_blink()
            
            # 更新状态
            self._state = new_state
            
            # 更新状态数据
            for key, value in kwargs.items():
                if hasattr(self._data, key):
                    setattr(self._data, key, value)
            
            # 特殊状态处理
            if new_state == State.RECORDING:
                self._data.recording_start_time = time.time()
            elif new_state in (State.PRE_HOLD, State.ERROR):
                self._start_blink(STATE_LED_COLORS[new_state])
            
            # 触发回调
            if self._on_state_change:
                self._on_state_change(old_state, new_state, self._data)
            
            if self._on_led_change and new_state not in (State.PRE_HOLD, State.ERROR):
                self._on_led_change(STATE_LED_COLORS[new_state])
            
            if self._on_lcd_update:
                self._on_lcd_update(new_state, self._data)
    
    def update_recording_duration(self):
        """更新录音时长"""
        if self._state == State.RECORDING:
            self._data.recording_duration = time.time() - self._data.recording_start_time
            if self._on_lcd_update:
                self._on_lcd_update(self._state, self._data)
    
    def set_error(self, message: str):
        """设置错误状态"""
        self.transition_to(State.ERROR, error_message=message)
    
    def set_answer(self, text: str):
        """更新回答文字"""
        self._data.answer_text = text
        if self._state == State.ANSWERING and self._on_lcd_update:
            self._on_lcd_update(self._state, self._data)
    
    def append_answer(self, text: str):
        """追加回答文字"""
        self._data.answer_text += text
        if self._state == State.ANSWERING and self._on_lcd_update:
            self._on_lcd_update(self._state, self._data)
    
    def reset(self):
        """重置到空闲状态"""
        self._data = StateData()
        self.transition_to(State.IDLE)
    
    def _start_blink(self, color: str):
        """开始 LED 闪烁"""
        self._blink_running = True
        self._blink_thread = threading.Thread(
            target=self._blink_loop,
            args=(color,),
            daemon=True
        )
        self._blink_thread.start()
    
    def _stop_blink(self):
        """停止 LED 闪烁"""
        self._blink_running = False
        if self._blink_thread:
            self._blink_thread.join(timeout=0.5)
            self._blink_thread = None
    
    def _blink_loop(self, color: str):
        """闪烁循环"""
        on = True
        while self._blink_running:
            if self._on_led_change:
                self._on_led_change(color if on else "off")
            on = not on
            time.sleep(0.3)
    
    def can_cancel(self) -> bool:
        """是否可以取消当前操作"""
        return self._state in (State.BUSY, State.PROCESSING, State.ANSWERING)
    
    def cancel(self):
        """取消当前操作"""
        if self.can_cancel():
            self.reset()
