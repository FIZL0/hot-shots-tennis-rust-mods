#!/usr/bin/env python3
"""Golf mods' voice lines the packager left out, transcribed and sorted by what they say into
out/voice_candidates/<mod>/<bucket>/ (bucket = suggested HST program group by keywords, a starting point for picking
by ear, not a verdict) with index.tsv (bucket, seconds, language, transcript, source wav). Lines already in the mod
and worded non-English takes are left out. Transcripts are cached by md5 in out/voice_candidates/.transcripts.json.
usage: tools/voice_candidates.py   (after rerig/package.py; needs `pip install faster-whisper`; ~30 min the first time)"""
import glob, hashlib, json, os, re, shutil, sys, wave
from concurrent.futures import ProcessPoolExecutor

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(R, "out/voice_candidates")
CACHE = os.path.join(OUT, ".transcripts.json")
A = os.path.join(R, "out/audio")


def sources(game, pc):
    n = f"{pc:02d}"
    if game == "oob":  # .xb0 is the English cast (notes/audio.md "Language")
        return glob.glob(f"{A}/oob/**/ga_pc_{n}.xb0/**/*.wav", recursive=True)
    if game == "opentee2":  # .xb1 = English
        return glob.glob(f"{A}/opentee2/**/pc_*_{n}[ab].xb1/**/[0-9]*.wav", recursive=True)
    return glob.glob(f"{R}/out/voices/{game}/pc{n}/*.wav")


def md5(f):
    return hashlib.md5(open(f, "rb").read()).hexdigest()


def dur(f):
    with wave.open(f) as w:
        return w.getnframes() / w.getframerate()


_m = None


def transcribe(f):
    global _m
    if _m is None:
        from faster_whisper import WhisperModel
        _m = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=2)
    import numpy as np
    with wave.open(f) as w:  # ponytail: own loader, faster-whisper's PyAV decode breaks on av 19
        sr, ch, x = w.getframerate(), w.getnchannels(), np.frombuffer(w.readframes(w.getnframes()), np.int16)
    x = x.reshape(-1, ch).mean(1) / 32768
    x = np.interp(np.arange(0, len(x), sr / 16000), np.arange(len(x)), x).astype(np.float32)
    seg, info = _m.transcribe(x, beam_size=1, vad_filter=False)
    return " ".join(s.text.strip() for s in seg).strip(), info.language, round(info.language_probability, 2)


WIN = r"\b(yes|yeah|yay|all ?right|alright|did it|nice|great|best|perfect|woo+|yahoo|awesome|excellent|it'?s in|i win|got it|good|wonderful|fantastic|amazing|cool|lucky|hooray|ha ha|haha|beautiful|easy|victory|thank)\b"
LOSE = r"\b(no+|oh no|shoot|darn|damn|dang|pity|shame|awful|next time|ugh|aw+|why|miss|terrible|can'?t believe|not again|bad|unlucky|sorry|rats|oh man|geez|nuts|lost|lose)\b"
OOPS = r"\b(oops|whoops|huh|what|eh|uh[- ]?oh|hm+|wha)\b"


def bucket(text, d):
    t = text.lower()
    if re.search(OOPS, t) and d < 1.2:
        return "2-4_mishit_whiff"
    if re.search(LOSE, t):
        return "8-10_lost_point"
    if re.search(WIN, t):
        return "7-9_won_point"
    if d < 0.8:
        return "0-1-3_shout"
    return "other_long"


def slug(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:40] or "noword"


def main():
    os.makedirs(OUT, exist_ok=True)
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    mods = sorted(m for m in glob.glob(f"{R}/out/mods/*") if re.match(r"(fore|opentee2|oob)_pc\d\d", os.path.basename(m)))
    plan = {}
    for m in mods:
        name = os.path.basename(m)
        game, pc = re.match(r"(\w+?)_pc(\d\d)", name).groups()
        used = {md5(f) for f in glob.glob(f"{m}/voice/*.wav")}
        seen = {}
        for f in sorted(sources(game, int(pc))):
            h = md5(f)
            if h not in used and h not in seen:
                seen[h] = f
        plan[name] = seen
    todo = {h: f for s in plan.values() for h, f in s.items() if h not in cache}
    print(f"{sum(map(len, plan.values()))} unused lines, {len(todo)} to transcribe", flush=True)
    with ProcessPoolExecutor(8) as ex:
        for i, (h, r) in enumerate(zip(todo, ex.map(transcribe, todo.values(), chunksize=8))):
            cache[h] = r
            if i % 200 == 0:
                print(i, flush=True)
                json.dump(cache, open(CACHE, "w"))
    json.dump(cache, open(CACHE, "w"))
    for name, seen in plan.items():
        d = os.path.join(OUT, name)
        shutil.rmtree(d, ignore_errors=True)
        rows = []
        for h, f in seen.items():
            text, lang, p = cache[h]
            if lang != "en" and p > 0.6 and len(text) > 4:  # a worded non-English take (Japanese copy)
                continue
            ln = dur(f)
            b = bucket(text, ln)
            src = os.path.relpath(f, R)
            dst = os.path.join(d, b, f"{os.path.basename(os.path.dirname(f)).split('.')[0]}_{os.path.basename(f)[:-4]}__{slug(text)}.wav")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(f, dst)
            rows.append(f"{b}\t{ln:.2f}\t{lang}:{p}\t{text}\t{src}")
        with open(os.path.join(d, "index.tsv"), "w") as fh:
            fh.write("bucket\tsec\tlang\ttranscript\tsource\n" + "\n".join(sorted(rows)) + "\n")


if __name__ == "__main__":
    main()
