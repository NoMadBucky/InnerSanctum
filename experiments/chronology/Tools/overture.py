"""Render the Milestones cue with acoustic recordings from VSCO 2 CE (CC0)."""
from functools import lru_cache
from urllib.parse import quote
from urllib.request import urlopen

import numpy as np
import soundfile as sf


def render(seconds, reveal, cache, rate=48000):
    cache.mkdir(parents=True, exist_ok=True)
    base = "https://raw.githubusercontent.com/sgossner/VSCO-2-CE/440300901dfe9275fd84e0b7763af1f8443ae62e/"
    mix = np.zeros((round(seconds * rate), 2))

    @lru_cache(None)
    def sample(path):
        file = cache / path.rsplit("/", 1)[1]
        if not file.exists():
            with urlopen(base + quote(path), timeout=30) as response:
                file.write_bytes(response.read())
        audio, hz = sf.read(file, always_2d=True)
        return audio / max(.001, np.max(np.abs(audio))), hz

    def play(path, at, length, gain, semitones=0, pan=0):
        audio, hz = sample(path)
        start = round(at * rate)
        step = hz / rate * 2 ** (semitones / 12)
        n = min(round(length * rate), len(mix)-start, int((len(audio)-1)/step))
        idx = np.arange(n)*step
        envelope = gain * np.minimum(1, np.arange(n)[::-1] / (.17 * rate))
        for channel, balance in enumerate([1-pan, 1+pan]):
            mix[start:start+n, channel] += envelope * balance * np.interp(
                idx, np.arange(len(audio)), audio[:, channel % audio.shape[1]])

    # Short tongued pickups, then sustained horn notes with their recorded attack.
    for at, pitch, articulation, length, gain in [
        (0, "D2", "stac", .34, .22), (.29, "A2", "stac", .37, .22),
        (.61, "C3", "sus", 1.45, .26), (reveal, "A2", "sus", .57, .20),
        (reveal+.50, "C3", "sus", .75, .24), (reveal+1.16, "F4", "sus", 1.8, .21),
        (seconds-1.65, "C3", "sus", 1.6, .21),
    ]:
        suffix = "v1_1" if articulation == "sus" else "v2_rr1"
        play(f"Brass/F Horn/{articulation}/MOHorn_{articulation}_{pitch}_{suffix}.wav",
             at, length, gain, {"C3": 2, "F4": -11}.get(pitch, 0), -.18)

    for begin, end, bass, upper, shift in [
        (0, reveal*.5, "D2", "F2", 0),
        (reveal*.5, reveal, "A2", "E3", 0),
        (reveal, seconds, "D2", "F2", 1),
    ]:
        # Rebow sustained parts and alternate pizzicato takes under the question.
        for beat, at in enumerate(np.arange(begin, end-.18, 1.04)):
            play(f"Strings/Cello Section/pizzT/pizzT_{bass}_v1_RR{1+beat%2}.wav",
                 at, min(.96, end-at), .105 if beat % 2 == 0 else .075, pan=.21)
        for at in np.arange(begin, end-.18, 2.8):
            play(f"Strings/Cello Section/susvib/susvib_{upper}_v1_1.wav",
                 at, min(2.92, end-at), .12, shift, .12)
        play("Percussion/Timpani/Timpani1_Hit_v1_rr1_Sum.wav", begin, 1.65, .24)

    mix *= np.minimum(1, np.arange(len(mix))[::-1] / (.42 * rate))[:, None]
    return mix
