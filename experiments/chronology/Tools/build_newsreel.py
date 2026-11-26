"""On macOS: python3 Tools/build_newsreel.py DIRECTORY_WITH_ORIGINALS

See README for footage, Kokoro model files and build dependencies.
"""
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont
from kokoro_onnx import Kokoro
import soundfile as sf

root = Path(__file__).resolve().parents[1]
sources = Path(sys.argv[1]).resolve()
narrator = Kokoro(str(sources / "kokoro-v1.0.int8.onnx"), str(sources / "voices-v1.0.bin"))
output = root / "Chronology/PeriodicalNewsreel.mp4"
duration = 4.75  # Four exactly frame-aligned chapters at 24 fps.
chapters = [
    ("train.webm", 6, "LA CIOTAT  /  THE LUMIÈRE TRAIN FILM", "The opening card",
     ["Begin with one dated event.", "Draw a card with its date hidden."],
     "Periodical presents a question of time. Which moment came first?"),
    ("quake.ogv", 27, "SAN FRANCISCO  /  AFTER THE 1906 QUAKE", "Find its place",
     ["Slide the timeline to a gap.", "Tap Place Here to make your guess."],
     "Here is San Francisco, picking itself up after the great earthquake."),
    ("moon.ogv", 40, "APOLLO 11  /  THE MOON WALK, 1969", "The verdict",
     ["Correct? Keep the card and score.", "Miss? See its place, then discard it."],
     "Within a lifetime, the scene shifts from Market Street to the Moon."),
    (None, 0, "END OF REEL  /  NOW IT’S YOUR TURN", "Choose your edition",
     ["Standard: ten guesses.", "Long Play: three misses or deck’s end."],
     "Now history is in your hands. Where does each moment belong?"),
]


def run(*args):
    subprocess.run(args, check=True)


with TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    for i, (file, start, slug, title, lines, speech) in enumerate(chapters):
        art = Image.new("RGBA", (640, 880), "#171813")
        draw = ImageDraw.Draw(art)

        def label(y, text, size, face="Georgia Bold", color="#f5efda"):
            font = ImageFont.truetype(f"/System/Library/Fonts/Supplemental/{face}.ttf", size)
            draw.text((320, y), text, font=font, fill=color, anchor="mm")

        draw.rectangle((15, 15, 624, 864), outline="#c8ba91", width=2)
        label(56, "PERIODICAL  •  NEWS IN PICTURES", 26)
        label(103, f"THE HISTORY DESK     /     REEL 01     /     {i+1} OF 4", 16, "Courier New Bold")
        if file:
            draw.rectangle((32, 147, 607, 522), fill=(0, 0, 0, 0))
        else:
            label(276, "PERIODICAL", 66)
            label(363, "A Snap History Game", 34, "Georgia Italic")
        label(568, slug, 19, "Courier New Bold", "#d8c99b")
        draw.line((44, 608, 596, 608), fill="#c8ba91", width=2)
        label(664, title, 38)
        for j, line in enumerate(lines):
            label(738 + 44*j, line, 28, "Georgia")
        overlay = tmp / "overlay.png"
        art.save(overlay)
        voice = tmp / "voice.wav"
        samples, rate = narrator.create(speech, voice="bm_george", lang="en-gb", speed=1.02)
        sf.write(voice, samples, rate)
        length = len(samples) / rate
        print(f"Chapter {i+1}: {length:.2f}s of narration", flush=True)
        footage = (["-ss", str(start), "-i", str(sources / file)] if file else
                   ["-f", "lavfi", "-i", "color=black:s=640x880:r=24"])
        run("ffmpeg", "-y", "-loglevel", "error", *footage, "-i", str(overlay), "-i", str(voice),
            "-filter_complex",
            "[0:v]fps=24,scale=576:376:force_original_aspect_ratio=increase,crop=576:376,"
            "setsar=1,hue=s=0,pad=640:880:32:147[film];[film][1:v]overlay[v];"
            f"[2:a]highpass=f=95,lowpass=f=7200,atempo={max(1,length/4.55):.4f},"
            "adelay=100,apad[a]", "-map", "[v]", "-map", "[a]", "-t", str(duration),
            "-c:v", "libx264", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le",
            "-ar", "44100", str(tmp / f"{i}.mov"))
    manifest = tmp / "shots.txt"
    manifest.write_text("".join(f"file '{i}.mov'\n" for i in range(len(chapters))))
    run("ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(manifest),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "80k", "-movflags", "+faststart", str(output))
