"""La app del teléfono (web/, armada con tools/sitio.py) en Chromium, con Playwright.

Se sirve _site/ con http.server en localhost (los service workers piden un origen seguro), se importa un
paquete de prueba y se reproduce. Los videos son páginas de juguete que hablan con la app igual que los
reales (postMessage "listo", "inicio", "fin"), pero terminan a los 0,3 s: no hace falta gsap, Piper ni audio.

Si Playwright o Chromium no están instalados, se saltean; con S2S_EXIGIR_NAVEGADOR=1 (el job "web" del CI)
fallan en vez de saltearse."""
import functools
import json
import os
import shutil
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
import sys  # noqa: E402
sys.path.insert(0, str(RAIZ / "tools"))
import sitio  # noqa: E402

EXIGIR = os.environ.get("S2S_EXIGIR_NAVEGADOR") == "1"
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    if EXIGIR:
        raise
    pytest.skip("playwright no está instalado", allow_module_level=True)

IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
VIDEO = """<!doctype html><html><head><title>{id}</title></head>
<body style="margin:0;height:100vh;background:#123;color:#fff">{id}<script>
const avisar = tipo => parent.postMessage({{ s2s: {{ tipo, video: "{id}" }} }}, "*");
window.VIDEO_ID = "{id}"; window.recibidos = [];
addEventListener("message", e => {{
  recibidos.push(e.data);
  // retomado tras una recarga ("desde"): se queda sonando, así el test lo puede mirar
  if (e.data && e.data.s2s === "play") {{ avisar("inicio"); if (!e.data.desde) setTimeout(() => avisar("fin"), 300); }}
}});
avisar("listo");
</script></body></html>"""


def paquete(titulo="Redes", ids=("t01", "t02"), sufijo=""):
    return {"v": 1, "titulo": titulo, "idioma": "es", "generado": "2026-11-13T10:00:00+00:00",
            "videos": [{"id": i, "titulo": f"Tema {i}{sufijo}", "pregunta": f"¿Pregunta {i}?", "duracion": 42,
                        "html": VIDEO.format(id=i)} for i in ids]}


def archivo(d, nombre="Redes.s2s.json"):
    return {"name": nombre, "mimeType": "application/json", "buffer": json.dumps(d).encode("utf-8")}


class _Callado(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def sitio_url(tmp_path_factory):
    d = sitio.armar(tmp_path_factory.mktemp("web") / "_site")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Callado, directory=str(d)))
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()


class _Cacheable(_Callado):
    """Como GitHub Pages: deja que el navegador guarde cada archivo 10 minutos en su caché HTTP."""
    def send_head(self):
        # http.server compara fechas al segundo: A y B se arman en el mismo segundo y daría 304 sin serlo
        del self.headers["If-Modified-Since"]
        return super().send_head()

    def end_headers(self):
        self.send_header("Cache-Control", "max-age=600")
        super().end_headers()


@pytest.fixture
def sitio_cambiante(tmp_path, monkeypatch):
    """Un _site/ servido con Cache-Control: max-age=600 que se puede volver a armar en el mismo puerto.
    Devuelve (url, publicar): publicar(marca) arma el sitio con una línea más en app.js que deja
    window.S2S_SITIO = marca, como un deploy nuevo."""
    d = tmp_path / "_site"
    web = tmp_path / "web"

    def publicar(marca):
        if web.exists():
            shutil.rmtree(web)
        shutil.copytree(sitio.WEB_ORIGINAL, web)
        app = web / "app.js"
        app.write_text(app.read_text(encoding="utf-8") + f"\nwindow.S2S_SITIO = {json.dumps(marca)};\n",
                       encoding="utf-8")
        monkeypatch.setattr(sitio, "WEB", web)
        sitio.armar(d)

    monkeypatch.setattr(sitio, "WEB_ORIGINAL", sitio.WEB, raising=False)
    publicar("A")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Cacheable, directory=str(d)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/", publicar
    srv.shutdown()


@pytest.fixture(scope="module")
def navegador():
    try:
        with sync_playwright() as p:
            nav = p.chromium.launch()
            yield nav
            nav.close()
    except Exception as e:                     # Chromium no instalado (`playwright install chromium`)
        if EXIGIR:
            raise
        pytest.skip(f"Chromium no disponible: {e}")


@pytest.fixture
def contexto(navegador):
    ctxs = []

    def nuevo(**kw):
        kw.setdefault("locale", "es-UY")
        kw.setdefault("viewport", {"width": 390, "height": 844})
        c = navegador.new_context(**kw)
        ctxs.append(c)
        return c
    yield nuevo
    for c in ctxs:
        c.close()


def abrir(ctx, url):
    page = ctx.new_page()
    page.goto(url)
    page.wait_for_function("document.documentElement.dataset.appLista === '1'")
    return page


def frame_del_video(page, vid):
    page.wait_for_function("document.getElementById('v').src.startsWith('blob:')")
    for _ in range(50):
        for f in page.frames:
            if f.url.startswith("blob:"):
                try:
                    if f.evaluate("window.VIDEO_ID") == vid:
                        return f
                except Exception:
                    pass
        page.wait_for_timeout(100)
    raise AssertionError(f"no apareció el video {vid}")


def esperar(page, js, arg=None, segundos=15):
    """Como wait_for_function, pero para una función async (wait_for_function no espera la promesa)."""
    for _ in range(segundos * 10):
        r = page.evaluate(js, arg)
        if r:
            return r
        page.wait_for_timeout(100)
    raise AssertionError(f"no pasó: {js}")


def importar(page, d, **kw):
    page.set_input_files("#archivo", archivo(d, **kw))


def texto(page, sel):
    return page.text_content(sel).strip()


def test_importar_reproducir_y_el_progreso_sigue_al_recargar(contexto, sitio_url):
    page = abrir(contexto(), sitio_url)
    assert page.is_visible("#vacio") and page.is_visible("#importar") and not page.is_visible("#instalar")
    assert texto(page, "#importar") == "Importar videos"
    importar(page, paquete())
    page.wait_for_selector("#reproductor:not([hidden])")
    assert "2 videos guardados" in texto(page, "#aviso")
    assert texto(page, "#titulo") == "Redes" and texto(page, "#tToca") == "Tema t01"
    page.wait_for_function("document.getElementById('espacio').textContent.includes('MB')")

    # el video corre aislado: sandbox sin allow-same-origin, no ve el almacenamiento de la app
    f = frame_del_video(page, "t01")
    assert f.evaluate("(() => { try { return localStorage.length; } catch (e) { return 'bloqueado'; } })()") == "bloqueado"
    assert f.evaluate("(() => { try { return parent.document.title; } catch (e) { return 'bloqueado'; } })()") == "bloqueado"
    url_t01 = page.eval_on_selector("#v", "v => v.src")

    page.click("#toca")                                     # play -> inicio -> fin (0,3 s)
    page.wait_for_function("document.getElementById('nVistos').textContent === '1 / 2'")
    frame_del_video(page, "t02")                            # pasa solo al siguiente
    assert texto(page, "#nRacha") == "1" and texto(page, "#tToca") == "Tema t02"
    # la URL del video anterior se liberó
    assert page.evaluate("u => fetch(u).then(() => 'viva', () => 'liberada')", url_t01) == "liberada"
    guardado = json.loads(page.evaluate("localStorage.getItem('s2s:Redes')"))
    assert list(guardado["dias"].values()) == [["t01"]] and guardado["cur"] == "t02"

    page.reload()
    page.wait_for_function("document.documentElement.dataset.appLista === '1'")
    assert texto(page, "#nVistos") == "1 / 2" and texto(page, "#nRacha") == "1"
    assert texto(page, "#tToca") == "Tema t02"
    frame_del_video(page, "t02")
    assert page.is_visible("li.visto") and texto(page, "li.visto .num") == "✓"


def test_un_archivo_que_no_es_paquete_da_un_error_claro_y_no_guarda_nada(contexto, sitio_url):
    page = abrir(contexto(), sitio_url)
    page.set_input_files("#archivo", {"name": "foto.jpg", "mimeType": "image/jpeg", "buffer": b"\xff\xd8\xff\xe0"})
    page.wait_for_selector("#error:not([hidden])")
    assert "no es un paquete de scroll to study" in texto(page, "#error")
    malo = paquete()
    del malo["videos"][1]["duracion"]
    importar(page, malo)
    page.wait_for_function("document.getElementById('error').textContent.includes('videos[1].duracion')")
    assert page.is_visible("#vacio") and not page.is_visible("#reproductor")
    assert page.evaluate("""new Promise(ok => { const r = indexedDB.open('s2s-app');
        r.onsuccess = () => { const q = r.result.transaction('paquetes').objectStore('paquetes').count();
                              q.onsuccess = () => ok(q.result); }; })""") == 0


def test_un_paquete_mas_nuevo_que_la_app_dice_que_se_actualice_la_app(contexto, sitio_url):
    page = abrir(contexto(), sitio_url)
    page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=15000)
    page.evaluate("""navigator.serviceWorker.getRegistration().then(r => {
        window.pedidos = 0; const u = r.update.bind(r); r.update = () => { pedidos++; return u(); }; })""")
    importar(page, dict(paquete(), v=99, hecho_con="9.9.9"))
    page.wait_for_selector("#error:not([hidden])")
    assert texto(page, "#error") == ("Este paquete es de una versión más nueva que la app. Cerrá la app y abrila con "
                                     "internet para actualizarla. (Lo armó scroll-to-study 9.9.9.)")
    assert page.evaluate("window.pedidos") == 1                 # y ya busca la versión nueva
    assert page.is_visible("#vacio")


def test_varios_paquetes_reimportar_conserva_el_progreso_y_borrar(contexto, sitio_url):
    page = abrir(contexto(), sitio_url)
    importar(page, paquete())
    page.wait_for_selector("#reproductor:not([hidden])")
    frame_del_video(page, "t01")
    page.click("#toca")
    page.wait_for_function("document.getElementById('nVistos').textContent === '1 / 2'")

    importar(page, paquete("Bases de datos", ("b1",)), nombre="Bases.s2s.json")
    page.wait_for_function("document.getElementById('titulo').textContent === 'Bases de datos'")
    assert page.is_visible("#paquetes")
    assert page.eval_on_selector_all("#paquetes option", "os => os.map(o => o.value)") == ["Bases de datos", "Redes"]
    assert texto(page, "#nVistos") == "0 / 1"

    page.select_option("#paquetes", "Redes")
    page.wait_for_function("document.getElementById('titulo').textContent === 'Redes'")
    assert texto(page, "#nVistos") == "1 / 2"

    # reimportar el mismo título: reemplaza los videos (t02 sale, t03 entra) y el progreso queda
    importar(page, paquete("Redes", ("t01", "t03"), sufijo=" (nuevo)"))
    page.wait_for_function("document.getElementById('aviso').textContent.includes('Se actualizó')")
    assert texto(page, "#nVistos") == "1 / 2"
    assert page.eval_on_selector_all("#lista .t b", "bs => bs.map(b => b.textContent)") == ["Tema t01 (nuevo)", "Tema t03 (nuevo)"]
    claves = page.evaluate("""new Promise(ok => { const r = indexedDB.open('s2s-app');
        r.onsuccess = () => { const q = r.result.transaction('videos').objectStore('videos').getAllKeys();
                              q.onsuccess = () => ok(q.result); }; })""")
    assert sorted(claves) == sorted(['["Bases de datos","b1"]', '["Redes","t01"]', '["Redes","t03"]'])

    # borrar pide confirmación: con "no" no pasa nada
    page.once("dialog", lambda d: d.dismiss())
    page.click("#borrarPaq")
    assert texto(page, "#titulo") == "Redes"
    page.once("dialog", lambda d: d.accept())
    page.click("#borrarPaq")
    page.wait_for_function("document.getElementById('titulo').textContent === 'Bases de datos'")
    assert not page.is_visible("#paquetes")
    assert page.evaluate("localStorage.getItem('s2s:Redes')") is not None     # si lo reimporta, el progreso sigue


def test_abre_sin_conexion_desde_el_service_worker(contexto, sitio_url):
    ctx = contexto()
    page = abrir(ctx, sitio_url)
    importar(page, paquete())
    page.wait_for_selector("#reproductor:not([hidden])")
    page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=15000)
    page.wait_for_function("""caches.keys().then(ks => ks.some(k => k.startsWith('s2s-app-')))""")

    ctx.set_offline(True)
    page.reload()
    page.wait_for_function("document.documentElement.dataset.appLista === '1'")
    assert texto(page, "#titulo") == "Redes"
    frame_del_video(page, "t01")
    page.click("#toca")
    page.wait_for_function("document.getElementById('nVistos').textContent === '1 / 2'")
    # una pestaña nueva, también sin red
    otra = abrir(ctx, sitio_url)
    assert texto(otra, "#titulo") == "Redes"


def test_la_cache_nueva_del_service_worker_no_sale_de_la_cache_http(contexto, sitio_cambiante):
    """GitHub Pages deja cachear 10 minutos: la caché de una versión nueva tiene que tener los archivos nuevos,
    no los que el navegador guardó de la anterior."""
    url, publicar = sitio_cambiante
    page = abrir(contexto(), url)
    page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=15000)
    assert page.evaluate("window.S2S_SITIO") == "A"
    # el navegador ya tiene app.js de A en su caché HTTP (max-age=600)
    assert "S2S_SITIO = \"A\"" in page.evaluate("fetch('app.js', { cache: 'force-cache' }).then(r => r.text())")
    viejas = page.evaluate("caches.keys()")
    publicar("B")
    page.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update())")
    # la versión nueva se instala en una caché propia (con todos los archivos) y borra la vieja
    texto_app = esperar(page, """async vs => {
        const ks = await caches.keys();
        if (ks.length !== 1 || vs.includes(ks[0])) return null;
        const r = await (await caches.open(ks[0])).match('app.js');
        return r ? r.text() : null; }""", viejas)
    assert "S2S_SITIO = \"B\"" in texto_app and "S2S_SITIO = \"A\"" not in texto_app


def version_de(url):
    import urllib.request
    return json.loads(urllib.request.urlopen(url + "version.json").read())["app"]


def test_una_version_nueva_avisa_y_actualizar_corre_el_codigo_nuevo(contexto, sitio_cambiante):
    url, publicar = sitio_cambiante
    page = abrir(contexto(), url)
    page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=15000)
    version_a = version_de(url)
    page.wait_for_function("v => document.getElementById('version').textContent === 'versión ' + v", arg=version_a)
    assert page.evaluate("window.S2S_SITIO") == "A"
    page.wait_for_timeout(300)
    assert not page.is_visible("#nueva")                    # la primera instalación no es una versión nueva
    importar(page, paquete())
    f = frame_del_video(page, "t01")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'inicio', t: 0, video: 't01' } }, '*')")

    publicar("B")
    # volver a primer plano busca la versión nueva (en el iPhone la app casi nunca arranca de cero)
    page.evaluate("""Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
                     document.dispatchEvent(new Event('visibilitychange'))""")
    page.wait_for_selector("#nueva:not([hidden])", timeout=15000)
    assert texto(page, "#nuevaTxt") == "Hay una versión nueva de la app" and texto(page, "#actualizar") == "Actualizar"
    # no se recarga sola: sigue corriendo A, con el video donde estaba
    page.wait_for_timeout(500)
    assert page.evaluate("window.S2S_SITIO") == "A" and frame_del_video(page, "t01")

    page.click("#actualizar")
    page.wait_for_function("document.documentElement.dataset.appLista === '1' && window.S2S_SITIO === 'B'")
    version_b = version_de(url)
    assert version_b != version_a
    page.wait_for_function("v => document.getElementById('version').textContent === 'versión ' + v", arg=version_b)
    assert not page.is_visible("#nueva") and texto(page, "#titulo") == "Redes"


def test_iphone_sin_instalar_explica_como_instalarla(contexto, sitio_url):
    page = abrir(contexto(user_agent=IPHONE, locale="en-US", is_mobile=True, has_touch=True), sitio_url)
    assert page.is_visible("#instalar") and not page.is_visible("#importar") and not page.is_visible("#vacio")
    assert texto(page, "#iTitulo") == "First, install the app"
    assert "Add to Home Screen" in texto(page, "#iPaso2")
    assert "separate from Safari" in texto(page, "#iSeparado")
    page.click("#importarIgual")
    assert page.is_visible("#importar") and not page.is_visible("#instalar")
    assert texto(page, "#importar") == "Import videos"


def test_iphone_con_la_app_instalada_muestra_importar(contexto, sitio_url):
    ctx = contexto(user_agent=IPHONE, is_mobile=True, has_touch=True)
    ctx.add_init_script("Object.defineProperty(navigator, 'standalone', { get: () => true })")
    page = abrir(ctx, sitio_url)
    assert page.is_visible("#importar") and not page.is_visible("#instalar")


# --- preguntas después del video (paquete v2) ------------------------------------------------------

HOY = datetime(2026, 11, 12, 12, 0)
PREGUNTAS = [
    {"id": "q1", "texto": "¿A qué tabla apunta la FK de multa?", "opciones": ["A socio", "A prestamo", "A ejemplar"],
     "correcta": 1, "explicacion": "Apunta a prestamo con id_prestamo.", "general": False},
    {"id": "q2", "texto": "¿Cómo se ubica una FK?", "opciones": ["Por el nombre", "Por la dependencia", "Al azar"],
     "correcta": 1, "explicacion": "Método general, no está en tu material: por la dependencia.", "general": True},
]


def paquete_v2():
    """t01 trae preguntas; t02 no."""
    d = paquete()
    d["v"] = 2
    for x in d["videos"]:
        x["preguntas"] = PREGUNTAS if x["id"] == "t01" else []
    return d


def abrir_el_dia(ctx, url, fecha=HOY):
    page = ctx.new_page()
    page.clock.set_fixed_time(fecha)
    page.goto(url)
    page.wait_for_function("document.documentElement.dataset.appLista === '1'")
    return page


def test_preguntas_despues_del_video_y_el_tema_vuelve_manana(contexto, sitio_url):
    page = abrir_el_dia(contexto(), sitio_url)
    importar(page, paquete_v2())
    page.wait_for_selector("#reproductor:not([hidden])")
    frame_del_video(page, "t01")
    assert texto(page, "#nHoy") == "2" and texto(page, "#lHoy") == "para hoy"
    page.click("#toca")                                     # play -> fin (0,3 s) -> preguntas
    page.wait_for_selector(".caja .s2s-quiz")
    assert texto(page, ".s2s-quiz .q-num") == "Pregunta 1 de 2"
    assert texto(page, ".s2s-quiz h2") == "¿A qué tabla apunta la FK de multa?"

    page.click(".s2s-quiz .q-op >> text=A prestamo")        # bien
    assert texto(page, ".s2s-quiz .q-exp b") == "¡Bien!"
    page.click(".s2s-quiz .q-sig")
    assert texto(page, ".s2s-quiz .q-gen") == "método general · no está en tu material"
    page.click(".s2s-quiz .q-op >> text=Por el nombre")     # mal
    assert page.eval_on_selector_all(".s2s-quiz .q-op", "bs => bs.map(b => b.className)") == [
        "q-op mal", "q-op bien", "q-op"]
    assert texto(page, ".s2s-quiz .q-exp b") == "No era esa."
    assert "por la dependencia" in texto(page, ".s2s-quiz .q-exp")
    page.click(".s2s-quiz .q-sig")
    assert texto(page, ".s2s-quiz .q-res") == "1 de 2 correctas"
    assert texto(page, ".s2s-quiz .q-vuelve") == "Este tema vuelve mañana."
    assert texto(page, ".s2s-quiz .q-seguir") == "Seguir: Tema t02"
    g = json.loads(page.evaluate("localStorage.getItem('s2s:Redes')"))
    assert g["repaso"] == {"t01": {"nivel": 0, "proxima": "2026-11-13",
                                   "historial": [{"fecha": "2026-11-12", "aciertos": 1, "total": 2}]}}
    assert g["dias"] == {"2026-11-12": ["t01"]}

    page.reload()
    page.wait_for_function("document.documentElement.dataset.appLista === '1'")
    frame_del_video(page, "t02")                            # hoy toca t02 (nuevo); t01 vuelve mañana
    assert page.query_selector(".s2s-quiz") is None
    assert texto(page, "#lista li:nth-child(1) .s2s-rep") == "Al día · vuelve mañana"
    assert texto(page, "#lista li:nth-child(2) .s2s-rep") == "Nuevo"
    assert texto(page, "#nHoy") == "1" and texto(page, "#tToca") == "Tema t02"


def test_saltear_preguntas_en_la_app(contexto, sitio_url):
    page = abrir_el_dia(contexto(), sitio_url)
    importar(page, paquete_v2())
    page.wait_for_selector("#reproductor:not([hidden])")
    frame_del_video(page, "t01")
    page.click("#toca")
    page.wait_for_selector(".caja .s2s-quiz")
    page.click(".s2s-quiz >> text=Saltear preguntas")
    frame_del_video(page, "t02")                            # sigue con lo que toca hoy (y lo reproduce)
    page.wait_for_function("document.getElementById('nVistos').textContent === '2 / 2'")
    assert page.query_selector(".s2s-quiz") is None         # t02 no tiene preguntas
    g = json.loads(page.evaluate("localStorage.getItem('s2s:Redes')"))
    assert g["repaso"] == {} and g["dias"] == {"2026-11-12": ["t01", "t02"]}
    assert texto(page, "#lista li:nth-child(1) .s2s-rep") == "Al día"
    assert texto(page, "#tToca") == "Nada pendiente hoy" and texto(page, "#nHoy") == "0"


def test_si_el_video_se_recarga_solo_la_app_lo_retoma_y_anota_el_corte(contexto, sitio_url):
    ctx = contexto()
    ctx.add_init_script("Object.defineProperty(navigator, 'clipboard', "
                        "{ value: { writeText: async t => { window.copiado = t; } } });")
    page = abrir_el_dia(ctx, sitio_url)
    importar(page, paquete())
    page.wait_for_selector("#reproductor:not([hidden])")
    f = frame_del_video(page, "t01")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'inicio', t: 0, video: 't01' } }, '*')")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'tiempo', t: 7.25, video: 't01' } }, '*')")
    # un iframe sandbox no puede recargar su propia URL blob: se recarga desde afuera, sin pasar por abrir()
    # (para la app es lo mismo que cuando iOS lo recarga solo)
    page.evaluate("(v => { v.src = v.src; })(document.getElementById('v'))")
    f = frame_del_video(page, "t01")
    f.wait_for_function("window.recibidos.some(m => m && m.s2s === 'play' && m.desde === 7.25)")
    cortes = json.loads(page.evaluate("localStorage.getItem('s2s-cortes:Redes')"))
    assert [(c["video"], c["t"]) for c in cortes] == [("t01", 7.25)] and cortes[0]["fecha"].startswith("2026-11-12")
    assert json.loads(page.evaluate("localStorage.getItem('s2s:Redes')"))["dias"] == {}
    page.click("#exp")
    page.wait_for_function("window.copiado !== undefined")
    assert json.loads(page.evaluate("window.copiado"))["cortes"] == cortes


def test_si_la_app_entera_se_corto_sonando_anota_el_corte_y_ofrece_seguir_desde_ahi(contexto, sitio_url):
    """En el iPhone, sin memoria se recarga la app entera (no solo el iframe): queda la marca de "sonando", y al
    volver a abrir se anota el corte y se abre ese video quieto en ese segundo, sin reproducir solo."""
    ctx = contexto()
    page = abrir_el_dia(ctx, sitio_url)
    importar(page, paquete())
    page.wait_for_selector("#reproductor:not([hidden])")
    frame_del_video(page, "t01")
    page.click("#sig")
    f = frame_del_video(page, "t02")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'inicio', t: 0, video: 't02' } }, '*')")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'tiempo', t: 31.5, video: 't02' } }, '*')")
    page.wait_for_function("localStorage.getItem('s2s-marca:Redes') !== null")
    m = json.loads(page.evaluate("localStorage.getItem('s2s-marca:Redes')"))
    assert (m["video"], m["t"]) == ("t02", 31.5)
    # la recarga de iOS no avisa nada (una recarga normal, con la página sonando, borra la marca: no es un corte):
    # con el video quieto se deja la marca como quedaría y se recarga la página
    f.evaluate("parent.postMessage({ s2s: { tipo: 'pausa', t: 31.5, video: 't02' } }, '*')")
    page.wait_for_function("localStorage.getItem('s2s-marca:Redes') === null")
    page.evaluate("m => localStorage.setItem('s2s-marca:Redes', m)", json.dumps(m))
    page.reload()
    page2 = page
    page2.wait_for_function("document.documentElement.dataset.appLista === '1'")
    f = frame_del_video(page2, "t02")
    f.wait_for_function("window.recibidos.some(m => m && m.s2s === 'ir')")
    assert f.evaluate("window.recibidos") == [{"s2s": "ir", "t": 31.5}]
    cortes = json.loads(page2.evaluate("localStorage.getItem('s2s-cortes:Redes')"))
    assert [(c["video"], c["t"]) for c in cortes] == [("t02", 31.5)]
    assert page2.evaluate("localStorage.getItem('s2s-marca:Redes')") is None
    assert texto(page2, "#tAhora") == "Tema t02"


def test_cerrar_la_app_a_mitad_de_un_video_ofrece_seguir_y_no_es_un_corte(contexto, sitio_url):
    """Cerrar la app (pagehide) con un video sonando deja la marca con cerrada: true: al volver se ofrece
    "Seguir desde m:ss", pero no se anota un corte."""
    page = abrir_el_dia(contexto(), sitio_url)
    importar(page, paquete())
    page.wait_for_selector("#reproductor:not([hidden])")
    frame_del_video(page, "t01")
    page.click("#sig")
    f = frame_del_video(page, "t02")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'inicio', t: 0, video: 't02' } }, '*')")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'tiempo', t: 12.5, video: 't02' } }, '*')")
    page.wait_for_function("localStorage.getItem('s2s-marca:Redes') !== null")
    page.reload()
    page.wait_for_function("document.documentElement.dataset.appLista === '1'")
    f = frame_del_video(page, "t02")
    f.wait_for_function("window.recibidos.some(m => m && m.s2s === 'ir')")
    assert f.evaluate("window.recibidos") == [{"s2s": "ir", "t": 12.5}]     # quieto ahí: no reproduce solo
    assert page.evaluate("localStorage.getItem('s2s-cortes:Redes')") is None
    assert page.evaluate("localStorage.getItem('s2s-marca:Redes')") is None
    assert texto(page, "#tAhora") == "Tema t02"


def test_una_marca_de_hace_mas_de_12_horas_no_ofrece_seguir(contexto, sitio_url):
    page = abrir_el_dia(contexto(), sitio_url)
    importar(page, paquete())
    page.wait_for_selector("#reproductor:not([hidden])")
    frame_del_video(page, "t01")
    vieja = {"video": "t02", "t": 31.5, "fecha": "2026-11-11T20:00:00.000Z"}
    page.evaluate("m => localStorage.setItem('s2s-marca:Redes', m)", json.dumps(vieja))
    page.reload()
    page.wait_for_function("document.documentElement.dataset.appLista === '1'")
    f = frame_del_video(page, "t01")                            # lo que toca hoy
    page.wait_for_timeout(200)
    assert f.evaluate("window.recibidos") == []
    assert page.evaluate("localStorage.getItem('s2s-cortes:Redes')") is None
    assert page.evaluate("localStorage.getItem('s2s-marca:Redes')") is None


def test_la_app_no_cuenta_un_video_que_casi_no_sono(contexto, sitio_url):
    page = abrir_el_dia(contexto(), sitio_url)
    importar(page, paquete_v2())
    page.wait_for_selector("#reproductor:not([hidden])")
    f = frame_del_video(page, "t01")
    f.evaluate("parent.postMessage({ s2s: { tipo: 'fin', t: 42, duracion: 42, reproducidos: 12, video: 't01' } }, '*')")
    page.wait_for_timeout(300)
    assert page.query_selector(".s2s-quiz") is None and texto(page, "#nVistos") == "0 / 2"
    f.evaluate("parent.postMessage({ s2s: { tipo: 'fin', t: 42, duracion: 42, reproducidos: 30, video: 't01' } }, '*')")
    page.wait_for_selector(".caja .s2s-quiz")
    assert texto(page, "#nVistos") == "1 / 2"


def test_la_app_tiene_los_dos_modos(contexto, sitio_url):
    """Modo normal: arrastrar sobre el video no cambia de video. Feed: sí, y la X vuelve a la lista."""
    ctx = contexto(has_touch=True, is_mobile=True)
    page = abrir_el_dia(ctx, sitio_url)
    importar(page, paquete())
    page.wait_for_selector("#reproductor:not([hidden])")
    f = frame_del_video(page, "t01")
    assert texto(page, "#feed") == "Pantalla completa"
    f.evaluate("parent.postMessage({ s2s: { tipo: 'inicio', t: 0, duracion: 42, reproducidos: 0, video: 't01' } }, '*')")
    caja = page.query_selector(".caja").bounding_box()
    x, y = caja["x"] + caja["width"] / 2, caja["y"] + caja["height"] / 2
    arrastrar(page, x, y + 120, y - 120)
    page.wait_for_timeout(500)
    assert frame_del_video(page, "t01") and page.query_selector(".s2s-capa.activa") is None

    page.click("#feed")
    caja = page.query_selector(".caja").bounding_box()
    assert (caja["x"], caja["y"], caja["width"], caja["height"]) == (0, 0, 390, 844)
    f.evaluate("parent.postMessage({ s2s: { tipo: 'inicio', t: 0, duracion: 42, reproducidos: 0, video: 't01' } }, '*')")
    page.wait_for_selector(".s2s-capa.activa")
    arrastrar(page, 195, 600, 250)
    frame_del_video(page, "t02")
    page.click(".s2s-salir")
    assert not page.evaluate("document.querySelector('.caja').classList.contains('s2s-feed')")


@pytest.mark.parametrize("ios", [False, True])
def test_la_app_pide_playback_y_arranca_el_silencio_en_el_primer_toque(contexto, sitio_url, ios):
    """Que el audio suene con el iPhone en modo silencio: la categoría "playback" se pide en la página principal
    (dentro del iframe del video no alcanza) y el primer toque arranca un <audio> de silencio en bucle. Anda
    igual con o sin navigator.audioSession."""
    ctx = contexto()
    if ios:
        ctx.add_init_script("Object.defineProperty(navigator, 'audioSession', "
                            "{ configurable: true, value: { type: 'auto' } });")
    ctx.add_init_script("window.audios = []; const _Audio = window.Audio;"
                        "window.Audio = function (src) { const a = new _Audio(src); audios.push(a); return a; };")
    errores = []
    page = ctx.new_page()
    page.on("pageerror", lambda e: errores.append(str(e)))
    page.clock.set_fixed_time(HOY)
    page.goto(sitio_url)
    page.wait_for_function("document.documentElement.dataset.appLista === '1'")
    assert page.evaluate("!!navigator.audioSession") == ios
    if ios:
        assert page.evaluate("navigator.audioSession.type") == "playback"
    importar(page, paquete())
    page.wait_for_selector("#reproductor:not([hidden])")
    assert page.evaluate("audios.length") == 0
    page.click("#sig")
    page.wait_for_function("audios.length === 1")
    assert page.evaluate("[audios[0].loop, audios[0].src.startsWith('data:audio/mpeg;base64,')]") == [True, True]
    assert errores == []


def arrastrar(page, x, y0, y1, pasos=6):
    cdp = page.context.new_cdp_session(page)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y0}]})
    for k in range(1, pasos + 1):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y0 + (y1 - y0) * k / pasos}]})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    cdp.detach()
