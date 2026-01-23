"""
Snap2Know Device Agent Configuration
"""
import os
import subprocess
import re
from dataclasses import dataclass, field
from typing import Optional, Tuple


def detect_audio_devices() -> Tuple[str, str]:
    """
    动态检测声卡设备
    
    Returns:
        (wm8960_device, usb_mic_device): WM8960 播放/录音设备 和 USB 麦克风设备
    """
    wm8960_device = "plughw:1,0"  # 默认值
    usb_mic_device = "plughw:3,0"  # 默认值
    
    try:
        # 执行 arecord -l 获取录音设备列表
        result = subprocess.run(
            ["arecord", "-l"],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stdout
        
        # 解析输出，查找 WM8960 和 USB 设备
        # 格式: card X: name [description], device Y: ...
        for line in output.split('\n'):
            if 'card' in line.lower() and ':' in line:
                # 提取 card 号
                match = re.search(r'card\s+(\d+):', line, re.IGNORECASE)
                if match:
                    card_num = match.group(1)
                    
                    if 'wm8960' in line.lower():
                        wm8960_device = f"plughw:{card_num},0"
                        print(f"[Config] Detected WM8960 at card {card_num}")
                    elif 'usb' in line.lower() and ('audio' in line.lower() or 'pnp' in line.lower()):
                        usb_mic_device = f"plughw:{card_num},0"
                        print(f"[Config] Detected USB microphone at card {card_num}")
        
    except Exception as e:
        print(f"[Config] Audio detection failed: {e}, using defaults")
    
    return wm8960_device, usb_mic_device


# 启动时检测设备
_detected_wm8960, _detected_usb_mic = detect_audio_devices()


@dataclass
class Config:
    """Device Agent 配置"""
    
    # MBP 后端配置
    mbp_host: str = "192.168.1.100"
    mbp_port: int = 8000
    
    # 硬件配置 - 动态检测
    audio_device: str = field(default_factory=lambda: _detected_wm8960)
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
    wake_word_device: str = field(default_factory=lambda: _detected_usb_mic)
    
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
            mbp_port=int(os.getenv("MBP_PORT", str(cls.mbp_port))),
            audio_device=os.getenv("AUDIO_DEVICE", _detected_wm8960),
            button_pin=int(os.getenv("BUTTON_PIN", str(cls.button_pin))),
            led_red_pin=int(os.getenv("LED_RED_PIN", str(cls.led_red_pin))),
            led_green_pin=int(os.getenv("LED_GREEN_PIN", str(cls.led_green_pin))),
            led_blue_pin=int(os.getenv("LED_BLUE_PIN", str(cls.led_blue_pin))),
            record_duration=int(os.getenv("RECORD_DURATION", str(cls.record_duration))),
            record_sample_rate=int(os.getenv("RECORD_SAMPLE_RATE", str(cls.record_sample_rate))),
            wake_word_device=os.getenv("WAKE_WORD_DEVICE", _detected_usb_mic),
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

