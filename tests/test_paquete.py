"""s2s.py paquete (los videos en un .s2s.json para la app del teléfono) y su validación del lado de la
app (web/paquete.js, probado con node, suelto). Sin Piper ni red: los videos son html de juguete."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import etapas
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
# como las escribe Claude en T/tNN/preguntas.json (con "fuentes"); al paquete van sin fuentes y con "general"
PREGUNTAS = {"preguntas": [
    {"id": "q1", "texto": "¿A qué tabla apunta la FK de multa?", "opciones": ["A socio", "A prestamo", "A ejemplar"],
     "correcta": 1, "explicacion": "Apunta a prestamo.", "fuentes": ["A1"]},
    {"id": "q2", "texto": "¿Cómo se ubica una FK?", "opciones": ["Por el nombre", "Por la dependencia", "Al azar"],
     "correcta": 1, "explicacion": "Método general, no está en tu material: por la dependencia.", "fuentes": ["A1", "G1"]},
]}


def con_preguntas(t, tid, datos=PREGUNTAS, errores=()):
    """Escribe T/tid/preguntas.json y el reporte que deja s2s.py preguntas al validarlo."""
    (t / tid).mkdir(exist_ok=True)
    archivo = t / tid / "preguntas.json"
    archivo.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    (t / tid / "preguntas_reporte.json").write_text(json.dumps(
        {"errores": list(errores), "avisos": [], "intentos": 1, "huella": etapas.huella(archivo)}), encoding="utf-8")
    return archivo


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
    assert p["v"] == 2 and p["titulo"] == "Bases de datos & co" and p["idioma"] == "es"
    assert "T" in p["generado"] and p["generado"].endswith("+00:00")
    assert [x["id"] for x in p["videos"]] == ["t03", "t01"]
    assert p["videos"][1] == {"id": "t01", "titulo": "La FK de multa", "duracion": 41.3, "html": VIDEO.format(t="t01"),
                              "pregunta": "¿Cómo garantizan que una multa sea de un préstamo real?", "preguntas": []}
    # avisa el tamaño final, el tema sin video y los que van sin preguntas
    assert "2 videos" in salida and str(archivo) in salida and "KB)" in salida
    assert "AVISO  temas sin video (no van en el paquete): t02" in salida
    assert "AVISO  temas sin preguntas (van sin preguntas): t03, t01" in salida
    registro = [json.loads(x) for x in (t / "registro.jsonl").read_text(encoding="utf-8").splitlines()]
    assert registro[-1]["cmd"] == "paquete" and registro[-1]["videos"] == 2 and registro[-1]["sin_video"] == ["t02"]
    assert registro[-1]["bytes"] == archivo.stat().st_size
    assert registro[-1]["sin_preguntas"] == ["t01", "t03"]


def test_paquete_v2_lleva_las_preguntas_validadas_y_marca_las_generales(tmp_path, capsys):
    t = trabajo(tmp_path)
    (t / "inventario.json").write_text(json.dumps({"afirmaciones": [
        {"id": "A1", "estado": "ok", "texto": "La FK de multa apunta a prestamo."},
        {"id": "G1", "estado": "general", "origen": "general", "texto": "Para ubicar una FK, buscá la dependencia."},
    ]}), encoding="utf-8")
    con_preguntas(t, "t01")
    assert s2s.main(["paquete", "-t", str(t)]) == 0
    salida = capsys.readouterr().out
    p = json.loads(next(t.glob("*.s2s.json")).read_text(encoding="utf-8"))
    t01 = next(x for x in p["videos"] if x["id"] == "t01")
    assert t01["preguntas"] == [
        {"id": "q1", "texto": "¿A qué tabla apunta la FK de multa?", "opciones": ["A socio", "A prestamo", "A ejemplar"],
         "correcta": 1, "explicacion": "Apunta a prestamo.", "general": False},
        {"id": "q2", "texto": "¿Cómo se ubica una FK?", "opciones": ["Por el nombre", "Por la dependencia", "Al azar"],
         "correcta": 1, "explicacion": "Método general, no está en tu material: por la dependencia.", "general": True},
    ]
    assert "temas sin preguntas (van sin preguntas): t03" in salida and "t01:" not in salida


@pytest.mark.parametrize("arruinar, aviso", [
    # se editó preguntas.json después de validarlo: la huella del reporte es de otra versión
    (lambda a: a.write_text(a.read_text(encoding="utf-8").replace("Apunta", "Va"), encoding="utf-8"),
     "t01: preguntas.json no se validó o cambió después de validarlo; va sin preguntas"),
    (lambda a: (a.parent / "preguntas_reporte.json").unlink(),
     "t01: preguntas.json no se validó o cambió después de validarlo; va sin preguntas"),
    (lambda a: con_preguntas(a.parent.parent, "t01", errores=["pregunta q1: sin fuentes"]),
     "t01: preguntas.json tiene errores; va sin preguntas"),
])
def test_preguntas_sin_validar_no_viajan_y_se_avisa(tmp_path, capsys, arruinar, aviso):
    t = trabajo(tmp_path)
    arruinar(con_preguntas(t, "t01"))
    assert s2s.main(["paquete", "-t", str(t)]) == 0
    salida = capsys.readouterr().out
    p = json.loads(next(t.glob("*.s2s.json")).read_text(encoding="utf-8"))
    assert [x["preguntas"] for x in p["videos"]] == [[], []]
    assert f"AVISO  {aviso} (corré s2s.py preguntas -t {t} --tema t01)" in salida
    registro = json.loads((t / "registro.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert registro["sin_preguntas"] == ["t01", "t03"]


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
    con_preguntas(t, "t01")
    s2s.main(["paquete", "-t", str(t)])
    texto = next(t.glob("*.s2s.json")).read_text(encoding="utf-8")
    assert json.loads(texto)["v"] == 2 and json.loads(texto)["videos"][1]["preguntas"]
    assert validar_js([json.loads(texto), texto]) == [None, None]


def metadatos_js(paquetes):
    prog = (f"const PQ = require({json.dumps(str(PAQUETE_JS))});\n"
            "let datos = ''; process.stdin.on('data', d => datos += d).on('end', () => {\n"
            "  console.log(JSON.stringify(JSON.parse(datos).map(d => PQ.metadatos(d, 'ahora')))); });\n")
    r = subprocess.run([NODE, "-e", prog], input=json.dumps(paquetes), capture_output=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


PREGUNTA_APP = {"id": "q1", "texto": "¿Qué?", "opciones": ["a", "b", "c"], "correcta": 2, "explicacion": "Porque c.",
                "general": False}
V1 = {"v": 1, "titulo": "Redes", "idioma": "es", "generado": "2026-11-13T10:00:00+00:00",
      "videos": [{"id": "t01", "titulo": "Uno", "pregunta": "", "duracion": 30, "html": VIDEO.format(t="x")}]}
V2 = {**V1, "v": 2, "videos": [{**V1["videos"][0], "preguntas": [PREGUNTA_APP]}]}


@con_node
def test_la_app_acepta_v1_sin_preguntas_y_v2_con_preguntas():
    assert validar_js([V1, V2, {**V2, "videos": [{**V2["videos"][0], "preguntas": []}]}]) == [None, None, None]
    m1, m2 = metadatos_js([V1, V2])
    assert m1["videos"][0]["preguntas"] == []                 # v1 se lee como si no tuviera preguntas
    assert m2["videos"][0]["preguntas"] == [PREGUNTA_APP]
    assert "html" not in m2["videos"][0] and m2["importado"] == "ahora"


@con_node
def test_la_app_rechaza_preguntas_mal_armadas():
    def pregunta(**cambios):
        return {**V2, "videos": [{**V2["videos"][0], "preguntas": [{**PREGUNTA_APP, **cambios}]}]}

    sin = {**V2, "videos": [{k: v for k, v in V2["videos"][0].items() if k != "preguntas"}]}
    casos = [sin, {**V2, "videos": [{**V2["videos"][0], "preguntas": {}}]},
             {**V2, "videos": [{**V2["videos"][0], "preguntas": [PREGUNTA_APP] * 11}]},
             {**V2, "videos": [{**V2["videos"][0], "preguntas": [PREGUNTA_APP, "x"]}]},
             pregunta(id=1), pregunta(texto=" "), pregunta(opciones=["a"]), pregunta(opciones=["a", ""]),
             pregunta(opciones="abc"), pregunta(correcta=3), pregunta(correcta=-1), pregunta(correcta=1.5),
             pregunta(correcta="2"), pregunta(explicacion=None), pregunta(general="no")]
    assert [(x["codigo"], x["campo"]) for x in validar_js(casos)] == [
        ("campo", "videos[0].preguntas"), ("campo", "videos[0].preguntas"), ("campo", "videos[0].preguntas"),
        ("campo", "videos[0].preguntas[1]"),
        ("campo", "videos[0].preguntas[0].id"), ("campo", "videos[0].preguntas[0].texto"),
        ("campo", "videos[0].preguntas[0].opciones"), ("campo", "videos[0].preguntas[0].opciones"),
        ("campo", "videos[0].preguntas[0].opciones"), ("campo", "videos[0].preguntas[0].correcta"),
        ("campo", "videos[0].preguntas[0].correcta"), ("campo", "videos[0].preguntas[0].correcta"),
        ("campo", "videos[0].preguntas[0].correcta"), ("campo", "videos[0].preguntas[0].explicacion"),
        ("campo", "videos[0].preguntas[0].general"),
    ]


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
        con(v=3), con(v="1"), con(titulo=""), con(titulo=3), con(idioma="fr"), con(generado="ayer"),
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
        ("version", "3"), ("version", "1"), ("campo", "titulo"), ("campo", "titulo"), ("campo", "idioma"),
        ("campo", "generado"),
        ("campo", "videos"), ("vacio", ""),
        ("campo", "videos[0].id"), ("campo", "videos[0].id"), ("campo", "videos[0].titulo"),
        ("campo", "videos[0].pregunta"), ("campo", "videos[0].duracion"), ("campo", "videos[0].duracion"),
        ("campo", "videos[0].html"), ("campo", "videos[0].html"),
        ("repetido", "t01"),
    ]
