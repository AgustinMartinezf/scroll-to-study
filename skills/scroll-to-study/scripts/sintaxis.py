"""Resaltado de sintaxis propio para el elemento «codigo»: palabras clave, strings, comentarios y números,
por lenguaje, sin librerías externas. Trabaja de a una línea (un bloque de un video tiene hasta 12 líneas
de hasta 34 caracteres), así que un comentario o un string de varias líneas no se sigue de una a otra.
"""
from __future__ import annotations

import html
import re

LENGUAJES = ("java", "python", "c", "sql", "js", "bash", "texto")

_CLAVES = {
    "java": """abstract assert boolean break byte case catch char class const continue default do double else enum
        extends final finally float for if implements import instanceof int interface long native new null package
        private protected public return short static super switch synchronized this throw throws try void volatile
        while true false var record""",
    "python": """and as assert async await break class continue def del elif else except False finally for from
        global if import in is lambda None nonlocal not or pass raise return True try while with yield match case""",
    "c": """auto break case char const continue default do double else enum extern float for goto if int long
        register return short signed sizeof static struct switch typedef union unsigned void volatile while
        include define NULL""",
    "sql": """select from where insert into values update set delete create table alter drop primary key foreign
        references on join inner left right outer group by order having as and or not null is in like between
        distinct count sum avg min max index unique default check constraint view begin commit rollback
        int integer varchar char text date decimal cascade limit union all exists case when then else end""",
    "js": """async await break case catch class const continue default delete do else export extends false
        finally for function if import in instanceof let new null of return super switch this throw true try
        typeof undefined var void while yield""",
    "bash": """if then else elif fi for while do done case esac in function return exit echo export local
        cd ls git sudo""",
    "texto": "",
}
CLAVES = {l: set(v.split()) for l, v in _CLAVES.items()}
COMENTARIO = {"java": r"//.*|/\*.*?(?:\*/|$)", "c": r"//.*|/\*.*?(?:\*/|$)", "js": r"//.*|/\*.*?(?:\*/|$)",
              "python": r"#.*", "bash": r"#.*", "sql": r"--.*", "texto": None}
STRING = {"python": r"'(?:\\.|[^'\\])*'?|\"(?:\\.|[^\"\\])*\"?", "js": r"'(?:\\.|[^'\\])*'?|\"(?:\\.|[^\"\\])*\"?|`[^`]*`?",
          "sql": r"'(?:''|[^'])*'?"}
STRING_C = r"'(?:\\.|[^'\\])*'?|\"(?:\\.|[^\"\\])*\"?"
NUMERO = r"\b\d+(?:\.\d+)?\b"
PALABRA = r"[A-Za-z_#][A-Za-z_0-9]*"


def tokens(linea: str, lenguaje: str) -> list[tuple[str, str]]:
    """[(clase, texto)] que cubren la línea entera. clase: "kw", "str", "com", "num" o "" (texto común)."""
    if lenguaje == "texto" or lenguaje not in LENGUAJES:
        return [("", linea)] if linea else []
    partes = []
    if COMENTARIO.get(lenguaje):
        partes.append(("com", COMENTARIO[lenguaje]))
    partes.append(("str", STRING.get(lenguaje, STRING_C)))
    partes += [("num", NUMERO), ("pal", PALABRA)]
    patron = re.compile("|".join(f"(?P<{n}>{p})" for n, p in partes))
    claves = CLAVES[lenguaje]
    sql = lenguaje == "sql"
    out: list[tuple[str, str]] = []
    pos = 0
    for m in patron.finditer(linea):
        if m.start() > pos:
            out.append(("", linea[pos:m.start()]))
        clase, txt = m.lastgroup or "", m.group()
        if clase == "pal":
            palabra = txt.lstrip("#")
            clase = "kw" if (palabra.lower() if sql else palabra) in claves else ""
        out.append((clase, txt))
        pos = m.end()
    if pos < len(linea):
        out.append(("", linea[pos:]))
    # juntar los pedazos de texto común seguidos
    juntos: list[tuple[str, str]] = []
    for c, t in out:
        if juntos and juntos[-1][0] == c == "":
            juntos[-1] = ("", juntos[-1][1] + t)
        else:
            juntos.append((c, t))
    return juntos


def a_html(linea: str, lenguaje: str, colores: dict[str, str]) -> str:
    """La línea en HTML, con un <span> de color por cada pedazo resaltado (colores: kw, str, com, num)."""
    return "".join(f'<span class="s{c}" style="color:{colores[c]}">{html.escape(t)}</span>' if c else html.escape(t)
                   for c, t in tokens(linea, lenguaje))
