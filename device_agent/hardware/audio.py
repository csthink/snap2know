"""
Audio Module - WM8960 录音/播放封装
"""
import subprocess
import tempfile
import os
from typing import Optional


class Audio:
    """音频录制/播放封装类"""
    
    def __init__(self, device: str = "plughw:0,0"):
        """
        初始化音频模块
        
        Args:
            device: ALSA 设备名称
        """
        self.device = device
    
    def record(
        self,
        path: str,
        duration: int = 5,
        sample_rate: int = 16000,
        channels: int = 1
    ) -> str:
        """
        录制音频
        
        Args:
            path: 音频保存路径
            duration: 录制时长（秒）
            sample_rate: 采样率
            channels: 声道数
        
        Returns:
            保存的音频路径
        """
        # 确保目录存在
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        cmd = [
            "arecord",
            "-D", self.device,
            "-f", "S16_LE",
            "-r", str(sample_rate),
            "-c", str(channels),
            "-d", str(duration),
            path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Recording failed: {e.stderr.decode()}")
        except FileNotFoundError:
            raise RuntimeError("arecord not found. Install alsa-utils.")
        
        return path
    
    def record_bytes(
        self,
        duration: int = 5,
        sample_rate: int = 16000,
        channels: int = 1
    ) -> bytes:
        """
        录制音频并返回字节数据
        
        Returns:
            WAV 格式的音频字节数据
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
        
        try:
            self.record(temp_path, duration, sample_rate, channels)
            with open(temp_path, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def play(self, path: str) -> None:
        """
        播放音频文件
        
        Args:
            path: 音频文件路径
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Audio file not found: {path}")
        
        cmd = ["aplay", "-D", self.device, path]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Playback failed: {e.stderr.decode()}")
        except FileNotFoundError:
            raise RuntimeError("aplay not found. Install alsa-utils.")
    
    def play_bytes(self, data: bytes) -> None:
        """
        播放音频字节数据
        
        Args:
            data: 音频字节数据（WAV 或 MP3）
        """
        # 检测格式
        if data[:4] == b"RIFF":
            suffix = ".wav"
        elif data[:3] == b"ID3" or data[:2] == b"\xff\xfb":
            suffix = ".mp3"
        else:
            suffix = ".wav"
        
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(data)
            temp_path = f.name
        
        try:
            if suffix == ".mp3":
                # MP3 需要使用 mpg123 或转换
                subprocess.run(
                    ["mpg123", "-q", "-a", self.device, temp_path],
                    check=True,
                    capture_output=True
                )
            else:
                self.play(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


# 模拟模式
class MockAudio:
    """模拟音频（用于开发测试）"""
    
    def __init__(self, device: str = "mock"):
        self.device = device
    
    def record(self, path: str, duration: int = 5, **kwargs) -> str:
        print(f"[MockAudio] Recording {duration}s to {path}")
        return path
    
    def record_bytes(self, duration: int = 5, **kwargs) -> bytes:
        print(f"[MockAudio] Recording {duration}s to bytes")
        return b"mock_audio_data"
    
    def play(self, path: str) -> None:
        print(f"[MockAudio] Playing {path}")
    
    def play_bytes(self, data: bytes) -> None:
        print(f"[MockAudio] Playing {len(data)} bytes")
