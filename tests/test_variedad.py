"""Que los videos no salgan todos iguales ni con el sesgo de Bases de Datos con el que nació la herramienta."""
import json
import os
import re
import subprocess
import sys

import pytest
from compile import compilar
from conftest import SKILL
from etapas import FORMATOS, IDIOMAS, ejemplo_guion, escribir_salidas, iconos_de, validar_guion
from voz_falsa import generar

LEX = json.loads((SKILL / "scripts" / "lexico.json").read_text(encoding="utf-8"))
EJEMPLOS = [(f, i) for f in FORMATOS for i in IDIOMAS]


def test_un_ejemplo_por_formato_e_idioma():
    carpeta = SKILL / "prompts" / "ejemplos"
    assert sorted(p.name for p in carpeta.glob("*.json")) == sorted(f"{f}.{i}.json" for f, i in EJEMPLOS)
    assert not list((SKILL / "prompts").glob("*.json"))      # ya no hay ejemplos sueltos que Claude copie


@pytest.mark.parametrize("formato, idioma", EJEMPLOS)
def test_los_ejemplos_validan_sin_errores(formato, idioma):
    """Con el mismo validador que s2s.py guion: fuentes contra un inventario, íconos permitidos, léxico."""
    g = json.loads((SKILL / ejemplo_guion(formato, idioma)).read_text(encoding="utf-8"))
    fuentes = {f for b in g["bloques"] for f in b["fuentes"]}
    assert fuentes and all(re.fullmatch(r"A\d+", f) for f in fuentes)
    inv = {"afirmaciones": [{"id": f, "texto": "", "cita": "", "estado": "ok"} for f in sorted(fuentes)]}
    spec, errores, avisos = validar_guion(g, inv, idioma, "materia")
    assert errores == []
    # sin avisos de forma (duración, pronunciación, clímax); los de identificadores salen porque el
    # inventario de acá no tiene textos
    assert [a for a in avisos if "no aparecen en sus fuentes" not in a] == []
    assert any(e[1] == "boom" for e in spec["EVENTS"])
    tipos = {e["type"] for b in g["bloques"] for e in b["elementos"]}
    acciones = {e[1] for e in spec["EVENTS"]}
    if formato != "historia":                                 # solo el de la biblioteca es de Bases de Datos
        assert "table" not in tipos
        assert not {"database", "table"} & {ic for b in g["bloques"] for e in b["elementos"] for ic in iconos_de(e)}
    requisitos = {"pregunta": {"flow", "countdown"} <= tipos and "send" in acciones,
                  "avsb": bool({"formula", "venn"} & tipos),
                  "pasos": bool({"console", "list"} & tipos)}
    assert requisitos.get(formato, True)


def _cabeceras(html: str, elemento_id: str) -> str:
    """El html de la cabecera (div chead / lhead) del elemento con ese id."""
    m = re.search(rf'id="{elemento_id}"[^>]*>(<div class="(?:chead|lhead)".*?</div>)', html)
    assert m, f"no encontré la cabecera de {elemento_id}"
    return m[1]


def test_sin_icon_no_hay_icono_por_defecto(tmp_path):
    guion = {
        "bloques": [{"fuentes": ["A1"], "comprobar": [], "elementos": [
            {"type": "table", "id": "k", "title": "claves", "cols": ["clave", "firma"], "rows": [["KSK", "ZSK"]]},
            {"type": "list", "id": "l", "title": "pasos", "items": [["l1", "uno"]]},
            {"type": "chart", "id": "g", "title": "tiempos", "bars": [["a", 1], ["b", 2]]},
            {"type": "venn", "id": "v", "title": "conjuntos", "sets": ["A", "B"]},
            {"type": "table", "id": "c", "title": "con ícono", "icon": "key", "cols": ["a"], "rows": [["1"]]}],
            "frases": ["La {show k}tabla, la {show l}lista, el {show g}gráfico y el {show v}diagrama.",
                       "Y una {show c}tabla con ícono."]}],
        "final": {"frases": ["Acordate: {show fl1}uno.", "{show fnext}Mañana: dos."], "lineas": ["uno"], "mañana": "dos"},
    }
    spec, rep = compilar(guion, LEX, SKILL / "scripts" / "iconos")
    assert rep.errores == []
    d = tmp_path / "t01"
    escribir_salidas(d, spec)
    generar(d)
    subprocess.run([sys.executable, str(SKILL / "scripts" / "engine.py"), str(d)], check=True,
                   capture_output=True, env={**os.environ, "S2S_DATOS": str(tmp_path / "datos")})
    html = (d / "index.html").read_text(encoding="utf-8")
    for i in ("k", "l", "g", "v"):
        cabeza = _cabeceras(html, i)
        assert "<svg" not in cabeza and "<span>" in cabeza     # el título solo
    assert "<svg" in _cabeceras(html, "c")                     # con «icon», el ícono sigue


# ---------------------------------------------------------------------------
# un trabajo de Redes armado a mano (lo que dejarían corpus, verificar y temas)
# ---------------------------------------------------------------------------

REDES = [
    {"id": "A1", "tipo": "definicion", "texto": "TCP abre una conexión con tres mensajes: SYN, SYN-ACK y ACK.",
     "fuente": "redes.txt:1", "cita": "SYN, SYN-ACK y ACK", "estado": "ok", "motivos": []},
    {"id": "A2", "tipo": "propiedad", "texto": "El cliente manda SYN con su número de secuencia inicial.",
     "fuente": "redes.txt:2", "cita": "SYN con su número de secuencia inicial", "estado": "ok", "motivos": []},
    {"id": "A3", "tipo": "propiedad", "texto": "El servidor responde SYN-ACK y el cliente confirma con ACK.",
     "fuente": "redes.txt:3", "cita": "responde SYN-ACK", "estado": "ok", "motivos": []},
]


def guion_redes(icono="database"):
    servidor = {"id": "srv", "text": "servidor"}
    if icono:
        servidor["icon"] = icono
    return {
        "bloques": [{"fuentes": ["A1", "A2"], "comprobar": [], "elementos": [
            {"type": "flow", "id": "hs", "items": [{"id": "cli", "text": "cliente", "icon": "users"}, servidor]}],
            "frases": ["¿Cómo {show hs}arranca una conexión TCP? Con tres {send hs de=cli a=srv texto=SYN}mensajes.",
                       "El servidor {send hs de=srv a=cli texto=SYN-ACK}responde, y el cliente {send hs de=cli a=srv texto=ACK}confirma."]},
            {"fuentes": ["A3"], "comprobar": [], "elementos": [{"type": "big", "id": "b", "text": "3 mensajes"}],
             "frases": ["Son {show b}{boom b +0.2}[+tres] mensajes."]}],
        "final": {"frases": ["Para el examen, [+acordate]: {show fl1}tres mensajes.", "{show fnext}Mañana: ventanas de TCP."],
                  "lineas": ["<b>SYN, SYN-ACK, ACK</b>"], "mañana": "ventanas de TCP"},
        "lexico": {"syn": "sin", "syn-ack": "sin~ac", "ack": "ac", "tcp": "te~ce~pe"},
    }


def trabajo(tmp_path, afirmaciones=REDES, temas=None):
    import etapas
    t = tmp_path / "trabajo"
    etapas.escribir(t / "origen.json", {"modo": "materia", "idioma": "es", "estilo": "cuaderno"})
    etapas.escribir(t / "inventario.json", {"afirmaciones": afirmaciones})
    ids = [a["id"] for a in afirmaciones]
    etapas.escribir(t / "temas.json", {"temas": temas or [
        {"id": "t01", "titulo": "El saludo de TCP", "pregunta": "¿Por qué tres mensajes?", "afirmaciones": ids},
        {"id": "t02", "titulo": "Ventanas de TCP", "pregunta": "¿Qué es la ventana?", "afirmaciones": ids},
        {"id": "t03", "titulo": "Cierre de TCP", "pregunta": "¿Cómo se cierra?", "afirmaciones": ids}]})
    return t


def correr_guion(t, tema, guion, capsys):
    import s2s
    capsys.readouterr()
    (t / tema).mkdir(exist_ok=True)
    (t / tema / "guion.json").write_text(json.dumps(guion, ensure_ascii=False), encoding="utf-8")
    codigo = s2s.main(["guion", "-t", str(t), "--tema", tema])
    return codigo, capsys.readouterr().out


def test_icono_database_fuera_de_tema(tmp_path, capsys):
    t = trabajo(tmp_path)
    codigo, out = correr_guion(t, "t01", guion_redes("database"), capsys)
    assert codigo == 0                                        # es un aviso: el skill lo trata como error
    assert "AVISO      bloque 0 (flow hs): el ícono database no tiene que ver con este tema; sacalo o elegí otro" in out
    _, out = correr_guion(t, "t01", guion_redes("table"), capsys)
    assert "el ícono table no tiene que ver" in out
    _, out = correr_guion(t, "t01", guion_redes(None), capsys)
    assert "no tiene que ver" not in out


def test_icono_database_en_un_tema_de_bases_de_datos(tmp_path, capsys):
    bd = [dict(a) for a in REDES]
    bd[0]["texto"] = "La tabla conexion guarda los tres mensajes: SYN, SYN-ACK y ACK."
    codigo, out = correr_guion(trabajo(tmp_path, bd), "t01", guion_redes("database"), capsys)
    assert codigo == 0 and "no tiene que ver" not in out
