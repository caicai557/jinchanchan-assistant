"""
截图渲染器

将 PIL 图片转换为终端可显示的 ASCII/Unicode 艺术
"""

from PIL import Image


def image_to_ascii(
    image: Image.Image,
    width: int = 80,
    chars: str = " .:-=+*#%@",
) -> str:
    """
    将图片转换为 ASCII 艺术

    Args:
        image: PIL 图片
        width: 输出宽度（字符数）
        chars: 灰度字符集，从暗到亮

    Returns:
        ASCII 艺术字符串
    """
    # 转换为灰度
    img = image.convert("L")

    # 计算缩放比例（终端字符约为 2:1 高宽比）
    aspect_ratio = img.height / img.width
    new_width = width
    new_height = int(width * aspect_ratio * 0.5)

    # 缩放图片
    img = img.resize((new_width, new_height))

    # 转换为字符
    lines = []
    for y in range(new_height):
        line = []
        for x in range(new_width):
            pixel = img.getpixel((x, y))
            char_index = int(pixel / 256 * len(chars))
            char_index = min(char_index, len(chars) - 1)
            line.append(chars[char_index])
        lines.append("".join(line))

    return "\n".join(lines)


def image_to_unicode_blocks(
    image: Image.Image,
    width: int = 80,
) -> str:
    """
    将图片转换为 Unicode 块字符（更高分辨率）

    Args:
        image: PIL 图片
        width: 输出宽度（字符数）

    Returns:
        Unicode 块艺术字符串
    """
    # 转换为 RGB
    img = image.convert("RGB")

    # 计算缩放比例（▄ 是上半块，每个字符代表2个垂直像素）
    aspect_ratio = img.height / img.width
    new_width = width
    new_height = int(width * aspect_ratio * 0.5) * 2  # 每个▄代表2行

    # 确保高度是偶数
    if new_height % 2 != 0:
        new_height += 1

    # 缩放图片
    img = img.resize((new_width, new_height))

    # Unicode 块字符
    upper_block = "▀"  # 上半块
    lower_block = "▄"  # 下半块
    full_block = "█"  # 全块
    empty = " "

    lines = []
    for y in range(0, new_height, 2):
        line = []
        for x in range(new_width):
            # 获取上下两个像素的颜色
            r1, g1, b1 = img.getpixel((x, y))
            r2, g2, b2 = img.getpixel((x, y + 1)) if y + 1 < new_height else (0, 0, 0)

            # 计算灰度
            gray1 = (r1 + g1 + b1) / 3
            gray2 = (r2 + g2 + b2) / 3

            # 选择字符
            if gray1 > 128 and gray2 > 128:
                line.append(full_block)
            elif gray1 > 128:
                line.append(upper_block)
            elif gray2 > 128:
                line.append(lower_block)
            else:
                line.append(empty)

        lines.append("".join(line))

    return "\n".join(lines)


def image_to_colored_blocks(
    image: Image.Image,
    width: int = 60,
) -> str:
    """
    将图片转换为带 ANSI 颜色的 Unicode 块

    Args:
        image: PIL 图片
        width: 输出宽度（字符数）

    Returns:
        带 ANSI 颜色的字符串
    """
    img = image.convert("RGB")

    aspect_ratio = img.height / img.width
    new_width = width
    new_height = int(width * aspect_ratio * 0.5) * 2

    if new_height % 2 != 0:
        new_height += 1

    img = img.resize((new_width, new_height))

    lines = []
    for y in range(0, new_height, 2):
        line = []
        for x in range(new_width):
            r1, g1, b1 = img.getpixel((x, y))
            r2, g2, b2 = img.getpixel((x, y + 1)) if y + 1 < new_height else (0, 0, 0)

            # 使用上半块 ▀ 配合背景色和前景色
            # \033[38;2;R;G;Bm 设置前景色
            # \033[48;2;R;G;Bm 设置背景色
            line.append(f"\033[38;2;{r1};{g1};{b1}m\033[48;2;{r2};{g2};{b2}m▀\033[0m")

        lines.append("".join(line))

    return "\n".join(lines)


class ScreenshotRenderer:
    """截图渲染器"""

    def __init__(self, width: int = 60, use_color: bool = True):
        """
        初始化渲染器

        Args:
            width: 输出宽度（字符数）
            use_color: 是否使用颜色
        """
        self.width = width
        self.use_color = use_color
        self._last_image: Image.Image | None = None
        self._last_render: str = ""

    def render(self, image: Image.Image) -> str:
        """
        渲染图片为终端可显示的字符串

        Args:
            image: PIL 图片

        Returns:
            渲染后的字符串
        """
        self._last_image = image

        if self.use_color:
            self._last_render = image_to_colored_blocks(image, self.width)
        else:
            self._last_render = image_to_unicode_blocks(image, self.width)

        return self._last_render

    def get_last_render(self) -> str:
        """获取上次渲染结果"""
        return self._last_render

    def render_thumbnail(self, image: Image.Image, width: int = 40) -> str:
        """
        渲染缩略图

        Args:
            image: PIL 图片
            width: 缩略图宽度

        Returns:
            渲染后的字符串
        """
        if self.use_color:
            return image_to_colored_blocks(image, width)
        else:
            return image_to_unicode_blocks(image, width)
