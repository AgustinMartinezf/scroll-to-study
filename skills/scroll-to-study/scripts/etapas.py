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


def pedido_guion(inv: dict[str, Any], temas: list[dict[str, Any]], tema_id: str, modo: str = "proyecto",
                 idioma: str = "es") -> str:
    """El pedido de un guion: el tema y SOLO sus afirmaciones verificadas."""
    idx = next(i for i, t in enumerate(temas) if t["id"] == tema_id)
    tema = temas[idx]
    afirm = [a for a in inv["afirmaciones"] if a["id"] in tema["afirmaciones"]]
    manana = temas[idx + 1]["titulo"] if idx + 1 < len(temas) else "repaso general"
    i = IDIOMAS[idioma]; m = i[modo]
    formato = elegir_formato(tema, afirm, modo)
    return (f"IDIOMA DEL VIDEO: {idioma} (ejemplo: prompts/{i['ejemplo']})\n"
            f"FORMATO: {formato} ({FORMATOS[formato]})\n"
            f"Tema: {tema['titulo']}\n{m['pregunta']}: {tema['pregunta']}\n"
            f"Tema de mañana: {manana}\nCIERRE: {m['cierre']}\n\nAfirmaciones disponibles:\n"
            + "\n".join(f"- {a['id']}" + (f" ({i['general_pedido']})" if a["estado"] == "general" else "")
                        + f": {a['texto']}" for a in afirm))


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
