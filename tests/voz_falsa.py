"""timing.json y una voz en silencio, sin Piper: mismo reparto por sílabas que voice.py, 0,16 s por sílaba."""
import json
import re
import sys

import numpy as np
import soundfile as sf


def generar(d):
    S = json.load(open(f"{d}/script.json", encoding="utf-8"))
    G = {int(k): v for k, v in json.load(open(f"{d}/gaps.json", encoding="utf-8")).items()}
    t = 0.15; words = []; phrases = []
    for i, p in enumerate(S):
        text = p["tts"] or p["cap"]; cw = p["cap"].split(); tw = text.split(); assert len(cw) == len(tw)
        wts = [(len(re.findall(r"[aeiouáéíóúü]+", w.lower())) or 1) + (0.6 if re.search(r"[,:.?]$", w) else 0) for w in tw]
        dur = sum(wts) * 0.16; acc = 0
        for w, wt in zip(cw, wts):
            words.append({"text": w, "start": round(t + dur * acc / sum(wts), 3), "end": round(t + dur * (acc + wt) / sum(wts), 3), "phrase": i}); acc += wt
        phrases.append({"i": i, "start": round(t, 3), "end": round(t + dur, 3), "cap": p["cap"]})
        t += dur + (G.get(i, 0.22) if i < len(S) - 1 else 1.4)
    import os
    os.makedirs(f"{d}/assets", exist_ok=True)
    sf.write(f"{d}/assets/voz.wav", np.zeros(int(t * 22050), dtype=np.float32), 22050)
    json.dump({"duration": round(t, 3), "words": words, "phrases": phrases},
              open(f"{d}/timing.json", "w", encoding="utf-8"), ensure_ascii=False)
    return round(t, 3)


if __name__ == "__main__":
    print(sys.argv[1], "duración simulada", generar(sys.argv[1]))
