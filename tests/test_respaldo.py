"""La verificación mecánica no comprueba que la cita respalde la afirmación; S2S respaldo sí.

fuentes.verificar comprueba que la cita esté en la fuente y que siglas, snake_case y números de
2+ cifras aparezcan. No comprueba que la afirmación se siga de la cita, así que una cita real puede
respaldar una afirmación falsa. El comando respaldo le pide ese juicio a Claude y lo aplica.
"""
import json
from pathlib import Path

import pytest
import s2s

# Material inventado sobre redes: las citas son textuales, las afirmaciones les agregan o contradicen.
MATERIAL = (
    "WEP usa una clave compartida y fue quebrado hace años.\n"
    "WPA2 usa AES, el estándar actual.\n"
)

INV = {"afirmaciones": [
    # la cita dice que WEP fue quebrado; la afirmación dice lo contrario
    {"id": "R1", "tipo": "dato", "texto": "WEP nunca fue quebrado y sigue siendo seguro.",
     "fuente": "redes.md:1", "cita": "WEP usa una clave compartida y fue quebrado"},
    # la cita no dice cuántas rondas; la afirmación inventa "3 rondas"
    {"id": "R2", "tipo": "dato", "texto": "WPA2 usa 3 rondas de AES.",
     "fuente": "redes.md:2", "cita": "WPA2 usa AES"},
]}

# Lo que Claude respondería leyendo respaldo_pedido.txt: ninguna cita respalda su afirmación.
RESPALDO = {
    "R1": {"respalda": False, "motivo": "la cita dice que WEP fue quebrado; la afirmación dice lo contrario"},
    "R2": {"respalda": False, "motivo": "la cita no menciona 3 rondas"},
}


@pytest.fixture
def t(tmp_path):
    doc = tmp_path / "redes.md"
    doc.write_text(MATERIAL, encoding="utf-8")
    t = tmp_path / "trabajo"
    assert s2s.main(["corpus", "-t", str(t), "--doc", str(doc)]) == 0
    (t / "inventario.json").write_text(json.dumps(INV), encoding="utf-8")
    assert s2s.main(["verificar", "-t", str(t)]) == 0
    return t


def _inv(t):
    return {a["id"]: a for a in json.loads((t / "inventario.json").read_text(encoding="utf-8"))["afirmaciones"]}


def test_hoy_pasan_como_ok_aunque_la_cita_no_respalde(t):
    """El agujero: la cita está y las siglas aparecen, así que las dos afirmaciones quedan en «ok»."""
    inv = _inv(t)
    assert inv["R1"]["estado"] == "ok"
    assert inv["R2"]["estado"] == "ok"


def test_respaldo_sin_json_escribe_el_pedido(t):
    assert not (t / "respaldo.json").exists()
    assert s2s.main(["respaldo", "-t", str(t)]) == 0
    pedido = (t / "respaldo_pedido.txt").read_text(encoding="utf-8")
    assert "R1" in pedido and "R2" in pedido
    assert "WEP nunca fue quebrado" in pedido          # la afirmación
    assert "WEP usa una clave compartida" in pedido     # la cita
    assert "respalda" in pedido and "respaldo.json" in pedido   # las instrucciones para Claude


def test_respaldo_pasa_las_citas_que_no_respaldan_a_comprobar(t):
    s2s.main(["respaldo", "-t", str(t)])                       # fase a: escribe el pedido
    (t / "respaldo.json").write_text(json.dumps(RESPALDO), encoding="utf-8")
    assert s2s.main(["respaldo", "-t", str(t)]) == 0           # fase b: aplica
    inv = _inv(t)
    assert inv["R1"]["estado"] == "comprobar"
    assert inv["R2"]["estado"] == "comprobar"
    assert "no respalda" in " ".join(inv["R1"]["motivos"])
    assert "la cita dice que WEP fue quebrado" in " ".join(inv["R1"]["motivos"])


def test_respaldo_respeta_aprobado(t):
    p = t / "inventario.json"; inv = json.loads(p.read_text(encoding="utf-8"))
    inv["afirmaciones"][0]["aprobado"] = True                  # R1 aprobado a mano
    p.write_text(json.dumps(inv), encoding="utf-8")
    s2s.main(["respaldo", "-t", str(t)])
    (t / "respaldo.json").write_text(json.dumps(RESPALDO), encoding="utf-8")
    s2s.main(["respaldo", "-t", str(t)])
    assert _inv(t)["R1"]["estado"] == "ok"                     # aprobado: no se toca
    assert _inv(t)["R2"]["estado"] == "comprobar"


def test_respaldo_informa_ids_que_faltan_o_sobran(t, capsys):
    s2s.main(["respaldo", "-t", str(t)])
    (t / "respaldo.json").write_text(json.dumps({"R1": {"respalda": True, "motivo": ""},
                                                 "R9": {"respalda": False, "motivo": "x"}}), encoding="utf-8")
    assert s2s.main(["respaldo", "-t", str(t)]) == 1
    out = capsys.readouterr().out
    assert "faltan" in out and "R2" in out                     # falta R2
    assert "sobran" in out and "R9" in out                     # sobra R9
    assert _inv(t)["R1"]["estado"] == "ok"                     # no aplicó nada


def test_respaldo_queda_en_el_registro(t):
    s2s.main(["respaldo", "-t", str(t)])
    (t / "respaldo.json").write_text(json.dumps(RESPALDO), encoding="utf-8")
    s2s.main(["respaldo", "-t", str(t)])
    cmds = [json.loads(l)["cmd"] for l in (t / "registro.jsonl").read_text(encoding="utf-8").splitlines()]
    assert cmds.count("respaldo") == 2                         # fase pedido + fase aplicar
