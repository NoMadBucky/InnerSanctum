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
from overture import render
import numpy as np

root = Path(__file__).resolve().parents[1]
sources = Path(sys.argv[1]).resolve()
narrator = Kokoro(str(sources / "kokoro-v1.0.int8.onnx"), str(sources / "voices-v1.0.bin"))
output = root / "Chronology/MilestonesNewsreel.mp4"
chapters = [
    (None, "", "It’s all about timing.", []),
    ("quake.ogv", "SAN FRANCISCO  /  MARKET STREET", "Which moment came first —", ["San Francisco’s great earthquake…"]),
    ("Wrightflyer.jpg", "KITTY HAWK  /  THE WRIGHT FLYER", "OR the first powered flight", ["by the Wright brothers?"]),
    (None, "", "Find your place in history.", ["The fate of our timeline is in your hands.", "Play Milestones now!"]),
]


def run(*args):
    subprocess.run(args, check=True)


def speak(text, speed, credit=False, contrast=False):
    phones = narrator.tokenizer.phonemize(text, "en-gb")
    if credit:
        # BLAH-nee-in; pre-ZENTS (verb). Keep the printed title spelled normally.
        _, colon, title = phones.partition(":")
        assert colon
        phones = "blˈɑːniːɪn pɹədˈʌkʃənz pɹɪzˈɛnts: " + title.lstrip()
    if contrast:
        # Use the full, stressed British vowel instead of reducing the conjunction.
        phones = "ˈɔː " + phones.split(" ", 1)[1]
    samples, rate = narrator.create(phones, voice="bm_lewis", is_phonemes=True, speed=speed)
    # Keep consonant tails; use the explicit rests below rather than stacking
    # them on top of the synthesizer's variable trailing silence.
    active = np.flatnonzero(np.abs(samples) > 0.002)
    if active.size:
        samples = samples[max(0, active[0]-int(.035*rate)):active[-1]+int(.09*rate)]
    return samples, rate


credit, rate = speak("Blonien Productions presents: Milestones — A Snap History Game.", 1.14, credit=True)
timing, _ = speak("It’s all about timing.", 1.04)
first, _ = speak("Which moment came first — San Francisco’s great earthquake…", 1.09)
alternative, _ = speak("Or the first powered flight by the Wright brothers?", 1.06, contrast=True)
closing, _ = speak("The fate of our timeline is in your hands. Find your place in history. Play Milestones now!", 1.16)

silence = lambda seconds: np.zeros(round(seconds * rate), dtype=np.float32)
takes = [
    np.concatenate((silence(0.55), credit, silence(0.35), timing, silence(0.80))),
    np.concatenate((silence(0.65), first, silence(0.18))),
    np.concatenate((silence(0.72), alternative, silence(0.50))),
    np.concatenate((silence(0.80), closing, silence(1.50))),
]


with TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    durations = [ceil(len(t)/rate*24)/24 for t in takes]
    for i, (file, slug, title, lines) in enumerate(chapters):
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
        elif i == 0:
            label(213, "P R E S E N T S" if i == 0 else "F I N", 21, "Georgia")
            label(306, "MILESTONES", 66)
            label(363, "A Snap History Game", 34, "Georgia Italic")
        else:
            label(205, "T H E   A N S W E R", 22, "Georgia")
            label(295, "1903", 92)
            label(385, "The Wright brothers flew first.", 31)
            label(455, "San Francisco’s earthquake followed in 1906.", 24, "Georgia")
        label(568, slug, 19, "Courier New Bold", "#d8c99b")
        draw.line((44, 608, 596, 608), fill="#c8ba91", width=2)
        label(664, title, 31 if i == 1 else 38)
        for j, line in enumerate(lines):
            label(738 + 44*j, line, 28, "Georgia")
        overlay = tmp / "overlay.png"
        art.save(overlay)
        voice = tmp / "voice.wav"
        samples = takes[i]
        sf.write(voice, samples, rate)
        length = len(samples) / rate
        print(f"Chapter {i+1}: {length:.2f}s of narration", flush=True)
        duration = durations[i]
        footage = (["-loop", "1", "-framerate", "24", "-i", str(sources / file)] if file == "Wrightflyer.jpg" else
                   ["-ss", "27", "-i", str(sources / file)] if file else
                   ["-f", "lavfi", "-i", "color=black:s=640x880:r=24"])
        run("ffmpeg", "-y", "-loglevel", "error", *footage, "-i", str(overlay), "-i", str(voice),
            "-filter_complex",
            "[0:v]fps=24,scale=576:376:force_original_aspect_ratio=increase,crop=576:376,"
            "setsar=1,hue=s=0,pad=640:880:32:147[film];[film][1:v]overlay[v];"
            "[2:a]highpass=f=135,equalizer=f=1050:t=q:w=1.4:g=3,"
            "equalizer=f=2350:t=q:w=1:g=1.5,lowpass=f=6300,alimiter=limit=0.92:level=0,"
            "apad[a]", "-map", "[v]", "-map", "[a]", "-t", str(duration),
            "-c:v", "libx264", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le",
            "-ar", "44100", str(tmp / f"{i}.mov"))
    manifest = tmp / "shots.txt"
    manifest.write_text("".join(f"file '{i}.mov'\n" for i in range(len(chapters))))
    sf.write(tmp / "overture.wav", render(sum(durations), sum(durations[:3]), sources / "vsco"), 48000)
    run("ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(manifest),
        "-i", str(tmp / "overture.wav"), "-filter_complex",
        "[0:a]asplit[narration][key];[1:a][key]sidechaincompress=threshold=0.025:ratio=6:"
        "attack=12:release=250[bed];[narration]pan=stereo|c0=c0|c1=c0[center];[center][bed]amix=inputs=2:duration=first:"
        "normalize=0,alimiter=limit=0.94:level=0:latency=1[a]", "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output))
