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
    
    def record_vad(
        self,
        path: str,
        max_duration: int = 30,
        silence_threshold: int = 500,
        silence_duration: float = 2.0,
        sample_rate: int = 16000,
        channels: int = 1
    ) -> bool:
        """
        带 VAD (语音活动检测) 的录音
        
        Args:
            path: 保存路径
            max_duration: 最大录音时长（秒）
            silence_threshold: 静音阈值 (RMS)
            silence_duration: 持续静音多长时间停止（秒）
        
        Returns:
            bool: 是否录到了有效音频
        """
        import time
        import struct
        import math
        
        # 确保目录存在
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # 启动 arecord 进程，输出到 stdout
        cmd = [
            "arecord",
            "-D", self.device,
            "-f", "S16_LE",
            "-r", str(sample_rate),
            "-c", str(channels),
            "-t", "wav",
            "-"  # 输出到 stdout
        ]
        
        print(f"[Audio] Starting VAD record: max={max_duration}s, threshold={silence_threshold}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        
        audio_data = bytearray()
        start_time = time.time()
        silence_start_time = None
        has_voice = False
        chunk_size = 4096  # 每次读取的块大小
        
        try:
            # 读取 WAV 头（44字节）并保留
            header = process.stdout.read(44)
            audio_data.extend(header)
            
            while True:
                # 检查最大时长
                if time.time() - start_time > max_duration:
                    print("[Audio] Max duration reached")
                    break
                
                chunk = process.stdout.read(chunk_size)
                if not chunk:
                    break
                
                audio_data.extend(chunk)
                
                # 计算 RMS (手动实现 audioop.rms)
                try:
                    # S16_LE means signed 2-byte integers
                    count = len(chunk) // 2
                    if count > 0:
                        # unpack options: < = little endian, h = short (2 bytes)
                        format_str = f"<{count}h" 
                        shorts = struct.unpack(format_str, chunk[:count*2])
                        
                        # RMS = sqrt(sum(sample^2) / count)
                        sum_squares = sum(s * s for s in shorts)
                        rms = math.sqrt(sum_squares / count)
                    else:
                        rms = 0
                except Exception as e:
                    # print(f"[Audio] RMS calc error: {e}")
                    rms = 0
                
                # VAD 逻辑
                if rms > silence_threshold:
                    if not has_voice:
                        print(f"[Audio] Voice detected! RMS={rms}")
                        has_voice = True
                    silence_start_time = None  # 重置静音计时
                else:
                    if has_voice:
                        # 只有在已经检测到语音后才开始计算静音时长
                        if silence_start_time is None:
                            silence_start_time = time.time()
                        elif time.time() - silence_start_time > silence_duration:
                            print(f"[Audio] Silence detected for {silence_duration}s, stopping.")
                            break
                    else:
                        # 还没检测到语音，如果一直沉默超过 5 秒（初始等待），则退出
                        # 或者这里可以稍微宽容一点
                        if time.time() - start_time > 5.0:
                            # print("[Audio] No voice detected (initial timeout)")
                            # 暂时不退出，等待直到 max_duration 或用户说话
                            # 但为了体验，如果 5 秒没人说话，可以认为用户不想说话
                           pass

        except Exception as e:
            print(f"[Audio] VAD record error: {e}")
        finally:
            process.terminate()
            try:
                process.wait(timeout=1)
            except:
                process.kill()
        
        # 保存文件
        if len(audio_data) > 44:  # 只有头是不够的
            with open(path, "wb") as f:
                f.write(audio_data)
            return has_voice
        return False
    
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
        elif data[:3] == b"ID3":
            # MP3 with ID3 tag
            suffix = ".mp3"
        elif len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
            # MP3 sync word (0xFF followed by 0xE0-0xFF)
            suffix = ".mp3"
        else:
            suffix = ".wav"
            print(f"[Audio] Unknown format, first bytes: {data[:4].hex()}")
        
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
