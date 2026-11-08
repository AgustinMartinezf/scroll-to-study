"""Voz frase por frase (Piper) y el momento exacto de cada palabra.

Uso:  python3 voice.py CARPETA [voz] [velocidad]
Lee CARPETA/script.json y gaps.json (los escribe compile.py); escribe CARPETA/assets/voz.wav y
CARPETA/timing.json.

Los tiempos salen del propio modelo de voz: Piper informa cuántas muestras de audio dura cada fonema
(include_alignments), así que el inicio de cada palabra es exacto, sin transcribir el audio. Si una
frase no se puede alinear palabra por palabra (por ejemplo, un número que se lee como varias
palabras), esa frase vuelve al reparto por sílabas y queda anotada en timing.json.
"""
import json
import os
import re
import sys

import numpy as np
import soundfile as sf

from config import CFG, VOZ_DEFECTO

GAP, LEAD, TAIL = 0.22, 0.15, 1.4
UMBRAL = 0.01


def cargar_voz(nombre):
    from piper import PiperVoice
    modelo = str(CFG["voces"][nombre])
    if not os.path.exists(modelo):
        sys.exit(f"falta el modelo de voz {modelo}: corré `python3 s2s.py instalar`")
    return PiperVoice.load(modelo, config_path=modelo + ".json", include_alignments=True)


def palabras_foneticas(fonemas):
    """Agrupa los fonemas de un trozo en palabras: [(inicio_en_muestras, fin_en_muestras)]."""
    out, t, ini, hay = [], 0, 0, False
    for f, n in fonemas:
        if f == " ":
            if hay:
                out.append((ini, t))
            hay = False
            t += n
            ini = t
            continue
        if f not in "^$" and not re.fullmatch(r"[.,:;!?¡¿…]+", f):
            hay = True
        t += n
    if hay:
        out.append((ini, t))
    return out


ES_SONIDO = re.compile(r"[^\s^$ˈˌ.,:;!?¡¿…\"'()\-]")


def sintetizar(voz, texto, velocidad):
    """(audio, sr, [(ini, fin)] por palabra hablada en segundos o None, [(ini, fin)] por fonema con sonido)."""
    from piper import SynthesisConfig
    cfg = SynthesisConfig(length_scale=round(1 / velocidad, 3))
    trozos, palabras, fonemas, base, sr, alineado = [], [], [], 0, None, True
    for ch in voz.synthesize(texto, cfg, include_alignments=True):
        sr = ch.sample_rate
        a = ch.audio_float_array.astype(np.float32)
        if ch.phoneme_alignments:
            for i, f in palabras_foneticas([(x.phoneme, x.num_samples) for x in ch.phoneme_alignments]):
                palabras.append(((base + i) / sr, (base + f) / sr))
            pos = base
            for x in ch.phoneme_alignments:
                if ES_SONIDO.match(x.phoneme):
                    fonemas.append((pos / sr, (pos + x.num_samples) / sr))
                pos += x.num_samples
        else:
            alineado = False
        trozos.append(a)
        base += len(a)
    return np.concatenate(trozos), sr, (palabras if alineado else None), (fonemas if alineado else None)


def cuantos_fonemas(voz, token):
    return max(1, sum(1 for frase in voz.phonemize(token) for f in frase if ES_SONIDO.match(f)))


def cuantas_palabras(voz, token):
    """Cuántas palabras fonéticas produce un token (un número puede ser varias)."""
    fon = [p for frase in voz.phonemize(token) for p in frase]
    return max(1, len(palabras_foneticas([(f, 1) for f in fon])))


def por_silabas(cw, tw, t, dur):
    # peso por sílabas aproximadas (vocales) del texto hablado + pausa en la puntuación
    wts = [(len(re.findall(r"[aeiouyáéíóúü]+", w.lower())) or 1) + (0.6 if re.search(r"[,:.?]$", w) else 0) for w in tw]
    tot, acc, out = sum(wts), 0, []
    for w, wt in zip(cw, wts):
        out.append((round(t + dur * acc / tot, 3), round(t + dur * (acc + wt) / tot, 3)))
        acc += wt
    return out


def main():
    d = sys.argv[1]
    nombre = sys.argv[2] if len(sys.argv) > 2 else VOZ_DEFECTO
    velocidad = float(sys.argv[3]) if len(sys.argv) > 3 else 1.1
    if nombre not in CFG["voces"]:
        sys.exit(f"voz desconocida «{nombre}»; hay: {', '.join(CFG['voces'])}")
    voz = cargar_voz(nombre)
    S = json.load(open(f"{d}/script.json", encoding="utf-8"))
    G = {int(k): v for k, v in json.load(open(f"{d}/gaps.json", encoding="utf-8")).items()} \
        if os.path.exists(f"{d}/gaps.json") else {}

    out, words, phrases, estimadas, t, SR = [], [], [], [], LEAD, None
    for i, p in enumerate(S):
        texto = p["tts"] or p["cap"]
        cw, tw = p["cap"].split(), texto.split()
        assert len(cw) == len(tw), (cw, tw)
        a, sr, pal, fon = sintetizar(voz, texto.replace("~", " "), velocidad)
        idx = np.where(np.abs(a) > UMBRAL)[0]
        corte = max(0, idx[0] - int(sr * 0.02)) if len(idx) else 0
        a = a[corte:idx[-1] + int(sr * 0.04)] if len(idx) else a
        dur = len(a) / sr

        # cada palabra del subtítulo agrupa las palabras habladas de su token (efe~ka, i~de~prestamo, 1452…)
        grupos = [sum(cuantas_palabras(voz, parte) for parte in w.split("~") if parte) for w in tw]
        if pal is not None and sum(grupos) == len(pal):
            tiempos, k = [], 0
            for g in grupos:
                ini = pal[k][0] - corte / sr
                fin = pal[k + g - 1][1] - corte / sr
                tiempos.append((round(t + max(0.0, ini), 3), round(t + min(dur, fin), 3)))
                k += g
        elif fon:
            # el idioma junta palabras al hablar ("does not" → una sola): repartir por fonemas reales
            pesos = [sum(cuantos_fonemas(voz, parte) for parte in w.split("~") if parte) for w in tw]
            tot, acc, tiempos = sum(pesos), 0, []
            for peso in pesos:
                k0 = min(len(fon) - 1, round(len(fon) * acc / tot))
                k1 = min(len(fon) - 1, max(k0, round(len(fon) * (acc + peso) / tot) - 1))
                ini, fin = fon[k0][0] - corte / sr, fon[k1][1] - corte / sr
                tiempos.append((round(t + max(0.0, ini), 3), round(t + min(dur, fin), 3)))
                acc += peso
        else:
            estimadas.append(i)
            tiempos = por_silabas(cw, tw, t, dur)
        for w, (ini, fin) in zip(cw, tiempos):
            words.append({"text": w, "start": ini, "end": fin, "phrase": i})
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
    json.dump({"duration": round(len(audio) / SR, 3), "words": words, "phrases": phrases,
               "estimadas": estimadas},
              open(f"{d}/timing.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    aviso = f", {len(estimadas)} frase(s) con tiempos estimados: {estimadas}" if estimadas else ", tiempos exactos"
    print(f"{d}: voz {nombre}, {round(len(audio) / SR, 1)} s{aviso}")


if __name__ == "__main__":
    main()
