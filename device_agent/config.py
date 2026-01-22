"""
Snap2Know Device Agent Configuration
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Device Agent 配置"""
    
    # MBP 后端配置
    mbp_host: str = "192.168.1.100"
    mbp_port: int = 8000
    
    # 硬件配置
    audio_device: str = "auto"  # 自动检测 WM8960 声卡
    button_pin: int = 17
    led_red_pin: int = 5
    led_green_pin: int = 6
    led_blue_pin: int = 13
    
    # 录音配置
    record_duration: int = 5
    record_sample_rate: int = 16000
    
    # VAD (语音活动检测) 配置
    vad_threshold: int = 2000      # 静音阈值 (RMS) - 调高以避免底噪
    vad_max_duration: int = 30     # 最大录音时长（秒）
    vad_silence_duration: float = 2.0  # 持续沉默停止（秒）
    
    # 唤醒词配置
    wake_word_enabled: bool = True
    wake_word: str = "小帮"
    wake_word_count: int = 2       # 需要检测到几次（"小帮，小帮" = 2次）
    wake_word_model_path: str = "/opt/snap2know/vosk-model-small-cn-0.22"
    wake_word_device: str = "plughw:2,0"  # USB 麦克风用于唤醒词检测
    
    # 临时文件目录
    tmp_dir: str = "/opt/snap2know/tmp"
    
    # 日志目录
    log_dir: str = "/opt/snap2know/logs"
    
    # 调试模式
    debug: bool = True
    
    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量加载配置"""
        return cls(
            mbp_host=os.getenv("MBP_HOST", cls.mbp_host),
            mbp_port=int(os.getenv("MBP_PORT", cls.mbp_port)),
            audio_device=os.getenv("AUDIO_DEVICE", cls.audio_device),
            button_pin=int(os.getenv("BUTTON_PIN", cls.button_pin)),
            led_red_pin=int(os.getenv("LED_RED_PIN", cls.led_red_pin)),
            led_green_pin=int(os.getenv("LED_GREEN_PIN", cls.led_green_pin)),
            led_blue_pin=int(os.getenv("LED_BLUE_PIN", cls.led_blue_pin)),
            record_duration=int(os.getenv("RECORD_DURATION", cls.record_duration)),
            record_sample_rate=int(os.getenv("RECORD_SAMPLE_RATE", cls.record_sample_rate)),
            tmp_dir=os.getenv("TMP_DIR", cls.tmp_dir),
            log_dir=os.getenv("LOG_DIR", cls.log_dir),
            debug=os.getenv("DEBUG", "true").lower() == "true"
        )
    
    @property
    def mbp_base_url(self) -> str:
        """获取 MBP 后端基础 URL"""
        return f"http://{self.mbp_host}:{self.mbp_port}"
    
    @property
    def mbp_ws_url(self) -> str:
        """获取 MBP WebSocket URL"""
        return f"ws://{self.mbp_host}:{self.mbp_port}"


# 全局配置实例
config = Config.from_env()
