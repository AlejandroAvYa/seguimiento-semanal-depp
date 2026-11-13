"""El tablero (JavaScript) y el procesador (Python) deben entregar las mismas cifras y la misma minuta."""
import json
import pathlib
import shutil
import subprocess

import pytest

from conftest import MODELO, RAIZ, crear_captura, fila
from depp_corte import lectura, minuta_docx, motor

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js no disponible")


def correr_node(caso: dict, tmp_path: pathlib.Path):
    ruta = tmp_path / "caso.json"
    ruta.write_text(json.dumps(caso, ensure_ascii=False), encoding="utf-8")
    salida = subprocess.run([NODE, str(RAIZ / "pruebas" / "paridad_node.js"), str(ruta)],
                            capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(salida.stdout)


def resultado_python(corte):
    ej = motor.minuta(MODELO, corte, False)
    return {
        "summary": motor.analizar(MODELO, corte)["summary"],
        "ejecutiva": ej, "completa": motor.minuta(MODELO, corte, True),
        "docx": list(minuta_docx.cuerpo_minuta(ej)),
        "movimientos": [[m["tipo"], m["fila"]["id"], m["fecha"], m["cambios"]] for m in motor.movimientos(MODELO, corte)],
    }


@pytest.mark.parametrize("cut", ["2026-10-30", "2026-11-06", "2026-11-13"])
def test_paridad_con_cortes_publicados(cut, tmp_path):
    datos = json.loads((RAIZ / "ejemplos" / "salidas" / "cortes" / cut / f"Corte_DEPP_{cut}.json").read_text(encoding="utf-8"))
    js = correr_node({"corte": datos}, tmp_path)
    py = resultado_python(motor.leer_corte(MODELO, datos))
    for clave in ("summary", "ejecutiva", "completa", "docx", "movimientos"):
        assert js[clave] == py[clave], clave
    # El resumen guardado en el consolidado es el mismo que calcula el tablero.
    assert js["summary"] == datos["summary"]


def test_paridad_construccion_del_corte_con_incidencias(tmp_path):
    cap = tmp_path / "c"
    anterior = json.loads((RAIZ / "ejemplos" / "salidas" / "cortes" / "2026-11-06" / "Corte_DEPP_2026-11-06.json").read_text(encoding="utf-8"))
    filas = [fila("AET", 1, received="2026-10-26", request="Monitorear la situación delictual semanal",
                  product="Informe semanal STOP (semana 44)", state="Entregado", delivered="2026-10-28", due="2026-10-28"),
             fila("EE", 1, product=""),                       # error en registro existente
             fila("EPP", 9, received="2026-11-02"),           # registro tardío
             fila("EPP", 10, received="2026-11-20"),          # posterior al corte
             fila("CPHDV", 2, notes="Apoyo de Gabinete para coordinar con Fiscalía.")]
    crear_captura(cap / "2026-11-13", filas)
    lec = lectura.leer_carpeta(MODELO, cap / "2026-11-13")
    caso = {"lectura": lec, "cut": "2026-11-13", "anterior": anterior,
            "captura": {"late": True, "verified": False, "capturedAtLocal": "13/11/2026 13:05"}}
    js = correr_node(json.loads(json.dumps(caso, default=str)), tmp_path)
    py_corte = motor.construir_corte(MODELO, lec, "2026-11-13", motor.leer_corte(MODELO, anterior), caso["captura"])
    assert js["corte"] == json.loads(json.dumps(py_corte))
    assert py_corte["status"] == "en_revision"
    codigos = {i["code"] for i in py_corte["incidents"]}
    assert {"registro_eliminado", "registro_con_error", "fila_excluida", "captura_demorada"} <= codigos
