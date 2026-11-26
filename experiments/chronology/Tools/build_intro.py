"""Build the welcome loop: python3 Tools/build_intro.py DIRECTORY_WITH_ORIGINALS

Requires Pillow and ffmpeg. Original filenames and credits are in the README.
"""

from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageOps

root = Path(__file__).resolve().parents[1]
media = root / "Chronology"
assets = media / "Assets.xcassets/IntroStill.imageset"
shots = [
    ("The_Great_Wave_off_Kanagawa.jpg", 0.35, 0.43),
    ("Wrightflyer.jpg", 0.52, 0.50),
    ("NASA-Apollo8-Dec24-Earthrise.jpg", 0.60, 0.54),
]
size = (640, 800)
frames, fade, fps = 120, 24, 24
images = []
for filename, x, y in shots:
    with Image.open(Path(sys.argv[1]) / filename) as image:
        images.append(ImageOps.fit(image.convert("RGB"), (704, 880), centering=(x, y)))


def frame(index, t):
    # Slow drift across a slightly oversized crop; no zoom jumps at the cuts.
    x = round(32 + (t - 0.5) * (40 if index % 2 else -40))
    return images[index].crop((x, 40, x + size[0], 40 + size[1]))


frame(0, fade / frames).save(assets / "IntroStill.jpg", quality=86)
command = [
    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
    "-pix_fmt", "rgb24", "-s", "640x800", "-r", str(fps), "-i", "-",
    "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24",
    "-movflags", "+faststart", str(media / "HistoricalIntro.mp4"),
]
with subprocess.Popen(command, stdin=subprocess.PIPE) as encoder:
    for i in range(len(images)):
        for f in range(fade, frames):
            picture = frame(i, f / frames)
            if f >= frames - fade:
                offset = f - (frames - fade)
                picture = Image.blend(picture, frame((i + 1) % len(images), offset / frames),
                                      offset / fade)
            encoder.stdin.write(picture.tobytes())
    encoder.stdin.close()
    if encoder.wait():
        raise SystemExit("Video encoding failed")
