"""Reglas compartidas entre etapas: qué temas son válidos, qué ve el guion, qué errores son de quién."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Lo que cambia según qué se estudia: un proyecto propio o una materia para un examen
MODOS = {
    "proyecto": {"aprobar": True, "generales": False},
    "materia": {"aprobar": False, "generales": True},
}

# Textos del video y del pedido según el idioma del video (las reglas de arriba no cambian)
IDIOMAS = {
    "es": {"voz": "davefx", "ritmo": 6.15, "lexico": "lexico.json", "ejemplo": "ejemplo_guion.json",
           "manana": "Mañana", "general": "método general · no está en tu material",
           "proyecto": {"pregunta": "Pregunta que te pueden hacer", "cierre": "Si te lo preguntan, decí:",
                        "titulo_final": "PARA EXPLICARLO", "decilo": "Decilo así"},
           "materia": {"pregunta": "Pregunta de examen", "cierre": "Para el examen, acordate:",
                       "titulo_final": "PARA EL EXAMEN", "decilo": "Acordate de esto"},
           "general_pedido": "método general, NO está en el material"},
    "en": {"voz": "hfc_male", "ritmo": 4.91, "lexico": "lexico_en.json", "ejemplo": "example_script_en.json",
           "manana": "Tomorrow", "general": "general method · not in your material",
           "proyecto": {"pregunta": "A question they may ask you", "cierre": "If they ask you, say:",
                        "titulo_final": "TO EXPLAIN IT", "decilo": "Say it like this"},
           "materia": {"pregunta": "Exam question", "cierre": "For the exam, remember:",
                       "titulo_final": "FOR THE EXAM", "decilo": "Remember this"},
           "general_pedido": "general method, NOT in the material"},
}


FORMATOS = {
    "pregunta": "pregunta y respuesta: plantea la pregunta, cuenta regresiva, revela",
    "mito": "mito contra realidad: la idea equivocada, tachada, y la correcta",
    "avsb": "A contra B: dos lados que se completan a la par",
    "pasos": "paso a paso: pasos que aparecen y se tildan en orden",
    "historia": "historia o caso: problema, intento, por qué falló, solución",
}


def elegir_formato(tema: dict[str, Any], afirm: list[dict[str, Any]], modo: str) -> str:
    """El formato que mejor le va al contenido del tema; la persona puede forzar otro con "formato"."""
    if tema.get("formato") in FORMATOS:
        return tema["formato"]
    tipos = {a.get("tipo") for a in afirm}
    if tipos & {"trampa", "error"}:
        return "mito"
    if tipos & {"procedimiento", "metodo"}:
        return "pasos"
    if modo == "proyecto" and tipos & {"decision", "motivo"}:
        return "historia"
    return "pregunta"


def _origen(t: Path) -> dict[str, Any]:
    p = Path(t) / "origen.json"
    return leer(p) if p.exists() else {}


def modo_de(t: Path) -> str:
    return _origen(t).get("modo", "proyecto")


def idioma_de(t: Path) -> str:
    return _origen(t).get("idioma", "es")


def textos(t: Path) -> dict[str, Any]:
    """Los textos del idioma del trabajo, con los del modo adentro."""
    i = IDIOMAS[idioma_de(t)]
    return {**i, **i[modo_de(t)]}


def leer(p: Path) -> Any:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def escribir(p: Path, datos: Any) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def resumen_inventario(inv: dict[str, Any]) -> None:
    comp = [a for a in inv["afirmaciones"] if a["estado"] == "comprobar"]
    print(f"{len(inv['afirmaciones'])} afirmaciones, {len(comp)} para comprobar")
    for a in comp:
        print(f"  {a['id']} [{a.get('fuente', 'general')}] {a['texto'][:70]}\n      → {'; '.join(a['motivos'])}")


def filtrar_temas(temas: dict[str, Any], inv: dict[str, Any]) -> dict[str, Any]:
    """Saca de cada tema las afirmaciones inexistentes o sin verificar y anota las que no cubre nadie."""
    ok = {a["id"] for a in inv["afirmaciones"] if a["estado"] == "ok"}
    general = {a["id"] for a in inv["afirmaciones"] if a["estado"] == "general"}
    usadas: set[str] = set()
    for t in temas["temas"]:
        malas = [a for a in t["afirmaciones"] if a not in ok | general]
        if malas:
            print(f"AVISO  {t['id']}: saco afirmaciones inexistentes o sin verificar {malas}")
            t["afirmaciones"] = [a for a in t["afirmaciones"] if a in ok | general]
        if t["afirmaciones"] and not set(t["afirmaciones"]) & ok:
            print(f"AVISO  {t['id']}: solo tiene métodos generales; sumale el ejercicio del material al que se aplican")
        usadas |= set(t["afirmaciones"])
    sin_usar = sorted(ok - usadas, key=lambda x: int(x[1:]) if x[1:].isdigit() else 0)
    if sin_usar:
        print(f"AVISO  afirmaciones verificadas que no cubre ningún tema: {', '.join(sin_usar)}")
    temas["sin_cubrir"] = sin_usar
    return temas


def _afirmaciones_del_tema(inv: dict[str, Any], tema: dict[str, Any]) -> list[dict[str, Any]]:
    return [a for a in inv["afirmaciones"] if a["id"] in tema["afirmaciones"]]


def _lista_afirmaciones(afirm: list[dict[str, Any]], idioma: str) -> str:
    general = IDIOMAS[idioma]["general_pedido"]
    return "\n".join(f"- {a['id']}" + (f" ({general})" if a["estado"] == "general" else "") + f": {a['texto']}"
                     for a in afirm)


def pedido_guion(inv: dict[str, Any], temas: list[dict[str, Any]], tema_id: str, modo: str = "proyecto",
                 idioma: str = "es") -> str:
    """El pedido de un guion: el tema y SOLO sus afirmaciones verificadas."""
    idx = next(i for i, t in enumerate(temas) if t["id"] == tema_id)
    tema = temas[idx]
    afirm = _afirmaciones_del_tema(inv, tema)
    manana = temas[idx + 1]["titulo"] if idx + 1 < len(temas) else "repaso general"
    i = IDIOMAS[idioma]; m = i[modo]
    formato = elegir_formato(tema, afirm, modo)
    return (f"IDIOMA DEL VIDEO: {idioma} (ejemplo: prompts/{i['ejemplo']})\n"
            f"FORMATO: {formato} ({FORMATOS[formato]})\n"
            f"Tema: {tema['titulo']}\n{m['pregunta']}: {tema['pregunta']}\n"
            f"Tema de mañana: {manana}\nCIERRE: {m['cierre']}\n\nAfirmaciones disponibles:\n"
            + _lista_afirmaciones(afirm, idioma))


# ---------------------------------------------------------------------------
# preguntas de práctica después de cada video
# ---------------------------------------------------------------------------

PREGUNTAS = (2, 3)          # cuántas preguntas por tema
OPCIONES = (3, 4)           # cuántas opciones por pregunta
MARCA_GENERAL = ("método general", "general method")   # lo que dice la explicación si usa un método general


def pedido_preguntas(inv: dict[str, Any], temas: list[dict[str, Any]], tema_id: str, destino: Path,
                     modo: str = "proyecto", idioma: str = "es") -> str:
    """El pedido de las preguntas de un tema: el tema y SOLO sus afirmaciones verificadas, como el del guion."""
    tema = next(t for t in temas if t["id"] == tema_id)
    return (f"IDIOMA DEL VIDEO: {idioma}\n"
            f"Tema: {tema['titulo']}\n{IDIOMAS[idioma][modo]['pregunta']}: {tema['pregunta']}\n"
            f"Escribí {destino} siguiendo prompts/preguntas.md: {PREGUNTAS[0]} o {PREGUNTAS[1]} preguntas de "
            f"{OPCIONES[0]} o {OPCIONES[1]} opciones, solo con estas afirmaciones.\n\nAfirmaciones disponibles:\n"
            + _lista_afirmaciones(_afirmaciones_del_tema(inv, tema), idioma))


def _texto(x: Any) -> bool:
    return isinstance(x, str) and bool(x.strip())


def validar_preguntas(datos: Any, inv: dict[str, Any], tema: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Comprueba T/tNN/preguntas.json. Devuelve (errores, avisos), como compile.compilar.

    Errores: la forma (2–3 preguntas, 3–4 opciones distintas, «correcta» dentro de rango) y las fuentes
    (tienen que ser afirmaciones de ESTE tema; las que quedaron para comprobar van a la persona).
    Avisos: identificadores o números de 2+ cifras de la opción correcta o de la explicación que no
    están en las afirmaciones citadas (texto y cita), con el mismo criterio que el guion."""
    from fuentes import identificadores
    if not isinstance(datos, dict) or not isinstance(datos.get("preguntas"), list):
        return ['tiene que ser {"preguntas": [{"id", "texto", "opciones", "correcta", "explicacion", "fuentes"}, …]}'], []
    preguntas = datos["preguntas"]
    errores: list[str] = []
    avisos: list[str] = []
    if not PREGUNTAS[0] <= len(preguntas) <= PREGUNTAS[1]:
        errores.append(f"hay {len(preguntas)} preguntas: tienen que ser {PREGUNTAS[0]} o {PREGUNTAS[1]}")
    afirm = {a["id"]: a for a in inv["afirmaciones"]}
    del_tema = set(tema["afirmaciones"])
    ids: list[Any] = []
    for n, p in enumerate(preguntas, 1):
        if not isinstance(p, dict):
            errores.append(f"pregunta {n}: tiene que ser un objeto")
            continue
        donde = f"pregunta {p.get('id') or n}"
        ids.append(p.get("id"))
        if not _texto(p.get("id")):
            errores.append(f"{donde}: falta «id» (q1, q2, q3)")
        for clave in ("texto", "explicacion"):
            if not _texto(p.get(clave)):
                errores.append(f"{donde}: falta «{clave}»")
        opciones = p.get("opciones")
        if not isinstance(opciones, list) or not all(_texto(o) for o in opciones):
            errores.append(f"{donde}: «opciones» tiene que ser una lista de textos")
            opciones = None
        else:
            if not OPCIONES[0] <= len(opciones) <= OPCIONES[1]:
                errores.append(f"{donde}: tiene {len(opciones)} opciones; tienen que ser {OPCIONES[0]} o {OPCIONES[1]}")
            vistas = [" ".join(o.split()).casefold() for o in opciones]
            repetidas = sorted({o for o in vistas if vistas.count(o) > 1})
            if repetidas:
                errores.append(f"{donde}: opciones repetidas: {', '.join(repetidas)}")
        correcta = p.get("correcta")
        bien_correcta = (isinstance(correcta, int) and not isinstance(correcta, bool) and opciones is not None
                         and 0 <= correcta < len(opciones))
        if not bien_correcta:
            rango = f" (de 0 a {len(opciones) - 1})" if opciones else ""
            errores.append(f"{donde}: «correcta» tiene que ser la posición de la opción correcta{rango}, no {correcta!r}")
        fuentes = p.get("fuentes")
        if not isinstance(fuentes, list) or not fuentes:
            errores.append(f"{donde}: sin fuentes (los ids de las afirmaciones que la respaldan)")
            continue
        respaldo, general = "", False
        for f in fuentes:
            a = afirm.get(f)
            if a is None:
                errores.append(f"{donde}: la fuente «{f}» no está en el inventario")
            elif f not in del_tema:
                errores.append(f"{donde}: la fuente «{f}» es de otro tema; usá solo las afirmaciones del pedido")
            elif a.get("estado") not in ("ok", "general"):
                errores.append(f"{donde}: {f} está para comprobar: {'; '.join(a.get('motivos', [])) or 'sin verificar'}")
            else:
                respaldo += " " + a["texto"] + " " + a.get("cita", "")
                general = general or a.get("estado") == "general"
        if general and _texto(p.get("explicacion")) and not any(m in p["explicacion"].casefold() for m in MARCA_GENERAL):
            errores.append(f"{donde}: usa un método general y la explicación no lo dice "
                           "(«Método general, no está en tu material: …» / «General method, not from your material: …»)")
        if respaldo and bien_correcta:
            visible = f"{opciones[correcta]} {p.get('explicacion') or ''}"
            sueltos = sorted(i for i in identificadores(visible) if i.lower() not in respaldo.lower())
            if sueltos:
                avisos.append(f"{donde}: no aparecen en sus fuentes (¿inventados?): {', '.join(sueltos)}")
    validos = [i for i in ids if _texto(i)]
    if len(validos) != len(set(validos)):
        errores.append("hay ids de pregunta repetidos")
    return errores, avisos


# El código comprueba que la cita esté en la fuente, pero no que la afirmación se siga de ella: una
# cita real puede respaldar una afirmación falsa ("WPA2 usa AES" para "WPA2 usa 3 rondas de AES"). Ese
# juicio lo hace Claude, leyendo SOLO este pedido; respaldo lo pide y lo aplica.
INSTRUCCIONES_RESPALDO = (
    "For each statement below, the quote was already checked to appear in the source and to contain "
    "the acronyms, snake_case names and 2+ digit numbers of the statement. What is NOT checked by code "
    "is whether the quote actually SUPPORTS the statement. That is your job here.\n"
    "\n"
    "Read only this file. Do not look at the material again: decide using just each statement and its "
    "quote. Write ONLY JSON to respaldo.json, one entry per id below and no others, in this format:\n"
    '  {"<id>": {"respalda": true | false, "motivo": "<short reason, in the statement\'s language>"}}\n'
    "\n"
    "«respalda» is false when the statement says more than the quote (adds a number, a name, a reason), "
    "contradicts it, or does not follow from it; true only when the quote backs exactly what the "
    "statement claims. «motivo» is required when «respalda» is false. Statements with «respalda» false "
    "move to «comprobar»; in course mode (materia) they are removed from the videos."
)


def respaldo_vigente(a: dict[str, Any]) -> dict[str, Any] | None:
    """El juicio guardado en la afirmación, si sigue valiendo: se juzgó este mismo texto con esta misma
    cita. Si cambió alguno de los dos, el juicio ya no dice nada y hay que pedirlo de nuevo."""
    r = a.get("respaldo")
    if isinstance(r, dict) and r.get("texto") == a.get("texto") and r.get("cita") == a.get("cita", ""):
        return r
    return None


def pendientes_respaldo(inv: dict[str, Any]) -> list[dict[str, Any]]:
    """Afirmaciones en «ok» sin un juicio de respaldo vigente."""
    return [a for a in inv["afirmaciones"] if a.get("estado") == "ok" and respaldo_vigente(a) is None]


def _no_respalda(a: dict[str, Any], motivo: str) -> bool:
    """Pasa la afirmación a «comprobar» por falta de respaldo, salvo «aprobado» true (lo revisó una persona)."""
    if a.get("aprobado") is True:
        return False
    a["estado"] = "comprobar"
    a.setdefault("motivos", []).append("la cita no respalda la afirmación" + (f": {motivo}" if motivo else ""))
    return True


def reaplicar_respaldo(inv: dict[str, Any]) -> list[str]:
    """verificar recalcula estado y motivos desde cero: sin esto, volver a verificar devolvería a «ok» las
    afirmaciones que Claude juzgó sin respaldo. Aplica de nuevo los juicios vigentes y borra los viejos
    (texto o cita cambiaron), que quedan pendientes. Devuelve los ids que vuelven a «comprobar»."""
    movidos = []
    for a in inv["afirmaciones"]:
        if "respaldo" not in a:
            continue
        r = respaldo_vigente(a)
        if r is None:
            del a["respaldo"]
        elif a.get("estado") == "ok" and r["respalda"] is False and _no_respalda(a, r.get("motivo", "")):
            movidos.append(a["id"])
    return movidos


def pedido_respaldo(inv: dict[str, Any]) -> str:
    """Texto para que Claude juzgue si la cita respalda la afirmación. Solo las afirmaciones en «ok» que
    todavía no tienen juicio: las demás están en «comprobar» (no entran a ningún video) o ya se juzgaron."""
    partes = [INSTRUCCIONES_RESPALDO, ""]
    for a in pendientes_respaldo(inv):
        partes.append(a["id"])
        partes.append(f"  afirmación: {a['texto']}")
        partes.append(f"  cita: {a.get('cita', '')}")
        partes.append("")
    return "\n".join(partes)


def aplicar_respaldo(inv: dict[str, Any], respaldo: Any) -> tuple[list[str], list[str]]:
    """Aplica el juicio de Claude y lo guarda en cada afirmación (con el texto y la cita juzgados), así
    sobrevive a otro verificar. «respalda» false pasa la afirmación a «comprobar» con el motivo, salvo
    «aprobado» true. Devuelve (errores, ids movidos a comprobar); ante cualquier error no aplica nada:
    faltan o sobran respuestas respecto de las pendientes, o una respuesta está mal formada."""
    if not isinstance(respaldo, dict):
        return ["respaldo.json tiene que ser un objeto {\"<id>\": {\"respalda\": ..., \"motivo\": ...}}"], []
    pend = {a["id"] for a in pendientes_respaldo(inv)}
    faltan = sorted(pend - set(respaldo))
    sobran = sorted(set(respaldo) - pend)
    errores = []
    if faltan:
        errores.append(f"faltan respuestas para afirmaciones pendientes: {', '.join(faltan)}")
    if sobran:
        errores.append(f"sobran respuestas (no son afirmaciones en «ok» pendientes de juicio): {', '.join(sobran)}")
    for i, r in sorted(respaldo.items()):
        if not isinstance(r, dict) or not isinstance(r.get("respalda"), bool):
            errores.append(f"{i}: «respalda» tiene que ser true o false (sin comillas)")
        elif r["respalda"] is False and not str(r.get("motivo") or "").strip():
            errores.append(f"{i}: falta «motivo» (es obligatorio cuando «respalda» es false)")
    if errores:
        return errores, []
    movidos = []
    for a in inv["afirmaciones"]:
        r = respaldo.get(a["id"])
        if r is None:
            continue
        motivo = str(r.get("motivo") or "").strip()
        a["respaldo"] = {"respalda": r["respalda"], "motivo": motivo, "texto": a["texto"], "cita": a.get("cita", "")}
        if r["respalda"] is False and _no_respalda(a, motivo):
            movidos.append(a["id"])
    return [], movidos


def separar_errores(errores: list[str]) -> tuple[list[str], list[str]]:
    """(para el modelo, para la persona): los [COMPROBAR] y las fuentes sin verificar no los arregla el modelo."""
    persona = [e for e in errores if "COMPROBAR" in e or "está para comprobar" in e]
    return [e for e in errores if e not in persona], persona


def escribir_salidas(carpeta: Path, spec: dict[str, Any]) -> None:
    escribir(carpeta / "spec.json", spec)
    escribir(carpeta / "script.json", [{"cap": c, "tts": t} for c, t in spec["PHRASES"]])
    (carpeta / "gaps.json").write_text(json.dumps({str(k): v for k, v in spec["GAPS"].items()}), encoding="utf-8")
