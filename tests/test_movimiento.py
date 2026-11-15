"""Que los videos no se vean todos iguales: entradas por tipo de elemento, transiciones entre escenas y
disposición por formato, decididas por el motor con una semilla estable.

Las pruebas con navegador usan Chromium con Playwright y gsap instalado; sin ellos se saltean, y con
S2S_EXIGIR_NAVEGADOR=1 fallan."""
import base64
import json
import os
from pathlib import Path

import pytest

import animacion
from config import CFG
from conftest import SKILL
from etapas import FORMATOS
from videos_prueba import FIXTURES, compilar_guion, estado, motor, video, video_de_formato

EXIGIR = os.environ.get("S2S_EXIGIR_NAVEGADOR") == "1"


# --- semilla y generador ----------------------------------------------------------------------

def test_fnv1a_y_mulberry32_son_estables():
    assert animacion.fnv1a("") == 0x811C9DC5 and animacion.fnv1a("a") == 0xE40C292C   # valores de referencia
    r1, r2 = animacion.Mulberry32(42), animacion.Mulberry32(42)
    a = [r1.siguiente() for _ in range(50)]
    assert a == [r2.siguiente() for _ in range(50)] and all(0 <= x < 1 for x in a) and len(set(a)) == 50


def test_la_misma_semilla_elige_lo_mismo_y_cada_tipo_tiene_de_3_a_5_entradas():
    assert animacion.elegir("t01\nRedes", "mito") == animacion.elegir("t01\nRedes", "mito")
    for tipo, ops in animacion.ENTRADAS.items():
        assert 3 <= len(ops) <= 5 and ops[0] == "escala", tipo
        assert "letras" not in ops or tipo in ("chip", "big", "toast"), tipo
        assert "cascada" not in ops or tipo in ("table", "list", "row", "arbol", "chart", "flow"), tipo
    assert 3 <= len(animacion.TRANSICIONES) <= 4


def test_cinco_temas_no_salen_todos_iguales():
    elegidos = [animacion.elegir(animacion.texto_semilla(f"t0{i}", "Redes")) for i in range(1, 6)]
    assert len({json.dumps([e["entradas"], e["transicion"]], sort_keys=True) for e in elegidos}) > 1
    assert len({e["transicion"] for e in elegidos}) > 1


def test_la_disposicion_sale_del_formato():
    assert {f: animacion.elegir("x", f)["disposicion"] for f in FORMATOS} == {
        "pregunta": "columna", "mito": "lados", "avsb": "partida", "pasos": "progreso", "historia": "grilla"}
    assert animacion.elegir("x")["disposicion"] == "zigzag"


# --- el motor ---------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def spec_movimiento():
    return compilar_guion(json.loads((FIXTURES / "guion_movimiento.json").read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def con_voz(tmp_path_factory, spec_movimiento):
    """Una carpeta con spec, timing y voz falsa del guion de movimiento (sin correr el motor)."""
    from etapas import escribir_salidas
    from voz_falsa import generar
    d = tmp_path_factory.mktemp("mov") / "t01"
    escribir_salidas(d, spec_movimiento)
    generar(d)
    return d


def test_mismo_tema_mismo_video_byte_a_byte(con_voz):
    a = motor(con_voz, "cuaderno", "t01\nRedes").read_bytes()
    b = motor(con_voz, "cuaderno", "t01\nRedes").read_bytes()
    assert a == b


def test_temas_distintos_dan_entradas_o_transiciones_distintas(con_voz):
    vistos = set()
    for i in range(1, 6):
        S = estado(motor(con_voz, "cuaderno", f"t0{i}\nRedes"))
        vistos.add(json.dumps([S["ENT"], S["TRANS"], S["LADO"]], sort_keys=True))
    assert len(vistos) > 1
    # y lo que dice animacion.json es lo que se usó
    S = estado(motor(con_voz, "cuaderno", "t03\nRedes"))
    anim = json.loads((con_voz / "animacion.json").read_text(encoding="utf-8"))
    assert anim["transicion"] == S["TRANS"]["1"]
    assert all(anim["entradas"].get(t) == e for t, e in
               {"chip": S["ENT"].get("c1", "escala"), "table": S["ENT"].get("tb", "escala")}.items())


def test_la_animacion_forzada_pisa_la_semilla(con_voz):
    S = estado(motor(con_voz, "cuaderno", "t01", animacion={"entrada": "cascada", "transicion": "zoom"}))
    assert S["ENT"] == {"tb": "cascada", "ls": "cascada", "rw": "cascada", "ch": "cascada", "fl": "cascada",
                        "ar": "cascada", "fcard": "cascada"}          # solo los tipos con partes la tienen
    assert set(S["TRANS"].values()) == {"zoom"}
    html = (con_voz / "index.html").read_text(encoding="utf-8")
    assert 'id="pth' not in html                                     # sin viaje no hay camino dibujado


@pytest.mark.parametrize("formato", sorted(FORMATOS))
def test_disposicion_de_cada_formato(tmp_path, formato):
    from videos_prueba import guion_de_formato
    from etapas import escribir_salidas
    from voz_falsa import generar
    spec = compilar_guion(guion_de_formato(formato))
    d = tmp_path / "t01"; escribir_salidas(d, spec); generar(d)
    S = estado(motor(d, "pizarra", "t01", formato))
    html = (d / "index.html").read_text(encoding="utf-8")
    cajas, nst = S["boxes"], S["nst"]
    if formato in ("pregunta", "pasos", "avsb"):           # una columna, con la escena siguiente fuera de cuadro
        assert {b["x"] for b in cajas} == {540}
        assert all(b["top"] - (a["top"] + a["h"]) >= 1100 for a, b in zip(cajas, cajas[1:]))
    if formato == "pregunta":                              # la cuenta regresiva, más cerca
        assert S["CERCA"] == [si for si, ids in enumerate(S["stEls"]) if "cd" in ids]
    if formato == "pasos":                                 # la línea de progreso avanza en cada paso
        assert 'id="progreso"' in html and len(S["PASOS"]) >= 2 and S["PASOS"] == sorted(S["PASOS"])
    else:
        assert 'id="progreso"' not in html and S["PASOS"] == []
    if formato == "mito":                                  # la idea equivocada a la izquierda, la correcta a su derecha
        assert cajas[0]["x"] == 540 and cajas[1]["x"] == 1800 and cajas[1]["top"] == cajas[0]["top"]
        assert S["TRANS"]["1"] == "paneo"
    if formato == "historia":                              # viñetas de 2 x 2, en orden
        assert [b["x"] for b in cajas[:4]] == [540, 1800, 540, 1800]
        assert cajas[0]["top"] == cajas[1]["top"] < cajas[2]["top"] == cajas[3]["top"]
        assert html.count('stroke-dasharray="18 14"') == nst - 1
    if formato == "avsb":                                  # pantalla partida: fórmulas y chips, A a la izquierda
        anim = json.loads((d / "animacion.json").read_text(encoding="utf-8"))
        assert anim["partidas"] == [1]
        lados = {i: float(re_left(html, i)) for i in ("fp", "fc", "ep", "ec")}
        assert lados["fp"] < 540 < lados["fc"] and lados["ep"] < 540 < lados["ec"]
        assert "transform:scale(" in html


def re_left(html, id_):
    """El centro x del slot que contiene al elemento id_."""
    import re
    m = re.search(rf'<div class="slot" style="left:(-?\d+)px; top:\d+px; width:(\d+)px;[^"]*">(?:(?!<div class="slot").)*?id="{id_}"', html, re.S)
    return int(m[1]) + int(m[2]) / 2


def test_una_columna_de_pantalla_partida_no_baja_de_la_letra_minima():
    """Si para entrar en su mitad un tipo quedaría con letra de menos de 28 px, ese tipo va en una columna."""
    import copy
    from etapas import escribir_salidas
    g = json.loads((FIXTURES / "guion_avsb_partida.json").read_text(encoding="utf-8"))
    largo = copy.deepcopy(g)
    for e in largo["bloques"][1]["elementos"]:
        if e["type"] == "chip":
            e["text"] = e["text"] + ": AB BA AC CA BC CB"
    import tempfile
    from voz_falsa import generar
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "t01"; escribir_salidas(d, compilar_guion(largo)); generar(d)
        html = motor(d, "cuaderno", "t01", "avsb").read_text(encoding="utf-8")
    assert re_left(html, "ep") == re_left(html, "ec") == 540           # los chips, en una columna
    assert re_left(html, "fp") < 540 < re_left(html, "fc")            # las fórmulas, partidas


# --- en el navegador: el mismo cuadro final y saltar ------------------------------------------

@pytest.fixture(scope="module")
def navegador():
    if not Path(CFG["gsap"]).exists():
        if EXIGIR:
            pytest.fail(f"falta {CFG['gsap']}: el job web del CI lo baja antes de los tests")
        pytest.skip("gsap no está instalado (s2s.py instalar)")
    if EXIGIR:
        import playwright.sync_api as pw
    else:
        pw = pytest.importorskip("playwright.sync_api")
    try:
        with pw.sync_playwright() as p:
            nav = p.chromium.launch()
            yield nav
            nav.close()
    except Exception as e:
        if EXIGIR:
            raise
        pytest.skip(f"Chromium de Playwright no disponible: {e}")


VARIANTES = [{"entrada": e, "transicion": "viaje"} for e in ("costado", "abajo", "barrido", "letras", "cascada")] + \
            [{"entrada": "escala", "transicion": t} for t in ("corte", "paneo", "zoom")]


@pytest.fixture(scope="module")
def videos_movimiento(tmp_path_factory, spec_movimiento):
    """El video de siempre (escala y viaje) y uno por cada entrada y cada transición nueva."""
    base = tmp_path_factory.mktemp("variantes")
    out = {"actual": video(spec_movimiento, base / "actual" / "t01", animacion={"entrada": "escala", "transicion": "viaje"})}
    for v in VARIANTES:
        nombre = v["entrada"] if v["entrada"] != "escala" else v["transicion"]
        out[nombre] = video(spec_movimiento, base / nombre / "t01", animacion=v)
    return out


def _pagina(navegador, html):
    p = navegador.new_page(viewport={"width": 390, "height": 693})
    p.goto(html.as_uri())
    p.wait_for_selector("html[data-s2s-listo]", state="attached", timeout=30000)
    return p


def _captura(p, t):
    p.evaluate("t => window.__s2s.pintar(t)", t)
    return base64.b64encode(p.screenshot()).decode()


@pytest.mark.parametrize("variante", [v["entrada"] if v["entrada"] != "escala" else v["transicion"] for v in VARIANTES])
def test_cada_entrada_y_transicion_termina_en_el_mismo_cuadro(navegador, videos_movimiento, variante):
    from test_reproductor_controles import COMPARAR
    S = estado(videos_movimiento["actual"].parent / "t01" / "index.html")
    finales = [t - 0.05 for _, t in sorted((int(k), v) for k, v in S["travel"].items())] + [S["D"] - 0.2]
    a, b = _pagina(navegador, videos_movimiento["actual"]), _pagina(navegador, videos_movimiento[variante])
    # el camino que deja dibujado la transición «viaje» es decoración propia de ese estilo (como en
    # tools/revisar.py, se esconde la capa de caminos para comparar el contenido)
    for p in (a, b):
        p.evaluate("document.querySelectorAll('#world > svg.abs').forEach(e => e.style.visibility = 'hidden')")
    try:
        assert b.evaluate("window.__s2s.D") == S["D"]                 # las duraciones no cambian el reloj
        for t in finales:
            d = a.evaluate(COMPARAR, [_captura(a, t), _captura(b, t)])
            assert d["mismo_tamano"] and d["max"] <= 64, f"{variante}, al final del bloque ({t:.2f} s): {d}"
    finally:
        a.close(); b.close()


@pytest.mark.parametrize("variante", [v["entrada"] if v["entrada"] != "escala" else v["transicion"] for v in VARIANTES])
def test_saltar_da_el_mismo_cuadro_con_las_entradas_nuevas(navegador, videos_movimiento, variante):
    """pintar(30) y después pintar(10) da el mismo cuadro que pintar(10) recién cargado."""
    from test_reproductor_controles import COMPARAR, ESTADO
    html = videos_movimiento[variante]
    ida, directo = _pagina(navegador, html), _pagina(navegador, html)
    try:
        assert ida.evaluate("window.__s2s.D") > 30
        for antes, t in [(30.0, 10.0), (40.0, 22.5), (12.0, 5.0)]:
            ida.evaluate("t => window.__s2s.pintar(t)", antes)
            png_a = _captura(ida, t); estado_a = ida.evaluate(ESTADO)
            nuevo = _pagina(navegador, html)
            png_b = _captura(nuevo, t); estado_b = nuevo.evaluate(ESTADO)
            nuevo.close()
            assert estado_a == estado_b, f"{variante}: pintar({antes}) y luego pintar({t}): otros estilos"
            d = directo.evaluate(COMPARAR, [png_a, png_b])
            assert d["mismo_tamano"] and d["max"] <= 64, f"{variante}: pintar({antes}) y luego pintar({t}): {d}"
    finally:
        ida.close(); directo.close()


@pytest.fixture(scope="module", params=[(f, e) for e in ("cuaderno", "pizarra") for f in sorted(FORMATOS)],
                ids=lambda p: f"{p[0]}-{p[1]}")
def video_formato(request, tmp_path_factory):
    if not Path(CFG["gsap"]).exists():
        if EXIGIR:
            pytest.fail(f"falta {CFG['gsap']}")
        pytest.skip("gsap no está instalado")
    formato, estilo = request.param
    return video_de_formato(formato, estilo, tmp_path_factory.mktemp("formatos"))


def test_los_videos_de_cada_formato_no_crean_capas_3d(navegador, video_formato):
    from test_reproductor_controles import CAPAS_3D
    p = _pagina(navegador, video_formato)
    try:
        assert p.evaluate(CAPAS_3D, [p.evaluate("window.__s2s.D"), 0.25]) == []
    finally:
        p.close()
