"""Build finished PNGs locally: py -3.13 make_assets.py.

Only this offline script uses Pillow. The game loads the resulting assets/ files.
"""
import json
from pathlib import Path
import shutil
from PIL import Image

ROOT = Path(__file__).resolve().parent


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
    config = json.loads((ROOT / "data" / "game.json").read_text())
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
    with Image.open(ROOT / "raw_art" / "gem.png") as image:
        save(crystal(image, [(14, 73, 153), (20, 137, 238), (45, 199, 255),
                             (145, 237, 255), (234, 255, 255)]), "gem_blue.png")
        save(crystal(image, [(135, 25, 110), (222, 51, 169), (255, 111, 212),
                             (255, 181, 235), (255, 240, 253)]), "gem_pink.png")
    shutil.copyfile(ROOT / "raw_art" / "LICENSE-Kenney-CC0.txt",
                    destination / "LICENSE-Kenney-CC0.txt")


if __name__ == "__main__":
    main()
