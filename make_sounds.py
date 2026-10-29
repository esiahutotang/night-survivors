"""Build short PCM WAV sounds offline using only Python's standard library.

Run: py -3.13 make_sounds.py. The game loads these finished files.
"""
import json
import math
from pathlib import Path
import random
import struct
import wave

ROOT = Path(__file__).resolve().parent


def main():
    config = json.loads((ROOT / "data" / "game.json").read_text(encoding="utf-8"))["audio"]
    rate = config["sample_rate"]
    destination = ROOT / "sounds"
    destination.mkdir(exist_ok=True)
    rng = random.Random(0)
    for name, clip in config["clips"].items():
        samples = bytearray()
        for start, end, duration in clip["notes"]:
            count = round(duration * rate)
            phase = 0.0
            for i in range(count):
                t = i / rate
                frequency = start + (end-start) * i / max(1, count-1)
                phase += math.tau * frequency / rate
                tone = 0.8*math.sin(phase) + 0.2*math.sin(phase*2)
                signal = tone*(1-clip["noise"]) + rng.uniform(-1, 1)*clip["noise"]
                fade = config["fade_seconds"]
                envelope = max(0, min(1, t/fade, (count-1-i)/rate/fade))
                value = round(signal * envelope * config["volume"] * 32767)
                samples.extend(struct.pack("<h", max(-32768, min(32767, value))))
        path = destination / f"{name}.wav"
        with wave.open(str(path), "wb") as sound:
            sound.setnchannels(1)
            sound.setsampwidth(2)
            sound.setframerate(rate)
            sound.writeframes(samples)
        print(f"Built {path.name}: {len(samples)/2/rate:.3f} s")


if __name__ == "__main__":
    main()
