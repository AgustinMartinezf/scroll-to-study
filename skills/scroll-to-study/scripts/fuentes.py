"""Material de estudio -> corpus numerado, y verificación mecánica de afirmaciones.

Cada afirmación del inventario trae su fuente ("sql/schema.sql:12-18" o "informe.pdf:p4")
y una cita textual. Acá se comprueba, sin LLM, que:
  1. la fuente existe y el rango no es enorme,
  2. la cita aparece en ese lugar (si aparece en otro, se dice dónde),
  3. los identificadores y números de la afirmación están en lo citado.
Lo que no pasa queda en estado "comprobar" con sus motivos; nada se borra.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EXT_TEXTO = {".sql", ".java", ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".md", ".txt",
             ".json", ".yml", ".yaml", ".xml", ".c", ".h", ".cpp", ".cs", ".go", ".rb", ".php",
             ".kt", ".swift", ".sh", ".properties", ".gradle"}
IGNORAR = {".git", "node_modules", "dist", "build", "target", "__pycache__", ".venv", "venv",
           ".idea", ".vscode", ".gradle", "out"}
MAX_BYTES = 200_000
MAX_LINEAS_CITA = 40
# sinónimos habituales: la afirmación dice "FK", el SQL dice "FOREIGN KEY"
EQUIV = {"fk": "foreign key", "pk": "primary key"}


@dataclass
class Corpus:
    archivos: dict[str, list[str]] = field(default_factory=dict)   # ruta -> líneas
    paginas: dict[str, list[str]] = field(default_factory=dict)    # pdf -> texto por página
    omitidos: list[str] = field(default_factory=list)

    def texto_para_llm(self) -> str:
        partes = []
        for ruta, lineas in self.archivos.items():
            partes.append(f"=== archivo: {ruta} ===")
            partes += [f"{i}| {l}" for i, l in enumerate(lineas, 1)]
        for pdf, pags in self.paginas.items():
            for i, t in enumerate(pags, 1):
                partes.append(f"=== {pdf} p{i} ===")
                partes.append(t)
        return "\n".join(partes)

    def fragmento(self, ref: str) -> tuple[str | None, str | None]:
        """Devuelve (texto, error) para una referencia."""
        m = re.fullmatch(r"(.+):p(\d+)(?:-(\d+))?", ref)
        if m and m.group(1) in self.paginas:
            pags = self.paginas[m.group(1)]
            a, b = int(m.group(2)), int(m.group(3) or m.group(2))
            if not 1 <= a <= b <= len(pags):
                return None, f"{m.group(1)} tiene {len(pags)} páginas"
            if b - a > 1:
                return None, "rango de páginas demasiado amplio (máximo 2)"
            return "\n".join(pags[a - 1:b]), None
        m = re.fullmatch(r"(.+):(\d+)(?:-(\d+))?", ref)
        if not m:
            return None, f"referencia mal formada «{ref}» (usá ruta:12-18 o archivo.pdf:p4)"
        ruta, a, b = m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))
        if ruta not in self.archivos:
            return None, f"no existe el archivo «{ruta}»"
        lineas = self.archivos[ruta]
        if not 1 <= a <= b <= len(lineas):
            return None, f"«{ruta}» tiene {len(lineas)} líneas"
        if b - a + 1 > MAX_LINEAS_CITA:
            return None, f"rango demasiado amplio ({b - a + 1} líneas, máximo {MAX_LINEAS_CITA})"
        return "\n".join(lineas[a - 1:b]), None

    def buscar(self, cita_norm: str) -> list[str]:
        """Dónde aparece una cita normalizada en todo el corpus (para sugerir la fuente correcta)."""
        lugares = []
        for ruta, lineas in self.archivos.items():
            dentro = lambda a, b: cita_norm in _norm(" ".join(lineas[a:b]))
            for i in range(len(lineas)):
                # la cita empieza en i: está en la ventana que arranca en i y no en la siguiente
                if dentro(i, i + 8) and not dentro(i + 1, i + 9):
                    fin = next(j for j in range(i + 1, i + 9) if dentro(i, j))
                    lugares.append(f"{ruta}:{i + 1}" + (f"-{fin}" if fin > i + 1 else ""))
        for pdf, pags in self.paginas.items():
            lugares += [f"{pdf}:p{i}" for i, t in enumerate(pags, 1) if cita_norm in _norm(t)]
        return lugares[:3]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _paginas_pdf(p: Path) -> list[str]:
    if shutil.which("pdftotext"):
        out = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, check=True).stdout
        pags = out.decode("utf-8", "replace").split("\f")
        return pags[:-1] if pags and not pags[-1].strip() else pags
    from pypdf import PdfReader
    return [pg.extract_text() or "" for pg in PdfReader(str(p)).pages]


def cargar(repo: Path | None, docs: list[Path]) -> Corpus:
    c = Corpus()
    if repo:
        for p in sorted(repo.rglob("*")):
            rel = p.relative_to(repo)
            if any(parte in IGNORAR for parte in rel.parts) or not p.is_file():
                continue
            if p.suffix.lower() not in EXT_TEXTO:
                continue
            datos = p.read_bytes()
            if len(datos) > MAX_BYTES or b"\x00" in datos:
                c.omitidos.append(str(rel))
                continue
            c.archivos[rel.as_posix()] = datos.decode("utf-8", "replace").splitlines()
    for d in docs:
        if d.suffix.lower() == ".pdf":
            c.paginas[d.name] = _paginas_pdf(d)
        else:
            c.archivos[d.name] = d.read_text(encoding="utf-8", errors="replace").splitlines()
    return c


IDENT = re.compile(r"\b[a-zA-Z]+_[a-zA-Z0-9_]+\b|\b[A-Z]{2,}\b|\b\d{2,}\b")


def identificadores(texto: str) -> set[str]:
    """Lo que no se puede inventar: snake_case, SIGLAS y números de 2+ cifras."""
    return set(IDENT.findall(texto))


def _aparece(ident: str, texto_norm: str) -> bool:
    i = ident.lower()
    return i in texto_norm or (i in EQUIV and EQUIV[i] in texto_norm)


def verificar(inventario: dict[str, Any], corpus: Corpus) -> dict[str, Any]:
    """Agrega estado ('ok' | 'comprobar' | 'general') y motivos a cada afirmación. No borra nada.

    'general': métodos y trampas que no están en el material (origen "general"). Solo valen si
    anclan a un tipo de ejercicio que sí está en el material (campo "para"), y el video los marca.
    """
    generales = [a for a in inventario["afirmaciones"] if a.get("origen") == "general"]
    for a in inventario["afirmaciones"]:
        if a.get("origen") == "general":
            continue
        motivos: list[str] = []
        frag, err = corpus.fragmento(a["fuente"])
        cita = _norm(a.get("cita", ""))
        if err:
            motivos.append(err)
        if not cita:
            motivos.append("sin cita textual")
        elif frag is not None and cita not in _norm(frag):
            otros = corpus.buscar(cita)
            motivos.append(f"la cita no está en {a['fuente']}" +
                           (f"; aparece en {', '.join(otros)}" if otros else "; no aparece en el material"))
        if frag is not None:
            fn = _norm(frag)
            faltan = sorted(i for i in identificadores(a["texto"]) if not _aparece(i, fn))
            if faltan:
                motivos.append(f"no aparecen en la fuente: {', '.join(faltan)}")
        # "aprobado": true lo pone una persona después de revisar; los motivos quedan a la vista
        a["estado"] = "ok" if not motivos or a.get("aprobado") is True else "comprobar"
        a["motivos"] = motivos
    estado = {a["id"]: a for a in inventario["afirmaciones"]}
    for a in generales:
        motivos = []
        if a.get("tipo") not in ("metodo", "trampa"):
            motivos.append("lo que no sale del material solo puede ser un método o una trampa (tipo metodo|trampa)")
        para = a.get("para") or []
        if not para:
            motivos.append("falta «para»: los ids de los ejercicios del material a los que se aplica")
        for p in para:
            e = estado.get(p)
            if e is None or e.get("origen") == "general" or e.get("estado") != "ok" or e.get("tipo") != "ejercicio":
                motivos.append(f"«para» tiene que apuntar a ejercicios verificados del material; {p} no lo es")
        a["estado"] = "general" if not motivos else "comprobar"
        a["motivos"] = motivos
    return inventario
