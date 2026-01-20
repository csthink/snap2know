"""
LCD Module - Pi 5 Compatible SPI LCD Driver (Whisplay 1.3" LCD)
使用 gpiod + spidev 替代 RPi.GPIO
"""
import os
import time
from typing import Optional, Tuple

# GPIO 引脚映射 (BOARD -> BCM)
# DC_PIN = 13 (BOARD) = GPIO 27
# RST_PIN = 7 (BOARD) = GPIO 4
# LED_PIN = 15 (BOARD) = GPIO 22

BCM_DC_PIN = 27
BCM_RST_PIN = 4
BCM_LED_PIN = 22


class LCD:
    """LCD 显示封装类（Pi 5 兼容，使用 lgpio）"""
    
    # LCD 配置
    WIDTH = 240
    HEIGHT = 240  # 实际高度 280，但可视区 240
    CORNER_HEIGHT = 20  # 圆角偏移
    
    def __init__(self):
        self._initialized = False
        self._spi = None
        self._gpio_handle = None
    
    def _ensure_initialized(self):
        """确保显示已初始化"""
        if self._initialized:
            return
        
        try:
            import spidev
            import lgpio
            
            self._lgpio = lgpio
            
            # 初始化 GPIO
            self._gpio_handle = lgpio.gpiochip_open(0)
            
            # 设置引脚为输出
            lgpio.gpio_claim_output(self._gpio_handle, BCM_DC_PIN)
            lgpio.gpio_claim_output(self._gpio_handle, BCM_RST_PIN)
            lgpio.gpio_claim_output(self._gpio_handle, BCM_LED_PIN)
            
            # 初始化 SPI
            self._spi = spidev.SpiDev()
            self._spi.open(0, 0)
            self._spi.max_speed_hz = 62_500_000  # 62.5 MHz
            self._spi.mode = 0b00
            
            # 初始化显示
            self._reset_lcd()
            self._init_display()
            self.fill_screen(0x0000)  # 黑色
            self._set_backlight(True)
            
            self._initialized = True
            print("[LCD] Initialized successfully")
            
        except Exception as e:
            print(f"[LCD] Init failed: {e}")
            raise RuntimeError(f"LCD initialization failed: {e}")
    
    def _set_gpio(self, pin: int, value: bool):
        """设置 GPIO 输出"""
        if self._gpio_handle is not None:
            self._lgpio.gpio_write(self._gpio_handle, pin, 1 if value else 0)
    
    def _set_backlight(self, on: bool):
        """控制背光"""
        # LED_PIN 低电平点亮
        self._set_gpio(BCM_LED_PIN, not on)
    
    def _reset_lcd(self):
        """复位 LCD"""
        self._set_gpio(BCM_RST_PIN, True)
        time.sleep(0.1)
        self._set_gpio(BCM_RST_PIN, False)
        time.sleep(0.1)
        self._set_gpio(BCM_RST_PIN, True)
        time.sleep(0.12)
    
    def _send_command(self, cmd, *args):
        """发送命令"""
        self._set_gpio(BCM_DC_PIN, False)  # Command mode
        self._spi.xfer2([cmd])
        if args:
            self._set_gpio(BCM_DC_PIN, True)  # Data mode
            self._send_data(list(args))
    
    def _send_data(self, data):
        """发送数据"""
        self._set_gpio(BCM_DC_PIN, True)  # Data mode
        # 分块发送避免溢出
        max_chunk = 4096
        for i in range(0, len(data), max_chunk):
            self._spi.writebytes(data[i:i + max_chunk])
    
    def _init_display(self):
        """初始化显示"""
        self._send_command(0x11)  # Sleep out
        time.sleep(0.12)
        
        # Memory Data Access Control - 设置方向
        self._send_command(0x36, 0xC0)  # Horizontal display
        
        # Pixel Format
        self._send_command(0x3A, 0x05)  # 16-bit color
        
        # Porch Setting
        self._send_command(0xB2, 0x0C, 0x0C, 0x00, 0x33, 0x33)
        
        # Gate Control
        self._send_command(0xB7, 0x35)
        
        # VCOM Setting
        self._send_command(0xBB, 0x32)
        
        # LCM Control
        self._send_command(0xC2, 0x01)
        
        # VDV and VRH Command Enable
        self._send_command(0xC3, 0x15)
        
        # VRH Set
        self._send_command(0xC4, 0x20)
        
        # Frame Rate Control
        self._send_command(0xC6, 0x0F)
        
        # Power Control
        self._send_command(0xD0, 0xA4, 0xA1)
        
        # Positive Voltage Gamma Control
        self._send_command(0xE0, 0xD0, 0x08, 0x0E, 0x09, 0x09, 0x05, 0x31, 0x33,
                          0x48, 0x17, 0x14, 0x15, 0x31, 0x34)
        
        # Negative Voltage Gamma Control
        self._send_command(0xE1, 0xD0, 0x08, 0x0E, 0x09, 0x09, 0x15, 0x31, 0x33,
                          0x48, 0x17, 0x14, 0x15, 0x31, 0x34)
        
        # Display Inversion On
        self._send_command(0x21)
        
        # Display On
        self._send_command(0x29)
    
    def _set_window(self, x0, y0, x1, y1):
        """设置绘图窗口"""
        # 添加圆角偏移
        y0 += self.CORNER_HEIGHT
        y1 += self.CORNER_HEIGHT
        
        self._send_command(0x2A, x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF)
        self._send_command(0x2B, y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF)
        self._send_command(0x2C)
    
    def fill_screen(self, color: int):
        """填充整个屏幕"""
        self._ensure_initialized()
        
        self._set_window(0, 0, self.WIDTH - 1, self.HEIGHT - 1)
        
        # 生成颜色数据
        hi = (color >> 8) & 0xFF
        lo = color & 0xFF
        data = [hi, lo] * (self.WIDTH * self.HEIGHT)
        
        self._send_data(data)
    
    def draw_image(self, image) -> None:
        """
        绘制 PIL Image 到 LCD
        
        Args:
            image: PIL.Image 对象 (RGB 模式, 240x240)
        """
        self._ensure_initialized()
        
        # 确保尺寸正确
        if image.size != (self.WIDTH, self.HEIGHT):
            image = image.resize((self.WIDTH, self.HEIGHT))
        
        # 转换为 RGB565
        pixel_data = []
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                r, g, b = image.getpixel((x, y))[:3]
                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                pixel_data.extend([(rgb565 >> 8) & 0xFF, rgb565 & 0xFF])
        
        self._set_window(0, 0, self.WIDTH - 1, self.HEIGHT - 1)
        self._send_data(pixel_data)
    
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
        
        from PIL import Image, ImageDraw, ImageFont
        
        image = Image.new("RGB", (self.WIDTH, self.HEIGHT), bg_color)
        draw = ImageDraw.Draw(image)
        
        font = self._get_font(size)
        
        lines = text.split('\n')
        y = position[1]
        for line in lines:
            draw.text((position[0], y), line, font=font, fill=color)
            y += size + 5
        
        self.draw_image(image)
    
    def _get_font(self, size: int = 24):
        """获取字体"""
        from PIL import ImageFont
        
        font_paths = [
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        
        for path in font_paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except:
                    continue
        
        return ImageFont.load_default()
    
    def show_status(self, status: str, message: str = "") -> None:
        """显示状态"""
        from PIL import Image, ImageDraw
        
        self._ensure_initialized()
        
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
    
    def clear(self) -> None:
        """清屏"""
        self._ensure_initialized()
        self.fill_screen(0x0000)
    
    def cleanup(self):
        """释放资源"""
        if self._gpio_handle is not None:
            try:
                self._set_backlight(False)
                self._lgpio.gpiochip_close(self._gpio_handle)
            except:
                pass
            self._gpio_handle = None
        
        if self._spi:
            try:
                self._spi.close()
            except:
                pass
            self._spi = None
        
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
    
    def show_image(self, path: str) -> None:
        print(f"[MockLCD] Image: {path}")
    
    def show_status(self, status: str, message: str = "") -> None:
        print(f"[MockLCD] Status: {status}, Message: {message}")
    
    def draw_image(self, image) -> None:
        print(f"[MockLCD] Drawing image")
    
    def fill_screen(self, color: int) -> None:
        print(f"[MockLCD] Fill: 0x{color:04X}")
    
    def clear(self) -> None:
        print("[MockLCD] Cleared")
    
    def cleanup(self):
        pass
