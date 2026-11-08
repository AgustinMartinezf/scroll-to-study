"""Reglas compartidas entre etapas: qué temas son válidos, qué ve el guion, qué errores son de quién."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def leer(p: Path) -> Any:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def escribir(p: Path, datos: Any) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def resumen_inventario(inv: dict[str, Any]) -> None:
    comp = [a for a in inv["afirmaciones"] if a["estado"] != "ok"]
    print(f"{len(inv['afirmaciones'])} afirmaciones, {len(comp)} para comprobar")
    for a in comp:
        print(f"  {a['id']} [{a['fuente']}] {a['texto'][:70]}\n      → {'; '.join(a['motivos'])}")


def filtrar_temas(temas: dict[str, Any], inv: dict[str, Any]) -> dict[str, Any]:
    """Saca de cada tema las afirmaciones inexistentes o sin verificar y anota las que no cubre nadie."""
    ok = {a["id"] for a in inv["afirmaciones"] if a["estado"] == "ok"}
    usadas: set[str] = set()
    for t in temas["temas"]:
        malas = [a for a in t["afirmaciones"] if a not in ok]
        if malas:
            print(f"AVISO  {t['id']}: saco afirmaciones inexistentes o sin verificar {malas}")
            t["afirmaciones"] = [a for a in t["afirmaciones"] if a in ok]
        usadas |= set(t["afirmaciones"])
    sin_usar = sorted(ok - usadas, key=lambda x: int(x[1:]) if x[1:].isdigit() else 0)
    if sin_usar:
        print(f"AVISO  afirmaciones verificadas que no cubre ningún tema: {', '.join(sin_usar)}")
    temas["sin_cubrir"] = sin_usar
    return temas


def pedido_guion(inv: dict[str, Any], temas: list[dict[str, Any]], tema_id: str) -> str:
    """El pedido de un guion: el tema y SOLO sus afirmaciones verificadas."""
    idx = next(i for i, t in enumerate(temas) if t["id"] == tema_id)
    tema = temas[idx]
    afirm = [a for a in inv["afirmaciones"] if a["id"] in tema["afirmaciones"]]
    manana = temas[idx + 1]["titulo"] if idx + 1 < len(temas) else "repaso general"
    return (f"Tema: {tema['titulo']}\nPregunta del tribunal: {tema['pregunta']}\n"
            f"Tema de mañana: {manana}\n\nAfirmaciones disponibles:\n"
            + "\n".join(f"- {a['id']}: {a['texto']}" for a in afirm))


def separar_errores(errores: list[str]) -> tuple[list[str], list[str]]:
    """(para el modelo, para la persona): los [COMPROBAR] y las fuentes sin verificar no los arregla el modelo."""
    persona = [e for e in errores if "COMPROBAR" in e or "está para comprobar" in e]
    return [e for e in errores if e not in persona], persona


def escribir_salidas(carpeta: Path, spec: dict[str, Any]) -> None:
    escribir(carpeta / "spec.json", spec)
    escribir(carpeta / "script.json", [{"cap": c, "tts": t} for c, t in spec["PHRASES"]])
    (carpeta / "gaps.json").write_text(json.dumps({str(k): v for k, v in spec["GAPS"].items()}), encoding="utf-8")
