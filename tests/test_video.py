"""Del guion validado a un video .html autocontenido, sin Piper ni red (voz en silencio)."""
import base64
import pytest
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

    assert "<audio" not in html and "assets/" not in html                 # nada fuera del archivo
    assert not re.findall(r'(?:src|href)="https?:', html)
    assert "<title>La FK de multa</title>" in html and "/*stub*/" in html
    assert html.index("window.__timelines = {}") < html.index("const S = ")   # el registro antes del motor
    mp3 = base64.b64decode(re.search(r'<script type="application/octet-stream" id="s2s-mp3">([^<]+)</script>', html)[1])
    a, sr = sf.read(io.BytesIO(mp3))
    assert abs(len(a) / sr - dur) < 0.15 and a.std() > 0.001             # dura lo mismo y suena (música y efectos)


def test_indice(tmp_path):
    p = reproductor.indice(tmp_path / "index.html", "Biblioteca <ejemplo>",
                           [{"archivo": "t01.html", "titulo": "La FK de multa", "pregunta": "¿Por qué?", "duracion": 48.2}])
    s = p.read_text(encoding="utf-8")
    assert '"archivo": "t01.html"' in s and '"duracion": 48.2' in s and "<title>Biblioteca &lt;ejemplo&gt;</title>" in s
    assert '"id": "t01"' in s                                   # sin id, el nombre del archivo
    assert "Hoy toca" in s and "Borrar progreso" in s and "Exportar progreso" in s and "localStorage" in s
    assert "window.Progreso" in s or "raiz.Progreso" in s        # progreso.js va embebido
    assert s.lower().count("</script") == s.lower().count("<script")


def test_indice_con_ids_y_en_ingles(tmp_path):
    videos = [{"id": "t07", "archivo": "t07.html", "titulo": "__TX__ </script>", "duracion": 30},
              {"id": "t02", "archivo": "t02.html", "titulo": "B", "duracion": 40}]
    s = reproductor.indice(tmp_path / "index.html", "Course", videos, "en").read_text(encoding="utf-8")
    assert '"id": "t07"' in s and '"id": "t02"' in s
    assert "Up today" in s and "Clear progress" in s and "Export progress" in s
    assert '"titulo": "__TX__ <\\/script>"' in s                 # una sola pasada, y sin cerrar el <script>
    with pytest.raises(ValueError):
        reproductor.indice(tmp_path / "x.html", "C", [videos[0], dict(videos[1], id="t07")])


def test_mezcla_no_satura():
    import numpy as np
    import sonido
    uno = np.ones((sonido.SR, 2), dtype=np.float32) * 0.8
    m = sonido.mezclar([(uno, 0, 1, 1), (uno, 0, 1, 1)], 1.0)
    assert m.shape == (sonido.SR, 2) and abs(m).max() <= 0.99


def test_palabras_foneticas_agrupa_por_espacios_y_salta_la_puntuacion():
    import voice
    fon = [("^", 2), ("l", 3), ("a", 5), (" ", 1), ("ˈ", 0), ("e", 4), ("s", 2), (",", 6), (" ", 1), (".", 3), ("$", 2)]
    assert voice.palabras_foneticas(fon) == [(0, 10), (11, 23)]        # "la", "es," ; el "." final no es palabra


def test_motor_con_chat_grafica_y_contador(tmp_path, monkeypatch):
    g = json.loads((SKILL.parents[1] / "tests" / "fixtures" / "guion_elementos.json").read_text(encoding="utf-8"))
    spec, rep = compilar(g, json.loads((SKILL / "scripts" / "lexico.json").read_text(encoding="utf-8")))
    assert rep.errores == []
    d = tmp_path / "t02"; escribir_salidas(d, spec); generar(d)
    subprocess.run([sys.executable, str(SKILL / "scripts" / "engine.py"), str(d)], check=True,
                   capture_output=True, env={**os.environ, "S2S_DATOS": str(tmp_path / "datos")})
    html = (d / "index.html").read_text(encoding="utf-8")
    assert 'class="card chat"' in html and 'id="ch-m1"' in html
    assert 'class="bar" id="g-b0"' in html and 'data-d="4"' in html


def test_sonoridad_como_ebu_r128():
    import numpy as np
    import sonido
    t = np.arange(sonido.SR * 5) / sonido.SR
    x = (0.1 * np.sin(2 * np.pi * 997 * t)).astype(np.float32)
    seno = np.stack([x, x], axis=1)
    assert abs(sonido.lufs(seno) - (-20.0)) < 0.05          # valor de referencia medido con ffmpeg ebur128
    n = sonido.normalizar(seno)
    assert abs(sonido.lufs(n) - (-14.0)) < 0.2 and abs(n).max() <= 0.8911


@pytest.mark.parametrize("estilo, color", [("pizarra", "#1fbf6a"), ("cuaderno", "#2f5bd3")])
def test_estilos(tmp_path, estilo, color):
    spec, _ = compilar(EJEMPLO, json.loads((SKILL / "scripts" / "lexico.json").read_text(encoding="utf-8")))
    d = tmp_path / "t01"; escribir_salidas(d, spec); generar(d)
    subprocess.run([sys.executable, str(SKILL / "scripts" / "engine.py"), str(d), estilo], check=True,
                   capture_output=True, env={**os.environ, "S2S_DATOS": str(tmp_path / "datos")})
    html = (d / "index.html").read_text(encoding="utf-8")
    assert f'stroke="{color}"' in html                                   # el camino toma el color del estilo
    assert ("#f6f1e3" in html) == (estilo == "cuaderno")                 # papel solo en cuaderno
