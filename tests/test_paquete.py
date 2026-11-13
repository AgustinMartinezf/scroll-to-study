"""s2s.py paquete (los videos en un .s2s.json para la app del teléfono) y su validación del lado de la
app (web/paquete.js, probado con node, suelto). Sin Piper ni red: los videos son html de juguete."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import paquete
import s2s
from datos import TEMAS

RAIZ = Path(__file__).resolve().parents[1]
PAQUETE_JS = RAIZ / "web" / "paquete.js"
NODE = shutil.which("node")
if NODE is None and os.environ.get("S2S_EXIGIR_NAVEGADOR") == "1":   # el job "web" del CI no los saltea
    raise RuntimeError("node no está instalado")
con_node = pytest.mark.skipif(NODE is None, reason="node no está instalado")

VIDEO = "<!doctype html>\n<html lang=\"es\"><head><title>{t}</title></head><body>{t}</body></html>"


def trabajo(tmp_path, titulo_lista="Bases de datos & co"):
    """t01 y t03 tienen video; t02 no. temas.json los pone en el orden t03, t01, t02."""
    t = tmp_path / "trabajo"
    temas = [{"id": "t03", "titulo": "Índices", "pregunta": "¿Para qué sirve un índice?", "afirmaciones": ["A1"]},
             *TEMAS["temas"]]
    (t / "videos").mkdir(parents=True)
    (t / "temas.json").write_text(json.dumps({"temas": temas}, ensure_ascii=False), encoding="utf-8")
    (t / "origen.json").write_text(json.dumps({"idioma": "es", "modo": "proyecto"}), encoding="utf-8")
    for tid, dur in (("t01", 41.26), ("t03", 33.0)):
        (t / "videos" / f"{tid}.html").write_text(VIDEO.format(t=tid), encoding="utf-8")
        (t / tid).mkdir()
        (t / tid / "timing.json").write_text(json.dumps({"duration": dur}), encoding="utf-8")
    if titulo_lista:
        (t / "videos" / "index.html").write_text(
            f"<!doctype html><html><head><title>{titulo_lista.replace('&', '&amp;')}</title></head></html>", encoding="utf-8")
    return t


def test_paquete_en_el_orden_de_temas_y_avisa_lo_que_falta(tmp_path, capsys):
    t = trabajo(tmp_path)
    assert s2s.main(["paquete", "-t", str(t)]) == 0
    salida = capsys.readouterr().out
    archivo = t / "Bases-de-datos-&-co.s2s.json"        # el título de la lista, sin espacios
    p = json.loads(archivo.read_text(encoding="utf-8"))
    assert set(p) == {"v", "titulo", "idioma", "generado", "videos"}
    assert p["v"] == 1 and p["titulo"] == "Bases de datos & co" and p["idioma"] == "es"
    assert "T" in p["generado"] and p["generado"].endswith("+00:00")
    assert [x["id"] for x in p["videos"]] == ["t03", "t01"]
    assert p["videos"][1] == {"id": "t01", "titulo": "La FK de multa", "duracion": 41.3, "html": VIDEO.format(t="t01"),
                              "pregunta": "¿Cómo garantizan que una multa sea de un préstamo real?"}
    # avisa el tamaño final y el tema sin video
    assert "2 videos" in salida and str(archivo) in salida and "KB)" in salida
    assert "AVISO" in salida and "t02" in salida
    registro = [json.loads(x) for x in (t / "registro.jsonl").read_text(encoding="utf-8").splitlines()]
    assert registro[-1]["cmd"] == "paquete" and registro[-1]["videos"] == 2 and registro[-1]["sin_video"] == ["t02"]
    assert registro[-1]["bytes"] == archivo.stat().st_size


def test_titulo_explicito_e_idioma_del_trabajo(tmp_path, capsys):
    t = trabajo(tmp_path, titulo_lista=None)
    (t / "origen.json").write_text(json.dumps({"idioma": "en"}), encoding="utf-8")
    assert s2s.main(["paquete", "-t", str(t), "--titulo", "Networks: midterm / 2"]) == 0
    p = json.loads((t / "Networks-midterm-2.s2s.json").read_text(encoding="utf-8"))
    assert p["titulo"] == "Networks: midterm / 2" and p["idioma"] == "en"
    # sin --titulo ni lista, el título por defecto del idioma
    (t / "Networks-midterm-2.s2s.json").unlink()
    assert s2s.main(["paquete", "-t", str(t)]) == 0
    assert (t / "Study-playlist.s2s.json").exists()


def test_sin_videos_no_escribe_nada(tmp_path, capsys):
    t = trabajo(tmp_path)
    shutil.rmtree(t / "videos")
    assert s2s.main(["paquete", "-t", str(t)]) == 1
    assert "no hay videos" in capsys.readouterr().out
    assert not list(t.glob("*.s2s.json"))
    assert json.loads((t / "registro.jsonl").read_text(encoding="utf-8").splitlines()[-1])["error"] == "sin videos"


def test_sin_timing_va_con_duracion_cero_y_avisa(tmp_path, capsys):
    t = trabajo(tmp_path)
    (t / "t03" / "timing.json").unlink()
    assert s2s.main(["paquete", "-t", str(t)]) == 0
    assert "duración 0: t03" in capsys.readouterr().out


@pytest.mark.parametrize("titulo, nombre", [
    ("Redes 2026: parcial", "Redes-2026-parcial.s2s.json"),
    ("  a  b\tc ", "a-b-c.s2s.json"),
    ('<>:"/\\|?*', "videos.s2s.json"),
    ("Álgebra lineal", "Álgebra-lineal.s2s.json"),
])
def test_nombre_de_archivo(titulo, nombre):
    assert paquete.nombre_archivo(titulo) == nombre


# --- web/paquete.js con node -----------------------------------------------------------------------

def validar_js(paquetes):
    """Corre Paquete.validar sobre cada paquete (o Paquete.leer si es un texto) y devuelve los resultados."""
    prog = (f"const PQ = require({json.dumps(str(PAQUETE_JS))});\n"
            "let datos = ''; process.stdin.on('data', d => datos += d).on('end', () => {\n"
            "  const r = JSON.parse(datos).map(x => typeof x === 'string' ? PQ.leer(x).error || null : PQ.validar(x));\n"
            "  console.log(JSON.stringify(r)); });\n")
    r = subprocess.run([NODE, "-e", prog], input=json.dumps(paquetes), capture_output=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@con_node
def test_el_paquete_que_arma_python_lo_acepta_la_app(tmp_path, capsys):
    t = trabajo(tmp_path)
    s2s.main(["paquete", "-t", str(t)])
    texto = next(t.glob("*.s2s.json")).read_text(encoding="utf-8")
    assert validar_js([json.loads(texto), texto]) == [None, None]


@con_node
def test_la_app_rechaza_lo_que_no_es_un_paquete():
    bueno = {"v": 1, "titulo": "Redes", "idioma": "es", "generado": "2026-11-13T10:00:00+00:00",
             "videos": [{"id": "t01", "titulo": "Uno", "pregunta": "", "duracion": 30, "html": VIDEO.format(t="x")}]}

    def con(**cambios):
        return {**bueno, **cambios}

    def video(**cambios):
        return con(videos=[{**bueno["videos"][0], **cambios}])

    casos = [
        bueno, "no es json", "[1, 2]", [], None, {"titulo": "x"},
        con(v=2), con(v="1"), con(titulo=""), con(titulo=3), con(idioma="fr"), con(generado="ayer"),
        con(videos={}), con(videos=[]),
        video(id=""), video(id="../x"), video(titulo=None), video(pregunta=None), video(duracion="30"),
        video(duracion=-1), video(html="hola"), video(html=None),
        con(videos=bueno["videos"] * 2),
    ]
    r = validar_js(casos)
    assert r[0] is None
    codigos = [(x["codigo"], x["campo"]) for x in r[1:]]
    assert codigos == [
        ("no_es_json", ""), ("no_es_paquete", ""), ("no_es_paquete", ""), ("no_es_paquete", ""), ("no_es_paquete", ""),
        ("version", "2"), ("version", "1"), ("campo", "titulo"), ("campo", "titulo"), ("campo", "idioma"),
        ("campo", "generado"),
        ("campo", "videos"), ("vacio", ""),
        ("campo", "videos[0].id"), ("campo", "videos[0].id"), ("campo", "videos[0].titulo"),
        ("campo", "videos[0].pregunta"), ("campo", "videos[0].duracion"), ("campo", "videos[0].duracion"),
        ("campo", "videos[0].html"), ("campo", "videos[0].html"),
        ("repetido", "t01"),
    ]
