"""
LED Module - RGB LED 控制封装（Pi 5 兼容 gpiod 版本）
"""
from typing import Tuple


class LED:
    """RGB LED 控制封装类（使用 gpiod 支持 Pi 5）"""
    
    # 预定义颜色 (R, G, B)
    COLORS = {
        "red": (1, 0, 0),
        "green": (0, 1, 0),
        "blue": (0, 0, 1),
        "yellow": (1, 1, 0),
        "cyan": (0, 1, 1),
        "magenta": (1, 0, 1),
        "white": (1, 1, 1),
        "off": (0, 0, 0)
    }
    
    def __init__(
        self,
        red_pin: int = 5,
        green_pin: int = 6,
        blue_pin: int = 13,
        chip: str = "/dev/gpiochip4"  # Pi 5 使用 gpiochip4
    ):
        """
        初始化 LED 模块
        
        Args:
            red_pin: 红色 LED GPIO 引脚
            green_pin: 绿色 LED GPIO 引脚
            blue_pin: 蓝色 LED GPIO 引脚
            chip: GPIO 芯片设备路径
        """
        self.red_pin = red_pin
        self.green_pin = green_pin
        self.blue_pin = blue_pin
        self.chip_path = chip
        self._initialized = False
        self._chip = None
        self._lines = None
    
    def _ensure_initialized(self):
        """确保 GPIO 已初始化"""
        if self._initialized:
            return
        
        try:
            import gpiod
            from gpiod.line import Direction, Value
            
            self._gpiod = gpiod
            self._Direction = Direction
            self._Value = Value
            
            # 打开 GPIO 芯片
            self._chip = gpiod.Chip(self.chip_path)
            
            # 配置输出线
            config = {
                self.red_pin: gpiod.LineSettings(
                    direction=Direction.OUTPUT,
                    output_value=Value.INACTIVE
                ),
                self.green_pin: gpiod.LineSettings(
                    direction=Direction.OUTPUT,
                    output_value=Value.INACTIVE
                ),
                self.blue_pin: gpiod.LineSettings(
                    direction=Direction.OUTPUT,
                    output_value=Value.INACTIVE
                )
            }
            
            self._lines = self._chip.request_lines(
                consumer="snap2know-led",
                config=config
            )
            
            self._initialized = True
        except ImportError:
            raise RuntimeError("gpiod not installed. Run: pip install gpiod")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize GPIO: {e}")
    
    def set_color(self, color: str) -> None:
        """
        设置 LED 颜色
        
        Args:
            color: 颜色名称（red, green, blue, yellow, cyan, magenta, white, off）
        """
        self._ensure_initialized()
        
        r, g, b = self.COLORS.get(color.lower(), (0, 0, 0))
        
        self._lines.set_value(
            self.red_pin,
            self._Value.ACTIVE if r else self._Value.INACTIVE
        )
        self._lines.set_value(
            self.green_pin,
            self._Value.ACTIVE if g else self._Value.INACTIVE
        )
        self._lines.set_value(
            self.blue_pin,
            self._Value.ACTIVE if b else self._Value.INACTIVE
        )
    
    def set_rgb(self, r: int, g: int, b: int) -> None:
        """
        设置 RGB 值
        
        Args:
            r: 红色（0 或 1）
            g: 绿色（0 或 1）
            b: 蓝色（0 或 1）
        """
        self._ensure_initialized()
        
        self._lines.set_value(
            self.red_pin,
            self._Value.ACTIVE if r else self._Value.INACTIVE
        )
        self._lines.set_value(
            self.green_pin,
            self._Value.ACTIVE if g else self._Value.INACTIVE
        )
        self._lines.set_value(
            self.blue_pin,
            self._Value.ACTIVE if b else self._Value.INACTIVE
        )
    
    def off(self) -> None:
        """关闭 LED"""
        self.set_color("off")
    
    def cleanup(self):
        """清理 GPIO 资源"""
        if self._lines:
            try:
                # 关闭所有 LED
                self._lines.set_value(self.red_pin, self._Value.INACTIVE)
                self._lines.set_value(self.green_pin, self._Value.INACTIVE)
                self._lines.set_value(self.blue_pin, self._Value.INACTIVE)
                self._lines.release()
            except:
                pass
            self._initialized = False


# 模拟模式
class MockLED:
    """模拟 LED（用于开发测试）"""
    
    COLORS = LED.COLORS
    
    def __init__(self, red_pin: int = 5, green_pin: int = 6, blue_pin: int = 13, chip: str = ""):
        self.red_pin = red_pin
        self.green_pin = green_pin
        self.blue_pin = blue_pin
        self._current_color = "off"
    
    def set_color(self, color: str) -> None:
        self._current_color = color
        print(f"[MockLED] Color set to: {color}")
    
    def set_rgb(self, r: int, g: int, b: int) -> None:
        print(f"[MockLED] RGB set to: ({r}, {g}, {b})")
    
    def off(self) -> None:
        self.set_color("off")
    
    def cleanup(self):
        pass
