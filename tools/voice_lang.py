#!/usr/bin/env python3
"""Language of each packaged mod's voice lines (catches a Japanese bank picked over the English one).
usage: tools/voice_lang.py [out/mods/<mod> ...]   (default every mod; needs `pip install faster-whisper`, ffmpeg)
Prints '<lang> <prob> <wav> | <transcript>' for each mod's four longest voice wavs; trust only long, worded lines."""
import glob, os, subprocess, sys
import numpy as np
from faster_whisper import WhisperModel

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
m = WhisperModel("small", device="cpu", compute_type="int8")
for d in sys.argv[1:] or sorted(glob.glob(f"{R}/out/mods/*/")):
    for f in sorted(glob.glob(os.path.join(d, "voice/*.wav")), key=os.path.getsize, reverse=True)[:4]:
        pcm = subprocess.run(["ffmpeg", "-v", "quiet", "-i", f, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                             capture_output=True).stdout
        seg, info = m.transcribe(np.frombuffer(pcm, np.int16).astype(np.float32) / 32768, beam_size=1)
        print(f"{info.language} {info.language_probability:.2f} {os.path.relpath(f, R)} | "
              + " ".join(s.text for s in seg).strip()[:70], flush=True)
