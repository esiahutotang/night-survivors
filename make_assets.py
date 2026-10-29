"""Build finished PNGs locally: py -3.13 make_assets.py.

Only this offline script uses Pillow. The game loads the resulting assets/ files.
"""
import json
from pathlib import Path
import shutil
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent


def gold_coins(stacked=False):
    """Original 16px coin icons, using the same crisp scaling as the sprites."""
    image = Image.new("RGBA", (16, 16))
    draw = ImageDraw.Draw(image)
    def coin(dx, dy):
        points = [(5, 2), (9, 2), (12, 5), (12, 9), (9, 12), (5, 12), (2, 9), (2, 5)]
        draw.polygon([(x+dx, y+dy) for x, y in points], fill=(255, 207, 64), outline=(113, 60, 26))
        draw.ellipse((4+dx, 4+dy, 10+dx, 10+dy), fill=(219, 136, 35))
        draw.line((6+dx, 5+dy, 6+dx, 9+dy), fill=(255, 238, 139), width=2)
        draw.point((4+dx, 4+dy), fill=(255, 255, 205))
    if stacked:
        coin(2, -1)
        coin(-1, 2)
    else:
        coin(0, 0)
    return image


def crystal(source, palette):
    """Keep the gem's original facets and transparency, replacing its five shades."""
    image = source.convert("RGBA")
    pixels = [image.getpixel((x, y)) for y in range(image.height) for x in range(image.width)]
    shades = sorted({pixel[:3] for pixel in pixels if pixel[3]},
                    key=lambda rgb: sum(rgb))
    colors = {shade: palette[round(i * (len(palette)-1) / max(1, len(shades)-1))]
              for i, shade in enumerate(shades)}
    image.putdata([(*colors[pixel[:3]], pixel[3]) if pixel[3] else pixel
                   for pixel in pixels])
    return image


def main():
    config = json.loads((ROOT / "data" / "game.json").read_text(encoding="utf-8"))
    scale = config["art"]["scale"]
    destination = ROOT / "assets"
    destination.mkdir(exist_ok=True)

    def save(image, name):
        size = (image.width * scale, image.height * scale)
        image.resize(size, Image.Resampling.NEAREST).save(destination / name)
        print(f"Built {name}: {size[0]} x {size[1]}")

    for path in sorted((ROOT / "raw_art").glob("*.png")):
        with Image.open(path) as image:
            save(image.convert("RGBA"), path.name)
    save(gold_coins(), "coin.png")
    save(gold_coins(stacked=True), "coin_stack.png")
    with Image.open(ROOT / "raw_art" / "gem.png") as image:
        save(crystal(image, [(14, 73, 153), (20, 137, 238), (45, 199, 255),
                             (145, 237, 255), (234, 255, 255)]), "gem_blue.png")
        save(crystal(image, [(135, 25, 110), (222, 51, 169), (255, 111, 212),
                             (255, 181, 235), (255, 240, 253)]), "gem_pink.png")
    shutil.copyfile(ROOT / "raw_art" / "LICENSE-Kenney-CC0.txt",
                    destination / "LICENSE-Kenney-CC0.txt")


if __name__ == "__main__":
    main()
