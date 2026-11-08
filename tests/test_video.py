"""Del guion validado a un video .html autocontenido, sin Piper ni red (voz en silencio)."""
import base64
import io
import json
import os
import re
import subprocess
import sys

import reproductor
import soundfile as sf
from compile import compilar
from conftest import SKILL
from datos import EJEMPLO
from etapas import escribir_salidas
from voz_falsa import generar


def test_video_autocontenido(tmp_path, monkeypatch):
    d = tmp_path / "t01"
    spec, rep = compilar(EJEMPLO, json.loads((SKILL / "scripts" / "lexico.json").read_text(encoding="utf-8")))
    assert rep.errores == []
    escribir_salidas(d, spec)
    dur = generar(d)
    subprocess.run([sys.executable, str(SKILL / "scripts" / "engine.py"), str(d)], check=True,
                   capture_output=True, env={**os.environ, "S2S_DATOS": str(tmp_path / "datos")})
    gsap = tmp_path / "gsap.min.js"; gsap.write_text("window.gsap={};/*stub*/", encoding="utf-8")
    monkeypatch.setitem(reproductor.CFG, "gsap", gsap)
    html = reproductor.construir(d, tmp_path / "videos" / "t01.html", "La FK de multa").read_text(encoding="utf-8")

    assert html.count("<audio") == 1 and "assets/" not in html            # nada fuera del archivo
    assert not re.findall(r'(?:src|href)="https?:', html)
    assert "<title>La FK de multa</title>" in html and "/*stub*/" in html
    assert html.index("window.__timelines = {}") < html.index("const S = ")   # el registro antes del motor
    mp3 = base64.b64decode(re.search(r'data:audio/mpeg;base64,([^"]+)', html)[1])
    a, sr = sf.read(io.BytesIO(mp3))
    assert abs(len(a) / sr - dur) < 0.15 and a.std() > 0.001             # dura lo mismo y suena (música y efectos)


def test_indice(tmp_path):
    p = reproductor.indice(tmp_path / "index.html", "Biblioteca <ejemplo>",
                           [{"archivo": "t01.html", "titulo": "La FK de multa", "pregunta": "¿Por qué?", "duracion": 48.2}])
    s = p.read_text(encoding="utf-8")
    assert 'href="t01.html"' in s and "0:48" in s and "Biblioteca &lt;ejemplo&gt;" in s


def test_mezcla_no_satura():
    import numpy as np
    import sonido
    uno = np.ones((sonido.SR, 2), dtype=np.float32) * 0.8
    m = sonido.mezclar([(uno, 0, 1, 1), (uno, 0, 1, 1)], 1.0)
    assert m.shape == (sonido.SR, 2) and abs(m).max() <= 0.99
