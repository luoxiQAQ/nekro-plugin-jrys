"""运势海报绘制（PIL）"""

import os
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .plugin import FONT_DIR, JrysConfig, plugin

logger = plugin.logger

IMAGE_HEIGHT = 1920
IMAGE_WIDTH = 1080
AVATAR_SIZE = (150, 150)
AVATAR_POSITION = (60, 1350)
FONT_NAME = "千图马克手写体.ttf"
TEXT_BOX_Y = 1270
TEXT_BOX_HEIGHT = 700
TEXT_BOX_RADIUS = 50
DATE_Y = 1300
SUMMARY_Y = 1400
LUCKY_STAR_Y = 1500
SIGN_TEXT_Y = 1600
UNSIGN_TEXT_Y = 1700
WARNING_TEXT_Y = 1850
WARNING_TEXT_Y_OFFSET = 10
UNSIGN_TEXT_Y_OFFSET = 15
TEXT_WRAP_WIDTH = 1000
LEFT_PADDING = 20

WARNING_TEXT = "仅供娱乐 | 相信科学 | 请勿迷信"
FONT_SIZES = (50, 60, 36, 30)

LIGHT_COLORS: List[Tuple[int, int, int]] = [
    (255, 250, 205),  # 浅黄色
    (173, 216, 230),  # 浅蓝色
    (221, 160, 221),  # 浅紫色
    (255, 182, 193),  # 浅粉色
    (240, 230, 140),  # 浅卡其色
    (224, 255, 255),  # 浅青色
    (245, 245, 220),  # 浅米色
    (230, 230, 250),  # 浅薰衣草色
]


class FortunePainter:
    """今日运势海报生成器"""

    def __init__(self, config: JrysConfig) -> None:
        self.config = config

        self.font_name = config.FONT_NAME or FONT_NAME
        self.image_width = config.IMG_WIDTH or IMAGE_WIDTH
        self.image_height = config.IMG_HEIGHT or IMAGE_HEIGHT

        avatar_position = list(config.AVATAR_POSITION) or list(AVATAR_POSITION)
        avatar_size = list(config.AVATAR_SIZE) or list(AVATAR_SIZE)
        self.avatar_position: Tuple[int, int] = (int(avatar_position[0]), int(avatar_position[1]))
        self.avatar_size: Tuple[int, int] = (int(avatar_size[0]), int(avatar_size[1]))

        self.date_y = config.DATE_Y_POSITION
        self.summary_y = config.SUMMARY_Y_POSITION
        self.lucky_star_y = config.LUCKY_STAR_Y_POSITION
        self.sign_text_y = config.SIGN_TEXT_Y_POSITION
        self.unsign_text_y = config.UNSIGN_TEXT_Y_POSITION
        self.warning_text_y = config.WARNING_TEXT_Y_POSITION

        self.font_path = FONT_DIR / self.font_name
        self.fonts: Dict[int, Any] = {}
        self.default_font: Optional[Any] = None
        self._load_fonts()

    def _load_fonts(self) -> None:
        try:
            for size in FONT_SIZES:
                self.fonts[size] = ImageFont.truetype(str(self.font_path), size)
        except Exception:
            logger.error(f"无法加载字体文件 {self.font_path}，使用默认字体回退")
            self.default_font = ImageFont.load_default()
            for size in FONT_SIZES:
                self.fonts[size] = self.default_font

    def render(
        self,
        user_id: str,
        avatar_path: Optional[str],
        background_path: str,
        entry: Dict[str, Any],
        out_path: Path,
    ) -> Optional[Path]:
        """合成海报并写入 out_path，失败返回 None"""
        date_y = self.date_y
        unsign_text_y = self.unsign_text_y
        warning_text_y = self.warning_text_y

        try:
            fortune_summary = entry.get("fortuneSummary", "运势数据未知")
            lucky_star = entry.get("luckyStar", "幸运星未知")
            sign_text = entry.get("signText", "星座运势未知")
            unsign_text = entry.get("unsignText", "非星座运势未知")

            unsign_lines = self.wrap_text(unsign_text, font=self.fonts[36], max_width=TEXT_WRAP_WIDTH)
            if len(unsign_lines) > 3:
                warning_text_y += (len(unsign_lines) - 3) * WARNING_TEXT_Y_OFFSET
                unsign_text_y -= (len(unsign_lines) - 3) * UNSIGN_TEXT_Y_OFFSET

            image = self.crop_center(background_path)
            if image is None:
                logger.error("裁剪背景图片失败")
                return None

            image = self.add_transparent_layer(
                image,
                position=(0, TEXT_BOX_Y),
                box_width=self.image_width,
                box_height=TEXT_BOX_HEIGHT,
            )

            date = datetime.now().strftime("%Y/%m/%d")
            image = self.draw_text(
                image,
                text=date,
                position="center",
                y=date_y,
                color=(255, 255, 255),
                font=self.fonts[50],
                gradients=True,
            )
            image = self.draw_text(
                image,
                text=fortune_summary,
                position="center",
                y=self.summary_y,
                color=(255, 255, 255),
                font=self.fonts[60],
            )
            image = self.draw_text(
                image,
                text=lucky_star,
                position="center",
                y=self.lucky_star_y,
                color=(255, 255, 255),
                font=self.fonts[60],
                gradients=True,
            )
            image = self.draw_text(
                image,
                text=sign_text,
                position="left",
                y=self.sign_text_y,
                color=(255, 255, 255),
                font=self.fonts[30],
            )
            image = self.draw_text(
                image,
                text=unsign_text,
                position="left",
                y=unsign_text_y,
                color=(255, 255, 255),
                font=self.fonts[30],
            )
            image = self.draw_text(
                image,
                text=WARNING_TEXT,
                position="center",
                y=warning_text_y,
                color=(255, 255, 255),
                font=self.fonts[30],
            )

            if avatar_path:
                image = self.draw_avatar_img(avatar_path, image)

            out_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = out_path.with_name(f"{out_path.name}.{random.randint(0, 1 << 32):08x}.tmp")
            image.convert("RGB").save(tmp_path, format="JPEG", quality=85, optimize=True)
            os.replace(tmp_path, out_path)
            return out_path
        except Exception as e:
            logger.error(f"生成运势图片失败: {e}")
            return None

    def draw_text(
        self,
        img: Image.Image,
        text: str,
        position: str,
        font: Any,
        y: Optional[int] = None,
        color: Tuple[int, int, int] = (255, 255, 255),
        max_width: int = 800,
        gradients: bool = False,
    ) -> Image.Image:
        """在图片上绘制文字（支持居中/左对齐与渐变填充）"""
        try:
            draw = ImageDraw.Draw(img)
            lines = self.wrap_text(text=text, font=font, draw=draw, max_width=TEXT_WRAP_WIDTH)
            img_width, _img_height = img.size

            if isinstance(position, str):
                if position == "center":

                    def x_func(line: str) -> int:
                        bbox = draw.textbbox((0, 0), line, font=font)
                        return (img_width - (bbox[2] - bbox[0])) // 2

                    def offset_x_func(line: str) -> int:
                        return -draw.textbbox((0, 0), line, font=font)[0]

                elif position == "left":

                    def x_func(line: str) -> int:
                        return LEFT_PADDING

                    def offset_x_func(line: str) -> int:
                        return 0

                else:
                    raise ValueError("position 参数错误，只能为 'left'、'center' 或坐标元组")

                text_y = y if y is not None else 0
            elif isinstance(position, tuple):
                text_x, text_y = position

                def x_func(line: str) -> int:
                    return text_x

                def offset_x_func(line: str) -> int:
                    return 0

            else:
                raise ValueError("position 参数错误，只能为 'left'、'center' 或坐标元组")

            line_spacing = int(font.size * 1.5)
            for line in lines:
                if gradients:
                    base_x = x_func(line)
                    offset_x = offset_x_func(line)
                    for char in line:
                        gradient_char = self.create_gradients_image(char, font, self.get_light_color())
                        img.paste(gradient_char, (base_x + offset_x, text_y), gradient_char)

                        bbox = font.getbbox(char)
                        base_x += bbox[2] - bbox[0]
                        offset_x += bbox[0]
                else:
                    offset_x = offset_x_func(line)
                    draw.text((x_func(line) + offset_x, text_y), line, font=font, fill=color)

                text_y += line_spacing

            return img
        except Exception as e:
            logger.error(f"绘制文字时出错: {e}")
            return img

    def crop_center(self, image_path: str, width: Optional[int] = None, height: Optional[int] = None) -> Optional[Image.Image]:
        """从图片中间裁剪目标尺寸区域，过小则放大、过大则缩放"""
        width = width if width is not None else self.image_width
        height = height if height is not None else self.image_height
        try:
            img = Image.open(image_path).convert("RGBA")
            img_width, img_height = img.size

            if img_width < width or img_height < height:
                scale = max(width / img_width, height / img_height)
                img = img.resize((int(img_width * scale), int(img_height * scale)), Image.LANCZOS)
            else:
                max_scale = 1.8
                if img_width > width * max_scale or img_height > height * max_scale:
                    scale = min((width * max_scale) / img_width, (height * max_scale) / img_height)
                    img = img.resize((int(img_width * scale), int(img_height * scale)), Image.LANCZOS)

            img_width, img_height = img.size
            left = (img_width - width) / 2
            top = (img_height - height) / 2
            return img.crop((left, top, (img_width + width) / 2, (img_height + height) / 2))
        except FileNotFoundError:
            logger.error(f"找不到背景图片文件: {image_path}")
            return None
        except Exception as e:
            logger.error(f"裁剪背景图片时出错: {e}")
            return None

    def add_transparent_layer(
        self,
        base_img: Image.Image,
        box_width: int = 800,
        box_height: int = 400,
        position: Tuple[int, int] = (100, 200),
        layer_color: Tuple[int, int, int, int] = (0, 0, 0, 128),
        radius: int = TEXT_BOX_RADIUS,
    ) -> Image.Image:
        """叠加圆角半透明文字底板"""
        try:
            x1, y1 = position
            overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
            ImageDraw.Draw(overlay).rounded_rectangle(
                (x1, y1, x1 + box_width, y1 + box_height),
                radius=radius,
                fill=layer_color,
            )
            return Image.alpha_composite(base_img, overlay)
        except Exception as e:
            logger.error(f"添加半透明图层时出错: {e}")
            return base_img

    def wrap_text(
        self,
        text: str,
        font: Any,
        draw: Optional[ImageDraw.ImageDraw] = None,
        max_width: int = TEXT_WRAP_WIDTH,
    ) -> List[str]:
        """按像素宽度逐字换行"""
        try:
            if draw is None:
                draw = ImageDraw.Draw(Image.new("RGB", (self.image_width, self.image_height)))

            lines: List[str] = []
            current_line = ""
            for char in text:
                test_line = current_line + char
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if bbox[2] - bbox[0] <= max_width:
                    current_line = test_line
                else:
                    # 单个字符就超宽时也要收下，避免死循环
                    if not current_line:
                        current_line = test_line
                        continue
                    lines.append(current_line)
                    current_line = char
            if current_line:
                lines.append(current_line)
            return lines
        except Exception as e:
            logger.error(f"换行时出错: {e}")
            return [text]

    def create_gradients_image(self, char: str, font: Any, colors: List[Tuple[int, int, int]]) -> Image.Image:
        """为单个字符生成横向渐变填充图"""
        width, height = font.size, font.size
        try:
            bbox = font.getbbox(char)
            bbox_width = bbox[2] - bbox[0]
            bbox_height = bbox[3] - bbox[1]
            if bbox_width <= 0 or bbox_height <= 0:
                width, height = font.size, font.size
                offset_x, offset_y = 0, 0
            else:
                width, height = bbox_width, bbox_height
                offset_x, offset_y = -bbox[0], -bbox[1]

            gradient = Image.new("RGBA", (width, height), color=0)
            draw = ImageDraw.Draw(gradient)

            mask = Image.new("L", (width, height), 0)
            ImageDraw.Draw(mask).text((offset_x, offset_y), char, font=font, fill=255)

            if len(colors) < 2:
                raise ValueError("至少需要两个颜色进行渐变")

            segment_width = width / (len(colors) - 1)
            for i in range(len(colors) - 1):
                start_color, end_color = colors[i], colors[i + 1]
                start_x, end_x = int(i * segment_width), int((i + 1) * segment_width)
                for x in range(start_x, end_x):
                    factor = (x - start_x) / segment_width
                    draw.line(
                        [(x, 0), (x, height)],
                        fill=tuple(int(start_color[j] + (end_color[j] - start_color[j]) * factor) for j in range(3)),
                    )

            gradient.putalpha(mask)
            return gradient
        except Exception as e:
            logger.error(f"创建渐变色字体图像时出错: {e}")
            img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
            ImageDraw.Draw(img).text((0, 0), char, font=font, fill=(255, 255, 255))
            return img

    @staticmethod
    def get_light_color() -> List[Tuple[int, int, int]]:
        return random.choices(LIGHT_COLORS, k=4)

    def draw_avatar_img(self, avatar_path: str, img: Image.Image) -> Image.Image:
        """把头像裁成圆形后贴到海报上"""
        try:
            avatar = Image.open(avatar_path).convert("RGBA").resize(self.avatar_size, Image.LANCZOS)
            mask = Image.new("L", avatar.size, 0)
            ImageDraw.Draw(mask).ellipse((0, 0, avatar.size[0], avatar.size[1]), fill=255)
            avatar.putalpha(mask)
            img.paste(avatar, self.avatar_position, avatar)
            return img
        except Exception as e:
            logger.error(f"绘制头像时出错: {e}")
            return img
