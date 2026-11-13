"""Lectura de las planillas DEPP (cuatro tablas en tres libros)."""
from __future__ import annotations

import pathlib
import re

import openpyxl

from . import motor

_FORMULA_N = re.compile(r",(\d+)\)$")


def _celda_n(valor_cache, formula):
    """N° desde el valor calculado; si la caché viene vacía, desde la constante de la fórmula."""
    if valor_cache not in (None, ""):
        return valor_cache
    if isinstance(formula, str):
        m = _FORMULA_N.search(formula)
        if m:
            return m.group(1)
    return ""


def leer_libro(modelo, ruta: pathlib.Path, libro_modelo):
    """Devuelve (entries, coverage, problems) para un libro."""
    entries, coverage, problems = [], [], []
    try:
        valores = openpyxl.load_workbook(ruta, data_only=True, read_only=False)
        formulas = openpyxl.load_workbook(ruta, data_only=False, read_only=False)
    except Exception as exc:  # archivo dañado, con contraseña o no xlsx
        for p in libro_modelo["prefixes"]:
            problems.append({"code": "archivo_ilegible", "area": p,
                             "message": f"No se pudo abrir {ruta.name}: {exc.__class__.__name__}."})
        return entries, coverage, problems
    epoca1904 = bool(valores.epoch == openpyxl.utils.datetime.CALENDAR_MAC_1904)
    encabezados = [f[1] for f in modelo["fields"]]
    for area in modelo["areas"]:
        if area["prefix"] not in libro_modelo["prefixes"]:
            continue
        if area["tab"] not in valores.sheetnames:
            problems.append({"code": "tabla_ausente", "area": area["prefix"],
                             "message": f"{ruta.name} no tiene la pestaña «{area['tab']}»."})
            continue
        ws, wf = valores[area["tab"]], formulas[area["tab"]]
        if area["table"] not in wf.tables:
            problems.append({"code": "tabla_ausente", "area": area["prefix"],
                             "message": f"La pestaña «{area['tab']}» no contiene la tabla {area['table']}."})
            continue
        fila3 = [str(ws.cell(3, c).value or "").strip() for c in range(1, 12)]
        if fila3 != encabezados:
            problems.append({"code": "encabezados_alterados", "area": area["prefix"],
                             "message": f"Los encabezados de «{area['tab']}» cambiaron. Restituye la fila 3 de la plantilla."})
            continue
        coverage.append(area["prefix"])
        for linea in range(4, ws.max_row + 1):
            datos = [ws.cell(linea, c).value for c in range(1, 12)]
            if not any(str(v).strip() for v in datos[1:] if v is not None):
                continue
            datos[0] = _celda_n(datos[0], wf.cell(linea, 1).value)
            entries.append(motor.registro(modelo, datos, area, linea, epoca1904))
    return entries, coverage, problems


def leer_carpeta(modelo, carpeta: pathlib.Path):
    """Lee los tres libros esperados desde una carpeta de captura."""
    lectura = {"entries": [], "coverage": [], "problems": [], "files": []}
    for libro in modelo["books"]:
        ruta = carpeta / libro["file"]
        if not ruta.exists():
            for p in libro["prefixes"]:
                area = next(a for a in modelo["areas"] if a["prefix"] == p)
                lectura["problems"].append({"code": "archivo_ausente", "area": p,
                                            "message": f"Falta {libro['file']} ({area['name']}) en la captura."})
            continue
        e, c, p = leer_libro(modelo, ruta, libro)
        for prefijo in c:
            if prefijo in lectura["coverage"]:
                p.append({"code": "pestana_repetida", "area": prefijo, "message": f"La pestaña de {prefijo} aparece en más de un archivo."})
        lectura["entries"] += e
        lectura["coverage"] += [x for x in c if x not in lectura["coverage"]]
        lectura["problems"] += p
        lectura["files"].append(libro["file"])
    return lectura
