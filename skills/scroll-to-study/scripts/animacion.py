"""Cómo se anima cada video: la entrada de cada tipo de elemento, la transición entre escenas y la
disposición de las estaciones. Claude no elige animaciones: lo decide el motor.

Las entradas y la transición salen de una semilla estable (FNV-1a de 32 bits del id del tema y el título
de la lista) y de un generador propio (mulberry32), nunca de Math.random ni de la hora: el mismo tema da
el mismo video, byte a byte. La disposición sale del formato del tema.
"""
from __future__ import annotations

import json
import os
from typing import Any

# entradas posibles por tipo de elemento ("escala" es la de siempre). letras: solo textos de una línea;
# cascada: elementos con partes (filas, renglones, chips, barras, cajas, nodos), que entran de a una
ENTRADAS: dict[str, list[str]] = {
    "chip":      ["escala", "costado", "abajo", "barrido", "letras"],
    "big":       ["escala", "abajo", "barrido", "letras"],
    "toast":     ["escala", "costado", "barrido", "letras"],
    "table":     ["escala", "abajo", "barrido", "cascada"],
    "list":      ["escala", "costado", "barrido", "cascada"],
    "chart":     ["escala", "abajo", "barrido", "cascada"],
    "row":       ["escala", "costado", "cascada"],
    "flow":      ["escala", "abajo", "barrido", "cascada"],
    "arbol":     ["escala", "abajo", "barrido", "cascada"],
    "secuencia": ["escala", "costado", "abajo", "barrido"],
    "venn":      ["escala", "abajo", "barrido"],
    "console":   ["escala", "costado", "abajo", "barrido"],
    "chat":      ["escala", "costado", "abajo"],
    "formula":   ["escala", "costado", "abajo", "barrido"],
    "counter":   ["escala", "costado", "abajo"],
    "dialog":    ["escala", "abajo", "barrido"],
    "arrow":     ["escala", "costado", "barrido"],
    "countdown": ["escala", "costado", "abajo"],
}
TRANSICIONES = ["viaje", "corte", "paneo", "zoom"]
# cómo se acomodan las estaciones en el mundo según el formato
DISPOSICIONES = {"pregunta": "columna", "mito": "lados", "avsb": "partida", "pasos": "progreso",
                 "historia": "grilla"}
DISPOSICION_SIN_FORMATO = "zigzag"


def fnv1a(texto: str) -> int:
    """Hash FNV-1a de 32 bits de los bytes UTF-8: estable entre corridas y máquinas (hash() no lo es)."""
    h = 0x811C9DC5
    for b in texto.encode("utf-8"):
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


class Mulberry32:
    """Generador de números pseudoaleatorios de 32 bits (mulberry32): chico, rápido y reproducible."""

    def __init__(self, semilla: int) -> None:
        self.a = semilla & 0xFFFFFFFF

    def siguiente(self) -> float:
        """Un número en [0, 1)."""
        self.a = (self.a + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.a
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    def entero(self, n: int) -> int:
        return int(self.siguiente() * n)


def texto_semilla(tema_id: str, titulo_lista: str = "") -> str:
    return f"{tema_id}\n{titulo_lista}" if titulo_lista else tema_id


def elegir(semilla: str, formato: str = "", forzar: dict[str, Any] | None = None) -> dict[str, Any]:
    """{"semilla", "formato", "entradas": {tipo: entrada}, "lado", "transicion", "disposicion"}.

    Las entradas se sortean para todos los tipos, en un orden fijo: la de un tipo no depende de qué otros
    tipos tenga el video. forzar (o la variable S2S_ANIMACION, JSON) pisa lo que haga falta: es para los
    tests y la revisión visual."""
    r = Mulberry32(fnv1a(semilla))
    out: dict[str, Any] = {
        "semilla": semilla,
        "formato": formato,
        "entradas": {tipo: ops[r.entero(len(ops))] for tipo, ops in ENTRADAS.items()},
        "lado": "izquierda" if r.entero(2) == 0 else "derecha",
        "transicion": TRANSICIONES[r.entero(len(TRANSICIONES))],
        "disposicion": DISPOSICIONES.get(formato, DISPOSICION_SIN_FORMATO),
    }
    extra = dict(forzar or {})
    if not forzar and os.environ.get("S2S_ANIMACION"):
        extra = json.loads(os.environ["S2S_ANIMACION"])
    if "entrada" in extra:                       # la misma entrada para todos los tipos que la tengan
        e = extra.pop("entrada")
        out["entradas"] = {t: (e if e in ops else "escala") for t, ops in ENTRADAS.items()}
    if "entradas" in extra:
        out["entradas"] = {**out["entradas"], **extra.pop("entradas")}
    out.update(extra)
    return out


def resumen(anim: dict[str, Any], tipos: list[str]) -> dict[str, Any]:
    """Lo que se mide de un video: formato, entradas de los tipos que usa, transición y disposición."""
    return {"formato": anim["formato"], "entradas": {t: anim["entradas"][t] for t in sorted(set(tipos))
                                                      if t in anim["entradas"]},
            "transicion": anim["transicion"], "disposicion": anim["disposicion"]}


def combinacion(res: dict[str, Any]) -> str:
    """Una clave que identifica la combinación (para contar cuántas distintas hay en la lista)."""
    return json.dumps(res, sort_keys=True, ensure_ascii=False)
