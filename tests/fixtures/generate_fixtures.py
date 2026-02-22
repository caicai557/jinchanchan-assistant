"""
生成测试 fixtures 截图

使用 PIL 生成简单的测试截图，用于离线回放回归测试
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def create_shop_screenshot() -> Image.Image:
    """创建商店场景截图 (1920x1080)"""
    img = Image.new("RGB", (1920, 1080), color=(30, 30, 40))
    draw = ImageDraw.Draw(img)

    # 商店区域背景
    draw.rectangle([40, 900, 1880, 1060], fill=(50, 50, 60))

    # 5个商店槽位
    for i in range(5):
        x = 60 + i * 360
        draw.rectangle([x, 910, x + 340, 1050], fill=(70, 70, 80), outline=(100, 100, 110))
        # 费用颜色指示
        colors = [(80, 160, 80), (80, 80, 160), (160, 80, 160), (160, 120, 80), (200, 160, 80)]
        draw.rectangle([x + 5, 915, x + 335, 940], fill=colors[i])
        # 英雄名占位
        draw.text((x + 20, 960), f"Hero_{i + 1}", fill=(200, 200, 200))
        # 价格
        draw.text((x + 260, 1000), f"{i + 1}G", fill=(255, 215, 0))

    return img


def create_board_screenshot() -> Image.Image:
    """创建棋盘场景截图 (1920x1080)"""
    img = Image.new("RGB", (1920, 1080), color=(25, 30, 40))
    draw = ImageDraw.Draw(img)

    # 棋盘区域 (4行7列)
    for row in range(4):
        for col in range(7):
            x = 200 + col * 220
            y = 200 + row * 160
            draw.rectangle([x, y, x + 200, y + 140], fill=(60, 60, 70), outline=(80, 80, 90))

    # 放置一些英雄
    positions = [(0, 1), (1, 2), (2, 3), (0, 5)]
    for row, col in positions:
        x = 200 + col * 220
        y = 200 + row * 160
        draw.rectangle([x + 10, y + 10, x + 190, y + 130], fill=(100, 100, 120))

    return img


def create_info_screenshot() -> Image.Image:
    """创建回合/金币/等级UI截图 (1920x1080)"""
    img = Image.new("RGB", (1920, 1080), color=(30, 30, 40))
    draw = ImageDraw.Draw(img)

    # 顶部信息栏
    draw.rectangle([0, 0, 1920, 60], fill=(40, 40, 50))

    # 回合信息
    draw.text((100, 20), "Stage: 4-5", fill=(255, 255, 255))
    draw.text((400, 20), "Round: 45", fill=(255, 255, 255))

    # 金币
    draw.ellipse([700, 15, 730, 45], fill=(255, 215, 0))
    draw.text((740, 20), "50G", fill=(255, 215, 0))

    # 等级
    draw.text((900, 20), "Lv.8", fill=(100, 200, 255))
    draw.rectangle([950, 25, 1100, 35], fill=(60, 60, 70))
    draw.rectangle([950, 25, 1020, 35], fill=(100, 200, 255))

    # HP bar
    draw.text((1200, 20), "HP: 85", fill=(255, 100, 100))
    draw.rectangle([1300, 25, 1500, 35], fill=(60, 60, 70))
    draw.rectangle([1300, 25, 1410, 35], fill=(255, 80, 80))

    return img


def create_selection_screenshot() -> Image.Image:
    """创建选择/按钮界面截图 (1920x1080)"""
    img = Image.new("RGB", (1920, 1080), color=(30, 30, 40))
    draw = ImageDraw.Draw(img)

    # 中央选择框
    draw.rectangle([560, 300, 1360, 780], fill=(50, 50, 60), outline=(100, 100, 110), width=2)

    # 标题
    draw.text((720, 330), "Choose Your Champion", fill=(255, 255, 255))

    # 3个选择
    for i in range(3):
        y = 400 + i * 120
        draw.rectangle([600, y, 1320, y + 100], fill=(70, 70, 80), outline=(90, 90, 100))
        draw.text((650, y + 30), f"Option {i + 1}: Champion Name", fill=(200, 200, 200))

    # 按钮
    draw.rectangle([700, 850, 900, 920], fill=(80, 120, 80))
    draw.text((750, 865), "Confirm", fill=(255, 255, 255))

    draw.rectangle([1020, 850, 1220, 920], fill=(120, 80, 80))
    draw.text((1080, 865), "Reroll 2G", fill=(255, 255, 255))

    return img


def create_bench_screenshot() -> Image.Image:
    """创建备战席场景截图 (1920x1080)"""
    img = Image.new("RGB", (1920, 1080), color=(30, 30, 40))
    draw = ImageDraw.Draw(img)

    # 备战席区域 (9个槽位)
    for i in range(9):
        x = 80 + i * 190
        draw.rectangle([x, 700, x + 170, 860], fill=(50, 50, 60), outline=(70, 70, 80))

    # 放置一些英雄
    for i in [0, 2, 5, 7]:
        x = 80 + i * 190
        draw.rectangle([x + 10, 710, x + 160, 850], fill=(90, 90, 100))

    # 羁绊显示
    draw.rectangle([50, 920, 400, 1050], fill=(40, 40, 50))
    draw.text((70, 940), "Synergies:", fill=(200, 200, 200))
    draw.text((70, 970), "Warrior (2/4)", fill=(100, 200, 100))
    draw.text((70, 1000), "Blademaster (2/3)", fill=(100, 200, 100))

    return img


def main():
    """生成所有 fixture 截图"""
    fixtures_dir = Path(__file__).parent / "screens"
    fixtures_dir.mkdir(exist_ok=True)

    fixtures = [
        ("shop.png", create_shop_screenshot),
        ("board.png", create_board_screenshot),
        ("info.png", create_info_screenshot),
        ("selection.png", create_selection_screenshot),
        ("bench.png", create_bench_screenshot),
    ]

    for name, create_fn in fixtures:
        img = create_fn()
        path = fixtures_dir / name
        img.save(path)
        print(f"Generated: {path}")

    print(f"\nTotal fixtures: {len(fixtures)}")


if __name__ == "__main__":
    main()
