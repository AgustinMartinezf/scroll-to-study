#!/usr/bin/env python3
"""index.html de engine.py -> un video que se reproduce solo en el navegador (un único .html).

    python3 reproductor.py CARPETA SALIDA.html

engine.py arma una composición de HyperFrames: una línea de tiempo GSAP en pausa, "clips" que se
muestran según data-start/data-duration y varios <audio> sueltos. Acá se hace lo que haría un runtime:
  - se mezclan todos los <audio> en una pista MP3 a −14 LUFS (un celular no sincroniza 30 audios sueltos);
  - el audio es el reloj: en cada cuadro, tl.seek(tiempo del audio) y visibilidad de los clips;
  - el MP3 va como texto y se decodifica con Web Audio (sin <audio> ni URL data:, que algunos
    visores bloquean);
  - se incrustan Inter y JetBrains Mono (el layout se calculó con esas fuentes) y engine.js corre
    recién cuando cargaron, porque mide posiciones con getBoundingClientRect;
  - el lienzo de 1080x1920 se escala a la pantalla después de que engine.js midió.
El resultado no depende de nada externo: audio, fuentes y gsap van adentro.
"""
from __future__ import annotations

import base64
import html
import io
import json
import re
import sys
from pathlib import Path

import sonido
from config import CFG

AUDIO_RE = re.compile(r"<audio\b([^>]*)></audio>")
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
# dos scripts seguidos: los datos (const S = …) y engine.js
SCRIPT_ENGINE_RE = re.compile(r"<script>(const S = .*?)</script>\s*<script>(.*?)</script>", re.S)
GSAP_TAG = '<script src="assets/gsap.min.js"></script>'

PLAYER_CSS = """
html, body { width:100% !important; height:100% !important; background:#000 !important; }
html { touch-action:manipulation; }   /* sin zoom por doble toque: el doble toque salta 5 s */
#root { position:fixed !important; left:0; top:0; transform-origin:0 0; }
#s2s-tapa { position:fixed; inset:0; display:flex; align-items:center; justify-content:center;
  background:rgba(0,0,0,.45); z-index:99; cursor:pointer; -webkit-tap-highlight-color:transparent; }
#s2s-tapa[hidden] { display:none; }
#s2s-tapa button { font:800 20px/1 Inter, sans-serif; color:#04170b; background:#1fbf6a; border:0;
  border-radius:999px; padding:18px 30px; pointer-events:none; }
/* la barra se ve fina pero se agarra en 36 px de alto, por encima de la zona segura de abajo (la del
   gesto de inicio del iPhone), y queda arriba de la tapa: se puede saltar antes del primer toque */
#s2s-pista { position:fixed; left:0; right:0; bottom:env(safe-area-inset-bottom, 0px); height:36px; z-index:100;
  cursor:pointer; touch-action:none; -webkit-tap-highlight-color:transparent; }
#s2s-pista::before { content:""; position:absolute; left:0; right:0; bottom:0; height:4px; background:rgba(255,255,255,.22); }
#s2s-barra { position:absolute; left:0; bottom:0; height:4px; width:0; background:#1fbf6a; }
#s2s-pista.arrastrando::before, #s2s-pista.arrastrando #s2s-barra { height:10px; }
#s2s-salto { position:fixed; top:50%; left:50%; z-index:101; transform:translate(-50%, -50%); pointer-events:none;
  font:800 22px/1 Inter, sans-serif; white-space:nowrap; color:#fff; background:rgba(0,0,0,.6); border-radius:999px; padding:14px 20px;
  opacity:0; transition:opacity .3s; }
#s2s-salto.ver { opacity:1; transition:none; }
"""

TEXTOS = {
    "es": {"tocar": "Tocar para ver", "seguir": "Seguir", "otraVez": "Ver de nuevo", "cargando": "Cargando…",
           "error": "No se pudo reproducir", "barra": "Posición del video",
           "sub": "Un video por día, en orden. Cada uno prepara una pregunta que te pueden hacer."},
    "en": {"tocar": "Tap to play", "seguir": "Resume", "otraVez": "Watch again", "cargando": "Loading…",
           "error": "Couldn't play", "barra": "Video position",
           "sub": "One video a day, in order. Each one prepares a question you may get."},
}


def marcado(tx: dict) -> str:
    """Los controles que se suman al video: la barra (que se arrastra), el aviso de ±5 s y la tapa."""
    return (f'<div id="s2s-pista" role="slider" aria-label="{html.escape(tx["barra"])}" aria-valuemin="0">'
            '<div id="s2s-barra"></div></div><div id="s2s-salto" aria-hidden="true"></div>'
            f'<div id="s2s-tapa"><button>{html.escape(tx["tocar"])}</button></div>')


PLAYER_JS = """
(function () {
  // El audio se decodifica con Web Audio desde el propio archivo: no usa un elemento de audio ni URLs
  // data:, que algunos visores (vistas previas, apps) bloquean por su política de contenido.
  const $ = id => document.getElementById(id);
  const root = $("root"), tapa = $("s2s-tapa"), boton = tapa.querySelector("button");
  const pista = $("s2s-pista"), barra = $("s2s-barra"), marca = $("s2s-salto");
  const tl = window.__timelines.main, D = tl.duration();
  const clips = [...document.querySelectorAll("#root .clip")].map(e => ({ e, s: +e.dataset.start, d: +e.dataset.duration }));
  const SALTO = 5, DOBLE_MS = 250;
  let ctx = null, buffer = null, fuente = null, t0 = 0, pos = 0, sonando = false, silencio = null;
  let empezado = false;      // ya sonó alguna vez (antes de eso, un salto también arranca)
  let arrastre = null;       // el tiempo bajo el dedo mientras se arrastra la barra
  let pendiente = null;      // el arranque en curso (decodificar puede tardar)
  let tramo = null;          // desde dónde suena el tramo actual
  const tramos = [];         // [desde, hasta] de lo que ya sonó
  const acotar = t => Math.max(0, Math.min(D, t));
  const ahora = () => sonando ? Math.min(D, ctx.currentTime - t0) : pos;
  // Segundos que sonaron de verdad, sin contar dos veces lo que se vio dos veces: la lista marca el
  // video como visto (y pregunta) solo si llegan al 70 % de la duración.
  function reproducidos() {
    const ts = tramos.slice();
    if (sonando && tramo !== null) ts.push([tramo, ahora()]);
    ts.sort((a, b) => a[0] - b[0]);
    let total = 0, hasta = 0;
    for (const [a, b] of ts) { if (b > hasta) { total += b - Math.max(a, hasta); hasta = b; } }
    return total;
  }
  function desbloquearSilencio() {
    // Respaldo para iOS anterior a 17 (sin navigator.audioSession): un elemento Audio() en bucle usa
    // el canal "media", que suena con el teléfono en silencio, y arrastra a Web Audio con él. Todo en
    // try/catch: algunos visores bloquean ese elemento; si falla, el video sigue igual que hoy.
    if (silencio) return;
    try {
      silencio = new Audio("data:audio/mpeg;base64,__SILENCIO_MP3__");
      silencio.loop = true;
      const pr = silencio.play();
      if (pr && pr.catch) pr.catch(() => {});
    } catch (e) { silencio = null; }
  }
  const avisar = (tipo, extra) => {
    const detalle = Object.assign({ tipo, t: +ahora().toFixed(2), video: document.title, duracion: +D.toFixed(2),
                                    reproducidos: +reproducidos().toFixed(2) }, extra);
    window.dispatchEvent(new CustomEvent("s2s", { detail: detalle }));
    if (window.parent !== window) window.parent.postMessage({ s2s: detalle }, "*");
  };
  function encajar() {
    const k = Math.min(innerWidth / 1080, innerHeight / 1920);
    root.style.transform = `translate(${(innerWidth - 1080 * k) / 2}px, ${(innerHeight - 1920 * k) / 2}px) scale(${k})`;
  }
  // El cuadro de t depende solo de t: da lo mismo llegar reproduciendo o saltando, para adelante o para atrás.
  function pintar(t) {
    t = acotar(t);
    tl.seek(t, false);
    for (const c of clips) c.e.style.visibility = (t >= c.s && t < c.s + c.d) ? "" : "hidden";
    barra.style.width = (100 * t / D) + "%";
    pista.setAttribute("aria-valuenow", Math.round(t));
  }
  function bucle() { pintar(arrastre !== null ? arrastre : ahora()); if (sonando) requestAnimationFrame(bucle); }
  function decodificar() {
    const b64 = document.getElementById("s2s-mp3").textContent.trim();
    const bin = atob(b64), bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new Promise((ok, mal) => ctx.decodeAudioData(bytes.buffer, ok, mal));
  }
  // mientras suena, cada 2 s avisa por dónde va: si el iframe se recarga solo (iOS lo hace cuando el
  // proceso del video se queda sin memoria), la lista lo retoma desde ahí y no desde el principio
  let reloj = null;
  function marcarReloj(prendido) {
    clearInterval(reloj); reloj = null;
    if (prendido) reloj = setInterval(() => { if (sonando) avisar("tiempo"); }, 2000);
  }
  function cerrarTramo() { if (tramo !== null) { tramos.push([tramo, ahora()]); tramo = null; } }
  // una fuente nueva que suena desde `desde` (una fuente de Web Audio no se puede mover: se cambia por otra)
  function arrancarFuente(desde) {
    desde = Math.min(acotar(desde), Math.max(0, D - 0.01));
    const f = ctx.createBufferSource(); f.buffer = buffer; f.connect(ctx.destination);
    f.onended = () => { if (f === fuente && sonando && ahora() >= D - 0.1) terminar(); };
    fuente = f; t0 = ctx.currentTime - desde; f.start(0, desde); sonando = true; tramo = desde;
  }
  function frenarFuente() { const f = fuente; fuente = null; if (f) { try { f.stop(); } catch (e) {} } }
  function terminar() {
    cerrarTramo(); sonando = false; fuente = null; pos = D; pintar(D); marcarReloj(false);
    boton.textContent = TX.otraVez; tapa.hidden = false; avisar("fin");
  }
  async function empezar() {
    if (!ctx) {
      // iOS 17 o más: pedir la categoría "playback" hace sonar el audio con el teléfono en silencio
      // (iOS silencia Web Audio en modo silencio: bug 237322 de WebKit).
      if (navigator.audioSession) navigator.audioSession.type = "playback";
      desbloquearSilencio();   // en el mismo toque del usuario, antes de crear el AudioContext
      ctx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (ctx.state === "suspended") await ctx.resume();
    if (!buffer) { boton.textContent = TX.cargando; buffer = await decodificar(); }
    if (sonando) return;
    if (pos >= D - 0.05) pos = 0;
    arrancarFuente(pos); empezado = true;
    tapa.hidden = true; avisar(pos < 0.1 ? "inicio" : "sigue"); marcarReloj(true); requestAnimationFrame(bucle);
  }
  // La lista, un toque y un salto pueden pedirlo a la vez: hay un solo arranque. Si quedó esperando un
  // toque (el navegador dejó el AudioContext suspendido), este pedido puede traerlo: se reanuda acá mismo.
  function reproducir() {
    if (pendiente) { if (ctx && ctx.state === "suspended") ctx.resume().catch(() => {}); return pendiente; }
    pendiente = empezar().finally(() => { pendiente = null; });
    return pendiente;
  }
  function pausar() {
    if (!sonando) return;
    pos = ahora(); cerrarTramo(); sonando = false; frenarFuente(); marcarReloj(false);
    boton.textContent = TX.seguir; tapa.hidden = false; avisar("pausa");
  }
  // Saltar: con audio sonando, se frena la fuente y arranca otra en el lugar nuevo. Quieto, se mueve el
  // cuadro; si nunca sonó, arranca desde ahí.
  function saltar(t) {
    t = acotar(t);
    if (sonando) { cerrarTramo(); frenarFuente(); arrancarFuente(t); pintar(t); }
    else {
      pos = t; pintar(t);
      if (!empezado) reproducir().catch(() => {});
      else boton.textContent = t >= D - 0.05 ? TX.otraVez : TX.seguir;
    }
    avisar("salto");
  }
  let mostrando = null;
  function mostrarSalto(lado) {
    marca.textContent = (lado > 0 ? "+" : "\\u2212") + SALTO + " s";
    marca.style.left = lado > 0 ? "83%" : "17%";
    marca.classList.add("ver");
    clearTimeout(mostrando); mostrando = setTimeout(() => marca.classList.remove("ver"), 450);
  }
  function saltarPor(lado) { saltar(ahora() + SALTO * lado); mostrarSalto(lado); }
  // Un toque pausa; dos toques seguidos en el tercio izquierdo o derecho saltan 5 s para atrás o para
  // adelante. Para distinguirlos, la pausa espera DOBLE_MS por si llega el segundo toque; después de un
  // doble toque, cada toque más del mismo lado vuelve a saltar.
  let toque = null, racha = null;
  function tocar(x) {          // x: de 0 (borde izquierdo) a 1 (borde derecho)
    if (!sonando) { reproducir().catch(() => {}); return; }
    const lado = x < 1 / 3 ? -1 : x > 2 / 3 ? 1 : 0, ya = performance.now();
    if (racha && lado !== 0 && lado === racha.lado && ya < racha.hasta) {
      if (toque) { clearTimeout(toque.reloj); toque = null; }
      saltarPor(lado); racha.hasta = ya + 500; return;
    }
    racha = null;
    if (toque) {
      clearTimeout(toque.reloj); const primero = toque; toque = null;
      if (lado !== 0 && lado === primero.lado) { saltarPor(lado); racha = { lado, hasta: ya + 500 }; }
      else pausar();
      return;
    }
    toque = { lado, reloj: setTimeout(() => { toque = null; pausar(); }, DOBLE_MS) };
  }
  root.addEventListener("click", e => tocar(e.clientX / innerWidth));
  // En el modo feed de la lista, con el video quieto, la tapa es lo que recibe el dedo: un gesto sobre ella
  // se le avisa a la lista (que decide si es cambiar de video o salir) en vez de reproducir.
  let feed = false, gestoIni = null, fueGesto = false;   // fueGesto: el click que sigue a ese gesto no reproduce
  tapa.addEventListener("pointerdown", e => { fueGesto = false; gestoIni = feed ? { x: e.clientX, y: e.clientY, t: e.timeStamp } : null; });
  tapa.addEventListener("pointercancel", () => { gestoIni = null; });
  tapa.addEventListener("pointerup", e => {
    const a = gestoIni; gestoIni = null;
    if (!a || !feed) return;
    const dx = e.clientX - a.x, dy = e.clientY - a.y;
    if (Math.abs(dx) < 12 && Math.abs(dy) < 12) return;
    fueGesto = true;
    avisar("deslizar", { dx, dy, ms: e.timeStamp - a.t, y0: a.y });
  });
  tapa.addEventListener("click", () => {
    if (fueGesto) { fueGesto = false; return; }
    reproducir().catch(err => { boton.textContent = TX.error; console.error(err); });
  });
  addEventListener("wheel", e => { if (feed) { e.preventDefault(); avisar("rueda", { dy: e.deltaY }); } }, { passive: false });
  // la barra: se arrastra, y mientras tanto se ve el cuadro de ese momento; al soltar, salta ahí
  const tEn = e => acotar(D * e.clientX / innerWidth);
  function soltar() { arrastre = null; pista.classList.remove("arrastrando"); }
  pista.addEventListener("pointerdown", e => {
    if (e.button > 0) return;
    e.preventDefault();
    try { pista.setPointerCapture(e.pointerId); } catch (err) {}
    arrastre = tEn(e); pista.classList.add("arrastrando"); pintar(arrastre);
  });
  pista.addEventListener("pointermove", e => { if (arrastre === null) return; arrastre = tEn(e); if (!sonando) pintar(arrastre); });
  pista.addEventListener("pointerup", e => { if (arrastre === null) return; soltar(); saltar(tEn(e)); });
  pista.addEventListener("pointercancel", () => { if (arrastre === null) return; soltar(); pintar(ahora()); });
  // teclado: ← y → saltan 5 s, espacio pausa o sigue
  function tecla(k) {
    if (k === "ArrowLeft" || k === "ArrowRight") { saltarPor(k === "ArrowLeft" ? -1 : 1); return true; }
    if (k === " " || k === "Spacebar") { if (sonando) pausar(); else reproducir().catch(() => {}); return true; }
    return false;
  }
  addEventListener("keydown", e => {
    if (e.altKey || e.ctrlKey || e.metaKey || (e.repeat && e.key === " ")) return;
    if (tecla(e.key)) { e.preventDefault(); return; }
    // ↑, ↓ y Esc son de la lista (cambiar de video y salir del modo feed): se le pasan
    if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Escape"].includes(e.key)) {
      if (feed) e.preventDefault();
      avisar("tecla", { tecla: e.key });
    }
  });
  // La lista de reproducción (index.html) pide arrancar el siguiente video (si el navegador exige un
  // toque, queda la tapa) o pausar, o pasa un toque o una tecla que le llegó a ella. "play" con "desde"
  // retoma un video que se recargó solo: aunque el navegador exija un toque, la tapa queda en "Seguir"
  // en ese punto.
  addEventListener("message", e => {
    const m = e.data;
    if (!m) return;
    if (m.s2s === "play" && !sonando) {
      if (typeof m.desde === "number" && isFinite(m.desde) && m.desde > 0) {
        pos = acotar(m.desde); pintar(pos); boton.textContent = TX.seguir;
      }
      reproducir().catch(() => {});
    }
    if (m.s2s === "pausa") pausar();
    if (m.s2s === "toque" && typeof m.x === "number") tocar(m.x);
    if (m.s2s === "tecla" && typeof m.tecla === "string") tecla(m.tecla);
    if (m.s2s === "feed") { feed = !!m.activo; tapa.style.touchAction = feed ? "none" : ""; }
  });
  addEventListener("resize", encajar);
  pista.setAttribute("aria-valuemax", Math.round(D));
  // Cada tween de gsap anota sus valores de partida la primera vez que se pinta; si eso pasara recién al
  // reproducir o al saltar, el cuadro de t dependería del camino (dos tweens sobre lo mismo se pisan
  // distinto). Se recorre la línea de tiempo entera una vez al cargar: desde acá el cuadro depende solo de t.
  tl.progress(1, true).progress(0, true);
  encajar(); pintar(0);
  window.__s2s = { pintar, D, ahora, reproducir, saltar, tocar, reproducidos };   // para pruebas
  document.documentElement.dataset.s2sListo = "1";
  avisar("listo");
})();
"""


def _fuente_de_audio(carpeta: Path, src: str) -> Path | None:
    """Los efectos vienen con el skill; la voz está en la carpeta del video; la música se sintetiza."""
    if src.startswith("assets/sfx/"):
        return Path(CFG["sfx"]) / src.split("/")[-1]
    if src == "assets/musica.wav" and not (carpeta / src).exists():
        return None
    return carpeta / src


def pista(carpeta: Path, src_html: str, dur: float) -> bytes:
    pistas = []
    for attrs in AUDIO_RE.findall(src_html):
        a = dict(ATTR_RE.findall(attrs))
        ini = float(a.get("data-start", 0))
        d = float(a.get("data-duration", dur - ini))
        p = _fuente_de_audio(carpeta, a["src"])
        audio = sonido.musica(dur) if p is None else sonido.leer(p)
        pistas.append((audio, ini, d, float(a.get("data-volume", 1))))
    buf = io.BytesIO()
    sonido.sf.write(buf, sonido.normalizar(sonido.mezclar(pistas, dur)), sonido.SR, format="MP3", subtype="MPEG_LAYER_III")
    return buf.getvalue()


def mp3_silencio(dur: float = 0.1) -> str:
    """Base64 de un MP3 de silencio muy corto (se incrusta y se reproduce en bucle como respaldo de audio
    para iOS). No toca la pista principal: se sintetiza aparte con el mismo codificador."""
    buf = io.BytesIO()
    sonido.sf.write(buf, sonido.mezclar([], dur), sonido.SR, format="MP3", subtype="MPEG_LAYER_III")
    return base64.b64encode(buf.getvalue()).decode()


def fuentes_css() -> str:
    reglas = []
    for familia, archivo in (("Inter", "inter-latin-wght-normal.woff2"),
                             ("JetBrains Mono", "jetbrains-mono-latin-wght-normal.woff2")):
        b64 = base64.b64encode((Path(CFG["fuentes"]) / archivo).read_bytes()).decode()
        reglas.append(f"@font-face {{ font-family:'{familia}'; font-weight:100 900; font-display:block; "
                      f"src:url(data:font/woff2;base64,{b64}) format('woff2'); }}")
    return "\n".join(reglas)


def katex_embebido() -> tuple[str, str]:
    """(css con las fuentes adentro, js) de KaTeX, o ("", "") si no está instalado."""
    k = Path(CFG["katex"])
    if not (k / "katex.min.js").exists():
        return "", ""
    css = (k / "katex.min.css").read_text(encoding="utf-8")
    def fuente(m):
        f = k / "fonts" / (m.group(1) + ".woff2")
        return f"url(data:font/woff2;base64,{base64.b64encode(f.read_bytes()).decode()}) format(\"woff2\")" if f.exists() else ""
    css = re.sub(r"url\(fonts/([\w-]+)\.woff2\) format\(\"woff2\"\)", fuente, css)
    css = re.sub(r",\s*url\(fonts/[^)]+\) format\(\"[^\"]+\"\)", "", css)      # sin woff ni ttf
    return css, (k / "katex.min.js").read_text(encoding="utf-8")


DIBUJAR_FORMULAS = """
const formulas = [...document.querySelectorAll(".ftex")];
if (formulas.length && window.katex) formulas.forEach(e => {
  katex.render(e.dataset.tex, e, { throwOnError: false, displayMode: false });
  if (e.querySelector(".katex-error")) console.error("fórmula con error: " + e.dataset.tex);
});
const fuentesKatex = ["KaTeX_Main", "KaTeX_Math", "KaTeX_Size1", "KaTeX_Size2", "KaTeX_Size3", "KaTeX_Size4", "KaTeX_AMS"];
const cargarFuentes = formulas.length && window.katex
  ? Promise.all(fuentesKatex.map(f => document.fonts.load("64px " + f).catch(() => null))) : Promise.resolve();
"""


def construir(carpeta: Path, destino: Path, titulo: str = "") -> Path:
    src = (carpeta / "index.html").read_text(encoding="utf-8")
    spec = carpeta / "spec.json"
    idioma = json.loads(spec.read_text(encoding="utf-8")).get("IDIOMA", "es") if spec.exists() else "es"
    tx = TEXTOS.get(idioma, TEXTOS["es"])
    if src.count("<audio") != len(AUDIO_RE.findall(src)) or GSAP_TAG not in src or not SCRIPT_ENGINE_RE.search(src):
        sys.exit(f"{carpeta}/index.html no tiene el formato que espero de engine.py")
    gsap = Path(CFG["gsap"])
    if not gsap.exists():
        sys.exit(f"falta {gsap}: corré `python3 s2s.py instalar`")
    dur = float(re.search(r'data-composition-id="main" data-start="0" data-duration="([\d.]+)"', src)[1])
    mp3 = base64.b64encode(pista(carpeta, src, dur)).decode()

    out = AUDIO_RE.sub("", src)
    out = out.replace(GSAP_TAG, f"<script>{gsap.read_text(encoding='utf-8')}</script>", 1)
    out = out.replace('<meta name="viewport" content="width=1080, height=1920" />',
                      '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />'
                      f"<title>{html.escape(titulo or carpeta.name)}</title>", 1)
    kcss, kjs = katex_embebido() if 'class="formula"' in out else ("", "")
    if 'class="formula"' in out and not kjs:
        print("AVISO  el video tiene fórmulas pero KaTeX no está instalado: corré `s2s.py instalar`")
    out = out.replace("</style>", f"{fuentes_css()}\n{kcss}\n{PLAYER_CSS}</style>", 1)
    if kjs:
        out = out.replace("</style>", "</style><script>" + kjs + "</script>", 1)
    m = SCRIPT_ENGINE_RE.search(out)       # se busca de nuevo: el texto cambió arriba
    player_js = PLAYER_JS.replace("__SILENCIO_MP3__", mp3_silencio())
    motor = ("window.__timelines = {};\nconst TX = " + json.dumps(tx, ensure_ascii=False) + ";\n" + DIBUJAR_FORMULAS +
             "Promise.all([document.fonts.ready, cargarFuentes]).then(() => {\n" + m.group(1) + "\n" + m.group(2) + "\n" + player_js + "\n});")
    out = out[:m.start()] + (
        f'<script type="application/octet-stream" id="s2s-mp3">{mp3}</script>'
        + marcado(tx) +
        f"<script>{motor}</script>") + out[m.end():]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(out, encoding="utf-8")
    return destino


INDICE = r"""<!doctype html>
<html lang="__IDIOMA__"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>__TITULO__</title>
<style>
:root { --bg:#f6f1e3; --card:#fffdf6; --line:#d9cfb4; --fg:#1d2b4f; --muted:#5f6a86; --accent:#2f5bd3;
  --ok:#1f8f52; --ok-ink:#fff; color-scheme:light; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.4 system-ui, -apple-system, "Segoe UI", sans-serif;
  padding:20px max(16px, env(safe-area-inset-right)) 40px max(16px, env(safe-area-inset-left)); }
.wrap { max-width:1040px; margin:0 auto; display:grid; gap:20px; grid-template-columns:1fr; }
@media (min-width:860px) { .wrap { grid-template-columns:minmax(0,400px) minmax(0,1fr); align-items:start; }
  .player { position:sticky; top:20px; } }
header { grid-column:1/-1; display:flex; flex-wrap:wrap; gap:12px 24px; align-items:flex-end; justify-content:space-between; }
h1 { font:800 clamp(24px,5vw,36px)/1.1 system-ui, sans-serif; margin:0; letter-spacing:-.01em; }
.sub { color:var(--muted); margin:6px 0 0; max-width:60ch; }
.stats { display:flex; gap:24px; }
.stat { color:var(--muted); font-size:13px; text-align:right; }
.stat b { display:block; font:800 28px system-ui, sans-serif; color:var(--fg); font-variant-numeric:tabular-nums; }
.barra { grid-column:1/-1; height:8px; border-radius:4px; background:var(--line); overflow:hidden; }
.barra i { display:block; height:100%; width:0; background:var(--ok); transition:width .3s; }
.player { display:flex; flex-direction:column; gap:12px; min-width:0; }
.caja { position:relative; width:100%; max-width:400px; aspect-ratio:9/16; margin:0 auto; border-radius:18px; overflow:hidden;
  background:#000; border:1px solid var(--line); }
.caja iframe { width:100%; height:100%; border:0; display:block; }
.ahora small { display:block; color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }
.ahora span { font-weight:700; font-size:17px; }
.ctrls { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
button { font:600 14px system-ui, sans-serif; color:var(--fg); background:var(--card); border:1px solid var(--line);
  border-radius:10px; padding:9px 14px; cursor:pointer; }
button:focus-visible, textarea:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
button.prim { background:var(--accent); border-color:var(--accent); color:#fff; }
.aviso { color:var(--ok); font-weight:600; }
#expCaja { display:flex; flex-direction:column; gap:6px; }
#expCaja small { color:var(--muted); }
#expTxt { width:100%; min-height:140px; font:12px/1.4 ui-monospace, Consolas, monospace; color:var(--fg);
  background:var(--card); border:1px solid var(--line); border-radius:10px; padding:10px; resize:vertical; }
.lado { display:flex; flex-direction:column; gap:12px; min-width:0; }
#toca { width:100%; display:grid; grid-template-columns:minmax(0,1fr) auto; gap:4px 12px; align-items:center;
  text-align:left; padding:14px 16px; border-radius:14px; background:var(--accent); border-color:var(--accent); color:#fff; }
#toca small { grid-column:1/-1; font-size:12px; text-transform:uppercase; letter-spacing:.06em; opacity:.85; }
#toca b { font-size:18px; }
#toca span { font-size:13px; opacity:.85; }
ol { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:8px; min-width:0; }
li button { width:100%; display:grid; grid-template-columns:32px minmax(0,1fr) auto; gap:12px; align-items:center;
  text-align:left; padding:12px 14px; border-radius:14px; }
.num { text-align:center; color:var(--muted); font-weight:700; }
.t b { display:block; font-size:16px; }
.t span { display:block; color:var(--muted); font-size:13px; font-weight:400; margin-top:2px; }
.dur { color:var(--muted); font-size:13px; font-variant-numeric:tabular-nums; }
li.cur button { border-color:var(--accent); box-shadow:inset 0 0 0 1px var(--accent); }
li.visto .num { background:var(--ok); color:var(--ok-ink); border-radius:999px; height:28px; display:flex;
  align-items:center; justify-content:center; }
#toca:disabled { opacity:.8; cursor:default; }
@media (prefers-reduced-motion:reduce) { .barra i { transition:none; } }
</style></head><body>
<div class="wrap">
  <header>
    <div><h1>__TITULO__</h1><p class="sub">__SUB__</p></div>
    <div class="stats">
      <div class="stat"><b id="nHoy">0</b><span id="lHoy"></span></div>
      <div class="stat"><b id="nRacha">0</b><span id="lRacha"></span></div>
      <div class="stat"><b id="nVistos">0 / 0</b><span id="lVistos"></span></div>
    </div>
  </header>
  <div class="barra" aria-hidden="true"><i id="lleno"></i></div>
  <section class="player">
    <div class="caja"><iframe id="v" allow="autoplay" title="video"></iframe></div>
    <div class="ahora"><small id="nAhora"></small><span id="tAhora"></span></div>
    <div class="ctrls">
      <button id="ant" type="button"></button>
      <button id="sig" type="button" class="prim"></button>
      <button id="feed" type="button"></button>
    </div>
    <div class="ctrls" id="ctrls2">
      <button id="exp" type="button"></button>
      <button id="cero" type="button"></button>
      <span id="aviso" class="aviso" role="status"></span>
    </div>
  </section>
  <div class="lado">
    <button id="toca" type="button"><small id="lToca"></small><b id="tToca"></b><span id="nToca"></span></button>
    <ol id="lista"></ol>
  </div>
</div>
<script>__PROGRESO__</script>
<script>__CUESTIONARIO__</script>
<script>__REPRODUCCION__</script>
<script>
const VIDEOS = __VIDEOS__, TX = __TX__, P = window.Progreso, C = window.Cuestionario;
const IDIOMA = document.documentElement.lang, QX = C.textos(IDIOMA);
const CLAVE = "s2s:" + document.title, hoy = () => P.fechaLocal(new Date());
let st = P.vacio(VIDEOS);
try { st = P.cargar(localStorage.getItem(CLAVE), VIDEOS); } catch (e) {}
const guardar = () => { try { localStorage.setItem(CLAVE, JSON.stringify(st)); } catch (e) {} };
guardar();   // deja guardado el formato nuevo si venía del viejo
const $ = id => document.getElementById(id), v = $("v");
const pos = id => Math.max(0, VIDEOS.findIndex(x => x.id === id));
const mmss = s => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
$("ant").textContent = TX.ant; $("sig").textContent = TX.sig; $("cero").textContent = TX.cero;
$("exp").textContent = TX.exportar; $("lToca").textContent = TX.toca; $("lVistos").textContent = TX.vistos;
$("lHoy").textContent = QX.paraHoy;
function vistosAlgunaVez() {
  const s = new Set(); for (const f in st.dias) for (const id of st.dias[f]) s.add(id); return s;
}
function pintar() {
  const cur = pos(st.cur), vistos = vistosAlgunaVez(), toca = P.queTocaHoy(st, VIDEOS, hoy());
  const ol = $("lista"); ol.textContent = "";
  VIDEOS.forEach((x, i) => {
    const li = document.createElement("li"), b = document.createElement("button");
    li.classList.toggle("cur", i === cur); li.classList.toggle("visto", vistos.has(x.id));
    b.type = "button";
    const n = document.createElement("span"); n.className = "num"; n.textContent = vistos.has(x.id) ? "✓" : i + 1;
    const t = document.createElement("span"); t.className = "t";
    const tb = document.createElement("b"); tb.textContent = x.titulo;
    const ts = document.createElement("span"); ts.textContent = x.pregunta; t.append(tb, ts);
    const e = P.estadoTema(st, x, hoy()); li.dataset.rep = e.estado;
    t.append(C.chip(document, e, e.proxima ? P.diasEntre(hoy(), e.proxima) : 0, IDIOMA));
    const d = document.createElement("span"); d.className = "dur"; d.textContent = mmss(x.duracion);
    b.append(n, t, d); b.onclick = () => abrir(i, true); li.append(b); ol.append(li);
  });
  // si hoy no queda nada, se dice, y cualquier video de la lista se puede ver igual
  const it = toca === null ? -1 : pos(toca);
  $("toca").disabled = it < 0;
  $("tToca").textContent = it < 0 ? QX.nada : VIDEOS[it].titulo; $("toca").onclick = () => abrir(it, true);
  $("nToca").textContent = it < 0 ? "" : TX.de.replace("{n}", it + 1).replace("{t}", VIDEOS.length);
  $("nHoy").textContent = P.pendientesHoy(st, VIDEOS, hoy()).length;
  const r = P.racha(st, hoy());
  $("nRacha").textContent = r; $("lRacha").textContent = r === 1 ? TX.racha1 : TX.racha;
  const n = VIDEOS.filter(x => vistos.has(x.id)).length;
  $("nVistos").textContent = `${n} / ${VIDEOS.length}`;
  $("lleno").style.width = (100 * n / VIDEOS.length) + "%";
  $("nAhora").textContent = TX.de.replace("{n}", cur + 1).replace("{t}", VIDEOS.length);
  $("tAhora").textContent = VIDEOS[cur].titulo;
  $("ant").disabled = cur === 0; $("sig").disabled = cur === VIDEOS.length - 1;
}
let quiz = null;
// lo que pasa con el iframe del video (avisos, retomar si se recarga solo, cortes) y los dos modos: el normal,
// sin gestos sobre el video, y "Pantalla completa" (feed), donde se desliza entre videos: reproduccion.js
const R = window.Reproduccion.conectar({
  iframe: v, caja: document.querySelector(".caja"), botonFeed: $("feed"), idioma: IDIOMA,
  claveCortes: () => "s2s-cortes:" + document.title,
  hay: d => pos(st.cur) + d >= 0 && pos(st.cur) + d < VIDEOS.length, mover: d => abrir(pos(st.cur) + d, true),
  alFin: visto => { if (visto) terminoVideo(); },
});
function cerrarQuiz() { if (quiz) { quiz.cerrar(); quiz = null; } }
function seguirConLoQueToca() {
  const t = P.queTocaHoy(st, VIDEOS, hoy());
  if (t !== null) abrir(pos(t), true); else pintar();
}
// después del video, sus preguntas (cuestionario.js); el resultado decide cuándo vuelve el tema (progreso.js)
function preguntar(x) {
  cerrarQuiz();
  quiz = C.mostrar(document.querySelector(".caja"), {
    idioma: IDIOMA, preguntas: x.preguntas,
    alTerminar: (aciertos, total) => {
      st = P.responder(st, x.id, aciertos, total, hoy()); guardar(); pintar();
      const t = P.queTocaHoy(st, VIDEOS, hoy());
      return { dias: P.diasEntre(hoy(), st.repaso[x.id].proxima), siguiente: t === null ? null : VIDEOS[pos(t)].titulo };
    },
    alSeguir: () => { quiz = null; seguirConLoQueToca(); },
    alSaltear: () => { quiz = null; seguirConLoQueToca(); },   // no cuenta como respuesta: ya quedó visto
  });
}
function abrir(i, auto) {
  if (i < 0 || i >= VIDEOS.length) return;
  cerrarQuiz();
  st = Object.assign({}, st, { cur: VIDEOS[i].id }); guardar();
  R.cargar(VIDEOS[i].id, auto); v.src = VIDEOS[i].archivo; pintar();
}
// cuando el video termina (y sonó al menos el 70 %): queda visto y vienen sus preguntas, o el siguiente
function terminoVideo() {
  if (quiz) return;
  const cur = pos(st.cur), x = VIDEOS[cur];
  st = P.marcarVisto(st, x.id, hoy()); guardar();
  if (x.preguntas.length) { pintar(); preguntar(x); return; }
  if (cur < VIDEOS.length - 1) abrir(cur + 1, true); else pintar();
}
$("ant").onclick = () => abrir(pos(st.cur) - 1, true);
$("sig").onclick = () => abrir(pos(st.cur) + 1, true);
function avisar(texto) {
  const a = $("aviso"); a.textContent = texto;
  clearTimeout(avisar.t); avisar.t = setTimeout(() => { a.textContent = ""; }, 3000);
}
function mostrarJson(texto) {
  let caja = $("expCaja");
  if (!caja) {
    caja = document.createElement("div"); caja.id = "expCaja";
    const s = document.createElement("small"); s.textContent = TX.copiaManual;
    const ta = document.createElement("textarea"); ta.id = "expTxt"; ta.readOnly = true; ta.setAttribute("aria-label", TX.exportar);
    ta.onfocus = () => ta.select();
    caja.append(s, ta); $("ctrls2").after(caja);
  }
  const ta = $("expTxt"); ta.value = texto; ta.focus(); ta.select();
}
$("exp").onclick = async () => {
  const datos = Object.assign(P.exportar(st, { titulo: document.title, fecha: hoy(), generado: new Date().toISOString() }),
                              { cortes: R.cortes() });
  const texto = JSON.stringify(datos, null, 2);
  try {
    if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error("sin portapapeles");
    await navigator.clipboard.writeText(texto);
    avisar(TX.copiado);
  } catch (e) { mostrarJson(texto); }
};
$("cero").onclick = () => {
  if (document.getElementById("conf")) return;
  const caja = document.createElement("span"); caja.id = "conf"; caja.className = "ctrls";
  const q = document.createElement("span"); q.textContent = TX.seguro;
  const si = document.createElement("button"); si.type = "button"; si.className = "prim"; si.textContent = TX.si;
  const no = document.createElement("button"); no.type = "button"; no.textContent = TX.no;
  si.onclick = () => { st = P.vacio(VIDEOS); guardar(); caja.remove(); abrir(0, false); };
  no.onclick = () => caja.remove();
  caja.append(q, si, no); $("cero").after(caja);
};
const inicial = P.queTocaHoy(st, VIDEOS, hoy());
abrir(pos(inicial === null ? st.cur : inicial), false);   // se abre lo que toca hoy (o el último, si no queda nada)
</script>
</body></html>
"""

LISTA = {
    "es": {"toca": "Hoy toca", "racha": "días seguidos", "racha1": "día seguido", "vistos": "temas vistos",
           "de": "Video {n} de {t}", "ant": "Anterior", "sig": "Siguiente",
           "cero": "Borrar progreso", "seguro": "¿Borrar todo el progreso?", "si": "Sí", "no": "No",
           "exportar": "Exportar progreso", "copiado": "Copiado al portapapeles",
           "copiaManual": "No se pudo copiar solo: seleccioná este texto y copialo."},
    "en": {"toca": "Up today", "racha": "days in a row", "racha1": "day in a row", "vistos": "topics watched",
           "de": "Video {n} of {t}", "ant": "Previous", "sig": "Next",
           "cero": "Clear progress", "seguro": "Clear all progress?", "si": "Yes", "no": "No",
           "exportar": "Export progress", "copiado": "Copied to the clipboard",
           "copiaManual": "Couldn't copy it automatically: select this text and copy it."},
}

PROGRESO_JS = Path(__file__).with_name("progreso.js")
CUESTIONARIO_JS = Path(__file__).with_name("cuestionario.js")
REPRODUCCION_JS = Path(__file__).with_name("reproduccion.js")


def _json_en_script(x) -> str:
    return json.dumps(x, ensure_ascii=False).replace("</", "<\\/")


def indice(destino: Path, titulo: str, videos: list[dict], idioma: str = "es") -> Path:
    """videos: [{id, archivo, titulo, pregunta, duracion, preguntas?}] en el orden en que se ven (sin id, se
    usa el nombre del archivo). preguntas: las de etapas.preguntas_listas (validadas), o nada. La lista
    reproduce cada video en un iframe; cuando termina, si el tema tiene preguntas las muestra encima del
    video y con el resultado decide cuándo vuelve el tema a repaso. Guarda qué temas se vieron cada día y
    el repaso en el navegador, con localStorage (si no está disponible, la lista anda igual sin recordar).
    La lógica del progreso está en progreso.js, las preguntas en cuestionario.js y lo que pasa con el iframe
    del video (retomarlo si se recarga solo, registro de cortes) en reproduccion.js; las tres van embebidas."""
    datos = [{"id": str(v.get("id") or Path(v["archivo"]).stem), "archivo": v["archivo"], "titulo": v["titulo"],
              "pregunta": v.get("pregunta", ""), "duracion": round(float(v["duracion"]), 1),
              "preguntas": list(v.get("preguntas") or [])} for v in videos]
    ids = [d["id"] for d in datos]
    if len(set(ids)) != len(ids):
        raise ValueError(f"ids de tema repetidos en la lista: {ids}")
    progreso, cuestionario = PROGRESO_JS.read_text(encoding="utf-8"), CUESTIONARIO_JS.read_text(encoding="utf-8")
    reproduccion = REPRODUCCION_JS.read_text(encoding="utf-8")
    for nombre, js in (("progreso.js", progreso), ("cuestionario.js", cuestionario), ("reproduccion.js", reproduccion)):
        if "</script" in js.lower():
            raise ValueError(f"{nombre} no puede contener </script")
    valores = {"IDIOMA": idioma, "TITULO": html.escape(titulo), "SUB": html.escape(TEXTOS[idioma]["sub"]),
               "VIDEOS": _json_en_script(datos), "TX": _json_en_script(LISTA[idioma]), "PROGRESO": progreso,
               "CUESTIONARIO": cuestionario, "REPRODUCCION": reproduccion}
    # una sola pasada: un título que contenga "__TX__" no se reemplaza dos veces
    s = re.sub(r"__(IDIOMA|TITULO|SUB|VIDEOS|TX|PROGRESO|CUESTIONARIO|REPRODUCCION)__", lambda m: valores[m[1]], INDICE)
    destino.write_text(s, encoding="utf-8")
    return destino


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    d = construir(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"{d} ({d.stat().st_size // 1024} KB)")
