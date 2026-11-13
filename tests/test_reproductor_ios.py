"""El toque en #s2s-tapa arranca el audio sin errores de consola, con o sin navigator.audioSession.

Prueba el PLAYER_JS real de reproductor.py en Chromium (Playwright). Se monta en una página mínima
con una línea de tiempo de juguete y un MP3 que sí decodifica, así no hace falta gsap, engine.js ni
Piper. Si Playwright o Chromium no están instalados, el test se saltea (la suite sigue en verde)."""
import json

import pytest

import reproductor

pw = pytest.importorskip("playwright.sync_api")


def _pagina(ios: bool) -> str:
    """Página autocontenida con el PLAYER_JS real. `ios` finge navigator.audioSession (iOS 17+)."""
    player = reproductor.PLAYER_JS.replace("__SILENCIO_MP3__", reproductor.mp3_silencio())
    mp3 = reproductor.mp3_silencio(0.5)                       # un MP3 válido para que decodeAudioData no falle
    tx = json.dumps(reproductor.TEXTOS["es"], ensure_ascii=False)
    finge = ("Object.defineProperty(navigator, 'audioSession', "
             "{ configurable: true, value: { type: 'auto' } });") if ios else ""
    return (
        "<!doctype html><html><head><meta charset='utf-8'></head><body>"
        "<div id='root'></div><div id='s2s-barra'></div>"
        "<div id='s2s-tapa'><button>Tocar</button></div>"
        f"<script type='application/octet-stream' id='s2s-mp3'>{mp3}</script>"
        "<script>"
        f"{finge}"
        "window.__timelines = { main: { duration: () => 10, seek: () => {} } };"
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
        pytest.skip(f"Chromium de Playwright no disponible: {e}")


@pytest.mark.parametrize("ios", [False, True])
def test_toque_arranca_sin_errores(tmp_path, navegador, ios):
    page = navegador.new_page()
    errores = []
    page.on("pageerror", lambda e: errores.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errores.append(m.text))

    archivo = tmp_path / f"player_{ios}.html"
    archivo.write_text(_pagina(ios), encoding="utf-8")
    page.goto(archivo.resolve().as_uri())
    page.wait_for_selector("html[data-s2s-listo]", state="attached", timeout=20000)

    page.click("#s2s-tapa")
    # el video arrancó: reproducir() oculta la tapa justo después de empezar la fuente de audio
    # (señal estable; el reloj de audio del headless no siempre avanza sin dispositivo de sonido)
    page.wait_for_function("document.getElementById('s2s-tapa').hidden === true", timeout=8000)

    assert errores == [], f"el toque dejó errores en consola: {errores}"
    assert page.evaluate("typeof window.__s2s.ahora() === 'number'")
    assert page.evaluate("!!window.navigator.audioSession") == ios
    if ios:                                                    # iOS 17+: se pidió la categoría playback
        assert page.evaluate("navigator.audioSession.type") == "playback"
    page.close()


def test_la_lista_puede_pausar_con_un_mensaje(tmp_path, navegador):
    """La capa de gestos de la lista tapa el video mientras suena: el toque llega como postMessage "pausa"."""
    page = navegador.new_page()
    archivo = tmp_path / "player_pausa.html"
    archivo.write_text(_pagina(False), encoding="utf-8")
    page.goto(archivo.resolve().as_uri())
    page.wait_for_selector("html[data-s2s-listo]", state="attached", timeout=20000)
    page.click("#s2s-tapa")
    page.wait_for_function("document.getElementById('s2s-tapa').hidden === true", timeout=8000)
    page.evaluate("window.postMessage({ s2s: 'pausa' }, '*')")
    page.wait_for_function("document.getElementById('s2s-tapa').hidden === false", timeout=8000)
    assert page.text_content("#s2s-tapa button") == reproductor.TEXTOS["es"]["seguir"]
    page.close()
