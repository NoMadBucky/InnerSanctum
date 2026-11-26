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
from overture import PIZZ_BEAT, render
from hourglass import HourglassShot
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
        phones = "blˈɑːniːɪn pɹədˈʌkʃənz pɹɪzˈɛnts:"
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


credit, rate = speak("Blonien Productions presents:", 1.14, credit=True)
name, _ = speak("Milestones.", 1.14)
subtitle, _ = speak("A Snap History Game.", 1.14)
timing, _ = speak("It’s all about timing.", 1.04)
first, _ = speak("Which moment came first — San Francisco’s great earthquake…", 1.09)
alternative, _ = speak("Or the first powered flight by the Wright brothers?", 1.06, contrast=True)
fate, _ = speak("The fate of our timeline is in your hands.", 1.16)
place, _ = speak("Find your place in history.", 1.16)
play_now, _ = speak("Play Milestones now!", 1.16)

silence = lambda seconds: np.zeros(round(seconds * rate), dtype=np.float32)
def cue_track(*phrases):
    """One clock for spoken phrases and their on-screen cues."""
    blocks, cues, length = [], {}, 0
    for name, audio in phrases:
        cues[name] = length / rate
        blocks.append(audio)
        length += len(audio)
    return np.concatenate(blocks), cues


opening, intro = cue_track(("hourglass", silence(1.75)), ("music", silence(3)), ("credit", credit),
                          ("titleBeat", silence(.12)), ("name", name),
                          ("subtitle", subtitle), ("pause", silence(.35)),
                          ("timing", timing), ("hold", silence(.8)))
ending, outro = cue_track(("guess", silence(3)), ("answer", silence(.85)),
                         ("fate", fate), ("beat", silence(.18)), ("place", place),
                         ("breath", silence(.18)), ("cta", play_now), ("ring", silence(3.4)))
takes = [
    opening,
    np.concatenate((silence(0.65), first, silence(0.18))),
    np.concatenate((silence(0.72), alternative, silence(0.50))),
    ending,
]


with TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    durations = [ceil(len(t)/rate*24)/24 for t in takes]
    last_in_score = sum(durations[:3]) - intro["music"]
    reveal = last_in_score + outro["answer"]
    stamp_flight = .16
    for i, (file, slug, title, lines) in enumerate(chapters):
        art = Image.new("RGBA", (640, 880), (0, 0, 0, 0) if i == 0 else "#171813")
        draw = ImageDraw.Draw(art)
        layers = []

        def label(y, text, size, face="Georgia Bold", color="#f5efda", cue=None, until=None, effect=None):
            font = ImageFont.truetype(f"/System/Library/Fonts/Supplemental/{face}.ttf", size)
            if cue is None:
                draw.text((320, y), text, font=font, fill=color, anchor="mm")
            else:
                sprite = Image.new("RGBA", art.size)
                ImageDraw.Draw(sprite).text((320, y), text, font=font, fill=color, anchor="mm")
                box = sprite.getbbox()
                layers.append((sprite.crop(box), box[:2], cue, until, effect))

        border = Image.new("RGBA", art.size) if i == 0 else art
        ImageDraw.Draw(border).rectangle((15, 15, 624, 864), outline="#c8ba91", width=2)
        if i == 0:
            layers.append((border, (0, 0), intro["subtitle"], None, False))
        label(56, "BLONIEN PRODUCTIONS", 26, cue=intro["credit"] if i == 0 else None)
        if i:
            label(103, f"THE HISTORY DESK     /     REEL 01     /     {i+1} OF 4", 16, "Courier New Bold")
        if file:
            draw.rectangle((32, 147, 607, 522), fill=(0, 0, 0, 0))
        elif i == 0:
            hourglass = HourglassShot(root / "Chronology/Assets.xcassets/AppIcon.appiconset/Chronology.png", art.size)
            label(99, "P R E S E N T S", 21, "Georgia", cue=intro["credit"]+.25)
            label(478, "MILESTONES", 66, cue=intro["name"], effect="pop")
            label(550, "A Snap History Game", 34, "Georgia Italic", cue=intro["subtitle"])
        else:
            label(302, "?", 125, cue=0, until=outro["answer"], effect="pulse")
            label(205, "T H E   A N S W E R", 22, "Georgia", cue=outro["answer"])
            label(295, "1903", 92, cue=outro["answer"])
            label(385, "The Wright brothers flew first.", 31, cue=outro["answer"])
            label(455, "San Francisco’s earthquake followed in 1906.", 24, "Georgia", cue=outro["answer"])
        label(568, slug, 19, "Courier New Bold", "#d8c99b")
        if i:
            draw.line((44, 608, 596, 608), fill="#c8ba91", width=2)
        label(664, title, 31 if i == 1 else 38,
              cue=intro["timing"] if i == 0 else outro["place"] if i == 3 else None)
        for j, line in enumerate(lines):
            if i == 3 and j == 1:
                # A broad ink impression in the gap between the answer and
                # sign-off; the date and both supporting lines remain legible.
                stamp = Image.new("RGBA", (578, 82))
                ink = ImageDraw.Draw(stamp)
                ink.rounded_rectangle((3, 3, 574, 78), 5, fill="#31251a", outline="#e9bc78", width=4)
                font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Georgia Bold.ttf", 40)
                ink.text((289, 40), "PLAY MILESTONES NOW!", font=font, fill="#f4cd8e", anchor="mm")
                stamp = stamp.rotate(5, Image.Resampling.BICUBIC, expand=True)
                layers.append((stamp, ((640-stamp.width)//2, 545-stamp.height//2),
                               outro["cta"], None, "stamp"))
                continue
            label(738 + 44*j, line, 28, "Georgia",
                  cue=outro[("fate", "cta")[j]] if i == 3 else None)
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
        overlay_input = (["-f", "rawvideo", "-pix_fmt", "rgba", "-s", "640x880", "-r", "24", "-i", "pipe:0"]
                         if layers else ["-i", str(overlay)])
        cmd = ["ffmpeg", "-y", "-loglevel", "error", *footage, *overlay_input, "-i", str(voice),
            "-filter_complex",
            "[0:v]fps=24,scale=576:376:force_original_aspect_ratio=increase,crop=576:376,"
            "setsar=1,hue=s=0,pad=640:880:32:147[film];[film][1:v]overlay[v];"
            "[2:a]highpass=f=135,equalizer=f=1050:t=q:w=1.4:g=3,"
            "equalizer=f=2350:t=q:w=1:g=1.5,lowpass=f=6300,alimiter=limit=0.92:level=0,"
            "apad[a]", "-map", "[v]", "-map", "[a]", "-t", str(duration),
            "-c:v", "libx264", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le",
            "-ar", "44100", str(tmp / f"{i}.mov")]
        if layers:
            with subprocess.Popen(cmd, stdin=subprocess.PIPE) as encoder:
                for frame in range(round(duration * 24)):
                    canvas = (Image.alpha_composite(hourglass.frame(frame/24, intro["music"], intro["name"]), art)
                              if i == 0 else art.copy())
                    for sprite, xy, begin, end, effect in layers:
                        t = frame / 24
                        age = t - begin
                        opacity = min(1, age/(.08 if effect in ("pop", "stamp") else .42), (end-t)/.30 if end is not None else 1)
                        if opacity > 0:
                            scale = 1
                            if effect == "pop" and age < .34:
                                # Grow from the optical center, overshoot, then settle.
                                u = min(age/.34, 1) - 1
                                scale = 1 + .34*(3.8*u**3 + 2.8*u**2)
                            elif effect == "pulse":
                                # Same origin and period as the question's cello plucks.
                                phase = (last_in_score + t - reveal*.5) % PIZZ_BEAT
                                scale += .19*np.exp(-phase/.17)
                            elif effect == "stamp" and age < stamp_flight:
                                scale += .46*(1-age/stamp_flight)**2
                            if scale != 1:
                                w, h = sprite.size
                                sprite = sprite.resize((round(w*scale), round(h*scale)), Image.Resampling.LANCZOS)
                                xy = (xy[0]+(w-sprite.width)//2, xy[1]+(h-sprite.height)//2)
                            canvas.paste(sprite, xy, sprite.getchannel("A").point(lambda a: a*opacity))
                    encoder.stdin.write(canvas.tobytes())
                encoder.stdin.close()
                if encoder.wait():
                    raise RuntimeError("Could not render timed title card")
        else:
            run(*cmd)
    manifest = tmp / "shots.txt"
    manifest.write_text("".join(f"file '{i}.mov'\n" for i in range(len(chapters))))
    start = intro["music"]
    score = render(sum(durations) - start, reveal, last_in_score + outro["cta"] + stamp_flight, sources / "vsco")
    sf.write(tmp / "overture.wav", np.pad(score, ((round(start*48000), 0), (0, 0))), 48000)
    run("ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(manifest),
        "-i", str(tmp / "overture.wav"), "-filter_complex",
        "[0:a]asplit[narration][key];[1:a][key]sidechaincompress=threshold=0.025:ratio=6:"
        "attack=12:release=250[bed];[narration]pan=stereo|c0=c0|c1=c0[center];[center][bed]amix=inputs=2:duration=first:"
        "normalize=0,alimiter=limit=0.94:level=0:latency=1[a]", "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output))
