"""
Local STT Service using Faster-Whisper
"""
import os
import time
from typing import Optional
from faster_whisper import WhisperModel

# 模型保存路径
MODEL_CACHE_DIR = os.path.join(os.path.dirname(__file__), "models")

class LocalSTT:
    _instance = None
    _model = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = LocalSTT()
        return cls._instance
    
    def __init__(self, model_size: str = "large-v3", device: str = "auto"):
        self.model_size = model_size
        # 在 M2 Max 上，auto 通常会选择 CPU (使用 CTranslate2 优化)，也可能尝试 MPS
        # faster-whisper 在 Mac 上 CPU 推理速度极快，特别是量化后
        self.device = device 
        self.compute_type = "int8"  # int8 量化显著提升速度且精度损失微小
        
    def _load_model(self):
        """懒加载模型"""
        if self._model is None:
            print(f"[LocalSTT] Loading model {self.model_size} ({self.device})...")
            start_time = time.time()
            try:
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                    download_root=MODEL_CACHE_DIR
                )
                print(f"[LocalSTT] Model loaded in {time.time() - start_time:.2f}s")
            except Exception as e:
                print(f"[LocalSTT] Failed to load model: {e}")
                raise e

    def transcribe(self, audio_file, language: str = "zh") -> str:
        """
        转写音频文件
        
        Args:
            audio_file: 文件路径或文件对象
            language: 语言代码 (默认 'zh')
            
        Returns:
            转写后的文本
        """
        self._load_model()
        
        try:
            # faster-whisper 返回 segments 生成器
            segments, info = self._model.transcribe(
                audio_file,
                language=language,
                beam_size=5
            )
            
            # 收集所有段落文本
            text = "".join([segment.text for segment in segments])
            return text.strip()
            
        except Exception as e:
            print(f"[LocalSTT] Transcription failed: {e}")
            raise e
