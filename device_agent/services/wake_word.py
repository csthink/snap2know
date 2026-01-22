"""
Snap2Know Wake Word Detector
使用 Vosk 实现唤醒词检测 ("小帮，小帮")
"""
import subprocess
import json
import threading
import time
from typing import Optional, Callable

try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    print("[WakeWord] Vosk not installed, wake word detection disabled")


class WakeWordDetector:
    """唤醒词检测器"""
    
    def __init__(
        self,
        model_path: str = "/opt/snap2know/vosk-model-small-cn-0.22",
        audio_device: str = "auto",
        wake_word: str = "小帮",
        required_count: int = 2,  # 需要检测到几次唤醒词
        detection_window: float = 5.0,  # 检测窗口时间（秒）- 增加到5秒更宽容
        on_wake: Optional[Callable[[], None]] = None
    ):
        """
        初始化唤醒词检测器
        
        Args:
            model_path: Vosk 中文模型路径
            audio_device: ALSA 音频设备
            wake_word: 唤醒词
            required_count: 需要检测到的次数（如 "小帮，小帮" = 2次）
            detection_window: 检测窗口时间
            on_wake: 唤醒回调函数
        """
        self.model_path = model_path
        self.audio_device = audio_device
        self.wake_word = wake_word
        self.required_count = required_count
        self.detection_window = detection_window
        self.on_wake = on_wake
        
        self._running = False
        self._active = False  # 是否正在监听
        self._thread: Optional[threading.Thread] = None
        self._model: Optional[Model] = None
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        
        # 对话模式（对话期间检测命令词）
        self._in_conversation = False
        self._on_command: Optional[Callable[[str], None]] = None
        
        # 检测状态
        self._detections: list = []
    
    def _detect_audio_device(self) -> str:
        """自动检测 WM8960 音频设备"""
        try:
            result = subprocess.run(
                ["arecord", "-l"],
                capture_output=True,
                text=True,
                timeout=5
            )
            for line in result.stdout.split('\n'):
                if 'wm8960' in line.lower() and line.startswith('card '):
                    parts = line.split(':')
                    if parts:
                        card_num = parts[0].replace('card ', '').strip()
                        return f"plughw:{card_num},0"
            return "plughw:1,0"
        except Exception:
            return "plughw:1,0"
    
    def start(self) -> bool:
        """启动唤醒词检测"""
        if not VOSK_AVAILABLE:
            print("[WakeWord] Vosk not available, cannot start")
            return False
        
        if self._running:
            return True
        
        # 加载模型
        try:
            print(f"[WakeWord] Loading model from {self.model_path}")
            self._model = Model(self.model_path)
            print("[WakeWord] Model loaded")
        except Exception as e:
            print(f"[WakeWord] Failed to load model: {e}")
            return False
        
        # 解析设备
        if self.audio_device == "auto":
            self.audio_device = self._detect_audio_device()
            print(f"[WakeWord] Auto-detected device: {self.audio_device}")
        
        self._running = True
        self._active = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        print(f"[WakeWord] Started listening for '{self.wake_word}' x{self.required_count}")
        return True
    
    def stop(self):
        """停止唤醒词检测"""
        self._running = False
        self._active = False
        self._stop_recording()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        print("[WakeWord] Stopped")
    
    def pause(self):
        """暂停检测（对话期间释放麦克风）"""
        self._active = False
        self._stop_recording()
        print("[WakeWord] Paused (microphone released)")
    
    def resume(self):
        """恢复检测"""
        self._active = True
        self._in_conversation = False
        self._detections.clear()
        print("[WakeWord] Resumed")
    
    def enter_conversation(self, on_command: Callable[[str], None]):
        """
        进入对话模式（保持监听，但切换到命令检测）
        
        Args:
            on_command: 命令回调 ("stop" 或 "new_topic")
        """
        self._in_conversation = True
        self._on_command = on_command
        self._active = True  # 保持监听
        self._detections.clear()
        print("[WakeWord] Entered conversation mode (listening for commands)")
    
    def exit_conversation(self):
        """退出对话模式"""
        self._in_conversation = False
        self._on_command = None
        self._detections.clear()
        print("[WakeWord] Exited conversation mode")
    
    def _stop_recording(self):
        """停止 arecord 进程"""
        with self._lock:
            if self._process:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=1)
                except:
                    try:
                        self._process.kill()
                    except:
                        pass
                self._process = None
    
    def _start_recording(self) -> Optional[subprocess.Popen]:
        """启动 arecord 进程"""
        cmd = [
            "arecord",
            "-D", self.audio_device,
            "-f", "S16_LE",
            "-r", "16000",
            "-c", "1",
            "-t", "raw",
            "-"
        ]
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            return process
        except Exception as e:
            print(f"[WakeWord] Failed to start recording: {e}")
            return None
    
    def _listen_loop(self):
        """监听循环"""
        sample_rate = 16000
        
        print("[WakeWord] Listen loop started")
        
        while self._running:
            # 等待激活
            if not self._active:
                time.sleep(0.2)
                continue
            
            # 启动录音
            with self._lock:
                self._process = self._start_recording()
            
            if not self._process:
                time.sleep(1)
                continue
            
            print("[WakeWord] Listening...")
            recognizer = KaldiRecognizer(self._model, sample_rate)
            recognizer.SetWords(True)
            
            try:
                while self._running and self._active:
                    data = self._process.stdout.read(4096)
                    if not data:
                        break
                    
                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        text = result.get("text", "")
                        if text:
                            self._process_text(text)
                    else:
                        partial = json.loads(recognizer.PartialResult())
                        text = partial.get("partial", "")
                        if text:
                            self._process_text(text)
            except Exception as e:
                print(f"[WakeWord] Error in listen loop: {e}")
            finally:
                self._stop_recording()
        
        print("[WakeWord] Listen loop ended")
    
    # 唤醒词变体（Vosk 常见误识别）
    WAKE_WORD_VARIANTS = [
        "小帮", "小芳", "少帮", "小胖", "晓帮", "小棒", "小邦",
        "小 帮", "少 帮", "小 芳"  # 带空格的变体
    ]
    
    def _contains_wake_word(self, text: str) -> bool:
        """检查文本是否包含唤醒词（含变体）"""
        for variant in self.WAKE_WORD_VARIANTS:
            if variant in text:
                return True
        return self.wake_word in text
    
    def _process_text(self, text: str):
        """处理识别到的文本"""
        # 调试日志
        if self._in_conversation:
            print(f"[WakeWord] [CONV] Heard: '{text}'")
        
        # 检查命令词（对话期间优先）
        if self._in_conversation and self._on_command:
            # 对话期间：检测 "小帮 + 命令词"（含变体）
            if self._contains_wake_word(text):
                command = self.detect_command(text)
                if command:
                    print(f"[WakeWord] Command detected during conversation: {command}")
                    self._on_command(command)
                    return
        
        # 正常唤醒词检测
        if self._contains_wake_word(text):
            # 统计唤醒词及所有变体出现的总次数
            count = 0
            if self.wake_word in text:
                count += text.count(self.wake_word)
            
            for variant in self.WAKE_WORD_VARIANTS:
                if variant in text:
                    count += text.count(variant)
            
            # 保底：如果检测到了但计数为0（防止逻辑漏洞），至少算1次
            if count == 0:
                count = 1
                
            now = time.time()
            
            for _ in range(count):
                self._detections.append(now)
            
            self._detections = [t for t in self._detections 
                              if now - t < self.detection_window]
            
            print(f"[WakeWord] Detected '{self.wake_word}' x{len(self._detections)} in window")
            
            if len(self._detections) >= self.required_count:
                print(f"[WakeWord] WAKE! Triggering callback")
                self._detections.clear()
                
                if self.on_wake:
                    # 暂停检测（释放麦克风）
                    self.pause()
                    self.on_wake()
    
    def quick_listen(self, duration: float = 1.0) -> Optional[str]:
        """
        快速监听一段时间，用于检测命令词
        
        Args:
            duration: 监听时长（秒）
        
        Returns:
            识别到的文本，或 None
        """
        if not VOSK_AVAILABLE or not self._model:
            return None
        
        # 解析设备
        device = self.audio_device
        if device == "auto":
            device = self._detect_audio_device()
        
        cmd = [
            "arecord",
            "-D", device,
            "-f", "S16_LE",
            "-r", "16000",
            "-c", "1",
            "-d", str(int(duration + 0.5)),  # 录音时长
            "-t", "raw",
            "-q",
            "-"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=duration + 2
            )
            
            if result.returncode != 0:
                return None
            
            audio_data = result.stdout
            if not audio_data:
                return None
            
            recognizer = KaldiRecognizer(self._model, 16000)
            recognizer.AcceptWaveform(audio_data)
            final = json.loads(recognizer.FinalResult())
            text = final.get("text", "")
            
            if text:
                print(f"[WakeWord] Quick listen result: {text}")
            return text if text else None
            
        except Exception as e:
            print(f"[WakeWord] Quick listen error: {e}")
            return None
    
    def detect_command(self, text: str) -> Optional[str]:
        """
        检测文本中的命令词
        
        Returns:
            "stop" - 暂停/停止
            "new_topic" - 换话题
            None - 无命令
        """
        if not text:
            return None
        
        # 停止命令
        stop_words = ["暂停", "停止", "够了", "停", "别说了"]
        for word in stop_words:
            if word in text:
                return "stop"
        
        # 换话题命令
        topic_words = ["换个话题", "换话题", "说别的", "下一个"]
        for word in topic_words:
            if word in text:
                return "new_topic"
        
        return None


# 测试代码
if __name__ == "__main__":
    def on_wake_callback():
        print("!!! WAKE WORD DETECTED !!!")
        time.sleep(3)  # 模拟对话
        print("!!! CONVERSATION DONE !!!")
    
    detector = WakeWordDetector(on_wake=on_wake_callback)
    if detector.start():
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            detector.stop()
