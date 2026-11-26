"""Render Marquee.svg into the app icon set on macOS (Python with Pillow)."""

from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFilter


design = Path(__file__).resolve().parent
assets = design.parent / "Bijou/Assets.xcassets/AppIcon.appiconset"
with tempfile.TemporaryDirectory() as tmp:
    raster = Path(tmp) / "master.png"
    subprocess.run(["/usr/bin/sips", "-s", "format", "png", str(design / "Marquee.svg"),
                    "--out", str(raster)], check=True, capture_output=True)
    with Image.open(raster) as image:
        master = image.convert("RGB")
    assert master.size == (1024, 1024)
    master.save(assets / "Marquee.png", optimize=True)

# iOS supplies its own mask. Classic macOS icon slots need a padded silhouette.
mask = Image.new("L", (1024, 1024))
ImageDraw.Draw(mask).rounded_rectangle((99, 99, 924, 924), radius=178, fill=255)
shadow = Image.new("L", mask.size)
shadow.paste(mask, (0, 9))
canvas = Image.new("RGBA", mask.size)
canvas.putalpha(shadow.filter(ImageFilter.GaussianBlur(10)).point(lambda p: p // 3))
face = Image.new("RGBA", mask.size)
face.paste(master.resize((826, 826), Image.Resampling.LANCZOS), (99, 99))
face.putalpha(mask)
canvas.alpha_composite(face)
for size in (16, 32, 64, 128, 256, 512, 1024):
    canvas.resize((size, size), Image.Resampling.LANCZOS).save(assets / f"Mac{size}.png", optimize=True)
