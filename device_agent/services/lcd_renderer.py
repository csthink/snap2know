"""
Snap2Know LCD Renderer
LCD 状态渲染器（PIL/Pillow 绘制）
"""
import os
from typing import Tuple, Optional
from PIL import Image, ImageDraw, ImageFont
from dataclasses import dataclass


# 屏幕尺寸
SCREEN_WIDTH = 240
SCREEN_HEIGHT = 240

# 颜色定义
COLORS = {
    "bg_idle": (20, 40, 80),        # 深蓝
    "bg_recording": (80, 20, 20),   # 深红
    "bg_processing": (80, 60, 20),  # 深黄
    "bg_answering": (20, 60, 40),   # 深绿
    "bg_done": (20, 60, 60),        # 深青
    "bg_menu": (60, 40, 80),        # 深紫
    "bg_error": (100, 20, 20),      # 红色
    "bg_busy": (80, 60, 20),        # 深黄
    
    "text_primary": (255, 255, 255),    # 白色
    "text_secondary": (180, 180, 180),  # 灰色
    "text_accent": (100, 200, 255),     # 浅蓝
    "text_warning": (255, 200, 100),    # 橙色
    "text_error": (255, 100, 100),      # 红色
}


@dataclass
class RenderData:
    """渲染数据"""
    duration: float = 0
    message: str = ""
    answer_text: str = ""
    error_message: str = ""
    menu_selection: int = 0


class LCDRenderer:
    """LCD 渲染器"""
    
    def __init__(self, lcd_driver=None):
        """
        初始化渲染器
        
        Args:
            lcd_driver: LCD 驱动实例（可选，用于实际推屏）
        """
        self._lcd = lcd_driver
        self._font_large: Optional[ImageFont.FreeTypeFont] = None
        self._font_medium: Optional[ImageFont.FreeTypeFont] = None
        self._font_small: Optional[ImageFont.FreeTypeFont] = None
        self._load_fonts()
    
    def _load_fonts(self):
        """加载字体"""
        font_paths = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",  # Pi 5 安装的 Noto CJK
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.otf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        
        font_path = None
        for path in font_paths:
            if os.path.exists(path):
                font_path = path
                break
        
        try:
            if font_path:
                self._font_large = ImageFont.truetype(font_path, 36)
                self._font_medium = ImageFont.truetype(font_path, 24)
                self._font_small = ImageFont.truetype(font_path, 18)
            else:
                self._font_large = ImageFont.load_default()
                self._font_medium = ImageFont.load_default()
                self._font_small = ImageFont.load_default()
        except Exception as e:
            print(f"[LCDRenderer] Font loading failed: {e}")
            self._font_large = ImageFont.load_default()
            self._font_medium = ImageFont.load_default()
            self._font_small = ImageFont.load_default()
    
    def render(self, state: str, data: RenderData = None) -> Image.Image:
        """
        根据状态渲染 LCD 界面
        
        Args:
            state: 状态名称
            data: 渲染数据
        
        Returns:
            PIL Image 对象
        """
        data = data or RenderData()
        
        render_methods = {
            "idle": self._render_idle,
            "pre_hold": self._render_pre_hold,
            "recording": self._render_recording,
            "processing": self._render_processing,
            "answering": self._render_answering,
            "done": self._render_done,
            "menu": self._render_menu,
            "error": self._render_error,
            "busy": self._render_busy,
        }
        
        method = render_methods.get(state.lower(), self._render_idle)
        image = method(data)
        
        # 推送到 LCD
        self._push_to_display(image)
        
        return image
    
    def _create_canvas(self, bg_color: Tuple[int, int, int]) -> Tuple[Image.Image, ImageDraw.Draw]:
        """创建画布"""
        image = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT), bg_color)
        draw = ImageDraw.Draw(image)
        return image, draw
    
    def _draw_centered_text(
        self,
        draw: ImageDraw.Draw,
        text: str,
        y: int,
        font: ImageFont.FreeTypeFont,
        color: Tuple[int, int, int]
    ):
        """绘制居中文本"""
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (SCREEN_WIDTH - text_width) // 2
        draw.text((x, y), text, font=font, fill=color)
    
    def _render_idle(self, data: RenderData) -> Image.Image:
        """渲染空闲状态"""
        image, draw = self._create_canvas(COLORS["bg_idle"])
        
        # 主图标区域
        self._draw_centered_text(draw, "📱", 60, self._font_large, COLORS["text_primary"])
        
        # 主文本
        self._draw_centered_text(draw, "Snap2Know", 110, self._font_large, COLORS["text_primary"])
        self._draw_centered_text(draw, "就绪", 155, self._font_medium, COLORS["text_secondary"])
        
        # 底部提示
        self._draw_centered_text(draw, "短按拍照 · 长按录音", 210, self._font_small, COLORS["text_accent"])
        
        return image
    
    def _render_pre_hold(self, data: RenderData) -> Image.Image:
        """渲染预按住状态"""
        image, draw = self._create_canvas(COLORS["bg_idle"])
        
        self._draw_centered_text(draw, "👆", 60, self._font_large, COLORS["text_primary"])
        self._draw_centered_text(draw, "继续按住...", 120, self._font_medium, COLORS["text_warning"])
        self._draw_centered_text(draw, "即将开始录音", 160, self._font_small, COLORS["text_secondary"])
        
        return image
    
    def _render_recording(self, data: RenderData) -> Image.Image:
        """渲染录音状态"""
        image, draw = self._create_canvas(COLORS["bg_recording"])
        
        # 录音图标
        self._draw_centered_text(draw, "🎤", 50, self._font_large, COLORS["text_primary"])
        
        # 录音状态
        self._draw_centered_text(draw, "正在录音", 110, self._font_medium, COLORS["text_primary"])
        
        # 录音时长
        duration = data.duration
        time_str = f"{int(duration // 60):02d}:{int(duration % 60):02d}"
        self._draw_centered_text(draw, time_str, 150, self._font_large, COLORS["text_warning"])
        
        # 底部提示
        self._draw_centered_text(draw, "松开结束录音", 210, self._font_small, COLORS["text_accent"])
        
        return image
    
    def _render_processing(self, data: RenderData) -> Image.Image:
        """渲染处理状态"""
        image, draw = self._create_canvas(COLORS["bg_processing"])
        
        self._draw_centered_text(draw, "⏳", 60, self._font_large, COLORS["text_primary"])
        self._draw_centered_text(draw, "处理中", 120, self._font_medium, COLORS["text_primary"])
        
        message = data.message or "请稍候..."
        self._draw_centered_text(draw, message, 160, self._font_small, COLORS["text_secondary"])
        
        return image
    
    def _render_answering(self, data: RenderData) -> Image.Image:
        """渲染回答状态"""
        image, draw = self._create_canvas(COLORS["bg_answering"])
        
        self._draw_centered_text(draw, "💬", 30, self._font_large, COLORS["text_primary"])
        
        # 回答文本（截取最后 100 字符）
        answer = data.answer_text[-100:] if data.answer_text else "正在回答..."
        
        # 自动换行
        lines = self._wrap_text(answer, 12)  # 每行约 12 个字符
        y = 80
        for line in lines[:5]:  # 最多显示 5 行
            self._draw_centered_text(draw, line, y, self._font_small, COLORS["text_primary"])
            y += 25
        
        # 底部提示
        self._draw_centered_text(draw, "短按静音 · 长按停止", 210, self._font_small, COLORS["text_accent"])
        
        return image
    
    def _render_done(self, data: RenderData) -> Image.Image:
        """渲染完成状态"""
        image, draw = self._create_canvas(COLORS["bg_done"])
        
        self._draw_centered_text(draw, "✅", 80, self._font_large, COLORS["text_primary"])
        self._draw_centered_text(draw, "完成", 140, self._font_large, COLORS["text_primary"])
        
        return image
    
    def _render_menu(self, data: RenderData) -> Image.Image:
        """渲染菜单状态"""
        image, draw = self._create_canvas(COLORS["bg_menu"])
        
        self._draw_centered_text(draw, "⚙️", 30, self._font_large, COLORS["text_primary"])
        self._draw_centered_text(draw, "菜单", 80, self._font_medium, COLORS["text_primary"])
        
        menu_items = ["清除会话", "网络设置", "返回"]
        y = 120
        for i, item in enumerate(menu_items):
            color = COLORS["text_accent"] if i == data.menu_selection else COLORS["text_secondary"]
            prefix = "▶ " if i == data.menu_selection else "  "
            self._draw_centered_text(draw, f"{prefix}{item}", y, self._font_small, color)
            y += 30
        
        return image
    
    def _render_error(self, data: RenderData) -> Image.Image:
        """渲染错误状态"""
        image, draw = self._create_canvas(COLORS["bg_error"])
        
        self._draw_centered_text(draw, "❌", 60, self._font_large, COLORS["text_primary"])
        self._draw_centered_text(draw, "错误", 120, self._font_medium, COLORS["text_error"])
        
        error_msg = data.error_message or "未知错误"
        # 截断过长的错误信息
        if len(error_msg) > 20:
            error_msg = error_msg[:20] + "..."
        self._draw_centered_text(draw, error_msg, 160, self._font_small, COLORS["text_secondary"])
        
        self._draw_centered_text(draw, "短按重试", 210, self._font_small, COLORS["text_accent"])
        
        return image
    
    def _render_busy(self, data: RenderData) -> Image.Image:
        """渲染拍照入库状态"""
        image, draw = self._create_canvas(COLORS["bg_busy"])
        
        self._draw_centered_text(draw, "📷", 60, self._font_large, COLORS["text_primary"])
        self._draw_centered_text(draw, "拍照中", 120, self._font_medium, COLORS["text_primary"])
        self._draw_centered_text(draw, "正在入库...", 160, self._font_small, COLORS["text_secondary"])
        
        return image
    
    def _wrap_text(self, text: str, chars_per_line: int) -> list:
        """文本自动换行"""
        lines = []
        while text:
            if len(text) <= chars_per_line:
                lines.append(text)
                break
            lines.append(text[:chars_per_line])
            text = text[chars_per_line:]
        return lines
    
    def _push_to_display(self, image: Image.Image):
        """推送到 LCD 显示"""
        if self._lcd:
            try:
                # 调用 LCD 驱动的显示方法
                if hasattr(self._lcd, 'draw_image'):
                    self._lcd.draw_image(image)
                elif hasattr(self._lcd, 'show_image'):
                    # 保存临时文件再显示
                    temp_path = "/tmp/lcd_frame.png"
                    image.save(temp_path)
                    self._lcd.show_image(temp_path)
            except Exception as e:
                print(f"[LCDRenderer] Display error: {e}")
        else:
            # 保存预览
            image.save("/tmp/lcd_preview.png")
            print("[LCD] Preview saved to /tmp/lcd_preview.png")
