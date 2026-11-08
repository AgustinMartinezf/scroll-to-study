"""Motor: lee spec.json + timing.json de una carpeta y escribe index.html (animación GSAP).

Uso:  python3 engine.py CARPETA
spec.json lo escribe compile.py (s2s.py guion); timing.json, voice.py. La página resultante es una
composición de HyperFrames; reproductor.py la convierte en un video que se reproduce solo en el navegador.
"""
import json, re, os, sys, html as H
from config import CFG

# estilo visual: temas/<nombre>.json (+ .css). Segundo argumento o S2S_ESTILO; por defecto, cuaderno
ESTILO = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("S2S_ESTILO", "cuaderno")
_ruta_tema = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temas", f"{ESTILO}.json")
if not os.path.exists(_ruta_tema):
    raise SystemExit(f"estilo desconocido «{ESTILO}»")
TEMA = json.load(open(_ruta_tema, encoding="utf-8"))
TP = TEMA["py"]

V = sys.argv[1]
HERE = os.path.abspath(V)
from types import SimpleNamespace
SPEC = SimpleNamespace(**json.load(open(f"{HERE}/spec.json", encoding="utf-8")))   # datos, nunca código
TM = json.load(open(f"{HERE}/timing.json", encoding="utf-8"))
D = round(TM["duration"], 2)
ICONS = CFG["iconos"]
SFX = CFG["sfx"]
# gsap y los efectos no se copian: reproductor.py los toma de su lugar (config.py)

def icon(name, size, color="currentColor"):
    svg = open(f"{ICONS}/{name}-bold.svg", encoding="utf-8").read()
    return svg.replace('<svg ', f'<svg width="{size}" height="{size}" style="color:{color};flex:none" ', 1)

def norm(w): return re.sub(r"[¿?¡!.,:;()«»\"]", "", w).lower()
words = TM["words"]; phrases = TM["phrases"]

def T(spec):
    """'3:palabra#2+0.1' -> segundos"""
    if isinstance(spec, (int, float)): return float(spec)
    if spec in ("0", "start"): return 0.0
    m = re.match(r"^(\d+)(?::([^#+\-]+)(?:#(\d+))?)?([+-][\d.]+)?$", spec)
    if not m: raise ValueError(spec)
    i = int(m.group(1)); w = m.group(2); n = int(m.group(3) or 1); off = float(m.group(4) or 0)
    if not w or w == "^": base = phrases[i]["start"]
    elif w == "$": base = phrases[i]["end"]
    else:
        hits = [x["start"] for x in words if x["phrase"] == i and norm(x["text"]) == norm(w)]
        if len(hits) < n: raise ValueError(f"palabra no encontrada: {spec}")
        base = hits[n - 1]
    return round(base + off, 3)

def phrase_of(t):
    for p in phrases:
        if p["start"] - 0.3 <= t <= p["end"] + 0.25: return p
    return None

# ---------- personajes ----------
def character(cid, shirt, hair="#2b1d14", glasses=False, skin="#f2c6a0"):
    g = f'<g fill="none" stroke="#17201a" stroke-width="4"><rect x="70" y="64" width="28" height="24" rx="8"/><rect x="104" y="64" width="28" height="24" rx="8"/><path d="M98 76 H104"/></g>' if glasses else ""
    return f"""<svg id="{cid}" class="char" viewBox="0 0 200 360" width="150" height="270">
  <g id="{cid}-legL"><rect x="78" y="228" width="24" height="104" rx="12" fill="#2a3340"/><rect x="70" y="320" width="40" height="18" rx="9" fill="#e8ecef"/></g>
  <g id="{cid}-legR"><rect x="100" y="228" width="24" height="104" rx="12" fill="#2a3340"/><rect x="96" y="320" width="40" height="18" rx="9" fill="#e8ecef"/></g>
  <g id="{cid}-body"><rect x="58" y="118" width="86" height="124" rx="34" fill="{shirt}"/></g>
  <g id="{cid}-armL"><rect x="48" y="126" width="24" height="96" rx="12" fill="{shirt}"/><circle cx="60" cy="222" r="13" fill="{skin}"/></g>
  <g id="{cid}-armR"><rect x="130" y="126" width="24" height="96" rx="12" fill="{shirt}"/><circle cx="142" cy="222" r="13" fill="{skin}"/></g>
  <g id="{cid}-head"><circle cx="101" cy="72" r="50" fill="{skin}"/><path d="M52 66 C52 26 150 20 151 64 C140 46 70 44 52 66Z" fill="{hair}"/>{g}
    <g id="{cid}-eyes"><ellipse cx="84" cy="76" rx="6.5" ry="8" fill="#17201a"/><ellipse cx="118" cy="76" rx="6.5" ry="8" fill="#17201a"/></g>
    <path id="{cid}-mouth" d="M88 100 Q101 110 114 100" stroke="#17201a" stroke-width="5" fill="none" stroke-linecap="round"/></g>
</svg>"""
ROLES = {"novato": ("#f08a24", "#5a3a1c", False), "pro": ("#1fae66", "#111", True), "estudiante": ("#2f6fe4", "#2b1d14", False),
         "admin": ("#7a5af8", "#2b1d14", True), "docente": ("#e0a400", "#3a2a10", False)}

KIND = {k: tuple(v) for k, v in TEMA["kind"].items()}
SK = '<i class="sk" data-layout-allow-occlusion></i>'

# ---------- elementos ----------
def el_table(e):
    cols = e["cols"]; w = e.get("weights", [1] * len(cols)); wid = e.get("w", 960)
    gt = "70px " + " ".join(f"{x}fr" for x in w)
    fs = e.get("fs", 46)
    hcells = "".join(f'<div class="hcell" id="{e["id"]}-h{j}" style="font-size:{fs-4}px">{H.escape(c)}{SK}</div>' for j, c in enumerate(cols))
    rows = ""
    for i, r in enumerate(e.get("rows", [])):
        rid = r.get("id", f'{e["id"]}-r{i}')
        cells = "".join(f'<div class="cell" id="{rid}-c{j}" style="font-size:{fs}px">{H.escape(str(c))}{SK}</div>' for j, c in enumerate(r["cells"]))
        rows += f'<div class="row" id="{rid}" style="grid-template-columns:{gt}"><div class="ico"><span id="{rid}-ok">{icon("check-circle",60,TP["icoOk"])}</span><span id="{rid}-no">{icon("x-circle",60,TP["icoNo"])}</span></div>{cells}</div>'
    h = 120 + 86 + 108 * len(e.get("rows", [])) + 24
    tag = f'<span class="ttag">{H.escape(e["tag"])}</span>' if e.get("tag") else ""
    return (f'<div class="card tbl" id="{e["id"]}" style="width:{wid}px;">'
            f'<div class="chead">{icon(e.get("icon","database"), 52, TP["cabeza"])}<span>{H.escape(e["title"])}</span>{tag}</div>'
            f'<div class="hrow" style="grid-template-columns:{gt}"><div></div>{hcells}</div>{rows}</div>'), wid, h

def el_chip(e):
    bg, fg = KIND[e.get("kind", "white")]
    fs = e.get("fs", 50); mono = e.get("mono", False)
    ic = icon(e["icon"], fs + 6, fg) if e.get("icon") else ""
    txt = H.escape(e["text"]) if not e.get("html") else e["text"]
    alt = ""
    if e.get("alt"):
        abg, afg = KIND[e.get("altkind", "good")]
        alt = f'<span class="alt" id="{e["id"]}-alt" style="background:{abg};color:{afg}">{H.escape(e["alt"])}</span>'
    fam = "'JetBrains Mono', monospace" if mono else "Inter"
    chars = len(re.sub(r"<[^>]+>", "", e["text"]))
    w = min(980, int(chars * fs * (0.6 if mono else 0.56)) + 80 + (fs + 20 if ic else 0))
    return (f'<div class="chip" id="{e["id"]}" style="background:{bg};color:{fg};font-family:{fam};font-size:{fs}px;font-weight:{800 if mono else 900}">'
            f'{ic}<span class="ctext">{txt}</span>{alt}{SK}</div>'), w, fs + 44

def el_toast(e):
    bad = e.get("kind", "bad") == "bad"
    col = TP["toastMal"] if bad else TP["toastBien"]
    fs = e.get("fs", 40)
    w = min(980, int(len(e["text"]) * fs * 0.6) + 140)
    return (f'<div class="toast" id="{e["id"]}" style="border-color:{col};font-size:{fs}px">{icon("x-circle" if bad else "check-circle", 56, col)}<span>{H.escape(e["text"])}</span></div>'), w, fs + 70

def el_dialog(e):
    role = e["char"]; shirt, hair, gl = ROLES[role]
    cid = e["id"] + "-c"
    kind = e.get("kind", "white" if role != "pro" else "good")
    bg, fg = KIND[kind]
    bw = e.get("bw", 720)
    return (f'<div class="dialog" id="{e["id"]}"><div class="cwrap" id="{e["id"]}-cw">{character(cid, shirt, hair, gl)}</div>'
            f'<div class="bubble" id="{e["id"]}-b" style="background:{bg};color:{fg};max-width:{bw}px">{e["text"]}</div></div>'), 960, 280

def el_console(e):
    lines = "".join(f'<div class="tyl" id="{e["id"]}-l{i}" data-n="{len(re.sub(r"<[^>]+>","",l))}">{l}</div>' for i, l in enumerate(e["lines"]))
    return (f'<div class="card console" id="{e["id"]}"><div class="chead" style="color:#9fdcb8">{icon("terminal-window",52,"#9fdcb8")}<span>{H.escape(e.get("title","mysql>"))}</span></div>'
            f'<div class="tybox">{lines}</div></div>'), 960, 120 + 70 * len(e["lines"]) + 30

def el_list(e):
    items = ""
    for it in e["items"]:
        iid, txt = it[0], it[1]
        ic = icon(it[2], 58, it[3] if len(it) > 3 else TP["cabeza"]) if len(it) > 2 and it[2] else ""
        items += f'<div class="li" id="{iid}">{ic}<span>{txt}</span>{SK}</div>'
    head = f'<div class="lhead">{icon(e.get("icon","list-checks"),50,TP["cabeza"])}<span>{H.escape(e["title"])}</span></div>' if e.get("title") else ""
    return (f'<div class="card lcard" id="{e["id"]}">{head}{items}</div>'), 960, (90 if e.get("title") else 30) + 84 * len(e["items"]) + 40

def el_arrow(e):
    lab = f'<div class="alab" id="{e["id"]}-lab">{H.escape(e.get("label",""))}</div>' if e.get("label") else ""
    col = e.get("color", TP["camino"])
    return (f'<div class="arrow" id="{e["id"]}"><svg width="60" height="110" viewBox="0 0 60 110" style="overflow:visible"><path id="{e["id"]}-p" d="M30 0 L30 92" stroke="{col}" stroke-width="10" stroke-linecap="round"/><path id="{e["id"]}-h" d="M10 78 L30 104 L50 78" stroke="{col}" stroke-width="10" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>{lab}</div>'), 600, 110

def el_flow(e):
    parts = []
    for k, it in enumerate(e["items"]):
        bg, fg = KIND[it.get("kind", "white")]
        ic = icon(it["icon"], 64, fg) if it.get("icon") else ""
        parts.append(f'<div class="fbox" id="{it["id"]}" style="background:{bg};color:{fg}">{ic}<span>{H.escape(it["text"])}</span>{SK}</div>')
        if k < len(e["items"]) - 1:
            parts.append(f'<div class="farrow" id="{e["id"]}-a{k}">{icon("arrow-right",56,TP["flecha"])}</div>')
    ancho = sum(max(220, len(it["text"]) * 24 + 40) + 76 for it in e["items"]) - 76   # misma cuenta que compile.py
    return f'<div class="flow" id="{e["id"]}">{"".join(parts)}</div>', min(980, ancho), 190

def el_big(e):
    fs = e.get("fs", 110)
    col = TP["big"] if e.get("color") in (None, "#1fbf6a", "#f4f7f5") else e["color"]
    return f'<div class="bigt" id="{e["id"]}" style="font-size:{fs}px;color:{col}">{e["text"]}{SK}</div>', 980, int(fs * 1.25)

def el_row(e):
    # varios chips en fila
    inner = []; tw = 0; mh = 0
    for c in e["items"]:
        h_, w_, hh = el_chip(c); inner.append(h_); tw += w_ + 24; mh = max(mh, hh)
    return f'<div class="crow" id="{e["id"]}">{"".join(inner)}</div>', min(980, tw), mh

def el_spacer(e): return f'<div id="{e["id"]}"></div>', 10, e.get("h", 20)

def el_counter(e):
    # dígitos en rodillo: cada dígito es una columna 0-9 que gira hasta su valor
    bg, fg = KIND[e.get("kind", "white")]
    fs = 150; digs = ""
    for ch in str(e["value"]):
        if ch.isdigit():
            col = "".join(f"<span>{d}</span>" for d in range(10))
            digs += f'<span class="dg" data-d="{ch}" style="height:{fs}px"><span class="dcol">{col}</span></span>'
        else:
            digs += f'<span class="dsep">{H.escape(ch)}</span>'
    lab = f'<div class="clab">{H.escape(e["label"])}</div>' if e.get("label") else ""
    w = min(980, max(420, int(len(str(e["value"])) * fs * 0.62) + 120))
    return (f'<div class="counter" id="{e["id"]}" style="background:{bg};color:{fg};font-size:{fs}px">'
            f'<div class="digits">{digs}</div>{lab}{SK}</div>'), w, fs + (90 if lab else 50)

def el_chart(e):
    bars = e["bars"]; mx = max(v for _, v in bars) or 1; unit = H.escape(e.get("unit", ""))
    rows = ""
    for i, (lab, v) in enumerate(bars):
        val = f"{v:g}{unit}"
        rows += (f'<div class="bar" id="{e["id"]}-b{i}"><span class="blab">{H.escape(str(lab))}</span>'
                 f'<span class="btrack"><span class="bfill" style="width:{100 * v / mx:.1f}%"></span></span>'
                 f'<span class="bval">{val}</span></div>')
    head = f'<div class="chead">{icon(e.get("icon", "chart-bar"), 52, TP["cabeza"])}<span>{H.escape(e["title"])}</span></div>' if e.get("title") else ""
    return f'<div class="card chart" id="{e["id"]}">{head}<div class="bars">{rows}</div></div>', 960, (110 if head else 40) + 96 * len(bars) + 30

def el_formula(e):
    # KaTeX la dibuja en el navegador (reproductor.py); acá se reserva el lugar
    tex = e["tex"]; fs = 64
    alta = 2.7 if re.search(r"\\(frac|dfrac|sum|int|prod|sqrt|lim|binom|begin)", tex) else 1.7
    lab = f'<div class="flab">{H.escape(e["label"])}</div>' if e.get("label") else ""
    w = min(960, max(360, int(len(re.sub(r"\\[a-zA-Z]+|[{}^_]", "", tex)) * fs * 0.55) + 120))
    return (f'<div class="formula" id="{e["id"]}" style="font-size:{fs}px"><div class="ftex" data-tex="{H.escape(tex)}">'
            f'{H.escape(tex)}</div>{lab}{SK}</div>'), w, int(fs * alta) + 56 + (60 if lab else 0)

VENN = {   # centros de los círculos y dónde va el texto de cada región (radio 210)
    2: {"c": [(-115, 0), (115, 0)], "pos": {"1": (-200, 0), "2": (200, 0), "12": (0, 0), "0": (330, -230)},
        "nom": [(-200, -235), (200, -235)], "h": 560},
    3: {"c": [(-115, -85), (115, -85), (0, 110)],
        "pos": {"1": (-215, -140), "2": (215, -140), "3": (0, 225), "12": (0, -150), "13": (-120, 55),
                "23": (120, 55), "123": (0, -20), "0": (330, -310)},
        "nom": [(-250, -310), (250, -310), (0, 360)], "h": 760},
}

def el_venn(e):
    n = len(e["sets"]); g = VENN[n]; W_, H_ = 780, g["h"]; cx, cy = W_ / 2, H_ / 2
    vid = e["id"]; r = 210
    defs, regs, labs = [], [], []
    for i, (x, y) in enumerate(g["c"]):
        defs.append(f'<clipPath id="{vid}-c{i}"><circle cx="{cx+x}" cy="{cy+y}" r="{r}"/></clipPath>')
    for code, (lx, ly) in g["pos"].items():
        dentro = [int(ch) - 1 for ch in code if ch != "0"]
        fuera = [i for i in range(n) if i not in dentro]
        defs.append(f'<mask id="{vid}-m{code}"><rect width="{W_}" height="{H_}" fill="#fff"/>'
                    + "".join(f'<circle cx="{cx+g["c"][i][0]}" cy="{cy+g["c"][i][1]}" r="{r}" fill="#000"/>' for i in fuera)
                    + '</mask>')
        forma = f'<rect width="{W_}" height="{H_}" rx="40"/>'
        for i in dentro:
            forma = f'<g clip-path="url(#{vid}-c{i})">{forma}</g>'
        regs.append(f'<g id="{vid}-{code}" class="vreg" mask="url(#{vid}-m{code})" fill="{TP["region"]}" opacity="0">{forma}</g>')
        txt = H.escape(str((e.get("labels") or {}).get(code, "")))
        labs.append(f'<text id="{vid}-{code}-t" class="vlab" x="{cx+lx}" y="{cy+ly}" text-anchor="middle" dominant-baseline="central">{txt}</text>')
    circ = "".join(f'<circle class="vcir" cx="{cx+x}" cy="{cy+y}" r="{r}"/>' for x, y in g["c"])
    noms = "".join(f'<text class="vnom" x="{cx+x}" y="{cy+y}" text-anchor="middle">{H.escape(s)}</text>'
                   for (x, y), s in zip(g["nom"], e["sets"]))
    head = f'<div class="chead">{icon("list-checks", 52, TP["cabeza"])}<span>{H.escape(e["title"])}</span></div>' if e.get("title") else ""
    svg = (f'<svg viewBox="0 0 {W_} {H_}" width="{W_}" height="{H_}"><defs>{"".join(defs)}</defs>'
           f'<rect class="vuni" x="4" y="4" width="{W_-8}" height="{H_-8}" rx="40"/>{"".join(regs)}{circ}{noms}{"".join(labs)}</svg>')
    return f'<div class="card venn" id="{vid}">{head}<div class="vbox">{svg}</div></div>', 860, H_ + (110 if head else 40)

def el_countdown(e):
    seg = e.get("seconds", 3)
    nums = "".join(f'<span class="cdn" id="{e["id"]}-n{k}">{k}</span>' for k in range(seg, 0, -1))
    return (f'<div class="countdown" id="{e["id"]}" data-s="{seg}"><svg class="cdr" viewBox="0 0 200 200">'
            f'<circle cx="100" cy="100" r="88"/><circle class="cdp" id="{e["id"]}-p" cx="100" cy="100" r="88"/></svg>{nums}</div>'), 300, 300

def el_chat(e):
    msgs = ""
    for i, (lado, txt) in enumerate(e["msgs"]):
        msgs += (f'<div class="msg {lado}" id="{e["id"]}-m{i}"><span class="dots"><i></i><i></i><i></i></span>'
                 f'<span class="mtxt">{H.escape(txt)}</span></div>')
    head = f'<div class="chathead">{icon("users", 44, "#ffffff")}<span>{H.escape(e.get("title", "Chat"))}</span></div>'
    return f'<div class="card chat" id="{e["id"]}">{head}<div class="msgs">{msgs}</div></div>', 960, 110 + 118 * len(e["msgs"]) + 30

MAKERS = {"table": el_table, "chip": el_chip, "toast": el_toast, "dialog": el_dialog, "console": el_console,
          "list": el_list, "arrow": el_arrow, "flow": el_flow, "big": el_big, "row": el_row, "spacer": el_spacer,
          "counter": el_counter, "chart": el_chart, "chat": el_chat, "formula": el_formula, "venn": el_venn, "countdown": el_countdown}

# ---------- estaciones ----------
STATIONS = list(SPEC.STATIONS)
FINAL = SPEC.FINAL
final_items = [(lid, html_, None) for (lid, html_, _) in FINAL["lines"]]
STATIONS.append([
    {"type": "list", "id": "fcard", "title": FINAL.get("title", "PARA EXPLICARLO"), "icon": "seal-check", "items": [(lid, html_) for (lid, html_, _) in FINAL["lines"]]},
    {"type": "dialog", "id": "fpro", "char": "pro", "text": FINAL.get("say", "Decilo así"), "kind": "good"},
    {"type": "chip", "id": "fnext", "text": FINAL.get("next_label", "Mañana: " + FINAL["next"]), "kind": "neutral", "icon": "calendar-check", "fs": 44},
])
# los bloques con métodos que no salen del material llevan una etiqueta que lo dice
for si, gen in enumerate(getattr(SPEC, "GENERAL", [])):
    if gen and si < len(STATIONS) - 1:
        _txt_general = {"es": "método general · no está en tu material", "en": "general method · not in your material"}
        STATIONS[si] = [{"type": "chip", "id": f"gen{si}", "text": _txt_general.get(getattr(SPEC, "IDIOMA", "es"), _txt_general["es"]),
                         "kind": "neutral", "icon": "lightning", "fs": 32, "gap": 24}] + list(STATIONS[si])
GAP_Y = 520
station_html = []; boxes = []
y = 300
for si, st in enumerate(STATIONS):
    x = 540 if si % 2 == 0 else 1800
    items = []; cy = 0; maxw = 0
    for e in st:
        h_, w_, hh = MAKERS[e["type"]](e)
        items.append((e, h_, w_, hh, cy)); cy += hh + e.get("gap", 40); maxw = max(maxw, w_)
    hgt = cy - 40
    top = y
    inner = ""
    for e, h_, w_, hh, oy in items:
        al = e.get("align", "center")
        left = x - 490 if al == "left" else (x + 490 - w_ if al == "right" else x - w_ / 2)
        left = max(x - 490, min(left, x + 490 - w_))
        inner += f'<div class="slot" style="left:{left:.0f}px; top:{top+oy:.0f}px; width:{w_:.0f}px;">{h_}</div>\n'
    station_html.append(inner)
    boxes.append({"x": x, "top": top, "h": hgt, "w": max(maxw, 600)})
    y = top + hgt + GAP_Y

paths = []
for i in range(len(boxes) - 1):
    a, b = boxes[i], boxes[i + 1]
    y0 = a["top"] + a["h"] + 40; y1 = b["top"] - 40
    paths.append(f'<path id="pth{i}" d="M{a["x"]} {y0} C{a["x"]} {y0+260} {b["x"]} {y1-260} {b["x"]} {y1}" stroke="{TP["camino"]}" stroke-width="12" fill="none" stroke-linecap="round"/>')
WORLD_H = y + 400

# ---------- eventos ----------
EV = []
for ev in SPEC.EVENTS:
    when, act, tid = ev[0], ev[1], ev[2]
    extra = ev[3] if len(ev) > 3 else {}
    EV.append({"t": T(when), "a": act, "id": tid, "x": extra})
# final
EV.append({"t": T(FINAL["start"]), "a": "show", "id": "fcard", "x": {}})
EV.append({"t": T(FINAL["start"]) + 0.15, "a": "show", "id": "fpro", "x": {}})
for (lid, _, when) in FINAL["lines"]:
    EV.append({"t": T(when), "a": "show", "id": lid, "x": {"from": "left"}})
EV.append({"t": T(FINAL["next_at"]), "a": "show", "id": "fnext", "x": {}})
EV.sort(key=lambda e: e["t"])

# a qué estación pertenece cada id
owner = {}
def collect(e, si):
    owner[e["id"]] = si
    if e["type"] == "table":
        for i, r in enumerate(e.get("rows", [])):
            rid = r.get("id", f'{e["id"]}-r{i}'); owner[rid] = si
            for j in range(len(r["cells"])): owner[f"{rid}-c{j}"] = si
        for j in range(len(e["cols"])): owner[f'{e["id"]}-h{j}'] = si
    for k in ("items",):
        for it in e.get(k, []) or []:
            if isinstance(it, dict): owner[it["id"]] = si
            elif isinstance(it, (list, tuple)): owner[it[0]] = si
    if e["type"] == "console":
        for i in range(len(e["lines"])): owner[f'{e["id"]}-l{i}'] = si
    if e["type"] == "chart":
        for i in range(len(e["bars"])): owner[f'{e["id"]}-b{i}'] = si
    if e["type"] == "chat":
        for i in range(len(e["msgs"])): owner[f'{e["id"]}-m{i}'] = si
    if e["type"] == "venn":
        for code in VENN[len(e["sets"])]["pos"]: owner[f'{e["id"]}-{code}'] = si
for si, st in enumerate(STATIONS):
    for e in st: collect(e, si)

# entrada a cada estación = primer evento que la toca
enter = {0: 0.0}
for e in EV:
    si = owner.get(e["id"], None)
    if si is None: raise SystemExit(f"id sin estación: {e['id']}")
    if si not in enter: enter[si] = e["t"]
# los viajes empiezan un poco antes de la primera aparición, al inicio de su frase
travel = {}
for si in range(1, len(STATIONS)):
    t0 = enter[si]
    p = phrase_of(t0)
    start = max(min(t0 - 0.35, (p["start"] if p else t0) - 0.25), t0 - 1.0)
    if p and p["i"] > 0:                       # no salir antes de que termine la frase anterior
        start = max(start, phrases[p["i"] - 1]["end"] + 0.35)
    travel[si] = round(max(start, 0.5), 3)

# lo que aparece muy poco antes de que la cámara se vaya de su escena casi no se ve
avisos = []
for e in EV:
    si = owner[e["id"]]
    if e["a"] != "show" or si >= len(STATIONS) - 1:
        continue
    visible = travel[si + 1] - e["t"]
    if visible < 1.2:
        avisos.append({"id": e["id"], "t": e["t"], "visible": round(visible, 2),
                       "msg": f"«{e['id']}» aparece {max(0, visible):.1f} s antes de que la cámara cambie de escena: "
                              "adelantá su {show} o agregá una frase corta después"})
json.dump(avisos, open(f"{HERE}/avisos.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# hidden by default: todo lo que aparece por evento show / type
hidden = sorted({e["id"] for e in EV if e["a"] in ("show",)})

# ---------- subtítulos ----------
KG = set(getattr(SPEC, "KEY_GOOD", [])); KB = set(getattr(SPEC, "KEY_BAD", []))
# resaltado por aparición: (frase, índice de palabra) -> "kg" | "kb"
KEYS = {(p, i): ("kg" if k == "g" else "kb") for p, i, k in getattr(SPEC, "KEYS", [])}
POS = {}
for ph in phrases:
    for k, w in enumerate(w for w in words if w["phrase"] == ph["i"]): POS[id(w)] = k
groups = []
for ph in phrases:
    ws = [w for w in words if w["phrase"] == ph["i"]]; cur = []
    for w in ws:
        cur.append(w)
        if len(cur) >= 4 or re.search(r"[,.:?]$", w["text"]): groups.append(cur); cur = []
    if cur: groups.append(cur)
merged = []
for g in groups:
    if merged and len(g) == 1 and len(merged[-1]) < 4 and merged[-1][0]["phrase"] == g[0]["phrase"]: merged[-1] = merged[-1] + g
    else: merged.append(g)
groups = merged
cap_html = []
for gi, g in enumerate(groups):
    st = max(0.1, g[0]["start"] - 0.05)
    nxt = groups[gi + 1][0]["start"] - 0.05 if gi + 1 < len(groups) else D
    en = min(nxt, g[-1]["end"] + 0.6)
    spans = []
    for wi, w in enumerate(g):
        n = norm(w["text"])
        if hasattr(SPEC, "KEYS"): kind = KEYS.get((w["phrase"], POS[id(w)]), "")
        else: kind = "kg" if n in KG else ("kb" if n in KB else "")
        spans.append(f'<span class="w {kind}" data-t="{w["start"]}">{H.escape(w["text"])}</span>')
    cap_html.append(f'<div id="cap{gi}" class="clip capg" data-start="{st:.3f}" data-duration="{max(0.2,en-st):.3f}" data-track-index="5">{" ".join(spans)}</div>')

# ---------- sonido ----------
MAN = json.load(open(f"{SFX}/manifest.json", encoding="utf-8")); DUR = {v["file"]: v["duration"] for v in MAN.values()}
audio = []; trk = [0]; last = {}
def sfx(f, t, vol=0.4):
    if t < 0 or t > D - 0.2: return
    k = f
    if k in last and t - last[k] < 0.25: return
    last[k] = t
    trk[0] += 1
    d = min(DUR.get(f, 1.0), D - t - 0.01)
    audio.append(f'<audio id="sx{len(audio)}" class="clip" src="assets/sfx/{f}" data-start="{t:.3f}" data-duration="{d:.3f}" data-track-index="{9 + trk[0] % 4}" data-volume="{vol}"></audio>')
sfx("impact-bass-2.mp3", 0.0, 0.45)
POPS = ["pop.mp3", "click-soft.mp3"]
whs = ["whoosh-short.mp3", "whoosh.mp3", "whoosh-cinematic.mp3"]
for si, t in travel.items(): sfx(whs[si % 3], t - 0.05, 0.32)
pc = 0
for e in EV:
    t = e["t"] - 0.02
    if e["a"] == "show": sfx(POPS[pc % 2], t, 0.35 if pc % 2 == 0 else 0.45); pc += 1
    elif e["a"] == "bad": sfx("glitch-3.mp3", t, 0.3)
    elif e["a"] == "type": sfx("typing.mp3", t, 0.3)
    elif e["a"] == "boom": sfx("impact-bass-1.mp3", t, 0.55); sfx("riser.mp3", t - 1.9, 0.2)
    elif e["a"] in ("good",): sfx("click.mp3", t, 0.35)
    elif e["a"] == "strike": sfx("click-soft.mp3", t, 0.45)

STATE = {"C": TEMA["c"], "D": D, "boxes": boxes, "EV": EV, "travel": travel, "hidden": hidden, "words": words, "phrases": phrases,
         "chars": [e["id"] + "-c" for st in STATIONS for e in st if e["type"] == "dialog"],
         "charStation": {e["id"] + "-c": si for si, st in enumerate(STATIONS) for e in st if e["type"] == "dialog"},
         "enter": enter, "nst": len(STATIONS), "stEls": [[e["id"] for e in st] for st in STATIONS]}

CSS = open(CFG["css"], encoding="utf-8").read()
if TEMA.get("css"):
    CSS += "\n" + open(os.path.join(os.path.dirname(_ruta_tema), TEMA["css"]), encoding="utf-8").read()
HTML = f"""<!doctype html>
<html lang="{getattr(SPEC, 'IDIOMA', 'es')}"><head><meta charset="UTF-8" /><meta name="viewport" content="width=1080, height=1920" />
<script src="assets/gsap.min.js"></script><style>{CSS}</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{D}" data-width="1080" data-height="1920">
<div id="bg" class="clip" data-start="0" data-duration="{D}" data-track-index="0" data-layout-ignore><div id="grid"></div><div id="glow"></div></div>
<div id="stage" class="clip" data-start="0" data-duration="{D}" data-track-index="1" data-layout-allow-overflow data-layout-allow-overlap>
<div id="shake" class="abs" style="left:0;top:0;width:1080px;height:1920px;">
<div id="drift" class="abs" style="left:0;top:0;width:1080px;height:1920px;transform-origin:540px 960px"><div id="world" style="height:{WORLD_H}px">
<svg class="abs" style="left:0;top:0;overflow:visible" width="2600" height="{WORLD_H}"><path d="M540 -600 L540 260" stroke="{TP['inicio']}" stroke-width="10" fill="none" stroke-dasharray="4 26" stroke-linecap="round"/>{"".join(paths)}</svg>
{"".join(station_html)}
</div></div></div></div>
<div id="caps" class="abs" style="left:0;top:0;width:1080px;height:1920px;pointer-events:none;">
{chr(10).join(cap_html)}
</div>
<audio id="voz" class="clip" src="assets/voz.wav" data-start="0" data-track-index="7" data-volume="1"></audio>
<audio id="musica" class="clip" src="assets/musica.wav" data-start="0" data-duration="{D}" data-track-index="8" data-volume="0.14"></audio>
{chr(10).join(audio)}
</div>
<script>const S = {json.dumps(STATE, ensure_ascii=False)};</script>
<script>{open(CFG["js"], encoding="utf-8").read()}</script>
</body></html>"""
open(f"{HERE}/index.html", "w", encoding="utf-8").write(HTML)
print("ok", V, D, "estaciones", len(STATIONS), "eventos", len(EV), "viajes", travel)
