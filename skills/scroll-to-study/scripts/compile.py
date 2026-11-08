#!/usr/bin/env python3
"""Compilador de guiones: guion.json (lo que escribe el LLM) -> spec.json + script.json + gaps.json.

Uso:
  python3 compile.py vNN/guion.json [--lexico lexico.json] [--iconos DIR] [-o DIR] [--solo-validar]

Formato de las frases:
  {accion id [+/-seg] [clave=valor ...]}  dispara la acción en la palabra que sigue
  [+palabra] / [-palabra]                 resalta esa aparición en verde / rojo

Todo lo que el motor puede deducir (GAPS, KEY_*, tamaños de letra, pronunciación, anclas)
lo calcula este script. Sale con código 1 si hay errores; los avisos no frenan.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constantes que tienen que coincidir con engine.py / engine.js
# ---------------------------------------------------------------------------

def norm(w: str) -> str:
    """Misma normalización que engine.py usa para buscar palabras."""
    return re.sub(r"[¿?¡!.,:;()«»\"]", "", w).lower()


ACCIONES = {"show", "hide", "hl", "good", "bad", "strike", "swap", "type",
            "pulse", "shake", "boom", "point", "focus", "send"}
EXTRAS_VALIDOS = {"from", "rot", "until", "bg", "color", "dur", "s", "dy", "de", "a", "texto"}
KINDS = {"good", "bad", "warn", "neutral", "blue", "white", "purple"}
ROLES = {"novato", "pro", "estudiante", "admin", "docente"}
IDS_FINAL = {"fcard", "fpro", "fnext"}

# claves obligatorias y opcionales por tipo (lo que lee cada el_* de engine.py)
TIPOS: dict[str, tuple[set[str], set[str]]] = {
    "table":   ({"id", "title", "cols"}, {"rows", "weights", "tag", "icon"}),
    "chip":    ({"id", "text"}, {"kind", "icon", "mono", "alt", "altkind", "html"}),
    "toast":   ({"id", "text"}, {"kind"}),
    "dialog":  ({"id", "char", "text"}, {"kind", "bw"}),
    "console": ({"id", "lines"}, {"title"}),
    "list":    ({"id", "items"}, {"title", "icon"}),
    "arrow":   ({"id"}, {"label", "color"}),
    "flow":    ({"id", "items"}, set()),
    "big":     ({"id", "text"}, {"color"}),
    "row":     ({"id", "items"}, set()),
    "spacer":  ({"id"}, {"h"}),
    "counter": ({"id", "value"}, {"label", "kind"}),
    "chart":   ({"id", "bars"}, {"title", "unit", "icon"}),
    "chat":    ({"id", "msgs"}, {"title"}),
    "formula": ({"id", "tex"}, {"label"}),
    "venn":    ({"id", "sets"}, {"labels", "title"}),
    "countdown": ({"id"}, {"seconds"}),
}
COMUNES = {"type", "gap", "align"}
LAYOUT_DEL_COMPILADOR = {"fs", "w"}   # si el LLM los pone, se ignoran

# Ancho útil de una estación (el motor centra en x±490; dejo margen)
ANCHO_MAX = 960
FS_MIN = 28
RITMO = 6.15         # sílabas por segundo de Piper davefx a velocidad 1.1 (medido en 59 frases)
PAUSA_BLOQUE = 0.4   # GAPS al final de cada bloque
PAUSA_TARDIA = 1.0   # ... si lo último que aparece cae en las últimas palabras
PAUSA_FRASE = 0.22   # voice.py: GAP por defecto


# ---------------------------------------------------------------------------
# Reporte
# ---------------------------------------------------------------------------

@dataclass
class Reporte:
    errores: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    def error(self, donde: str, msg: str) -> None:
        self.errores.append(f"{donde}: {msg}")

    def aviso(self, donde: str, msg: str) -> None:
        self.avisos.append(f"{donde}: {msg}")


# ---------------------------------------------------------------------------
# Frases
# ---------------------------------------------------------------------------

@dataclass
class Etiqueta:
    accion: str
    id: str
    off: float
    extra: dict[str, Any]


@dataclass
class Frase:
    palabras: list[str]
    etiquetas: list[tuple[int, Etiqueta]]   # (índice de palabra, etiqueta)
    marcas: list[tuple[int, str]]           # (índice de palabra, "g" | "b")


TOKEN = re.compile(r"\{([^{}]*)\}|(\s+)|(\{)|([^\s{]+)")
MARCA = re.compile(r"(.*?)\[([+-])([^\[\]\s]+)\](.*)")
OFFSET = re.compile(r"[+-]\d+(\.\d+)?")


def _valor(v: str) -> Any:
    if v in ("true", "false"):
        return v == "true"
    try:
        return float(v) if "." in v else int(v)
    except ValueError:
        return v


def parsear_etiqueta(txt: str, donde: str, rep: Reporte) -> Etiqueta | None:
    toks = txt.split()
    if len(toks) < 2:
        rep.error(donde, f"etiqueta incompleta {{{txt}}}: falta acción o id")
        return None
    accion, id_ = toks[0], toks[1]
    if accion not in ACCIONES:
        rep.error(donde, f"acción desconocida «{accion}»")
        return None
    off = 0.0
    extra: dict[str, Any] = {}
    for t in toks[2:]:
        if OFFSET.fullmatch(t):
            off = float(t)
        elif "=" in t:
            k, v = t.split("=", 1)
            if k not in EXTRAS_VALIDOS:
                rep.aviso(donde, f"extra «{k}» no lo usa el motor")
            extra[k] = _valor(v)
        else:
            rep.error(donde, f"no entiendo «{t}» en {{{txt}}}")
    return Etiqueta(accion, id_, off, extra)


def parsear_frase(texto: str, donde: str, rep: Reporte) -> Frase:
    palabras: list[str] = []
    etiquetas: list[tuple[int, Etiqueta]] = []
    marcas: list[tuple[int, str]] = []
    pendientes: list[Etiqueta] = []
    if "COMPROBAR" in texto:
        rep.error(donde, "tiene [COMPROBAR] sin resolver")
    for m in TOKEN.finditer(texto):
        tag, _esp, llave_suelta, palabra = m.groups()
        if tag is not None:
            et = parsear_etiqueta(tag, donde, rep)
            if et:
                pendientes.append(et)
        elif llave_suelta:
            rep.error(donde, "llave «{» sin cerrar")
        elif palabra:
            mm = MARCA.fullmatch(palabra)
            if mm:
                palabra = mm.group(1) + mm.group(3) + mm.group(4)
                marcas.append((len(palabras), "g" if mm.group(2) == "+" else "b"))
            if any(c in palabra for c in "[]}"):
                rep.error(donde, f"marca mal formada en «{palabra}» (una sola palabra: [+palabra])")
            if "~" in palabra:
                rep.error(donde, f"«{palabra}»: la pronunciación va en el léxico, no en el guion")
            idx = len(palabras)
            palabras.append(palabra)
            etiquetas.extend((idx, et) for et in pendientes)
            pendientes = []
    if pendientes:
        rep.error(donde, "etiqueta al final de la frase sin palabra después")
    if not palabras:
        rep.error(donde, "frase vacía")
    return Frase(palabras, etiquetas, marcas)


def ancla(i_frase: int, frase: Frase, idx: int, off: float, donde: str, rep: Reporte) -> str:
    """Traduce (frase, palabra, desfase) a la sintaxis de engine.py: 'i:palabra#n+off'."""
    if i_frase == 0 and idx == 0:          # arranque del video
        return "0" if off == 0 else f"0:^{off:+g}"
    w = norm(frase.palabras[idx])
    if not w or any(c in w for c in "#+-") or w in ("^", "$"):
        rep.error(donde, f"no se puede anclar a «{frase.palabras[idx]}» "
                         "(el motor no acepta - + # en la palabra); mové la etiqueta a otra")
        return "0"
    n = sum(norm(p) == w for p in frase.palabras[: idx + 1])
    s = f"{i_frase}:{w}" + (f"#{n}" if n > 1 else "")
    return s + (f"{off:+g}" if off else "")


# ---------------------------------------------------------------------------
# Pronunciación
# ---------------------------------------------------------------------------

PUNT = re.compile(r"([¿¡(«\"]*)(.*?)([.,:;?!)»\"]*)")


def pronunciar(palabra: str, lex: dict[str, str], donde: str, rep: Reporte) -> str:
    pre, nucleo, post = PUNT.fullmatch(palabra).groups()  # type: ignore[union-attr]
    bajo = nucleo.lower()
    if bajo in lex:
        nucleo = lex[bajo]
    elif "_" in nucleo:
        nucleo = "~".join(lex.get(p.lower(), p) for p in nucleo.split("_"))
    elif re.fullmatch(r"[A-Z]{2,}", nucleo):
        rep.aviso(donde, f"¿cómo se pronuncia «{nucleo}»? agregalo al léxico")
    return pre + nucleo + post


# ---------------------------------------------------------------------------
# Elementos: ids, chequeos y tamaño de letra
# ---------------------------------------------------------------------------

def _texto_plano(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def fs_chip(e: dict[str, Any], maxw: float) -> int:
    """Mayor fs (tope 50) para que entre en maxw según la estimación de el_chip."""
    chars = max(1, len(_texto_plano(e["text"])))
    k = 0.6 if e.get("mono") else 0.56
    ic = 1 if e.get("icon") else 0
    return min(50, int((maxw - 80 - 20 * ic) / (chars * k + ic)))


def fs_tabla(e: dict[str, Any]) -> int:
    cols = e["cols"]
    pesos = e.get("weights", [1] * len(cols))
    util = 960 - 44 - 70          # card 960 - márgenes de fila - columna del ícono
    fs = 46
    for j, c in enumerate(cols):
        colw = util * pesos[j] / sum(pesos)
        fs = min(fs, int((colw - 24) / (0.62 * max(1, len(c)))) + 4)   # encabezado: fs-4
        for r in e.get("rows", []):
            fs = min(fs, int((colw - 16) / (0.62 * max(1, len(str(r["cells"][j]))))))
    return fs


def fs_toast(e: dict[str, Any]) -> int:
    return min(40, int((ANCHO_MAX - 140) / (0.6 * max(1, len(e["text"])))))


@dataclass
class Ids:
    todos: set[str] = field(default_factory=set)
    con_tachado: set[str] = field(default_factory=set)   # tienen .sk adentro
    con_alt: set[str] = field(default_factory=set)
    barras: set[str] = field(default_factory=set)
    flujos: dict[str, list[str]] = field(default_factory=dict)   # id del flow -> ids de sus cajas
    cuentas: dict[str, int] = field(default_factory=dict)        # id de countdown -> segundos
    consolas: set[str] = field(default_factory=set)
    dialogos: set[str] = field(default_factory=set)


def preparar_elemento(e: dict[str, Any], donde: str, rep: Reporte, ids: Ids,
                      iconos: set[str]) -> dict[str, Any] | None:
    """Valida un elemento y devuelve la versión que espera engine.py (con fs calculado)."""
    tipo = e.get("type")
    if tipo not in TIPOS:
        rep.error(donde, f"tipo de elemento desconocido «{tipo}»")
        return None
    req, opc = TIPOS[tipo]
    falta = req - e.keys()
    if falta:
        rep.error(donde, f"{tipo} sin {sorted(falta)}")
        return None
    donde = f"{donde} ({tipo} {e['id']})"
    for k in e.keys() - req - opc - COMUNES:
        if k in LAYOUT_DEL_COMPILADOR:
            rep.aviso(donde, f"«{k}» lo calcula el compilador; lo ignoro")
        else:
            rep.aviso(donde, f"clave «{k}» desconocida")
    out = {k: v for k, v in e.items() if k not in LAYOUT_DEL_COMPILADOR}

    def nuevo_id(i: str) -> None:
        if i in ids.todos or i in IDS_FINAL or re.fullmatch(r"fl\d+", i):
            rep.error(donde, f"id repetido o reservado «{i}»")
        ids.todos.add(i)

    nuevo_id(e["id"])
    if e.get("icon"):
        iconos.add(e["icon"])
    if "kind" in e and tipo in ("chip", "dialog") and e["kind"] not in KINDS:
        rep.error(donde, f"kind «{e['kind']}» no existe ({sorted(KINDS)})")

    if tipo == "table":
        iconos.add(e.get("icon", "database"))
        filas = []
        for i, r in enumerate(e.get("rows", [])):
            r = {"cells": r} if isinstance(r, list) else r
            if len(r["cells"]) != len(e["cols"]):
                rep.error(donde, f"la fila {i} tiene {len(r['cells'])} celdas y hay {len(e['cols'])} columnas")
                return None
            rid = r.get("id", f"{e['id']}-r{i}")
            nuevo_id(rid)
            for j in range(len(r["cells"])):
                nuevo_id(f"{rid}-c{j}")
                ids.con_tachado.add(f"{rid}-c{j}")
            filas.append(r)
        out["rows"] = filas
        for j in range(len(e["cols"])):
            nuevo_id(f"{e['id']}-h{j}")
            ids.con_tachado.add(f"{e['id']}-h{j}")
        if "weights" in e and len(e["weights"]) != len(e["cols"]):
            rep.error(donde, "weights no tiene una entrada por columna")
            return None
        if len(filas) > 5:
            rep.aviso(donde, f"{len(filas)} filas: la cámara va a alejarse mucho")
        out["fs"] = fs_tabla(out)
    elif tipo == "chip":
        ids.con_tachado.add(e["id"])
        if e.get("alt"):
            ids.con_alt.add(e["id"])
            if e.get("altkind", "good") not in KINDS:
                rep.error(donde, f"altkind «{e['altkind']}» no existe")
            if len(e["alt"]) > len(_texto_plano(e["text"])):
                rep.aviso(donde, "el texto alternativo es más largo que el original y puede no entrar")
        out["fs"] = fs_chip(e, ANCHO_MAX)
    elif tipo == "toast":
        out["fs"] = fs_toast(e)
    elif tipo == "dialog":
        ids.dialogos.add(e["id"])
        if e["char"] not in ROLES:
            rep.error(donde, f"personaje «{e['char']}» no existe ({sorted(ROLES)})")
    elif tipo == "console":
        ids.consolas.add(e["id"])
        iconos.add("terminal-window")
        for i in range(len(e["lines"])):
            nuevo_id(f"{e['id']}-l{i}")
    elif tipo == "list":
        iconos.add(e.get("icon", "list-checks"))
        for it in e["items"]:
            nuevo_id(it[0])
            ids.con_tachado.add(it[0])
            if len(it) > 2 and it[2]:
                iconos.add(it[2])
    elif tipo == "flow":
        iconos.add("arrow-right")
        ids.flujos[e["id"]] = [it["id"] for it in e["items"]]
        ancho = 0
        for it in e["items"]:
            nuevo_id(it["id"])
            ids.con_tachado.add(it["id"])
            if it.get("icon"):
                iconos.add(it["icon"])
            if it.get("kind", "white") not in KINDS:
                rep.error(donde, f"kind «{it['kind']}» no existe")
            ancho += max(220, len(it["text"]) * 24 + 40) + 76
        if ancho - 76 > 980:
            rep.aviso(donde, f"el flujo mide ~{ancho - 76}px y no entra en 980; acortá textos o usá menos cajas")
    elif tipo == "big":
        ids.con_tachado.add(e["id"])
    elif tipo == "counter":
        v = str(e["value"])
        if not re.search(r"\d", v) or len(v) > 10:
            rep.error(donde, f"value «{v}»: tiene que ser un número de hasta 10 caracteres (puede llevar . , % o unidad)")
        if len(e.get("label", "")) > 40:
            rep.error(donde, "label de más de 40 caracteres")
        if e.get("kind", "white") not in KINDS:
            rep.error(donde, f"kind «{e['kind']}» no existe")
        ids.con_tachado.add(e["id"])
    elif tipo == "chart":
        iconos.add(e.get("icon", "chart-bar"))
        barras = e["bars"]
        if not 2 <= len(barras) <= 5:
            rep.error(donde, "un chart lleva entre 2 y 5 barras")
            return None
        for i, b in enumerate(barras):
            if not (isinstance(b, (list, tuple)) and len(b) == 2 and isinstance(b[1], (int, float)) and b[1] >= 0):
                rep.error(donde, f"la barra {i} tiene que ser [\"etiqueta\", número >= 0]")
                return None
            if len(str(b[0])) > 18:
                rep.error(donde, f"la etiqueta de la barra {i} pasa de 18 caracteres")
            nuevo_id(f"{e['id']}-b{i}")
            ids.barras.add(f"{e['id']}-b{i}")
    elif tipo == "venn":
        sets = e["sets"]
        if len(sets) not in (2, 3) or any(not isinstance(x, str) or not 1 <= len(x) <= 12 for x in sets):
            rep.error(donde, "sets: 2 o 3 nombres de hasta 12 caracteres")
            return None
        regiones = ["1", "2", "12", "0"] if len(sets) == 2 else ["1", "2", "3", "12", "13", "23", "123", "0"]
        for r in regiones:
            nuevo_id(f"{e['id']}-{r}")
        for r, txt in (e.get("labels") or {}).items():
            if r not in regiones:
                rep.error(donde, f"labels: la región «{r}» no existe (hay {', '.join(regiones)})")
            elif len(str(txt)) > 6:
                rep.error(donde, f"labels: «{txt}» pasa de 6 caracteres")
    elif tipo == "countdown":
        seg = e.get("seconds", 3)
        if not isinstance(seg, int) or not 2 <= seg <= 5:
            rep.error(donde, "seconds tiene que ser un entero de 2 a 5")
        ids.cuentas[e["id"]] = seg if isinstance(seg, int) else 3
    elif tipo == "formula":
        tex = e["tex"]
        if not tex.strip() or len(tex) > 140:
            rep.error(donde, "tex vacío o de más de 140 caracteres: partí la fórmula en dos")
        if re.search(r"\\(href|url|includegraphics|html\w*)\b", tex):
            rep.error(donde, "la fórmula usa un comando que no se permite (\\href, \\url, \\html…)")
        if tex.count("{") != tex.count("}"):
            rep.error(donde, "llaves { } desbalanceadas en la fórmula")
        if len(e.get("label", "")) > 50:
            rep.error(donde, "label de más de 50 caracteres")
        ids.con_tachado.add(e["id"])
    elif tipo == "chat":
        msgs = e["msgs"]
        if not 1 <= len(msgs) <= 4:
            rep.error(donde, "un chat lleva entre 1 y 4 mensajes")
            return None
        for i, m in enumerate(msgs):
            if not (isinstance(m, (list, tuple)) and len(m) == 2 and m[0] in ("a", "b")):
                rep.error(donde, f"el mensaje {i} tiene que ser [\"a\"|\"b\", texto]")
                return None
            if len(m[1]) > 70:
                rep.error(donde, f"el mensaje {i} pasa de 70 caracteres")
            nuevo_id(f"{e['id']}-m{i}")
    elif tipo == "row":
        n = len(e["items"])
        maxw = (ANCHO_MAX - 24 * (n - 1)) / max(1, n)
        chips = []
        for it in e["items"]:
            c = preparar_elemento({"type": "chip", **it}, donde, rep, ids, iconos)
            if c:
                c.pop("type")
                c["fs"] = fs_chip(c, maxw)
                if c["fs"] < FS_MIN:
                    rep.error(donde, f"el chip «{c['id']}» no entra en la fila; usá menos chips o textos más cortos")
                chips.append(c)
        out["items"] = chips

    fs = out.get("fs")
    if fs is not None and fs < FS_MIN:
        rep.error(donde, f"el texto no entra ni con letra {fs}px; acortalo o partilo en dos elementos")
    return out


# ---------------------------------------------------------------------------
# Compilación
# ---------------------------------------------------------------------------

def compilar(guion: dict[str, Any], lex: dict[str, str], dir_iconos: Path | None = None,
             inventario: dict[str, Any] | None = None, ritmo: float = RITMO) -> tuple[dict[str, Any], Reporte]:
    """inventario: si se pasa, cada fuente tiene que ser una afirmación verificada (estado ok)
    y se avisa de identificadores o números que no aparecen en las fuentes del bloque."""
    rep = Reporte()
    afirm = {a["id"]: a for a in inventario["afirmaciones"]} if inventario else {}
    for k, v in lex.items():
        if " " in v:
            rep.error("léxico", f"«{k}» → «{v}»: usá ~ en vez de espacios")

    bloques = guion.get("bloques", [])
    final = guion.get("final")
    if len(bloques) < 1:
        rep.error("guion", "no hay bloques")
    if not final:
        rep.error("guion", "falta el bloque final")
        return {}, rep
    if not 2 <= len(bloques) <= 5:
        rep.aviso("guion", f"{len(bloques)} bloques; la estructura pide 3 o 4")

    ids = Ids()
    iconos: set[str] = {"check-circle", "x-circle", "seal-check", "calendar-check"}
    stations: list[list[dict[str, Any]]] = []
    ids_bloque: list[set[str]] = []
    for b, bloque in enumerate(bloques):
        antes = set(ids.todos)
        st = []
        for e in bloque.get("elementos", []):
            el = preparar_elemento(e, f"bloque {b}", rep, ids, iconos)
            if el:
                st.append(el)
        if not st:
            rep.error(f"bloque {b}", "no tiene elementos")
        stations.append(st)
        ids_bloque.append(ids.todos - antes)
        if not bloque.get("fuentes"):
            (rep.error if inventario else rep.aviso)(f"bloque {b}", "sin fuentes: revisalo como [COMPROBAR]")
        if inventario:
            chequear_fuentes(b, bloque, afirm, rep)
        for c in bloque.get("comprobar", []):
            rep.error(f"bloque {b}", f"[COMPROBAR] sin resolver: {c}")

    lineas = final.get("lineas", [])
    ids_lineas = {f"fl{i + 1}" for i in range(len(lineas))}
    if not lineas:
        rep.error("final", "no tiene «lineas» para memorizar")
    if not final.get("mañana"):
        rep.error("final", "falta «mañana»")

    # --- frases ---
    phrases: list[list[Any]] = []
    gaps: dict[int, float] = {}
    events: list[list[Any]] = []
    keys: list[list[Any]] = []
    anclas_final: dict[str, str] = {}
    total_palabras = 0
    hay_boom = False
    secciones = [(b, bl.get("frases", [])) for b, bl in enumerate(bloques)] + [("final", final.get("frases", []))]
    for b, frases in secciones:
        if not frases:
            rep.error(f"bloque {b}", "no tiene frases")
        validos = (IDS_FINAL | ids_lineas) if b == "final" else ids_bloque[b]  # type: ignore[index]
        eventos_bloque = 0
        frases_bloque = []
        for texto in frases:
            i = len(phrases)
            donde = f"frase {i}"
            fr = parsear_frase(texto, donde, rep)
            frases_bloque.append(fr)
            cap = " ".join(fr.palabras)
            tts = " ".join(pronunciar(p, lex, donde, rep) for p in fr.palabras)
            phrases.append([cap, None if tts == cap else tts])
            total_palabras += len(fr.palabras)
            for idx, kind in fr.marcas:
                keys.append([i, idx, kind])
            for idx, et in fr.etiquetas:
                if et.id not in validos:
                    otro = " (es de otro bloque)" if et.id in ids.todos or et.id in IDS_FINAL | ids_lineas else ""
                    rep.error(donde, f"{et.accion} → id «{et.id}» no existe en este bloque{otro}")
                    continue
                chequear_accion(et, ids, donde, rep)
                hay_boom |= et.accion == "boom"
                a = ancla(i, fr, idx, et.off, donde, rep)
                eventos_bloque += 1
                if b == "final" and et.accion == "show" and (et.id in ids_lineas or et.id == "fnext"):
                    anclas_final[et.id] = a
                else:
                    events.append([a, et.accion, et.id] + ([et.extra] if et.extra else []))
        if b != "final":
            if eventos_bloque == 0:
                rep.error(f"bloque {b}", "ninguna frase anima sus elementos (el motor falla al calcular el viaje)")
            if phrases:
                # si algo aparece en las últimas palabras del bloque, una pausa más larga deja verlo
                # antes de que la cámara viaje a la escena siguiente
                ultimo = max((idx for idx, et in fr.etiquetas if et.accion == "show"), default=-1)
                tardio = ultimo >= 0 and len(fr.palabras) - 1 - ultimo <= 2
                pausa = bloques[b].get("pausa", PAUSA_TARDIA if tardio else PAUSA_BLOQUE)  # type: ignore[index]
                # una cuenta regresiva deja ese silencio para pensar la respuesta
                cuentas = [ids.cuentas[et.id] for _, et in fr.etiquetas if et.accion == "show" and et.id in ids.cuentas]
                if cuentas:
                    pausa = max(pausa, cuentas[0] + 0.4)
                for k, frase_previa in enumerate(frases_bloque[:-1]):
                    if any(et.accion == "show" and et.id in ids.cuentas for _, et in frase_previa.etiquetas):
                        rep.error(f"bloque {b}", "la cuenta regresiva va en la última frase del bloque (el silencio va ahí)")
                gaps[len(phrases) - 1] = pausa

    for lid in sorted(ids_lineas):
        if lid not in anclas_final:
            rep.error("final", f"la línea {lid} nunca aparece: poné {{show {lid}}} en la frase de cierre")
    if "fnext" not in anclas_final:
        rep.error("final", "falta {show fnext} antes de la palabra «Mañana»")
    if not hay_boom:
        rep.aviso("guion", "no hay clímax marcado (ninguna acción boom)")

    silabas = sum(len(re.findall(r"[aeiouyáéíóúü]+", w.lower())) or 1
                  for cap, tts in phrases for w in (tts or cap).replace("~", " ").split())
    dur = 0.15 + silabas / ritmo + sum(gaps.values()) + PAUSA_FRASE * (len(phrases) - len(gaps) - 1) + 1.4
    if not 30 <= dur <= 62:            # 30–45 s también sirven (validado con Redes y Conjuntos)
        corto = dur < 30
        rep.aviso("guion", f"duración estimada {dur:.0f}s ({total_palabras} palabras), fuera de 30–60s: "
                           + ("agregá una o dos frases" if corto else "sacá alguna frase"))

    if dir_iconos:
        for ic in sorted(iconos):
            if not (dir_iconos / f"{ic}-bold.svg").exists():
                rep.error("íconos", f"no existe el ícono «{ic}»")

    primera_final = len(phrases) - len(final.get("frases", []))
    spec = {
        "PHRASES": phrases,
        "GAPS": gaps,
        "KEY_GOOD": sorted({norm(phrases[i][0].split()[j]) for i, j, k in keys if k == "g"}),
        "KEY_BAD": sorted({norm(phrases[i][0].split()[j]) for i, j, k in keys if k == "b"}),
        "KEYS": keys,
        "STATIONS": stations,
        "EVENTS": events,
        "FINAL": {
            "start": f"{primera_final}:^",
            "title": final.get("titulo", "PARA EXPLICARLO"),
            "say": final.get("decilo", "Decilo así"),
            "next": final.get("mañana", ""),
            "next_label": final.get("etiqueta_manana", "Mañana: " + final.get("mañana", "")),
            "next_at": anclas_final.get("fnext", f"{primera_final}:^"),
            "lines": [[f"fl{i + 1}", h, anclas_final.get(f"fl{i + 1}", f"{primera_final}:^")]
                      for i, h in enumerate(lineas)],
        },
        "IDIOMA": guion.get("idioma", "es"),
        "FUENTES": [b.get("fuentes", []) for b in bloques],
        # bloques que usan métodos generales (no salen del material): el motor les pone una etiqueta
        "GENERAL": [any(afirm.get(f, {}).get("estado") == "general" for f in b.get("fuentes", [])) for b in bloques],
        "DURACION_ESTIMADA": round(dur, 1),
    }
    return spec, rep


def chequear_fuentes(b: int, bloque: dict[str, Any], afirm: dict[str, Any], rep: Reporte) -> None:
    from fuentes import identificadores
    respaldo = ""
    for f in bloque.get("fuentes", []):
        a = afirm.get(f)
        if a is None:
            rep.error(f"bloque {b}", f"la fuente «{f}» no está en el inventario")
        elif a.get("estado") not in ("ok", "general"):
            rep.error(f"bloque {b}", f"{f} está para comprobar: {'; '.join(a.get('motivos', [])) or 'sin verificar'}")
        else:
            respaldo += " " + a["texto"] + " " + a.get("cita", "")
    if not respaldo:
        return
    visible = " ".join(TOKEN.sub(lambda m: m.group(4) or " ", f) for f in bloque.get("frases", []))
    visible += " " + json.dumps(bloque.get("elementos", []), ensure_ascii=False)
    visible = re.sub(r'"(type|id|kind|icon|char|altkind|title|cols|rows|items|text|lines|label|alt|mono|labels|sets)"', " ", visible)
    visible = re.sub(r'"\d+":', " ", visible)          # códigos de región de un venn ("123": …)
    sueltos = sorted(i for i in identificadores(visible)
                     if i.lower() not in respaldo.lower() and not re.fullmatch(r"[a-z]+-r\d+(-c\d+)?|[a-z]+-h\d+", i))
    if sueltos:
        rep.aviso(f"bloque {b}", f"no aparecen en sus fuentes (¿inventados?): {', '.join(sueltos)}")


def chequear_accion(et: Etiqueta, ids: Ids, donde: str, rep: Reporte) -> None:
    requisitos = {
        "strike": (ids.con_tachado, "solo celdas, encabezados, chips, renglones de lista, cajas de flujo o big"),
        "swap": (ids.con_alt, "solo chips con «alt»"),
        "type": (ids.consolas, "solo consolas"),
        "point": (ids.dialogos, "solo diálogos"),
    }
    if et.accion == "send":
        cajas = ids.flujos.get(et.id)
        if cajas is None:
            rep.error(donde, f"send sobre «{et.id}»: solo flujos (flow)")
            return
        de, a = et.extra.get("de", cajas[0]), et.extra.get("a", cajas[-1])
        if de not in cajas or a not in cajas or de == a:
            rep.error(donde, f"send: de={de} a={a} tienen que ser dos cajas distintas de «{et.id}» ({', '.join(cajas)})")
        if len(str(et.extra.get("texto", ""))) > 12:
            rep.error(donde, "send: texto de más de 12 caracteres")
        return
    if et.accion in requisitos:
        validos, msg = requisitos[et.accion]
        if et.id not in validos:
            rep.error(donde, f"{et.accion} sobre «{et.id}»: {msg}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("guion", type=Path)
    ap.add_argument("--lexico", type=Path, default=Path(__file__).with_name("lexico.json"))
    ap.add_argument("--iconos", type=Path, help="carpeta de íconos de Phosphor (bold) para verificar nombres")
    ap.add_argument("-o", "--salida", type=Path, help="carpeta de salida (por defecto, la del guion)")
    ap.add_argument("--inventario", type=Path, help="inventario.json verificado: las fuentes tienen que estar ahí")
    ap.add_argument("--solo-validar", action="store_true")
    a = ap.parse_args(argv)

    guion = json.loads(a.guion.read_text(encoding="utf-8"))
    lex = {k.lower(): v for k, v in json.loads(a.lexico.read_text(encoding="utf-8")).items()} if a.lexico.exists() else {}
    lex.update({k.lower(): v for k, v in guion.get("lexico", {}).items()})
    inv = json.loads(a.inventario.read_text(encoding="utf-8")) if a.inventario else None
    spec, rep = compilar(guion, lex, a.iconos, inv)

    for m in rep.avisos:
        print("AVISO ", m)
    for m in rep.errores:
        print("ERROR ", m)
    if rep.errores:
        print(f"\n{len(rep.errores)} errores: no se escribió nada.")
        return 1
    print(f"ok: {len(spec['PHRASES'])} frases, {len(spec['EVENTS'])} eventos, ~{spec['DURACION_ESTIMADA']}s")
    if a.solo_validar:
        return 0
    out = a.salida or a.guion.parent
    out.mkdir(parents=True, exist_ok=True)
    (out / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "script.json").write_text(json.dumps([{"cap": c, "tts": t} for c, t in spec["PHRASES"]],
                                                ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "gaps.json").write_text(json.dumps({str(k): v for k, v in spec["GAPS"].items()}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
