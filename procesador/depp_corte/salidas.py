"""Publicación del corte: consolidado, manifiesto, minuta, detalle, índice y tablero."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import pathlib

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import minuta_docx, motor

ESTADOS_VALIDOS = ("valido", "valido_con_observaciones")
NOMBRE_TABLERO = "Tablero_Seguimiento_Semanal_DEPP.html"


def _json(datos) -> str:
    return json.dumps(datos, ensure_ascii=False, indent=1, sort_keys=False)


def huella(datos) -> str:
    return hashlib.sha256(json.dumps(datos, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def carpeta_corte(salidas: pathlib.Path, cut: str) -> pathlib.Path:
    return salidas / "cortes" / cut


def nombres(cut: str) -> dict:
    return {
        "corte": f"Corte_DEPP_{cut}.json",
        "manifiesto": f"Manifiesto_DEPP_{cut}.json",
        "minuta": f"Minuta_DEPP_{cut}.docx",
        "detalle": f"Detalle_DEPP_{cut}.xlsx",
    }


# ---------------------------------------------------------------------------- índice
def leer_indice(salidas: pathlib.Path) -> dict:
    ruta = salidas / "indice.json"
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return {"format": "DEPP-INDICE-1", "updatedAt": None, "lastValid": None, "lastRun": None, "cuts": []}


def guardar_indice(salidas: pathlib.Path, indice: dict):
    indice["cuts"].sort(key=lambda c: c["cut"])
    validos = [c["cut"] for c in indice["cuts"] if c["status"] in ESTADOS_VALIDOS]
    indice["lastValid"] = validos[-1] if validos else None
    (salidas / "indice.json").write_text(_json(indice), encoding="utf-8")


def ultimo_valido_anterior(salidas: pathlib.Path, modelo, cut: str):
    indice = leer_indice(salidas)
    previos = [c for c in indice["cuts"] if c["cut"] < cut and c["status"] in ESTADOS_VALIDOS]
    if not previos:
        return None
    previo = max(previos, key=lambda c: c["cut"])
    datos = json.loads((carpeta_corte(salidas, previo["cut"]) / nombres(previo["cut"])["corte"]).read_text(encoding="utf-8"))
    return motor.leer_corte(modelo, datos)


def _resumen_corto(corte) -> dict:
    s = corte["summary"]
    return {k: s[k] for k in ("ingresos", "entregas", "avances", "abiertos", "vencidos", "bloqueados", "apoyos", "proximos")}


# ---------------------------------------------------------------------------- detalle completo
def escribir_detalle(modelo, corte, ruta: pathlib.Path):
    azul = PatternFill("solid", fgColor="0E2841")
    blanco = Font(name="Verdana", size=9, bold=True, color="FFFFFF")
    normal = Font(name="Verdana", size=9)
    areas = {a["prefix"]: a["name"] for a in modelo["areas"]}
    analisis = motor.analizar(modelo, corte)
    wb = openpyxl.Workbook()

    def hoja(ws, titulo, encabezados, filas, anchos):
        ws.title = titulo
        ws.append(encabezados)
        for c in ws[1]:
            c.fill, c.font = azul, blanco
            c.alignment = Alignment(wrap_text=True, vertical="center")
        for fila in filas:
            ws.append(fila)
        for fila in ws.iter_rows(min_row=2):
            for c in fila:
                c.font = normal
                c.alignment = Alignment(wrap_text=True, vertical="top")
        for i, ancho in enumerate(anchos, start=1):
            ws.column_dimensions[get_column_letter(i)].width = ancho
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        ws.row_dimensions[1].height = 30

    ft = motor.fecha_texto
    movs = motor.movimientos(modelo, corte)
    hoja(wb.active, "Movimientos",
         ["Equipo", "Referencia", "Movimiento", "Fecha", "Producto comprometido", "Requerimiento", "Requirente",
          "Responsable", "Estado", "Plazo vigente", "Entrega efectiva", "Cambios respecto del corte anterior", "Observaciones generales"],
         [[areas[m["fila"]["area"]], m["fila"]["id"], m["tipo"], ft(m["fecha"]), m["fila"]["product"], m["fila"]["request"],
           m["fila"]["requester"], m["fila"]["owner"], m["fila"]["state"], ft(m["fila"]["due"]), ft(m["fila"]["delivered"]),
           m["cambios"], m["fila"]["notes"]] for m in movs],
         [30, 11, 18, 11, 34, 34, 20, 18, 12, 11, 11, 26, 44])

    def alertas(f):
        marcas = []
        if f["late"]:
            marcas.append("Vencido")
        if f["blocked"] and f["active"]:
            marcas.append("Bloqueado")
        if f["support"]:
            marcas.append("Decisión de Gabinete" if f["decision"] else "Apoyo de Gabinete")
        if f["upcoming"]:
            marcas.append("Vence en 7 días")
        if f["undated"]:
            marcas.append("Sin plazo")
        if f["held"]:
            marcas.append("Versión del corte anterior")
        return ", ".join(marcas)

    hoja(wb.create_sheet(), "Compromisos al corte",
         ["Equipo", "Referencia", "Fecha de ingreso", "Requerimiento", "Producto comprometido", "Tipo de encargo", "Requirente",
          "Responsable", "Plazo acordado", "Estado", "Fecha de entrega efectiva", "Observaciones generales", "Alertas"],
         [[areas[f["area"]], f["id"], ft(f["received"]), f["request"], f["product"], f["kind"], f["requester"], f["owner"],
           ft(f["due"]), f["state"], ft(f["delivered"]), f["notes"], alertas(f)] for f in analisis["rows"]],
         [30, 11, 11, 34, 34, 13, 20, 18, 11, 12, 11, 44, 26])
    niveles = {"bloqueante": "Bloquea la publicación", "observacion": "Observación"}
    hoja(wb.create_sheet(), "Incidencias", ["Nivel", "Equipo", "Código", "Detalle"],
         [[niveles.get(i["level"], i["level"]), areas.get(i["area"], i["area"] or "General"), i["code"], i["message"]]
          for i in corte.get("incidents") or []] or [["", "", "", "Sin incidencias en este corte."]],
         [22, 30, 22, 90])
    claves = [("ingresos", "Ingresos"), ("entregas", "Entregas"), ("entregasFueraPlazo", "Entregas fuera de plazo"),
              ("avances", "Avances"), ("abiertos", "Abiertos al corte"), ("vencidos", "Vencidos"), ("bloqueados", "Bloqueados"),
              ("apoyos", "Solicitudes a Gabinete"), ("proximos", "Vencen en 7 días"), ("sinPlazo", "Abiertos sin plazo")]
    s = analisis["summary"]
    hoja(wb.create_sheet(), "Resumen", ["Indicador", "DEPP"] + [areas[a["prefix"]] for a in modelo["areas"]],
         [[etq, s[k]] + [s["porArea"][a["prefix"]][k] for a in modelo["areas"]] for k, etq in claves],
         [26, 9, 24, 24, 24, 24])
    fijo = _dt.datetime.fromisoformat(corte["cut"] + "T12:00:00")
    wb.properties.created = fijo
    wb.properties.modified = fijo
    wb.properties.creator = "DEPP"
    wb.properties.lastModifiedBy = "DEPP"
    wb.properties.title = f"Detalle completo del corte DEPP {ft(corte['cut'])}"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    wb.save(ruta)


# ---------------------------------------------------------------------------- tablero con datos
def escribir_tablero(salidas: pathlib.Path, plantilla_tablero: pathlib.Path, modelo):
    indice = leer_indice(salidas)
    cortes = {}
    for c in indice["cuts"]:
        ruta = carpeta_corte(salidas, c["cut"]) / nombres(c["cut"])["corte"]
        if ruta.exists():
            cortes[c["cut"]] = json.loads(ruta.read_text(encoding="utf-8"))
    datos = {"index": indice, "cuts": cortes, "origin": "procesador"}
    insertar_datos(plantilla_tablero, salidas / NOMBRE_TABLERO, datos)


def insertar_datos(plantilla: pathlib.Path, salida: pathlib.Path, datos):
    html = plantilla.read_text(encoding="utf-8")
    marca = '<script id="datos-cortes" type="application/json">null</script>'
    if marca not in html:
        raise ValueError("La plantilla del tablero no tiene el bloque de datos.")
    carga = json.dumps(datos, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    salida.write_text(html.replace(marca, f'<script id="datos-cortes" type="application/json">{carga}</script>'), encoding="utf-8")


# ---------------------------------------------------------------------------- publicación
def publicar(salidas: pathlib.Path, modelo, corte: dict, plantilla_minuta: pathlib.Path, ejecucion: dict):
    """Escribe los archivos del corte. Si el contenido no cambió, no reescribe nada."""
    cut = corte["cut"]
    carpeta = carpeta_corte(salidas, cut)
    carpeta.mkdir(parents=True, exist_ok=True)
    n = nombres(cut)
    ruta_corte = carpeta / n["corte"]
    nueva = huella(corte)
    anterior = huella(json.loads(ruta_corte.read_text(encoding="utf-8"))) if ruta_corte.exists() else None
    sin_cambios = anterior == nueva and all((carpeta / n[k]).exists() for k in ("minuta", "detalle"))
    if not sin_cambios:
        ruta_corte.write_text(_json(corte), encoding="utf-8")
        minuta_docx.escribir(motor.minuta(modelo, corte, completo=False), plantilla_minuta, carpeta / n["minuta"])
        escribir_detalle(modelo, corte, carpeta / n["detalle"])
    ruta_man = carpeta / n["manifiesto"]
    manifiesto = json.loads(ruta_man.read_text(encoding="utf-8")) if ruta_man.exists() else {
        "format": "DEPP-MANIFIESTO-1", "cut": cut, "runs": []}
    manifiesto.update({
        "status": corte["status"], "contentHash": nueva, "previousCut": corte["previousCut"],
        "capture": ejecucion.get("capture"), "coverage": ejecucion.get("coverage"),
        "rowsRead": ejecucion.get("rowsRead"), "rowsValid": len(corte["rows"]),
        "rowsRejected": len(corte["rejected"]),
        "incidents": corte["incidents"], "files": n,
    })
    manifiesto["runs"].append({"at": ejecucion["at"], "result": "sin cambios" if sin_cambios else "publicado",
                               "status": corte["status"]})
    ruta_man.write_text(_json(manifiesto), encoding="utf-8")

    indice = leer_indice(salidas)
    indice["cuts"] = [c for c in indice["cuts"] if c["cut"] != cut]
    indice["cuts"].append({"cut": cut, "status": corte["status"], "previousCut": corte["previousCut"],
                           "summary": _resumen_corto(corte),
                           "incidents": {"bloqueantes": sum(1 for i in corte["incidents"] if i["level"] == "bloqueante"),
                                         "observaciones": sum(1 for i in corte["incidents"] if i["level"] == "observacion")},
                           "capturedAt": (ejecucion.get("capture") or {}).get("capturedAt"),
                           "files": {k: f"cortes/{cut}/{v}" for k, v in n.items()}})
    indice["updatedAt"] = ejecucion["at"]
    indice["lastRun"] = {"cut": cut, "at": ejecucion["at"], "status": corte["status"],
                         "result": "sin cambios" if sin_cambios else "publicado"}
    guardar_indice(salidas, indice)
    return {"unchanged": sin_cambios, "folder": carpeta, "files": n}


def registrar_falla(salidas: pathlib.Path, cut: str, mensaje: str, at: str):
    """Deja visible una ejecución fallida sin tocar los cortes publicados."""
    salidas.mkdir(parents=True, exist_ok=True)
    indice = leer_indice(salidas)
    indice["updatedAt"] = at
    indice["lastRun"] = {"cut": cut, "at": at, "status": "fallido", "result": mensaje}
    guardar_indice(salidas, indice)
