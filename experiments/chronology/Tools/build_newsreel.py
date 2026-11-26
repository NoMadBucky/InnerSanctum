"""On macOS: python3 Tools/build_newsreel.py DIRECTORY_WITH_ORIGINALS

See README for footage, Kokoro model files and build dependencies.
"""
from pathlib import Path
from math import ceil
import subprocess
import sys
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont
from kokoro_onnx import Kokoro
import soundfile as sf

root = Path(__file__).resolve().parents[1]
sources = Path(sys.argv[1]).resolve()
narrator = Kokoro(str(sources / "kokoro-v1.0.int8.onnx"), str(sources / "voices-v1.0.bin"))
output = root / "Chronology/MilestonesNewsreel.mp4"
chapters = [
    (None, "", "It’s all about timing.", ["Which historical moment came first?"],
     "Blonien Productions presents: Milestones. It’s all about timing. Which historical moment came first?"),
    ("quake.ogv", "SAN FRANCISCO  /  MARKET STREET", "San Francisco’s great earthquake…", [],
     "San Francisco’s great earthquake…"),
    ("Wrightflyer.jpg", "KITTY HAWK  /  THE WRIGHT FLYER", "Or the first powered flight", ["by the Wright brothers?"],
     "or the first powered flight by the Wright brothers?"),
    (None, "", "Find your place in history.", ["The fate of our timeline is in your hands.", "Play Milestones now!"],
     "The fate of our timeline is in your hands. Find your place in history. Play Milestones now!"),
]


def run(*args):
    subprocess.run(args, check=True)


with TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    for i, (file, slug, title, lines, speech) in enumerate(chapters):
        art = Image.new("RGBA", (640, 880), "#171813")
        draw = ImageDraw.Draw(art)

        def label(y, text, size, face="Georgia Bold", color="#f5efda"):
            font = ImageFont.truetype(f"/System/Library/Fonts/Supplemental/{face}.ttf", size)
            draw.text((320, y), text, font=font, fill=color, anchor="mm")

        draw.rectangle((15, 15, 624, 864), outline="#c8ba91", width=2)
        label(56, "BLONIEN PRODUCTIONS", 26)
        label(103, f"THE HISTORY DESK     /     REEL 01     /     {i+1} OF 4", 16, "Courier New Bold")
        if file:
            draw.rectangle((32, 147, 607, 522), fill=(0, 0, 0, 0))
        else:
            label(213, "P R E S E N T S" if i == 0 else "F I N", 21, "Georgia")
            label(306, "MILESTONES", 66)
            label(363, "A Snap History Game", 34, "Georgia Italic")
        label(568, slug, 19, "Courier New Bold", "#d8c99b")
        draw.line((44, 608, 596, 608), fill="#c8ba91", width=2)
        label(664, title, 31 if i == 1 else 38)
        for j, line in enumerate(lines):
            label(738 + 44*j, line, 28, "Georgia")
        overlay = tmp / "overlay.png"
        art.save(overlay)
        voice = tmp / "voice.wav"
        samples, rate = narrator.create(speech, voice="bm_fable", lang="en-gb", speed=1.0)
        sf.write(voice, samples, rate)
        length = len(samples) / rate
        print(f"Chapter {i+1}: {length:.2f}s of narration", flush=True)
        duration = ceil((length + (0.32 if i == 1 else 0.16)) * 24) / 24
        footage = (["-loop", "1", "-framerate", "24", "-i", str(sources / file)] if file == "Wrightflyer.jpg" else
                   ["-ss", "27", "-i", str(sources / file)] if file else
                   ["-f", "lavfi", "-i", "color=black:s=640x880:r=24"])
        run("ffmpeg", "-y", "-loglevel", "error", *footage, "-i", str(overlay), "-i", str(voice),
            "-filter_complex",
            "[0:v]fps=24,scale=576:376:force_original_aspect_ratio=increase,crop=576:376,"
            "setsar=1,hue=s=0,pad=640:880:32:147[film];[film][1:v]overlay[v];"
            "[2:a]highpass=f=65,adelay=60,apad[a]", "-map", "[v]", "-map", "[a]", "-t", str(duration),
            "-c:v", "libx264", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le",
            "-ar", "44100", str(tmp / f"{i}.mov"))
    manifest = tmp / "shots.txt"
    manifest.write_text("".join(f"file '{i}.mov'\n" for i in range(len(chapters))))
    run("ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(manifest),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "80k", "-movflags", "+faststart", str(output))
