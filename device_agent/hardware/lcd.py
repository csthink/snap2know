"""
LCD Module - Whisplay LCD Driver Wrapper
使用官方 WhisplayBoard 驱动实现 LCD 显示
"""
import os
import sys
from typing import Tuple

# 添加 whisplay-ai-chatbot 驱动路径
WHISPLAY_DRIVER_PATH = "/opt/whisplay-ai-chatbot/python"
if WHISPLAY_DRIVER_PATH not in sys.path:
    sys.path.insert(0, WHISPLAY_DRIVER_PATH)


class LCD:
    """LCD 显示封装类（使用 WhisplayBoard 驱动）"""
    
    # LCD 配置
    WIDTH = 240
    HEIGHT = 240  # 可视区高度
    REAL_HEIGHT = 280  # 实际高度
    
    def __init__(self):
        self._initialized = False
        self._board = None
        self._pil_image = None
        self._pil_draw = None
    
    def _ensure_initialized(self):
        """确保显示已初始化"""
        if self._initialized:
            return
        
        try:
            from whisplay import WhisplayBoard
            from PIL import Image, ImageDraw, ImageFont
            
            self._pil_image = Image
            self._pil_draw = ImageDraw
            self._pil_font = ImageFont
            
            self._board = WhisplayBoard()
            self._board.set_backlight(80)  # 80% 亮度
            
            self._initialized = True
            print("[LCD] Initialized successfully")
            
        except Exception as e:
            print(f"[LCD] Init failed: {e}")
            # 降级为预览模式
            self._initialized = True
            self._board = None
    
    def get_board(self):
        """获取 WhisplayBoard 实例（供按钮共享）"""
        self._ensure_initialized()
        return self._board
    
    def _get_font(self, size: int = 24):
        """获取字体"""
        font_paths = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        
        for path in font_paths:
            if os.path.exists(path):
                try:
                    return self._pil_font.truetype(path, size)
                except:
                    continue
        
        return self._pil_font.load_default()
    
    def _image_to_rgb565(self, image) -> list:
        """将 PIL Image 转换为 RGB565 格式"""
        if image.size != (self.WIDTH, self.HEIGHT):
            image = image.resize((self.WIDTH, self.HEIGHT))
        
        pixel_data = []
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                r, g, b = image.getpixel((x, y))[:3]
                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                pixel_data.extend([(rgb565 >> 8) & 0xFF, rgb565 & 0xFF])
        
        return pixel_data
    
    def draw_image(self, image) -> None:
        """绘制 PIL Image 到 LCD"""
        self._ensure_initialized()
        
        if self._board:
            pixel_data = self._image_to_rgb565(image)
            self._board.draw_image(0, 0, self.WIDTH, self.HEIGHT, pixel_data)
        else:
            # 预览模式
            image.save("/tmp/lcd_preview.png")
            print("[LCD] Preview saved to /tmp/lcd_preview.png")
    
    def fill_screen(self, color: int) -> None:
        """填充整个屏幕"""
        self._ensure_initialized()
        
        if self._board:
            self._board.fill_screen(color)
        else:
            print(f"[LCD] Fill: 0x{color:04X}")
    
    def show_status(self, status: str, message: str = "") -> None:
        """显示状态"""
        self._ensure_initialized()
        
        from PIL import Image, ImageDraw
        
        # 状态颜色映射
        colors = {
            "idle": (0, 80, 180),
            "pre_hold": (0, 100, 200),
            "recording": (180, 0, 0),
            "processing": (180, 180, 0),
            "answering": (0, 150, 0),
            "done": (0, 120, 100),
            "menu": (100, 0, 150),
            "error": (200, 0, 50),
            "busy": (150, 100, 0),
        }
        
        bg_color = colors.get(status.lower(), (80, 80, 80))
        
        image = Image.new("RGB", (self.WIDTH, self.HEIGHT), bg_color)
        draw = ImageDraw.Draw(image)
        
        font = self._get_font(28)
        small_font = self._get_font(18)
        
        status_text = {
            "idle": "就绪",
            "pre_hold": "继续按住...",
            "recording": "录音中...",
            "processing": "处理中...",
            "answering": "播放中...",
            "done": "完成",
            "menu": "菜单",
            "error": "错误",
            "busy": "拍照中..."
        }.get(status.lower(), status)
        
        # 居中显示
        bbox = draw.textbbox((0, 0), status_text, font=font)
        x = (self.WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((x, 100), status_text, font=font, fill=(255, 255, 255))
        
        if message:
            bbox = draw.textbbox((0, 0), message, font=small_font)
            x = (self.WIDTH - (bbox[2] - bbox[0])) // 2
            draw.text((x, 150), message, font=small_font, fill=(255, 255, 255))
        
        self.draw_image(image)
    
    def show_text(
        self,
        text: str,
        size: int = 24,
        color: Tuple[int, int, int] = (255, 255, 255),
        bg_color: Tuple[int, int, int] = (0, 0, 0),
        position: Tuple[int, int] = (10, 10)
    ) -> None:
        """显示文字"""
        self._ensure_initialized()
        
        from PIL import Image, ImageDraw
        
        image = Image.new("RGB", (self.WIDTH, self.HEIGHT), bg_color)
        draw = ImageDraw.Draw(image)
        
        font = self._get_font(size)
        
        lines = text.split('\n')
        y = position[1]
        for line in lines:
            draw.text((position[0], y), line, font=font, fill=color)
            y += size + 5
        
        self.draw_image(image)
    
    def set_backlight(self, brightness: int) -> None:
        """设置背光亮度 (0-100)"""
        self._ensure_initialized()
        
        if self._board:
            self._board.set_backlight(brightness)
    
    def set_rgb(self, r: int, g: int, b: int) -> None:
        """设置 RGB LED 颜色"""
        self._ensure_initialized()
        
        if self._board:
            self._board.set_rgb(r, g, b)
    
    def clear(self) -> None:
        """清屏"""
        self._ensure_initialized()
        self.fill_screen(0x0000)
    
    def cleanup(self):
        """释放资源"""
        if self._board:
            try:
                self._board.set_backlight(0)
                self._board.set_rgb(0, 0, 0)
                self._board.cleanup()
            except:
                pass
            self._board = None
        self._initialized = False


# 模拟模式
class MockLCD:
    """模拟 LCD（用于开发测试）"""
    
    WIDTH = 240
    HEIGHT = 240
    
    def __init__(self):
        pass
    
    def show_text(self, text: str, **kwargs) -> None:
        print(f"[MockLCD] Text: {text[:30]}...")
    
    def show_status(self, status: str, message: str = "") -> None:
        print(f"[MockLCD] Status: {status}, Message: {message}")
    
    def draw_image(self, image) -> None:
        print(f"[MockLCD] Drawing image")
    
    def fill_screen(self, color: int) -> None:
        print(f"[MockLCD] Fill: 0x{color:04X}")
    
    def set_backlight(self, brightness: int) -> None:
        print(f"[MockLCD] Backlight: {brightness}%")
    
    def set_rgb(self, r: int, g: int, b: int) -> None:
        print(f"[MockLCD] RGB: ({r}, {g}, {b})")
    
    def clear(self) -> None:
        print("[MockLCD] Cleared")
    
    def cleanup(self):
        pass
