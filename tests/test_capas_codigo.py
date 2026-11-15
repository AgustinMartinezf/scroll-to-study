"""Capas (OSI, TCP/IP, niveles de un sistema) con la acción atravesar, y código con resaltado de sintaxis propio
y las líneas comprobadas contra el material.

La validación y el resaltado se prueban con compile.py y sintaxis.py; el dibujo y la animación, con el video de
prueba (tests/fixtures/guion_capas_codigo.json) en Chromium con Playwright. Sin Playwright o sin gsap esos se
saltean; con S2S_EXIGIR_NAVEGADOR=1 fallan."""
import base64
import copy
import json
import os
from pathlib import Path

import pytest
from compile import FS_MIN, compilar
from config import CFG
from conftest import SKILL
from datos import EJEMPLO
from sintaxis import tokens
from videos_prueba import FIXTURES, compilar_guion, estado, video

LEX = json.loads((SKILL / "scripts" / "lexico.json").read_text(encoding="utf-8"))
EXIGIR = os.environ.get("S2S_EXIGIR_NAVEGADOR") == "1"

CAPAS = {"type": "capas", "id": "k", "capas": [{"id": "ka", "text": "aplicación", "detalle": "HTTP"},
                                              {"id": "kt", "text": "transporte", "detalle": "TCP"},
                                              {"id": "kr", "text": "red", "detalle": "IP"}]}
CODIGO = {"type": "codigo", "id": "q", "lenguaje": "sql",
          "lineas": ["CONSTRAINT fk_multa_prestamo", "  FOREIGN KEY (id_prestamo)"]}
# lo que tendría corpus.txt: las líneas numeradas de schema.sql (como escribe s2s.py corpus)
CORPUS = """=== archivo: sql/schema.sql ===
24|   monto DECIMAL(8,2) NOT NULL,
25|   CONSTRAINT fk_multa_prestamo
26|     FOREIGN KEY (id_prestamo) REFERENCES prestamo (id_prestamo)"""


def compilar_con(elemento, frase, corpus=None):
    g = copy.deepcopy(EJEMPLO)
    g["bloques"][0]["elementos"].append(elemento)
    g["bloques"][0]["frases"][0] = frase + " " + g["bloques"][0]["frases"][0]
    return compilar(g, LEX, SKILL / "scripts" / "iconos", corpus=corpus)


def errores(elemento, frase, corpus=None):
    return " | ".join(compilar_con(elemento, frase, corpus)[1].errores)


def con(base, **cambios):
    e = copy.deepcopy(base); e.update(cambios); return e


# --- capas -----------------------------------------------------------------------------------

@pytest.mark.parametrize("elemento, esperado", [
    (con(CAPAS, capas=CAPAS["capas"][:1]), "capas: entre 2 y 7"),
    (con(CAPAS, capas=[{"id": f"x{i}", "text": f"capa {i}"} for i in range(8)]), "capas: entre 2 y 7"),
    (con(CAPAS, capas=[{"id": "ka", "text": "una capa con nombre larguísimo"}, CAPAS["capas"][1]]), "pasa de 22 caracteres"),
    (con(CAPAS, capas=[{"id": "ka", "text": "app", "detalle": "HTTP, DNS, SMTP, FTP, SSH, X"}, CAPAS["capas"][1]]), "pasa de 26"),
    (con(CAPAS, capas=[{"id": "ka", "text": "app", "kind": "rosa"}, CAPAS["capas"][1]]), "kind «rosa» no existe"),
    (con(CAPAS, capas=[{"id": "ka", "text": "app"}, {"id": "ka", "text": "otra"}]), "id repetido o reservado «ka»"),
    (con(CAPAS, capas=[{"id": "m", "text": "app"}, CAPAS["capas"][1]]), "id repetido o reservado «m»"),   # m: la tabla
    (con(CAPAS, capas=["aplicación", "red"]), "tiene que ser"),
])
def test_capas_se_valida(elemento, esperado):
    assert esperado in errores(elemento, "{show k}Mirá.")


@pytest.mark.parametrize("frase, esperado", [
    ("{show k}Mirá {atravesar k de=ka a=kr texto=datos}cómo baja.", ""),
    ("{show k}Mirá {atravesar k de=kr a=ka}cómo sube.", ""),
    ("{show k}Mirá {atravesar k de=ka a=nada}esto.", "a=nada tienen que ser dos capas distintas"),
    ("{show k}Mirá {atravesar k de=ka a=ka}esto.", "tienen que ser dos capas distintas"),
    ("{show k}Mirá {atravesar k a=kr}esto.", "de=None"),
    ("{show k}Mirá {atravesar k de=ka a=kr texto=un-texto-muy-largo}esto.", "texto de más de 12"),
    ("{show k}Mirá {atravesar m de=ka a=kr}esto.", "atravesar sobre «m»: solo elementos capas"),
    ("{show k}Mirá {strike kt}esto y {hl ka}esto {good kr}acá.", ""),
])
def test_atravesar_se_valida(frase, esperado):
    e = errores(CAPAS, frase)
    assert (e == "") if not esperado else (esperado in e), e


def test_capas_compila_con_letra_calculada():
    spec, rep = compilar_con(CAPAS, "{show k}Mirá {show kt}esta y {atravesar k de=ka a=kr texto=datos}baja.")
    assert rep.errores == []
    k = next(e for e in spec["STATIONS"][0] if e["type"] == "capas")
    assert FS_MIN <= k["fs"] <= 40 and [c["id"] for c in k["capas"]] == ["ka", "kt", "kr"]
    assert ["0:baja", "atravesar", "k", {"de": "ka", "a": "kr", "texto": "datos"}] in spec["EVENTS"]


def test_una_capa_que_no_entra_ni_con_la_letra_minima():
    largas = [{"id": f"x{i}", "text": "nombre de veintidós ch", "detalle": "detalle de veintiséis cara", "icon": "users"}
              for i in range(2)]
    e = errores(con(CAPAS, capas=largas), "{show k}Mirá.")
    assert f"no entra ni con letra {FS_MIN}px" in e and "acortá su texto o su detalle" in e


# --- código ----------------------------------------------------------------------------------

@pytest.mark.parametrize("elemento, esperado", [
    (con(CODIGO, lenguaje="cobol"), "lenguaje «cobol» desconocido"),
    (con(CODIGO, lineas=[]), "entre 1 y 12 líneas"),
    (con(CODIGO, lineas=["x;"] * 13), "entre 1 y 12 líneas"),
    (con(CODIGO, lineas=["SELECT nombre, apellido, direccion FROM socio"]), "máximo 34): partila en dos"),
    (con(CODIGO, lineas=["\tSELECT 1"]), "tabulaciones"),
    (con(CODIGO, ejemplo="sí"), "ejemplo va true o false"),
])
def test_codigo_se_valida(elemento, esperado):
    assert esperado in errores(elemento, "{show q}Mirá.")


def test_las_lineas_de_codigo_se_comprueban_contra_el_material():
    # las dos líneas están (sin importar la sangría ni las mayúsculas): sin errores
    assert errores(CODIGO, "{show q}Mirá.", CORPUS) == ""
    # una que no está: error con la sugerencia
    inventada = con(CODIGO, lineas=CODIGO["lineas"] + ["  ON DELETE CASCADE"])
    e = errores(inventada, "{show q}Mirá.", CORPUS)
    assert "línea 2 «ON DELETE CASCADE»: esta línea no está en el material: copiala tal cual o marcá el bloque como ejemplo" in e
    assert "línea 0" not in e and "línea 1" not in e
    # la misma, marcada como ejemplo: sin errores
    assert errores(con(inventada, ejemplo=True), "{show q}Mirá.", CORPUS) == ""
    # las líneas vacías no se buscan
    assert errores(con(CODIGO, lineas=["CONSTRAINT fk_multa_prestamo", "", "  FOREIGN KEY (id_prestamo)"]),
                   "{show q}Mirá.", CORPUS) == ""
    # sin material (compile.py suelto, o el ejemplo de un formato) no se puede comprobar
    assert errores(inventada, "{show q}Mirá.") == ""


def test_el_codigo_comprobado_no_avisa_identificadores_inventados():
    g = copy.deepcopy(EJEMPLO)
    g["bloques"][0]["elementos"].append(con(CODIGO, lineas=["monto DECIMAL(8,2) NOT NULL,"]))
    g["bloques"][0]["frases"][0] = "{show q}Mirá " + g["bloques"][0]["frases"][0]
    inv = {"afirmaciones": [{"id": "A1", "texto": "La FK de multa", "cita": "id_prestamo", "estado": "ok"}]}
    for b in g["bloques"]:
        b["fuentes"] = ["A1"]
    avisos = " | ".join(a for a in compilar(g, LEX, inventario=inv, corpus=CORPUS)[1].avisos if "bloque 0" in a)
    assert "¿inventados?" in avisos and "DECIMAL" not in avisos       # sigue avisando por lo demás
    # el mismo bloque como ejemplo sí avisa: no se comprobó contra el material
    g["bloques"][0]["elementos"][-1]["ejemplo"] = True
    avisos = " | ".join(a for a in compilar(g, LEX, inventario=inv, corpus=CORPUS)[1].avisos if "bloque 0" in a)
    assert "DECIMAL" in avisos


def clases(linea, lenguaje):
    return {(c, t) for c, t in tokens(linea, lenguaje) if c}


def test_resaltado_java():
    t = clases('public int f(String s) { return 42; } // fin "x"', "java")
    assert {("kw", "public"), ("kw", "int"), ("kw", "return"), ("num", "42"), ("com", '// fin "x"')} <= t
    assert ("kw", "String") not in t and ("kw", "f") not in t                 # nombres de clases y métodos, no
    assert ("str", '"hola"') in clases('String s = "hola";', "java")
    assert "".join(x for _, x in tokens('  if (x) { y = "a"; }', "java")) == '  if (x) { y = "a"; }'


def test_resaltado_sql():
    t = clases("select nombre FROM socio WHERE ci = '4.123.456' -- todos", "sql")
    assert {("kw", "select"), ("kw", "FROM"), ("kw", "WHERE"), ("str", "'4.123.456'"), ("com", "-- todos")} <= t
    assert ("kw", "nombre") not in t and ("kw", "socio") not in t
    assert ("str", "'it''s'") in clases("SELECT 'it''s'", "sql")             # comilla escapada como en SQL


def test_resaltado_python():
    t = clases("def f(x):  # 'no es string'", "python")
    assert ("kw", "def") in t and ("com", "# 'no es string'") in t and not any(c == "str" for c, _ in t)
    t = clases("    return 'a' if x else None", "python")
    assert {("kw", "return"), ("str", "'a'"), ("kw", "if"), ("kw", "else"), ("kw", "None")} <= t
    assert ("kw", "x") not in t
    assert clases("print(3.14)", "python") == {("num", "3.14")}
    assert tokens("cualquier cosa", "texto") == [("", "cualquier cosa")]


# --- el video de prueba ------------------------------------------------------------------------

def test_el_guion_de_prueba_compila_sin_errores_ni_avisos():
    g = json.loads((FIXTURES / "guion_capas_codigo.json").read_text(encoding="utf-8"))
    spec = compilar_guion(g)
    jv = next(e for st in spec["STATIONS"] for e in st if e["id"] == "jv")
    assert len(jv["lineas"]) == 12 and jv["lenguaje"] == "java" and jv["fs"] >= FS_MIN
    assert any(e[1] == "atravesar" and e[3]["de"] == "c7" and e[3]["a"] == "c1" for e in spec["EVENTS"])


@pytest.fixture(scope="module", params=["cuaderno", "pizarra"])
def video_capas(request, tmp_path_factory):
    if not Path(CFG["gsap"]).exists():
        if EXIGIR:
            pytest.fail(f"falta {CFG['gsap']}: el job web del CI lo baja antes de los tests")
        pytest.skip("gsap no está instalado (s2s.py instalar)")
    g = json.loads((FIXTURES / "guion_capas_codigo.json").read_text(encoding="utf-8"))
    d = tmp_path_factory.mktemp(request.param) / "t01"
    html = video(compilar_guion(g), d, request.param, "t01\nRevisión 0.8.0")
    tema = json.loads((SKILL / "scripts" / "temas" / f"{request.param}.json").read_text(encoding="utf-8"))
    return html, estado(d / "index.html"), tema


def test_el_motor_dibuja_capas_y_codigo_con_los_colores_del_tema(video_capas):
    html, _, tema = video_capas
    texto = html.read_text(encoding="utf-8")
    assert 'class="card capas" id="osi"' in texto and 'class="card codigo" id="jv"' in texto
    for i in range(12):
        assert f'id="jv-l{i}"' in texto
    assert '<span class="skw" style="color:' + tema["py"]["codClave"] + '">public</span>' in texto
    assert '<span class="scom" style="color:' + tema["py"]["codComentario"] + '">-- atrasados</span>' in texto
    assert '<span class="ttag">ejemplo</span>' in texto
    assert tema["py"]["capa"] in texto and tema["py"]["codFondo"] in texto


@pytest.fixture(scope="module")
def navegador():
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


def _pagina(navegador, html):
    p = navegador.new_page(viewport={"width": 390, "height": 693})
    p.goto(html.as_uri())
    p.wait_for_selector("html[data-s2s-listo]", state="attached", timeout=30000)
    return p


def momento(S, accion, id_):
    return next(e["t"] for e in S["EV"] if e["a"] == accion and e["id"] == id_)


FONDOS = """id => [...document.getElementById(id).querySelectorAll(".capa")].map(c => [c.id, getComputedStyle(c).backgroundColor])"""
RGB = """c => { const d = document.createElement("div"); d.style.color = c; document.body.appendChild(d);
  const v = getComputedStyle(d).color; d.remove(); return v; }"""


def test_atravesar_resalta_exactamente_las_capas_del_medio(navegador, video_capas):
    html, S, tema = video_capas
    p = _pagina(navegador, html)
    try:
        t = momento(S, "atravesar", "osi")
        ruta = p.evaluate(RGB, tema["c"]["ruta"])
        p.evaluate("t => __s2s.pintar(t)", t - 0.05)
        antes = dict(p.evaluate(FONDOS, "osi"))
        # c7 -> c1: la ficha baja; al final del recorrido, las del medio (c6..c2) quedaron resaltadas
        p.evaluate("t => __s2s.pintar(t)", momento(S, "hl", "c4") - 0.05)
        despues = dict(p.evaluate(FONDOS, "osi"))
        medio = {"c6", "c5", "c4", "c3", "c2"}
        for c, fondo in despues.items():
            if c in medio:
                assert fondo == ruta and antes[c] != ruta, c
            else:
                assert fondo == antes[c], c                                 # c7 y c1 (los extremos), igual
        # de a una: al principio del recorrido, la de arriba del medio ya está y la de abajo todavía no
        p.evaluate("t => __s2s.pintar(t)", t + 1.0)
        medio_t = dict(p.evaluate(FONDOS, "osi"))
        assert medio_t["c6"] == ruta and medio_t["c2"] != ruta
        # la ficha se ve mientras viaja
        assert p.evaluate("+getComputedStyle(document.querySelector('#osi .ficha')).opacity") == 1
    finally:
        p.close()


def test_atravesar_de_subida_resalta_las_del_medio(navegador, video_capas):
    html, S, tema = video_capas
    p = _pagina(navegador, html)
    try:
        ruta = p.evaluate(RGB, tema["c"]["ruta"])
        p.evaluate("t => __s2s.pintar(t)", momento(S, "strike", "t3") - 0.05)
        fondos = dict(p.evaluate(FONDOS, "tcpip"))
        assert [c for c, f in fondos.items() if f == ruta] == ["t3", "t2"]  # t1 -> t4: las del medio
    finally:
        p.close()


OPAC = """id => [...document.getElementById(id).querySelectorAll(".cl")].map(l => +getComputedStyle(l).opacity)"""


def test_show_de_una_linea_muestra_solo_esa(navegador, video_capas):
    html, S, _ = video_capas
    p = _pagina(navegador, html)
    try:
        p.evaluate("t => __s2s.pintar(t)", momento(S, "show", "sq-l2") + 0.8)
        assert p.evaluate(OPAC, "sq") == [1, 1, 1, 0, 0]                    # l0, l1 y l2 ya, l3 y l4 todavía no
        p.evaluate("t => __s2s.pintar(t)", momento(S, "show", "sq-l3") + 0.8)
        assert p.evaluate(OPAC, "sq") == [1, 1, 1, 1, 0]
        # el bloque de java, con su {show jv}, aparece entero
        p.evaluate("t => __s2s.pintar(t)", momento(S, "show", "jv") + 1.6)
        assert p.evaluate(OPAC, "jv") == [1] * 12
    finally:
        p.close()


def test_el_video_de_capas_y_codigo_no_crea_capas_3d(navegador, video_capas):
    from test_reproductor_controles import CAPAS_3D
    html, S, _ = video_capas
    p = _pagina(navegador, html)
    try:
        assert p.evaluate(CAPAS_3D, [S["D"], 0.25]) == []
    finally:
        p.close()


def test_saltar_da_el_mismo_cuadro_en_el_video_de_capas_y_codigo(navegador, video_capas):
    from test_reproductor_controles import COMPARAR, ESTADO
    html, S, _ = video_capas
    assert S["D"] > 30
    ida = _pagina(navegador, html)
    try:
        for antes, t in [(30.0, 10.0), (S["D"] - 1, 4.0), (8.0, 25.0)]:
            ida.evaluate("t => __s2s.pintar(t)", antes)
            ida.evaluate("t => __s2s.pintar(t)", t)
            png_a, estado_a = base64.b64encode(ida.screenshot()).decode(), ida.evaluate(ESTADO)
            nuevo = _pagina(navegador, html)
            nuevo.evaluate("t => __s2s.pintar(t)", t)
            png_b, estado_b = base64.b64encode(nuevo.screenshot()).decode(), nuevo.evaluate(ESTADO)
            nuevo.close()
            assert estado_a == estado_b, f"pintar({antes}) y luego pintar({t}): otros estilos"
            d = ida.evaluate(COMPARAR, [png_a, png_b])
            assert d["mismo_tamano"] and d["max"] <= 64, f"pintar({antes}) y luego pintar({t}): {d}"
    finally:
        ida.close()


@pytest.fixture(scope="module")
def variantes_capas(tmp_path_factory):
    """El video de prueba con la entrada de siempre y con las entradas nuevas de capas y código."""
    if not Path(CFG["gsap"]).exists():
        if EXIGIR:
            pytest.fail(f"falta {CFG['gsap']}")
        pytest.skip("gsap no está instalado")
    spec = compilar_guion(json.loads((FIXTURES / "guion_capas_codigo.json").read_text(encoding="utf-8")))
    base = tmp_path_factory.mktemp("entradas")
    out = {}
    for capas, codigo in [("escala", "escala"), ("cascada", "lineas"), ("subida", "escribir")]:
        anim = {"entrada": "escala", "transicion": "viaje", "entradas": {"capas": capas, "codigo": codigo}}
        out[capas] = video(spec, base / capas / "t01", "cuaderno", "t01", animacion=anim)
    return out


@pytest.mark.parametrize("variante", ["cascada", "subida"])
def test_las_entradas_de_capas_y_codigo_terminan_en_el_mismo_cuadro(navegador, variantes_capas, variante):
    from test_reproductor_controles import COMPARAR
    S = estado(variantes_capas["escala"].parent / "t01" / "index.html")
    finales = [t - 0.05 for _, t in sorted((int(k), v) for k, v in S["travel"].items())] + [S["D"] - 0.2]
    a, b = _pagina(navegador, variantes_capas["escala"]), _pagina(navegador, variantes_capas[variante])
    try:
        assert estado(variantes_capas[variante].parent / "t01" / "index.html")["ENT"]["jv"] in ("lineas", "escribir")
        for t in finales:
            a.evaluate("t => __s2s.pintar(t)", t); b.evaluate("t => __s2s.pintar(t)", t)
            d = a.evaluate(COMPARAR, [base64.b64encode(a.screenshot()).decode(), base64.b64encode(b.screenshot()).decode()])
            assert d["mismo_tamano"] and d["max"] <= 64, f"{variante}, al final del bloque ({t:.2f} s): {d}"
    finally:
        a.close(); b.close()
