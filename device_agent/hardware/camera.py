"""
Camera Module - picamera2 封装
"""
import io
import os
from typing import Optional


class Camera:
    """相机封装类"""
    
    def __init__(self):
        self._camera = None
        self._initialized = False
    
    def warmup(self):
        """预热相机（提前初始化）"""
        print("[Camera] Warming up...")
        self._ensure_initialized()
        print("[Camera] Warmup complete")
    
    def _ensure_initialized(self):
        """确保相机已初始化"""
        if self._initialized:
            return
        
        try:
            from picamera2 import Picamera2
            self._camera = Picamera2()
            self._camera.configure(
                self._camera.create_still_configuration(
                    main={"size": (1920, 1080)},
                    lores={"size": (640, 480)},
                    display="lores"
                )
            )
            self._initialized = True
        except ImportError:
            raise RuntimeError("picamera2 not installed. Run: pip install picamera2")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize camera: {e}")
    
    def capture(self, path: str) -> str:
        """
        拍照并保存到指定路径
        
        Args:
            path: 图片保存路径
        
        Returns:
            保存的图片路径
        """
        self._ensure_initialized()
        
        # 确保目录存在
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        self._camera.start()
        try:
            self._camera.capture_file(path)
        finally:
            self._camera.stop()
        
        return path
    
    def capture_bytes(self) -> bytes:
        """
        拍照并返回字节数据
        
        Returns:
            JPEG 格式的图片字节数据
        """
        self._ensure_initialized()
        
        self._camera.start()
        try:
            stream = io.BytesIO()
            self._camera.capture_file(stream, format="jpeg")
            return stream.getvalue()
        finally:
            self._camera.stop()
    
    def close(self):
        """关闭相机"""
        if self._camera:
            self._camera.close()
            self._initialized = False


# 模拟模式（用于非 Pi 环境测试）
class MockCamera:
    """模拟相机（用于开发测试）"""
    
    def warmup(self):
        print("[MockCamera] Warming up...")
    
    def capture(self, path: str) -> str:
        print(f"[MockCamera] Capturing to {path}")
        return path
    
    def capture_bytes(self) -> bytes:
        print("[MockCamera] Capturing bytes")
        return b"mock_image_data"
    
    def close(self):
        pass
