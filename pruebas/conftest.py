import datetime as dt
import json
import pathlib
import shutil
import sys

import openpyxl
import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "procesador"))

from depp_corte import cli, motor  # noqa: E402

MODELO = json.loads((RAIZ / "tablero" / "src" / "modelo_depp.json").read_text(encoding="utf-8"))
CLAVES = ["received", "request", "product", "kind", "requester", "owner", "due", "state", "delivered", "notes"]
LIBROS = {"AET": ("Seguimiento_Departamento_Estudios.xlsx", "Análisis Estad. y Territorial"),
          "EE": ("Seguimiento_Departamento_Estudios.xlsx", "Encuestas y Estudios"),
          "EPP": ("Seguimiento_Evaluacion_Politicas_Publicas.xlsx", "Evaluación de Políticas"),
          "CPHDV": ("Seguimiento_CPHDV.xlsx", "CPHDV")}


def fila(area, n, **campos):
    base = dict(received="2026-11-09", request=f"Requerimiento {area}-{n}", product=f"Producto {area}-{n}",
                kind="Programado", requester="Gabinete SPD", owner="Equipo", due="2026-11-20", state="En curso",
                delivered="", notes="")
    base.update(campos)
    return {"area": area, "number": n, **base}


def crear_captura(carpeta: pathlib.Path, filas, capturada="12:00:30", cut=None, verificada=True, sin=()):
    """Escribe los tres Excel con las filas indicadas (línea = 3 + N°, salvo 'line')."""
    carpeta.mkdir(parents=True, exist_ok=True)
    libros = {}
    for archivo, _ in set(LIBROS.values()):
        shutil.copy(RAIZ / "plantillas" / archivo, carpeta / archivo)
        libros[archivo] = openpyxl.load_workbook(carpeta / archivo)
    for f in filas:
        archivo, pestaña = LIBROS[f["area"]]
        ws = libros[archivo][pestaña]
        linea = f.get("line", 3 + int(f["number"]))
        for i, clave in enumerate(CLAVES):
            v = f.get(clave, "")
            if clave in ("received", "due", "delivered"):
                v = dt.datetime.strptime(v, "%Y-%m-%d") if v else None
            ws.cell(linea, 2 + i).value = v or None
        if "a_override" in f:
            ws.cell(linea, 1).value = f["a_override"]
    for archivo, wb in libros.items():
        wb.save(carpeta / archivo)
    for archivo in sin:
        (carpeta / archivo).unlink()
    cut = cut or carpeta.name
    (carpeta / "captura.json").write_text(json.dumps({
        "scheduledAt": f"{cut}T12:00:00-03:00", "capturedAt": f"{cut}T{capturada}-03:00", "verified": verificada}),
        encoding="utf-8")
    return carpeta


def procesar(capturas, salidas, cut, *extra):
    return cli.main(["procesar", "--capturas", str(capturas), "--salidas", str(salidas), "--corte", cut, *extra])


def leer_corte(salidas, cut):
    return json.loads((salidas / "cortes" / cut / f"Corte_DEPP_{cut}.json").read_text(encoding="utf-8"))


def indice(salidas):
    return json.loads((salidas / "indice.json").read_text(encoding="utf-8"))


@pytest.fixture
def modelo():
    return MODELO
