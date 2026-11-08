#!/usr/bin/env python3
"""index.html de engine.py -> un video que se reproduce solo en el navegador (un único .html).

    python3 reproductor.py CARPETA SALIDA.html

engine.py arma una composición de HyperFrames: una línea de tiempo GSAP en pausa, "clips" que se
muestran según data-start/data-duration y varios <audio> sueltos. Acá se hace lo que haría un runtime:
  - se mezclan todos los <audio> en una pista MP3 (un celular no sincroniza 30 audios sueltos);
  - el audio es el reloj: en cada cuadro, tl.seek(audio.currentTime) y visibilidad de los clips;
  - se incrustan Inter y JetBrains Mono (el layout se calculó con esas fuentes) y engine.js corre
    recién cuando cargaron, porque mide posiciones con getBoundingClientRect;
  - el lienzo de 1080x1920 se escala a la pantalla después de que engine.js midió.
El resultado no depende de nada externo: audio, fuentes y gsap van adentro.
"""
from __future__ import annotations

import base64
import html
import io
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

PLAYER_JS = """
(function () {
  const A = document.getElementById("s2s-audio"), root = document.getElementById("root");
  const tapa = document.getElementById("s2s-tapa"), boton = tapa.querySelector("button");
  const barra = document.getElementById("s2s-barra");
  const tl = window.__timelines.main, D = tl.duration();
  const clips = [...document.querySelectorAll("#root .clip")].map(e => ({ e, s: +e.dataset.start, d: +e.dataset.duration }));
  const avisar = (tipo) => {
    const detalle = { tipo, t: +A.currentTime.toFixed(2), video: document.title };
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
  function bucle() { pintar(A.currentTime); if (!A.paused) requestAnimationFrame(bucle); }
  tapa.addEventListener("click", () => {
    if (A.ended) A.currentTime = 0;
    A.play().then(() => { tapa.hidden = true; avisar(A.currentTime < 0.1 ? "inicio" : "sigue"); requestAnimationFrame(bucle); })
             .catch(err => { boton.textContent = "No se pudo reproducir"; console.error(err); });
  });
  root.addEventListener("click", () => { if (!A.paused) { A.pause(); boton.textContent = "Seguir"; tapa.hidden = false; avisar("pausa"); } });
  A.addEventListener("ended", () => { pintar(D); boton.textContent = "Ver de nuevo"; tapa.hidden = false; avisar("fin"); });
  addEventListener("resize", encajar);
  encajar(); pintar(0);
  window.__s2s = { pintar, D };          // para pruebas: pintar(t) dibuja el cuadro del segundo t
  document.documentElement.dataset.s2sListo = "1";
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
    sonido.sf.write(buf, sonido.mezclar(pistas, dur), sonido.SR, format="MP3", subtype="MPEG_LAYER_III")
    return buf.getvalue()


def fuentes_css() -> str:
    reglas = []
    for familia, archivo in (("Inter", "inter-latin-wght-normal.woff2"),
                             ("JetBrains Mono", "jetbrains-mono-latin-wght-normal.woff2")):
        b64 = base64.b64encode((Path(CFG["fuentes"]) / archivo).read_bytes()).decode()
        reglas.append(f"@font-face {{ font-family:'{familia}'; font-weight:100 900; font-display:block; "
                      f"src:url(data:font/woff2;base64,{b64}) format('woff2'); }}")
    return "\n".join(reglas)


def construir(carpeta: Path, destino: Path, titulo: str = "") -> Path:
    src = (carpeta / "index.html").read_text(encoding="utf-8")
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
    out = out.replace("</style>", f"{fuentes_css()}\n{PLAYER_CSS}</style>", 1)
    m = SCRIPT_ENGINE_RE.search(out)       # se busca de nuevo: el texto cambió arriba
    motor = ("window.__timelines = {};\n"
             "document.fonts.ready.then(() => {\n" + m.group(1) + "\n" + m.group(2) + "\n" + PLAYER_JS + "\n});")
    out = out[:m.start()] + (
        f'<audio id="s2s-audio" preload="auto" playsinline src="data:audio/mpeg;base64,{mp3}"></audio>'
        '<div id="s2s-barra"></div><div id="s2s-tapa"><button>Tocar para ver</button></div>'
        f"<script>{motor}</script>") + out[m.end():]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(out, encoding="utf-8")
    return destino


INDICE = """<!doctype html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{titulo}</title>
<style>
:root {{ --bg:#0a0e0c; --fg:#eef3f0; --muted:#8fa197; --accent:#1fbf6a; --line:#1e2a23; color-scheme:dark; }}
* {{ box-sizing:border-box; margin:0; }}
body {{ background:var(--bg); color:var(--fg); font:16px/1.45 system-ui, sans-serif;
  padding:max(20px, env(safe-area-inset-top)) max(16px, env(safe-area-inset-right)) 32px max(16px, env(safe-area-inset-left)); }}
main {{ max-width:560px; margin:0 auto; display:grid; gap:18px; }}
h1 {{ font-size:22px; line-height:1.2; text-wrap:balance; }}
p.sub {{ color:var(--muted); font-size:14px; }}
ol {{ list-style:none; padding:0; display:grid; gap:8px; counter-reset:n; }}
li a {{ display:grid; grid-template-columns:2.2em 1fr auto; align-items:center; gap:10px; padding:14px;
  border:1px solid var(--line); border-radius:12px; color:inherit; text-decoration:none; }}
li a:hover, li a:focus-visible {{ border-color:var(--accent); outline:none; }}
li a::before {{ counter-increment:n; content:counter(n); font-variant-numeric:tabular-nums; color:var(--accent); font-weight:700; }}
.preg {{ color:var(--muted); font-size:13px; display:block; }}
.dur {{ color:var(--muted); font-size:13px; font-variant-numeric:tabular-nums; }}
</style></head><body><main>
<h1>{titulo}</h1>
<p class="sub">Un video por día, en orden. Cada uno prepara una pregunta del tribunal.</p>
<ol>
{items}
</ol>
</main></body></html>
"""


def indice(destino: Path, titulo: str, videos: list[dict]) -> Path:
    """videos: [{archivo, titulo, pregunta, duracion}] en el orden en que se ven."""
    items = "\n".join(
        f'<li><a href="{html.escape(v["archivo"])}"><span><b>{html.escape(v["titulo"])}</b>'
        f'<span class="preg">{html.escape(v.get("pregunta", ""))}</span></span>'
        f'<span class="dur">{int(v["duracion"]) // 60}:{int(v["duracion"]) % 60:02d}</span></a></li>'
        for v in videos)
    destino.write_text(INDICE.format(titulo=html.escape(titulo), items=items), encoding="utf-8")
    return destino


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    d = construir(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"{d} ({d.stat().st_size // 1024} KB)")
