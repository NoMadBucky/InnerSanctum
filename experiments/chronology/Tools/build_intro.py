"""Build the welcome loop: python3 Tools/build_intro.py DIRECTORY_WITH_ORIGINALS

Requires Pillow and ffmpeg. Original filenames and credits are in the README.
"""

from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageFilter, ImageOps

root = Path(__file__).resolve().parents[1]
media = root / "Chronology"
assets = media / "Assets.xcassets/IntroStill.imageset"
# Source-space (center x, center y, fraction of source height). Compose at
# phone aspect, not 4:5 followed by a second, uncontrolled horizontal crop.
shots = [
    # Approach the central seated figure; stay inside the scan's black border.
    ("Diamond_sutra.jpg", (.51, .50, .81), (.51, .48, .76)),
    # Follow the wave as it curls toward the right.
    ("The_Great_Wave_off_Kanagawa.jpg", (.335, .47, .92), (.373, .46, .90)),
    # Hold the horizontal span of the wings; slowly open out from the pilot.
    ("Wrightflyer.jpg", (.50, .49, .94), (.50, .50, 1.0)),
    # Lift from the lunar horizon toward Earth, keeping the globe on axis.
    ("NASA-Apollo8-Dec24-Earthrise.jpg", (.571, .64, .70), (.571, .62, .67)),
    # Follow Mandela's gesture from his face toward the ballot.
    ("Mandela_voting_in_1994.jpg", (.485, .485, .95), (.46, .50, .96)),
]
size = (576, 1248)
fps = 60
fade = 45  # 0.75-second overlap
frames = 174 + fade  # 2.9 seconds per shot, including its outgoing dissolve
images = []
for filename, _, _ in shots:
    with Image.open(Path(sys.argv[1]) / filename) as image:
        source = ImageOps.exif_transpose(image).convert("RGB")
        if filename == "Wrightflyer.jpg":
            # A full-height portrait crop cuts off both wingtips. Keep the
            # archival frame intact over a soft extension of the same photograph.
            plate = ImageOps.fit(source, size).filter(ImageFilter.GaussianBlur(32))
            photo = ImageOps.contain(source, (round(size[0]*1.44), size[1]))
            # Feather the sky and sand into the extension, away from the airplane.
            mask = Image.new("L", (1, photo.height))
            mask.putdata([round(255 * min(1, y/48, (photo.height-1-y)/48))
                          for y in range(photo.height)])
            plate.paste(photo, ((size[0]-photo.width)//2, int(.32*size[1] - .50*photo.height)),
                        mask.resize(photo.size))
            source = plate
        images.append(source)


def frame(index, t):
    _, start, end = shots[index]
    ease = t*t*(3-2*t)
    cx, cy, height = (a+(b-a)*ease for a, b in zip(start, end))
    image = images[index]
    h = height * image.height
    w = h * size[0] / size[1]
    x = max(0, min(cx*image.width-w/2, image.width-w))
    y = max(0, min(cy*image.height-h/2, image.height-h))
    return image.resize(size, Image.Resampling.BICUBIC, box=(x, y, x+w, y+h))


frame(0, fade / frames).save(assets / "IntroStill.jpg", quality=86)
command = [
    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
    "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}", "-r", str(fps), "-i", "-",
    "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24",
    "-movflags", "+faststart", str(media / "HistoricalIntro.mp4"),
]
with subprocess.Popen(command, stdin=subprocess.PIPE) as encoder:
    for i in range(len(images)):
        for f in range(fade, frames):
            picture = frame(i, f / frames)
            if f >= frames - fade:
                offset = f - (frames - fade)
                u = offset / fade
                picture = Image.blend(picture, frame((i + 1) % len(images), offset / frames),
                                      u * u * (3 - 2 * u))
            encoder.stdin.write(picture.tobytes())
    encoder.stdin.close()
    if encoder.wait():
        raise SystemExit("Video encoding failed")
