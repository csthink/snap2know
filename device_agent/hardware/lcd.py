"""
LCD Module - SPI LCD 显示封装（Whisplay 1.3" LCD）
"""
import os
from typing import Optional, Tuple


class LCD:
    """LCD 显示封装类"""
    
    # LCD 配置
    WIDTH = 240
    HEIGHT = 240
    
    # 状态颜色映射
    STATUS_COLORS = {
        "idle": (0, 128, 255),       # 蓝色
        "recording": (255, 0, 0),     # 红色
        "processing": (255, 255, 0),  # 黄色
        "speaking": (0, 255, 0),      # 绿色
        "error": (255, 0, 128)        # 紫红色
    }
    
    def __init__(self):
        self._initialized = False
        self._display = None
    
    def _ensure_initialized(self):
        """确保显示已初始化"""
        if self._initialized:
            return
        
        try:
            # 尝试导入 Whisplay LCD 驱动
            # 这里需要根据实际的 Whisplay 驱动调整
            from PIL import Image, ImageDraw, ImageFont
            self._pil_image = Image
            self._pil_draw = ImageDraw
            self._pil_font = ImageFont
            self._initialized = True
        except ImportError as e:
            raise RuntimeError(f"Required library not installed: {e}")
    
    def _get_font(self, size: int = 24):
        """获取字体"""
        font_paths = [
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
        ]
        
        for path in font_paths:
            if os.path.exists(path):
                try:
                    return self._pil_font.truetype(path, size)
                except:
                    continue
        
        # 使用默认字体
        return self._pil_font.load_default()
    
    def _display_image(self, image):
        """
        将图像发送到 LCD 显示
        
        注意：这里需要根据实际的 Whisplay 驱动实现
        目前先打印调试信息
        """
        # TODO: 实现实际的 SPI 显示驱动
        # 这里可能需要使用 Whisplay 提供的驱动库
        if hasattr(self, '_spi_display'):
            self._spi_display.display(image)
        else:
            # 调试模式：保存到临时文件
            debug_path = "/tmp/lcd_preview.png"
            image.save(debug_path)
            print(f"[LCD] Preview saved to {debug_path}")
    
    def show_text(
        self,
        text: str,
        size: int = 24,
        color: Tuple[int, int, int] = (255, 255, 255),
        bg_color: Tuple[int, int, int] = (0, 0, 0),
        position: Tuple[int, int] = (10, 10)
    ) -> None:
        """
        显示文字
        
        Args:
            text: 要显示的文字
            size: 字体大小
            color: 文字颜色 (R, G, B)
            bg_color: 背景颜色 (R, G, B)
            position: 文字位置 (x, y)
        """
        self._ensure_initialized()
        
        image = self._pil_image.new("RGB", (self.WIDTH, self.HEIGHT), bg_color)
        draw = self._pil_draw.Draw(image)
        font = self._get_font(size)
        
        # 支持多行文本
        lines = text.split('\n')
        y = position[1]
        for line in lines:
            draw.text((position[0], y), line, font=font, fill=color)
            y += size + 5
        
        self._display_image(image)
    
    def show_image(self, path: str) -> None:
        """
        显示图片
        
        Args:
            path: 图片路径
        """
        self._ensure_initialized()
        
        if not os.path.exists(path):
            raise FileNotFoundError(f"Image not found: {path}")
        
        image = self._pil_image.open(path)
        image = image.resize((self.WIDTH, self.HEIGHT))
        
        self._display_image(image)
    
    def show_status(self, status: str, message: str = "") -> None:
        """
        显示状态
        
        Args:
            status: 状态名称（idle, recording, processing, speaking, error）
            message: 附加消息
        """
        self._ensure_initialized()
        
        bg_color = self.STATUS_COLORS.get(status, (128, 128, 128))
        
        image = self._pil_image.new("RGB", (self.WIDTH, self.HEIGHT), bg_color)
        draw = self._pil_draw.Draw(image)
        font = self._get_font(28)
        small_font = self._get_font(18)
        
        # 状态文字
        status_text = {
            "idle": "就绪",
            "recording": "录音中...",
            "processing": "处理中...",
            "speaking": "播放中...",
            "error": "错误"
        }.get(status, status)
        
        # 居中显示状态
        text_bbox = draw.textbbox((0, 0), status_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        x = (self.WIDTH - text_width) // 2
        draw.text((x, 100), status_text, font=font, fill=(255, 255, 255))
        
        # 显示附加消息
        if message:
            msg_bbox = draw.textbbox((0, 0), message, font=small_font)
            msg_width = msg_bbox[2] - msg_bbox[0]
            x = (self.WIDTH - msg_width) // 2
            draw.text((x, 150), message, font=small_font, fill=(255, 255, 255))
        
        self._display_image(image)
    
    def clear(self) -> None:
        """清屏"""
        self._ensure_initialized()
        
        image = self._pil_image.new("RGB", (self.WIDTH, self.HEIGHT), (0, 0, 0))
        self._display_image(image)


# 模拟模式
class MockLCD:
    """模拟 LCD（用于开发测试）"""
    
    WIDTH = 240
    HEIGHT = 240
    
    def show_text(self, text: str, **kwargs) -> None:
        print(f"[MockLCD] Text: {text}")
    
    def show_image(self, path: str) -> None:
        print(f"[MockLCD] Image: {path}")
    
    def show_status(self, status: str, message: str = "") -> None:
        print(f"[MockLCD] Status: {status}, Message: {message}")
    
    def clear(self) -> None:
        print("[MockLCD] Cleared")
