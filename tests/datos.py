"""Lo que Claude escribiría para el proyecto inventado de tests/fixtures/biblioteca."""
import copy
import json
from pathlib import Path

FIX = Path(__file__).parent / "fixtures" / "biblioteca"
EJEMPLO = json.loads((Path(__file__).resolve().parents[1] / "skills" / "scroll-to-study" / "prompts"
                      / "ejemplo_guion.json").read_text(encoding="utf-8"))

INVENTARIO = {"afirmaciones": [
    {"id": "A1", "tipo": "regla", "texto": "La FK de multa es id_prestamo y apunta a prestamo.",
     "fuente": "sql/schema.sql:21-26", "cita": "FOREIGN KEY (id_prestamo) REFERENCES prestamo"},
    {"id": "A2", "tipo": "decision", "texto": "Multa no referencia a socio directamente: apunta a prestamo.",
     "fuente": "informe.md:5-6", "cita": "La clave foránea de multa apunta a prestamo"},
    {"id": "A3", "tipo": "motivo", "texto": "No hay FK directa a socio porque abriría un segundo camino que podría contradecirla.",
     "fuente": "informe.md:8-9", "cita": "abriría un segundo camino que podría contradecirla"},
    {"id": "A4", "tipo": "regla", "texto": "Que un ejemplar ya esté prestado lo controla un trigger, no una FK.",
     "fuente": "informe.md:11", "cita": "lo controla un trigger"},
    # malas a propósito
    {"id": "A5", "tipo": "regla", "texto": "La reserva apunta al ejemplar con id_ejemplar.",
     "fuente": "sql/schema.sql:12-19", "cita": "fk_reserva_ejemplar FOREIGN KEY (id_ejemplar)"},
    {"id": "A6", "tipo": "dato", "texto": "Hay un índice idx_multa_monto para los reportes.",
     "fuente": "sql/schema.sql:21-26", "cita": "CREATE INDEX idx_multa_monto ON multa"},
    {"id": "A7", "tipo": "dato", "texto": "La PK de reserva es (id_ejemplar, ci_socio) y guarda id_prestamo.",
     "fuente": "sql/schema.sql:28-34", "cita": "PRIMARY KEY (id_ejemplar, ci_socio)"},
    {"id": "A8", "tipo": "dato", "texto": "Se cargan 20 socios de prueba.", "fuente": "sql/datos.sql:3", "cita": "INSERT INTO socio"},
]}
TEMAS = {"temas": [
    {"id": "t01", "titulo": "La FK de multa", "pregunta": "¿Cómo garantizan que una multa sea de un préstamo real?",
     "afirmaciones": ["A1", "A2", "A3", "A4", "A5"]},
    {"id": "t02", "titulo": "El trigger de préstamo", "pregunta": "¿Qué no puede controlar una FK?", "afirmaciones": ["A4"]},
]}


def guion_bueno():
    g = copy.deepcopy(EJEMPLO)
    for b, f in zip(g["bloques"], [["A1", "A2"], ["A2"], ["A3"], ["A4"]]):
        b["fuentes"] = f
    return g
