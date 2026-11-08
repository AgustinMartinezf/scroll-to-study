"""Voz frase por frase (Piper) y los tiempos de cada palabra.

Uso:  python3 voice.py CARPETA [voz] [velocidad]
Lee CARPETA/script.json y gaps.json (los escribe compile.py); escribe CARPETA/assets/voz.wav y
CARPETA/timing.json. Los tiempos por palabra se reparten por sílabas aproximadas: no se alinean con
el audio, pero alcanza para el resaltado de subtítulos.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
import soundfile as sf

from config import CFG, VOZ_DEFECTO

d = sys.argv[1]
voz = sys.argv[2] if len(sys.argv) > 2 else VOZ_DEFECTO
velocidad = float(sys.argv[3]) if len(sys.argv) > 3 else 1.1
if voz not in CFG["voces"]:
    sys.exit(f"voz desconocida «{voz}»; hay: {', '.join(CFG['voces'])}")
modelo = str(CFG["voces"][voz])
if not os.path.exists(modelo):
    sys.exit(f"falta el modelo de voz {modelo}: corré `python3 s2s.py instalar`")

GAP, LEAD, TAIL = 0.22, 0.15, 1.4


def sintetizar(texto):
    with tempfile.TemporaryDirectory() as tmp:
        f = os.path.join(tmp, "f.wav")
        subprocess.run([sys.executable, "-m", "piper", "-m", modelo, "-c", modelo + ".json", "-f", f,
                        "--length-scale", str(round(1 / velocidad, 3))],
                       input=texto.encode("utf-8"), check=True, capture_output=True)
        return sf.read(f, dtype="float32")


def recortar(a, sr, umbral=0.01):
    idx = np.where(np.abs(a) > umbral)[0]
    return a[max(0, idx[0] - int(sr * 0.02)):idx[-1] + int(sr * 0.04)] if len(idx) else a


S = json.load(open(f"{d}/script.json", encoding="utf-8"))
G = {int(k): v for k, v in json.load(open(f"{d}/gaps.json", encoding="utf-8")).items()} \
    if os.path.exists(f"{d}/gaps.json") else {}

out, words, phrases, t, SR = [], [], [], LEAD, None
for i, p in enumerate(S):
    texto = p["tts"] or p["cap"]
    a, sr = sintetizar(texto.replace("~", " "))
    a = recortar(a.astype(np.float32), sr)
    dur = len(a) / sr
    cw, tw = p["cap"].split(), texto.split()
    assert len(cw) == len(tw), (cw, tw)
    # peso por sílabas aproximadas (vocales) del texto hablado + pausa en la puntuación
    wts = [(len(re.findall(r"[aeiouáéíóúü]+", w.lower())) or 1) + (0.6 if re.search(r"[,:.?]$", w) else 0) for w in tw]
    tot, acc = sum(wts), 0
    for w, wt in zip(cw, wts):
        words.append({"text": w, "start": round(t + dur * acc / tot, 3), "end": round(t + dur * (acc + wt) / tot, 3), "phrase": i})
        acc += wt
    phrases.append({"i": i, "start": round(t, 3), "end": round(t + dur, 3), "cap": p["cap"]})
    SR = sr
    out.append(a)
    t += dur
    pausa = G.get(i, GAP) if i < len(S) - 1 else TAIL
    out.append(np.zeros(int(sr * pausa), dtype=np.float32))
    t += pausa

audio = np.concatenate([np.zeros(int(SR * LEAD), dtype=np.float32)] + out)
os.makedirs(f"{d}/assets", exist_ok=True)
sf.write(f"{d}/assets/voz.wav", audio, SR)
json.dump({"duration": round(len(audio) / SR, 3), "words": words, "phrases": phrases},
          open(f"{d}/timing.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{d}: voz {voz}, {round(len(audio) / SR, 1)} s")
