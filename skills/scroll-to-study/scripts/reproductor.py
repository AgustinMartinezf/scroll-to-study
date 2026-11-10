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
#root { position:fixed !important; left:0; top:0; transform-origin:0 0; }
#s2s-tapa { position:fixed; inset:0; display:flex; align-items:center; justify-content:center;
  background:rgba(0,0,0,.45); z-index:99; cursor:pointer; -webkit-tap-highlight-color:transparent; }
#s2s-tapa[hidden] { display:none; }
#s2s-tapa button { font:800 20px/1 Inter, sans-serif; color:#04170b; background:#1fbf6a; border:0;
  border-radius:999px; padding:18px 30px; pointer-events:none; }
#s2s-barra { position:fixed; left:0; bottom:0; height:4px; width:0; background:#1fbf6a; z-index:98; }
"""

TEXTOS = {
    "es": {"tocar": "Tocar para ver", "seguir": "Seguir", "otraVez": "Ver de nuevo", "cargando": "Cargando…",
           "error": "No se pudo reproducir", "sub": "Un video por día, en orden. Cada uno prepara una pregunta que te pueden hacer."},
    "en": {"tocar": "Tap to play", "seguir": "Resume", "otraVez": "Watch again", "cargando": "Loading…",
           "error": "Couldn't play", "sub": "One video a day, in order. Each one prepares a question you may get."},
}

PLAYER_JS = """
(function () {
  // El audio se decodifica con Web Audio desde el propio archivo: no usa un elemento de audio ni URLs
  // data:, que algunos visores (vistas previas, apps) bloquean por su política de contenido.
  const root = document.getElementById("root");
  const tapa = document.getElementById("s2s-tapa"), boton = tapa.querySelector("button");
  const barra = document.getElementById("s2s-barra");
  const tl = window.__timelines.main, D = tl.duration();
  const clips = [...document.querySelectorAll("#root .clip")].map(e => ({ e, s: +e.dataset.start, d: +e.dataset.duration }));
  let ctx = null, buffer = null, fuente = null, t0 = 0, pos = 0, sonando = false;
  const ahora = () => sonando ? Math.min(D, ctx.currentTime - t0) : pos;
  const avisar = (tipo) => {
    const detalle = { tipo, t: +ahora().toFixed(2), video: document.title };
    window.dispatchEvent(new CustomEvent("s2s", { detail: detalle }));
    if (window.parent !== window) window.parent.postMessage({ s2s: detalle }, "*");
  };
  function encajar() {
    const k = Math.min(innerWidth / 1080, innerHeight / 1920);
    root.style.transform = `translate(${(innerWidth - 1080 * k) / 2}px, ${(innerHeight - 1920 * k) / 2}px) scale(${k})`;
  }
  function pintar(t) {
    tl.seek(Math.min(t, D), false);
    for (const c of clips) c.e.style.visibility = (t >= c.s && t < c.s + c.d) ? "" : "hidden";
    barra.style.width = (100 * t / D) + "%";
  }
  function bucle() { pintar(ahora()); if (sonando) requestAnimationFrame(bucle); }
  function decodificar() {
    const b64 = document.getElementById("s2s-mp3").textContent.trim();
    const bin = atob(b64), bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new Promise((ok, mal) => ctx.decodeAudioData(bytes.buffer, ok, mal));
  }
  function terminar() {
    sonando = false; pos = D; pintar(D);
    boton.textContent = TX.otraVez; tapa.hidden = false; avisar("fin");
  }
  async function reproducir() {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === "suspended") await ctx.resume();
    if (!buffer) { boton.textContent = TX.cargando; buffer = await decodificar(); }
    if (sonando) return;   // la lista y un toque pueden pedirlo a la vez
    if (pos >= D - 0.05) pos = 0;
    fuente = ctx.createBufferSource(); fuente.buffer = buffer; fuente.connect(ctx.destination);
    fuente.onended = () => { if (sonando && ahora() >= D - 0.1) terminar(); };
    t0 = ctx.currentTime - pos; fuente.start(0, pos); sonando = true;
    tapa.hidden = true; avisar(pos < 0.1 ? "inicio" : "sigue"); requestAnimationFrame(bucle);
  }
  tapa.addEventListener("click", () => reproducir().catch(err => { boton.textContent = TX.error; console.error(err); }));
  root.addEventListener("click", () => {
    if (!sonando) return;
    pos = ahora(); sonando = false; try { fuente.stop(); } catch (e) {}
    boton.textContent = TX.seguir; tapa.hidden = false; avisar("pausa");
  });
  // la lista de reproducción (index.html) pide arrancar el siguiente video; si el navegador exige un toque, queda la tapa
  addEventListener("message", e => { if (e.data && e.data.s2s === "play" && !sonando) reproducir().catch(() => {}); });
  addEventListener("resize", encajar);
  encajar(); pintar(0);
  window.__s2s = { pintar, D, ahora, reproducir };   // para pruebas
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
    motor = ("window.__timelines = {};\nconst TX = " + json.dumps(tx, ensure_ascii=False) + ";\n" + DIBUJAR_FORMULAS +
             "Promise.all([document.fonts.ready, cargarFuentes]).then(() => {\n" + m.group(1) + "\n" + m.group(2) + "\n" + PLAYER_JS + "\n});")
    out = out[:m.start()] + (
        f'<script type="application/octet-stream" id="s2s-mp3">{mp3}</script>'
        f'<div id="s2s-barra"></div><div id="s2s-tapa"><button>{tx["tocar"]}</button></div>'
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
.hoy { color:var(--muted); font-size:13px; text-align:right; }
.hoy b { display:block; font:800 28px system-ui, sans-serif; color:var(--fg); font-variant-numeric:tabular-nums; }
.barra { grid-column:1/-1; height:8px; border-radius:4px; background:var(--line); overflow:hidden; }
.barra i { display:block; height:100%; width:0; background:var(--ok); transition:width .3s; }
.player { display:flex; flex-direction:column; gap:12px; min-width:0; }
.caja { width:100%; max-width:400px; aspect-ratio:9/16; margin:0 auto; border-radius:18px; overflow:hidden;
  background:#000; border:1px solid var(--line); }
.caja iframe { width:100%; height:100%; border:0; display:block; }
.ahora small { display:block; color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }
.ahora span { font-weight:700; font-size:17px; }
.ctrls { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
button { font:600 14px system-ui, sans-serif; color:var(--fg); background:var(--card); border:1px solid var(--line);
  border-radius:10px; padding:9px 14px; cursor:pointer; }
button:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
button.prim { background:var(--accent); border-color:var(--accent); color:#fff; }
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
@media (prefers-reduced-motion:reduce) { .barra i { transition:none; } }
</style></head><body>
<div class="wrap">
  <header>
    <div><h1>__TITULO__</h1><p class="sub">__SUB__</p></div>
    <div class="hoy"><b id="nHoy">0 / 0</b><span id="lHoy"></span></div>
  </header>
  <div class="barra" aria-hidden="true"><i id="lleno"></i></div>
  <section class="player">
    <div class="caja"><iframe id="v" allow="autoplay" title="video"></iframe></div>
    <div class="ahora"><small id="nAhora"></small><span id="tAhora"></span></div>
    <div class="ctrls">
      <button id="ant" type="button"></button>
      <button id="sig" type="button" class="prim"></button>
      <button id="cero" type="button"></button>
    </div>
  </section>
  <ol id="lista"></ol>
</div>
<script>
const VIDEOS = __VIDEOS__, TX = __TX__;
const CLAVE = "s2s:" + document.title, hoy = new Date().toLocaleDateString("sv");
let st = { dia: hoy, vistos: [], cur: 0 };
try { const s = JSON.parse(localStorage.getItem(CLAVE) || "null"); if (s) { st = s; if (st.dia !== hoy) { st.dia = hoy; st.vistos = []; } } } catch (e) {}
const guardar = () => { try { localStorage.setItem(CLAVE, JSON.stringify(st)); } catch (e) {} };
const $ = id => document.getElementById(id), v = $("v");
const mmss = s => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
$("ant").textContent = TX.ant; $("sig").textContent = TX.sig; $("cero").textContent = TX.cero; $("lHoy").textContent = TX.hoy;
function pintar() {
  const ol = $("lista"); ol.textContent = "";
  VIDEOS.forEach((x, i) => {
    const li = document.createElement("li"), b = document.createElement("button");
    li.classList.toggle("cur", i === st.cur); li.classList.toggle("visto", st.vistos.includes(i));
    b.type = "button";
    const n = document.createElement("span"); n.className = "num"; n.textContent = st.vistos.includes(i) ? "✓" : i + 1;
    const t = document.createElement("span"); t.className = "t";
    const tb = document.createElement("b"); tb.textContent = x.titulo;
    const ts = document.createElement("span"); ts.textContent = x.pregunta; t.append(tb, ts);
    const d = document.createElement("span"); d.className = "dur"; d.textContent = mmss(x.duracion);
    b.append(n, t, d); b.onclick = () => abrir(i, true); li.append(b); ol.append(li);
  });
  $("nHoy").textContent = `${st.vistos.length} / ${VIDEOS.length}`;
  $("lleno").style.width = (100 * st.vistos.length / VIDEOS.length) + "%";
  $("nAhora").textContent = TX.de.replace("{n}", st.cur + 1).replace("{t}", VIDEOS.length);
  $("tAhora").textContent = VIDEOS[st.cur].titulo;
  $("ant").disabled = st.cur === 0; $("sig").disabled = st.cur === VIDEOS.length - 1;
}
let arrancar = false;
function abrir(i, auto) {
  st.cur = Math.max(0, Math.min(VIDEOS.length - 1, i)); guardar();
  arrancar = auto; v.src = VIDEOS[st.cur].archivo; pintar();
}
// el video avisa con postMessage cuándo está listo y cuándo termina (cada .html también se ve solo)
addEventListener("message", e => {
  if (e.source !== v.contentWindow || !e.data || !e.data.s2s) return;
  if (e.data.s2s.tipo === "listo") { if (arrancar) v.contentWindow.postMessage({ s2s: "play" }, "*"); return; }
  if (e.data.s2s.tipo !== "fin") return;
  if (!st.vistos.includes(st.cur)) st.vistos.push(st.cur);
  guardar();
  if (st.cur < VIDEOS.length - 1) abrir(st.cur + 1, true); else pintar();
});
$("ant").onclick = () => abrir(st.cur - 1, true);
$("sig").onclick = () => abrir(st.cur + 1, true);
$("cero").onclick = () => {
  if (document.getElementById("conf")) return;
  const caja = document.createElement("span"); caja.id = "conf"; caja.className = "ctrls";
  const q = document.createElement("span"); q.textContent = TX.seguro;
  const si = document.createElement("button"); si.type = "button"; si.className = "prim"; si.textContent = TX.si;
  const no = document.createElement("button"); no.type = "button"; no.textContent = TX.no;
  si.onclick = () => { st.vistos = []; guardar(); caja.remove(); abrir(0, false); };
  no.onclick = () => caja.remove();
  caja.append(q, si, no); $("cero").after(caja);
};
abrir(Math.min(st.cur || 0, VIDEOS.length - 1), false);
</script>
</body></html>
"""

LISTA = {
    "es": {"hoy": "vistos hoy", "de": "Video {n} de {t}", "ant": "Anterior", "sig": "Siguiente",
           "cero": "Empezar el día de cero", "seguro": "¿Desmarcar los vistos de hoy?", "si": "Sí", "no": "No"},
    "en": {"hoy": "watched today", "de": "Video {n} of {t}", "ant": "Previous", "sig": "Next",
           "cero": "Start the day over", "seguro": "Clear today's watched marks?", "si": "Yes", "no": "No"},
}


def _json_en_script(x) -> str:
    return json.dumps(x, ensure_ascii=False).replace("</", "<\\/")


def indice(destino: Path, titulo: str, videos: list[dict], idioma: str = "es") -> Path:
    """videos: [{archivo, titulo, pregunta, duracion}] en el orden en que se ven.
    La lista reproduce cada video en un iframe, pasa al siguiente cuando termina y marca los vistos del día
    (en el navegador, con localStorage; si no está disponible, la lista anda igual sin recordar)."""
    datos = [{"archivo": v["archivo"], "titulo": v["titulo"], "pregunta": v.get("pregunta", ""),
              "duracion": round(float(v["duracion"]), 1)} for v in videos]
    s = (INDICE.replace("__IDIOMA__", idioma).replace("__TITULO__", html.escape(titulo))
         .replace("__SUB__", html.escape(TEXTOS[idioma]["sub"]))
         .replace("__VIDEOS__", _json_en_script(datos)).replace("__TX__", _json_en_script(LISTA[idioma])))
    destino.write_text(s, encoding="utf-8")
    return destino


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    d = construir(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"{d} ({d.stat().st_size // 1024} KB)")
