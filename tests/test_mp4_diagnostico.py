"""s2s.py diagnostico (con dependencias simuladas) y s2s.py mp4 (sin ffmpeg ni Playwright, salvo el último test)."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import diagnostico
import mp4
import pytest
import s2s
from compile import compilar
from config import CFG
from conftest import SKILL
from datos import EJEMPLO
from etapas import escribir_salidas
from voz_falsa import generar

# cada paquete de requirements.txt instalado justo en su versión mínima (sigue a requirements.txt si cambia)
VERSIONES = {paquete: minimo or "1.0" for paquete, minimo in diagnostico.requisitos()}
VERSIONES["pypdf"] = "4.3.1"


@pytest.fixture
def todo_instalado(tmp_path, monkeypatch):
    """Una computadora con todo: los archivos de datos en tmp_path y las dependencias simuladas."""
    voces = {}
    for nombre in ("davefx", "hfc_male"):
        m = tmp_path / "voces" / f"{nombre}.onnx"
        m.parent.mkdir(parents=True, exist_ok=True)
        m.write_bytes(b"x"); Path(str(m) + ".json").write_text("{}", encoding="utf-8")
        voces[nombre] = m
    (tmp_path / "gsap.min.js").write_text("//", encoding="utf-8")
    (tmp_path / "katex").mkdir(); (tmp_path / "katex" / "katex.min.js").write_text("//", encoding="utf-8")
    monkeypatch.setitem(CFG, "voces", voces)
    monkeypatch.setitem(CFG, "gsap", tmp_path / "gsap.min.js")
    monkeypatch.setitem(CFG, "katex", tmp_path / "katex")
    monkeypatch.setattr(diagnostico, "version_python", lambda: (3, 12))
    monkeypatch.setattr(diagnostico, "version_de", VERSIONES.get)
    monkeypatch.setattr(diagnostico, "soundfile_con_mp3", lambda: True)
    monkeypatch.setattr(mp4, "hay_playwright", lambda: True)
    monkeypatch.setattr(mp4, "chromium_instalado", lambda: True)
    monkeypatch.setattr(mp4, "ffmpeg", lambda: "/usr/bin/ffmpeg")
    return tmp_path


def _lineas(capsys):
    return capsys.readouterr().out.splitlines()


def _linea(lineas, nombre):
    return next(x for x in lineas if x.strip().startswith(nombre))


def test_requisitos_lee_requirements_txt():
    assert ("numpy", "1.24") in diagnostico.requisitos() and ("piper-tts", "1.3") in diagnostico.requisitos()


def test_diagnostico_todo_ok(todo_instalado, capsys):
    assert s2s.main(["diagnostico"]) == 0                               # no pide -t
    lineas = _lineas(capsys)
    for nombre in ["python 3.12", *VERSIONES, "voz es (davefx)", "voz en (hfc_male)", "gsap", "katex",
                   "playwright", "chromium (playwright)", "ffmpeg"]:
        assert _linea(lineas, nombre).endswith("  ok"), nombre
    assert lineas[-1] == "todo lo necesario está instalado"


def test_diagnostico_dice_como_arreglar_cada_cosa(todo_instalado, monkeypatch, capsys):
    monkeypatch.setattr(diagnostico, "version_python", lambda: (3, 9))
    monkeypatch.setattr(diagnostico, "version_de", {**VERSIONES, "numpy": None, "pypdf": "3.9.0"}.get)
    monkeypatch.setattr(diagnostico, "soundfile_con_mp3", lambda: False)
    for voz in CFG["voces"].values():
        voz.unlink()
    CFG["gsap"].unlink()
    monkeypatch.setattr(mp4, "hay_playwright", lambda: False)
    monkeypatch.setattr(mp4, "ffmpeg", lambda: None)
    assert s2s.main(["diagnostico"]) == 1
    lineas = _lineas(capsys)
    assert "Python 3.10 o más nuevo" in _linea(lineas, "python 3.9")
    assert "no está instalado" in _linea(lineas, "numpy") and "-m pip install -r" in _linea(lineas, "numpy")
    assert "tenés 3.9.0 y hace falta 4.0" in _linea(lineas, "pypdf") and 'pypdf>=4.0' in _linea(lineas, "pypdf")
    assert "MP3" in _linea(lineas, "soundfile")
    assert "instalar --idioma es" in _linea(lineas, "voz es") and "(opcional" not in _linea(lineas, "voz es")
    assert "instalar --idioma en" in _linea(lineas, "voz en")
    assert "instalar" in _linea(lineas, "gsap") and _linea(lineas, "katex").endswith("  ok")
    assert "(opcional, para s2s.py mp4)" in _linea(lineas, "playwright") and "pip install playwright" in _linea(lineas, "playwright")
    assert "playwright install chromium" in _linea(lineas, "chromium")
    assert mp4.como_instalar_ffmpeg() in _linea(lineas, "ffmpeg")
    falta = lineas[-1]
    assert falta.startswith("falta arreglar:") and "gsap" in falta and "playwright" not in falta and "ffmpeg" not in falta


def test_diagnostico_con_una_sola_voz_y_sin_opcionales_sale_bien(todo_instalado, monkeypatch, capsys):
    CFG["voces"]["hfc_male"].unlink()
    monkeypatch.setattr(mp4, "hay_playwright", lambda: False)
    monkeypatch.setattr(mp4, "ffmpeg", lambda: None)
    assert s2s.main(["diagnostico"]) == 0
    lineas = _lineas(capsys)
    assert "(opcional, solo para videos con --idioma en)" in _linea(lineas, "voz en")
    assert _linea(lineas, "voz es").endswith("  ok")


@pytest.mark.parametrize("sistema, comando", [("win32", "winget install"), ("darwin", "brew install ffmpeg"),
                                               ("linux", "apt install ffmpeg")])
def test_como_instalar_ffmpeg_segun_el_sistema(monkeypatch, sistema, comando):
    monkeypatch.setattr(mp4.sys, "platform", sistema)
    assert comando in mp4.como_instalar_ffmpeg()


# ---------------------------------------------------------------------------
# s2s.py mp4
# ---------------------------------------------------------------------------

def _videos(t, *temas):
    (t / "videos").mkdir(parents=True)
    (t / "videos" / "index.html").write_text("lista", encoding="utf-8")
    for x in temas:
        (t / "videos" / f"{x}.html").write_text(x, encoding="utf-8")


def _registro(t):
    return [json.loads(x) for x in (t / "registro.jsonl").read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("sin", ["playwright", "ffmpeg"])
def test_mp4_sin_dependencias_dice_como_instalarlas(tmp_path, monkeypatch, capsys, sin):
    t = tmp_path / "trabajo"; _videos(t, "t01")
    monkeypatch.setattr(mp4, "hay_playwright", lambda: sin != "playwright")
    monkeypatch.setattr(mp4, "chromium_instalado", lambda: True)
    monkeypatch.setattr(mp4, "ffmpeg", lambda: None if sin == "ffmpeg" else "/usr/bin/ffmpeg")
    monkeypatch.setattr(mp4, "exportar", lambda *a, **k: pytest.fail("no tenía que exportar"))
    assert s2s.main(["mp4", "-t", str(t)]) == 1
    out = capsys.readouterr().out
    if sin == "playwright":
        assert "-m pip install playwright" in out and "-m playwright install chromium" in out and "ffmpeg" not in out
    else:
        assert mp4.como_instalar_ffmpeg() in out and "playwright" not in out
    assert not (t / "mp4").exists()                                     # no deja nada a medias
    assert _registro(t)[-1]["cmd"] == "mp4" and _registro(t)[-1]["faltan"]


def test_mp4_saltea_los_que_estan_al_dia(tmp_path, monkeypatch, capsys):
    t = tmp_path / "trabajo"; _videos(t, "t01", "t02")
    hechos = []

    def exportar(video, salida, fps=30, alto=1280):
        hechos.append((video.name, salida.relative_to(t).as_posix(), alto))
        salida.parent.mkdir(parents=True, exist_ok=True); salida.write_bytes(b"mp4")
        return 1
    monkeypatch.setattr(mp4, "faltantes", lambda: [])
    monkeypatch.setattr(mp4, "exportar", exportar)

    assert s2s.main(["mp4", "-t", str(t), "--alto", "960"]) == 0
    assert hechos == [("t01.html", "mp4/t01.mp4", 960), ("t02.html", "mp4/t02.mp4", 960)]   # index.html no

    hechos.clear()
    assert s2s.main(["mp4", "-t", str(t)]) == 0
    assert hechos == [] and "al día" in capsys.readouterr().out

    futuro = time.time() + 60                                           # rehice el video de t02
    os.utime(t / "videos" / "t02.html", (futuro, futuro))
    assert s2s.main(["mp4", "-t", str(t)]) == 0
    assert [h[0] for h in hechos] == ["t02.html"]

    hechos.clear()
    assert s2s.main(["mp4", "-t", str(t), "--tema", "t01", "--todo"]) == 0
    assert [h[0] for h in hechos] == ["t01.html"]

    reg = [r for r in _registro(t) if r["cmd"] == "mp4"]
    assert [(r["hechos"], r["al_dia"]) for r in reg] == [(2, 0), (0, 2), (1, 1), (1, 0)]
    assert reg[0]["alto"] == 960


def test_mp4_sin_videos_o_tema_que_no_existe(tmp_path, capsys):
    t = tmp_path / "trabajo"
    assert s2s.main(["mp4", "-t", str(t)]) == 1
    _videos(t, "t01")
    assert s2s.main(["mp4", "-t", str(t), "--tema", "t09"]) == 1
    assert "s2s.py video" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        s2s.main(["mp4", "-t", str(t), "--alto", "50"])


def test_tools_mp4_es_un_envoltorio():
    r = subprocess.run([sys.executable, str(SKILL.parents[1] / "tools" / "mp4.py"), "--help"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "--alto" in r.stdout


# ---------------------------------------------------------------------------
# De punta a punta: solo donde hay ffmpeg, Playwright con Chromium y gsap (no en CI)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(mp4.ffmpeg() is None or not mp4.hay_playwright(), reason="sin ffmpeg o sin Playwright")
def test_mp4_de_punta_a_punta(tmp_path):
    if not mp4.chromium_instalado():
        pytest.skip("Playwright sin Chromium")
    if not Path(CFG["gsap"]).exists():
        pytest.skip("sin gsap: s2s.py instalar")
    import reproductor
    t = tmp_path / "trabajo"; d = t / "t01"
    spec, rep = compilar(EJEMPLO, json.loads((SKILL / "scripts" / "lexico.json").read_text(encoding="utf-8")))
    assert rep.errores == []
    escribir_salidas(d, spec)
    dur = generar(d)
    subprocess.run([sys.executable, str(SKILL / "scripts" / "engine.py"), str(d)], check=True, capture_output=True)
    reproductor.construir(d, t / "videos" / "t01.html", "La FK de multa")
    assert s2s.main(["mp4", "-t", str(t), "--alto", "640"]) == 0
    salida = (t / "mp4" / "t01.mp4").read_bytes()
    assert salida[4:8] == b"ftyp" and len(salida) > 10_000
    assert not list((t / "mp4").glob("*.parcial.mp4"))
    if shutil.which("ffprobe"):
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height",
                            "-show_entries", "format=duration", "-of", "json", str(t / "mp4" / "t01.mp4")],
                           capture_output=True, text=True, encoding="utf-8", check=True)
        info = json.loads(r.stdout)
        assert {s["codec_name"] for s in info["streams"]} == {"h264", "aac"}
        assert any(s.get("width") == 360 and s.get("height") == 640 for s in info["streams"])
        assert abs(float(info["format"]["duration"]) - dur) < 0.5
