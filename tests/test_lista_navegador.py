"""La lista de reproducción completa (index.html de reproductor.indice) en Chromium, con Playwright.

Los videos son páginas de juguete que hablan con la lista igual que los reales (postMessage "listo",
"inicio", "pausa", "fin"), así no hace falta gsap, Piper ni audio. El reloj se fija en 2026-11-12.
Si Playwright o Chromium no están instalados, se saltea."""
import json
from datetime import datetime

import pytest

import reproductor

pw = pytest.importorskip("playwright.sync_api")

HOY = datetime(2026, 11, 12, 12, 0)
VIDEO_FALSO = """<!doctype html><html><body style="margin:0;height:100vh;background:#123"><script>
window.recibidos = []; window.clics = 0;
addEventListener("message", e => {
  recibidos.push(e.data);
  if (e.data && e.data.s2s === "play") parent.postMessage({ s2s: { tipo: "inicio" } }, "*");
  if (e.data && e.data.s2s === "pausa") parent.postMessage({ s2s: { tipo: "pausa" } }, "*");
});
document.addEventListener("click", () => { clics++; });
parent.postMessage({ s2s: { tipo: "listo" } }, "*");
</script></body></html>"""


@pytest.fixture(scope="module")
def navegador():
    try:
        with pw.sync_playwright() as p:
            nav = p.chromium.launch()
            yield nav
            nav.close()
    except Exception as e:                     # Chromium no instalado (`playwright install chromium`)
        pytest.skip(f"Chromium no disponible: {e}")


@pytest.fixture
def lista(tmp_path):
    for i in (1, 2, 3):
        (tmp_path / f"t0{i}.html").write_text(VIDEO_FALSO, encoding="utf-8")
    videos = [{"id": f"t0{i}", "archivo": f"t0{i}.html", "titulo": f"Tema {i}", "pregunta": "", "duracion": 40}
              for i in (1, 2, 3)]
    return reproductor.indice(tmp_path / "index.html", "Piloto", videos).as_uri()


def abrir(navegador, url, estado=None, tactil=False, init=""):
    ctx = navegador.new_context(has_touch=tactil, is_mobile=tactil, viewport={"width": 390, "height": 844})
    page = ctx.new_page()
    page.clock.set_fixed_time(HOY)
    if init:
        page.add_init_script(init)
    page.goto(url)
    if estado is not None:
        page.evaluate("e => localStorage.setItem('s2s:' + document.title, JSON.stringify(e))", estado)
        page.reload()
    return page


def video(page, archivo):
    page.wait_for_function(f"document.getElementById('v').src.endsWith('{archivo}')")
    f = page.query_selector("#v").content_frame()
    f.wait_for_load_state()
    f.wait_for_function("window.recibidos !== undefined")
    return f


def texto(page, sel):
    return page.text_content(sel).strip()


def test_migra_el_formato_viejo_y_abre_lo_que_toca_hoy(navegador, lista):
    page = abrir(navegador, lista, {"dia": "2026-11-12", "vistos": [0], "cur": 0})
    video(page, "t02.html")                                          # se abre lo que toca, no cur
    assert texto(page, "#lToca") == "Hoy toca" and texto(page, "#tToca") == "Tema 2"
    assert texto(page, "#nRacha") == "1" and texto(page, "#lRacha") == "día seguido"
    assert texto(page, "#nVistos") == "1 / 3"
    guardado = json.loads(page.evaluate("localStorage.getItem('s2s:' + document.title)"))
    assert guardado == {"v": 2, "cur": "t02", "dias": {"2026-11-12": ["t01"]}}


def test_al_terminar_marca_el_dia_y_pasa_al_siguiente(navegador, lista):
    estado = {"v": 2, "cur": "t01", "dias": {"2026-11-09": ["t01"], "2026-11-10": ["t01"], "2026-11-11": ["t02"]}}
    page = abrir(navegador, lista, estado)
    f = video(page, "t03.html")                                      # t03 nunca se vio
    assert texto(page, "#nRacha") == "3" and texto(page, "#lRacha") == "días seguidos"
    f.evaluate("parent.postMessage({ s2s: { tipo: 'fin' } }, '*')")
    page.wait_for_function("document.getElementById('nVistos').textContent === '3 / 3'")
    assert texto(page, "#nRacha") == "4"
    assert texto(page, "#tToca") == "Tema 1"                         # todos vistos: el visto hace más tiempo
    guardado = json.loads(page.evaluate("localStorage.getItem('s2s:' + document.title)"))
    assert guardado["dias"]["2026-11-12"] == ["t03"]


def test_borrar_progreso_con_confirmacion(navegador, lista):
    page = abrir(navegador, lista, {"v": 2, "cur": "t02", "dias": {"2026-11-12": ["t01"]}})
    video(page, "t02.html")
    page.click("#cero")
    page.click("#conf button.prim")
    page.wait_for_function("document.getElementById('nVistos').textContent === '0 / 3'")
    assert texto(page, "#nRacha") == "0" and texto(page, "#tToca") == "Tema 1"


def test_deslizar_cambia_de_video_y_el_toque_llega_al_video(navegador, lista):
    page = abrir(navegador, lista, tactil=True)
    f = video(page, "t01.html")
    caja = page.query_selector(".caja").bounding_box()
    cx, cy = caja["x"] + caja["width"] / 2, caja["y"] + caja["height"] / 2
    # con la tapa del video a la vista la capa no está: el toque llega al video ("Tocar para ver")
    assert page.evaluate("getComputedStyle(document.getElementById('capa')).display") == "none"
    page.touchscreen.tap(cx, cy)
    f.wait_for_function("window.clics === 1")
    # mientras suena, la capa toma los gestos
    f.evaluate("parent.postMessage({ s2s: { tipo: 'inicio' } }, '*')")
    page.wait_for_function("document.getElementById('capa').classList.contains('activa')")
    deslizar = """([x, y, dy]) => {
      const c = document.getElementById('capa'), o = { pointerId: 1, pointerType: 'touch', bubbles: true };
      c.dispatchEvent(new PointerEvent('pointerdown', { ...o, clientX: x, clientY: y }));
      c.dispatchEvent(new PointerEvent('pointerup', { ...o, clientX: x + 5, clientY: y + dy }));
    }"""
    page.evaluate(deslizar, [cx, cy, 0])                              # tocar = pausa
    f.wait_for_function("window.recibidos.some(m => m && m.s2s === 'pausa')")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'sigue' } }, '*')")
    page.wait_for_function("document.getElementById('capa').classList.contains('activa')")
    page.evaluate(deslizar, [cx, cy, -200])                           # hacia arriba = siguiente
    f2 = video(page, "t02.html")
    f2.wait_for_function("window.recibidos.some(m => m && m.s2s === 'play')")
    f2.evaluate("parent.postMessage({ s2s: { tipo: 'inicio' } }, '*')")
    page.wait_for_function("document.getElementById('capa').classList.contains('activa')")
    page.evaluate(deslizar, [cx, cy, 200])                            # hacia abajo = anterior
    video(page, "t01.html")


def test_en_escritorio_no_hay_capa(navegador, lista):
    page = abrir(navegador, lista)
    f = video(page, "t01.html")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'inicio' } }, '*')")
    page.wait_for_timeout(100)
    assert not page.evaluate("document.getElementById('capa').classList.contains('activa')")


def test_exportar_copia_al_portapapeles(navegador, lista):
    finge = "Object.defineProperty(navigator, 'clipboard', { value: { writeText: async t => { window.copiado = t; } } });"
    page = abrir(navegador, lista, {"v": 2, "cur": "t01", "dias": {"2026-11-12": ["t01"], "2026-11-11": ["t02"]}}, init=finge)
    video(page, "t03.html")
    page.click("#exp")
    page.wait_for_function("window.copiado !== undefined")
    x = json.loads(page.evaluate("window.copiado"))
    assert x["titulo"] == "Piloto" and x["racha"] == 2 and x["generado"].startswith("2026-11-12")
    assert x["dias"] == {"2026-11-11": ["t02"], "2026-11-12": ["t01"]}
    assert texto(page, "#aviso") == "Copiado al portapapeles"
    assert page.query_selector("#expTxt") is None


def test_exportar_sin_portapapeles_muestra_el_json(navegador, lista):
    sin = "Object.defineProperty(navigator, 'clipboard', { value: undefined });"
    page = abrir(navegador, lista, {"v": 2, "cur": "t01", "dias": {"2026-11-12": ["t01"]}}, init=sin)
    video(page, "t02.html")
    page.click("#exp")
    page.wait_for_selector("#expTxt")
    x = json.loads(page.input_value("#expTxt"))
    assert x["dias"] == {"2026-11-12": ["t01"]} and x["racha"] == 1
    assert page.evaluate("document.activeElement.id") == "expTxt"
    assert page.evaluate("(t => t.selectionEnd - t.selectionStart)(document.getElementById('expTxt'))") == len(
        page.input_value("#expTxt"))
