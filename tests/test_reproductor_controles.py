"""Avanzar y retroceder dentro del video (PLAYER_JS de reproductor.py) en Chromium, con Playwright.

Casi todo se prueba en una página mínima con el PLAYER_JS y el PLAYER_CSS reales, una línea de tiempo de
juguete (anota en window.cuadro el último tiempo pintado) y un MP3 en silencio que dura lo mismo que el
video. Lo de "el mismo cuadro llegue como llegue" se prueba con un video de verdad (engine.js + gsap), así
que necesita gsap instalado (`s2s.py instalar`; el job "web" del CI lo baja).

Si Playwright o Chromium no están instalados, se saltean; con S2S_EXIGIR_NAVEGADOR=1 (el job "web" del CI)
fallan en vez de saltearse."""
import json
import os
import random
import subprocess
import sys

import pytest

import reproductor
from compile import compilar
from config import CFG
from conftest import SKILL
from datos import EJEMPLO
from etapas import escribir_salidas
from voz_falsa import generar

EXIGIR = os.environ.get("S2S_EXIGIR_NAVEGADOR") == "1"
if EXIGIR:
    import playwright.sync_api as pw
else:
    pw = pytest.importorskip("playwright.sync_api")

# guarda lo que el video avisa (además del postMessage, avisar() dispara el evento "s2s" en la ventana) y
# las fuentes de audio que se arrancan y se frenan
ESPIAS = """
window.avisos = []; addEventListener("s2s", e => avisos.push(e.detail));
window.fuentes = [];
const _start = AudioBufferSourceNode.prototype.start, _stop = AudioBufferSourceNode.prototype.stop;
AudioBufferSourceNode.prototype.start = function (cuando, desde) { fuentes.push({ desde, frenada: false }); this._i = fuentes.length - 1; return _start.apply(this, arguments); };
AudioBufferSourceNode.prototype.stop = function () { if (this._i !== undefined) fuentes[this._i].frenada = true; return _stop.apply(this, arguments); };
"""


def _pagina(dur: float) -> str:
    player = reproductor.PLAYER_JS.replace("__SILENCIO_MP3__", reproductor.mp3_silencio())
    tx = json.dumps(reproductor.TEXTOS["es"], ensure_ascii=False)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<style>{reproductor.PLAYER_CSS}</style></head><body>"
        "<div id='root' style='width:1080px;height:1920px;background:#123'></div>"
        f"{reproductor.marcado(reproductor.TEXTOS['es'])}"
        f"<script type='application/octet-stream' id='s2s-mp3'>{reproductor.mp3_silencio(dur)}</script>"
        "<script>"
        f"window.__timelines = {{ main: {{ duration: () => {dur}, seek: t => {{ window.cuadro = t; }}, progress() {{ return this; }} }} }};"
        f"const TX = {tx};"
        f"{player}"
        "</script></body></html>"
    )


@pytest.fixture(scope="module")
def navegador():
    try:
        with pw.sync_playwright() as p:
            nav = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
            yield nav
            nav.close()
    except Exception as e:                                    # Chromium no instalado (playwright install chromium)
        if EXIGIR:
            raise
        pytest.skip(f"Chromium de Playwright no disponible: {e}")


@pytest.fixture
def abrir(navegador, tmp_path):
    paginas = []

    def nuevo(dur=10.0):
        page = navegador.new_page(viewport={"width": 390, "height": 844})
        paginas.append(page)
        page.add_init_script(ESPIAS)
        archivo = tmp_path / f"video_{len(paginas)}.html"
        archivo.write_text(_pagina(dur), encoding="utf-8")
        page.goto(archivo.as_uri())
        page.wait_for_selector("html[data-s2s-listo]", state="attached", timeout=20000)
        return page
    yield nuevo
    for p in paginas:
        p.close()


def avisos(page, tipo):
    return page.evaluate("t => avisos.filter(a => a.tipo === t)", tipo)


def esperar_aviso(page, tipo, n=1):
    page.wait_for_function("([t, n]) => avisos.filter(a => a.tipo === t).length >= n", arg=[tipo, n], timeout=8000)
    return avisos(page, tipo)[n - 1]


def tocar_para_ver(page):
    page.click("#s2s-tapa", position={"x": 195, "y": 300})
    page.wait_for_function("document.getElementById('s2s-tapa').hidden === true", timeout=8000)


def test_la_barra_se_agarra_en_32_px_y_esta_arriba_de_la_tapa(abrir):
    page = abrir()
    caja = page.query_selector("#s2s-pista").bounding_box()
    assert caja["height"] >= 32 and caja["width"] == 390 and caja["y"] + caja["height"] == 844
    visible = page.query_selector("#s2s-barra").bounding_box()
    assert visible["height"] <= 6                                          # se ve fina
    # con la tapa ("Tocar para ver") a la vista, el dedo en la barra agarra la barra
    assert page.evaluate("document.elementFromPoint(100, 830).closest('#s2s-pista') !== null")


def test_arrastrar_muestra_el_cuadro_y_un_salto_antes_del_primer_toque_reproduce_desde_ahi(abrir):
    page = abrir()
    page.mouse.move(390 * 0.25, 830)
    page.mouse.down()
    assert page.evaluate("window.cuadro") == pytest.approx(2.5, abs=0.05)   # se ve el cuadro de ese momento
    page.mouse.move(390 * 0.6, 830, steps=4)
    assert page.evaluate("window.cuadro") == pytest.approx(6.0, abs=0.05)
    assert page.evaluate("document.getElementById('s2s-pista').classList.contains('arrastrando')")
    assert avisos(page, "sigue") == [] and not page.evaluate("document.getElementById('s2s-tapa').hidden")
    page.mouse.up()
    a = esperar_aviso(page, "sigue")                                       # arranca desde ahí, no desde 0
    assert a["t"] == pytest.approx(6.0, abs=0.1)
    assert page.evaluate("fuentes.map(f => f.desde)") == [pytest.approx(6.0, abs=0.05)]
    assert page.evaluate("document.getElementById('s2s-tapa').hidden")


def test_saltar_sonando_frena_la_fuente_y_arranca_otra_en_el_lugar_nuevo(abrir):
    page = abrir()
    tocar_para_ver(page)
    page.evaluate("window.__s2s.saltar(7)")
    assert esperar_aviso(page, "salto")["t"] == pytest.approx(7.0, abs=0.05)
    f = page.evaluate("fuentes")
    assert [x["frenada"] for x in f] == [True, False] and f[1]["desde"] == pytest.approx(7.0, abs=0.01)
    assert page.evaluate("window.__s2s.ahora()") >= 7.0
    page.evaluate("window.__s2s.saltar(2)")                                # para atrás también
    assert esperar_aviso(page, "salto", 2)["t"] == pytest.approx(2.0, abs=0.05)
    assert [x["frenada"] for x in page.evaluate("fuentes")] == [True, True, False]


def test_doble_toque_a_los_costados_salta_5_s_y_un_toque_pausa(abrir):
    page = abrir()
    tocar_para_ver(page)
    page.mouse.dblclick(390 * 0.85, 400)                                   # tercio derecho: +5 s
    a = esperar_aviso(page, "salto")
    assert 5.0 <= a["t"] <= 6.5
    assert page.text_content("#s2s-salto") == "+5 s"
    assert page.evaluate("document.getElementById('s2s-salto').classList.contains('ver')")
    page.wait_for_timeout(700)                                             # pasa la racha de toques
    page.mouse.dblclick(390 * 0.15, 400)                                   # tercio izquierdo: -5 s
    b = esperar_aviso(page, "salto", 2)
    assert b["t"] == pytest.approx(a["t"] + 0.7 - 5, abs=0.6)
    assert page.text_content("#s2s-salto") == "−5 s"
    assert avisos(page, "pausa") == []                                     # ningún doble toque pausó
    page.wait_for_timeout(700)
    page.mouse.click(195, 400)                                             # un toque: pausa, pero no enseguida
    page.wait_for_timeout(80)
    assert avisos(page, "pausa") == []
    esperar_aviso(page, "pausa")
    assert page.text_content("#s2s-tapa button") == "Seguir"


def test_teclado_flechas_y_espacio(abrir):
    page = abrir()
    page.keyboard.press("ArrowRight")                                      # antes del primer toque: arranca en 5
    assert esperar_aviso(page, "sigue")["t"] == pytest.approx(5.0, abs=0.1)
    page.keyboard.press(" ")
    pausa = esperar_aviso(page, "pausa")
    page.keyboard.press("ArrowLeft")                                       # quieto: se mueve, sigue en pausa
    assert esperar_aviso(page, "salto", 2)["t"] == pytest.approx(max(0, pausa["t"] - 5), abs=0.05)
    assert page.text_content("#s2s-tapa button") == "Seguir" and len(avisos(page, "sigue")) == 1
    page.keyboard.press(" ")                                               # sigue (o "inicio", si quedó en 0)
    page.wait_for_function("avisos.filter(a => a.tipo === 'sigue' || a.tipo === 'inicio').length >= 2")
    otra = [a for a in page.evaluate("avisos") if a["tipo"] in ("sigue", "inicio")][1]
    assert otra["t"] == pytest.approx(max(0, pausa["t"] - 5), abs=0.1)


def test_al_terminar_avisa_cuanto_sono_de_verdad(abrir):
    page = abrir(1.5)
    tocar_para_ver(page)
    fin = esperar_aviso(page, "fin")
    assert fin["duracion"] == 1.5 and fin["reproducidos"] == pytest.approx(1.5, abs=0.15)
    assert page.text_content("#s2s-tapa button") == "Ver de nuevo"
    # saltando casi al final, lo que sonó es poco: la lista no lo va a contar como visto
    page = abrir(4.0)
    tocar_para_ver(page)
    page.evaluate("window.__s2s.saltar(3.2)")
    fin = esperar_aviso(page, "fin")
    assert fin["reproducidos"] < 1.6


def test_un_toque_que_llega_de_la_lista_hace_lo_mismo(abrir):
    """En el modo feed la capa de gestos de la lista tapa el video y le pasa los toques con postMessage."""
    page = abrir()
    tocar_para_ver(page)
    page.evaluate("postMessage({ s2s: 'toque', x: 0.9 }, '*'); setTimeout(() => postMessage({ s2s: 'toque', x: 0.9 }, '*'), 60)")
    assert 5.0 <= esperar_aviso(page, "salto")["t"] <= 6.5
    page.evaluate("postMessage({ s2s: 'tecla', tecla: 'ArrowRight' }, '*')")
    esperar_aviso(page, "salto", 2)
    assert avisos(page, "pausa") == []


# --- el mismo cuadro llegue como llegue (video de verdad, con gsap) --------------------------------

@pytest.fixture(scope="module")
def video_real(tmp_path_factory):
    from pathlib import Path
    gsap = Path(CFG["gsap"])
    if not gsap.exists():
        if EXIGIR:
            pytest.fail(f"falta {gsap}: el job web del CI lo baja antes de los tests")
        pytest.skip("gsap no está instalado (s2s.py instalar)")
    d = tmp_path_factory.mktemp("real") / "t01"
    spec, rep = compilar(EJEMPLO, json.loads((SKILL / "scripts" / "lexico.json").read_text(encoding="utf-8")))
    assert rep.errores == []
    escribir_salidas(d, spec)
    generar(d)
    subprocess.run([sys.executable, str(SKILL / "scripts" / "engine.py"), str(d)], check=True, capture_output=True)
    return reproductor.construir(d, d.parent / "t01.html", "La FK de multa")


def test_el_video_no_tiene_filtros(video_real):
    assert "blur(" not in video_real.read_text(encoding="utf-8")


# el estado de cada elemento (sus estilos en línea, con las propiedades en orden)
ESTADO = """[...document.querySelectorAll("body *")].map(e => e.id + "|" +
  (e.getAttribute("style") || "").split(";").map(x => x.trim()).filter(Boolean).sort().join(";"))"""
# la mayor diferencia por canal entre dos PNG, y cuántos píxeles difieren (en un canvas: sin Pillow)
COMPARAR = """async ([a, b]) => {
  const img = src => new Promise(ok => { const i = new Image(); i.onload = () => ok(i); i.src = "data:image/png;base64," + src; });
  const [x, y] = await Promise.all([img(a), img(b)]);
  const px = i => { const c = document.createElement("canvas"); c.width = i.width; c.height = i.height;
                    const g = c.getContext("2d"); g.drawImage(i, 0, 0); return g.getImageData(0, 0, i.width, i.height).data; };
  const p = px(x), q = px(y);
  let max = 0, n = 0;
  for (let k = 0; k < p.length; k += 4) {
    const d = Math.max(Math.abs(p[k] - q[k]), Math.abs(p[k + 1] - q[k + 1]), Math.abs(p[k + 2] - q[k + 2]));
    if (d) { n++; if (d > max) max = d; }
  }
  return { max, n, mismo_tamano: x.width === y.width && x.height === y.height };
}"""


def test_pintar_da_el_mismo_cuadro_llegue_como_llegue(navegador, video_real):
    """pintar(30) y después pintar(10) da el mismo cuadro que pintar(10) recién cargado, y lo mismo con tres
    tiempos al azar. "El mismo cuadro": cada elemento con exactamente los mismos estilos, y la captura igual
    salvo el suavizado de bordes. Chromium a veces rasteriza las líneas finas de la grilla con otro suavizado
    después de un cambio de escala (diferencias de hasta ~11 de 255 en esas líneas); un cuadro distinto
    (algo corrido, otro texto encendido) da diferencias de más de 100."""
    import base64

    def pagina():
        p = navegador.new_page(viewport={"width": 390, "height": 693})
        p.goto(video_real.as_uri())
        p.wait_for_selector("html[data-s2s-listo]", state="attached", timeout=30000)
        return p

    def cuadro(p, *tiempos):
        for t in tiempos:
            p.evaluate("t => window.__s2s.pintar(t)", t)
        return p.evaluate(ESTADO), base64.b64encode(p.screenshot()).decode()

    ida = pagina()
    D = ida.evaluate("window.__s2s.D")
    assert D > 30
    azar = random.Random()
    casos = [(30.0, 10.0)] + [(round(azar.uniform(0, D), 2), round(azar.uniform(0.5, D - 0.5), 2)) for _ in range(3)]
    for antes, t in casos:
        directo = pagina()
        try:
            estado_a, png_a = cuadro(ida, antes, t)
            estado_b, png_b = cuadro(directo, t)
            assert estado_a == estado_b, f"pintar({antes}) y luego pintar({t}): otros estilos"
            d = directo.evaluate(COMPARAR, [png_a, png_b])
            assert d["mismo_tamano"] and d["max"] <= 24, f"pintar({antes}) y luego pintar({t}): {d}"
        finally:
            directo.close()
    ida.close()


def test_en_el_modo_feed_un_gesto_sobre_la_tapa_se_le_avisa_a_la_lista(abrir):
    """Con el video quieto la lista no pone su capa (el toque que arranca el audio tiene que ser del video):
    es el video el que avisa el gesto. Fuera del modo feed, la tapa no toma gestos (la página scrollea)."""
    page = abrir()
    assert page.evaluate("getComputedStyle(document.getElementById('s2s-tapa')).touchAction") == "auto"
    page.evaluate("postMessage({ s2s: 'feed', activo: true }, '*')")
    page.wait_for_function("getComputedStyle(document.getElementById('s2s-tapa')).touchAction === 'none'")
    page.mouse.move(195, 600)
    page.mouse.down()
    page.mouse.move(195, 300, steps=3)
    page.mouse.up()
    d = esperar_aviso(page, "deslizar")
    assert d["dy"] == pytest.approx(-300, abs=2) and d["y0"] == pytest.approx(600, abs=2) and d["ms"] >= 0
    page.wait_for_timeout(100)
    assert avisos(page, "inicio") == [] and not page.evaluate("document.getElementById('s2s-tapa').hidden")
    page.keyboard.press("ArrowDown")                                       # ↓ y Esc son de la lista
    page.keyboard.press("Escape")
    assert [a["tecla"] for a in avisos(page, "tecla")] == ["ArrowDown", "Escape"]
    page.mouse.wheel(0, 100)
    assert esperar_aviso(page, "rueda")["dy"] == 100
    page.mouse.click(195, 400)                                             # un toque sigue reproduciendo
    esperar_aviso(page, "inicio")
