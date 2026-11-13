"""Genera capturas ficticias de tres viernes y las procesa como lo haría la automatización.

Salida: ejemplos/capturas/<fecha>/ (tres Excel + captura.json) y ejemplos/salidas/.
Todos los datos son ficticios. Uso: python herramientas/generar_ejemplos.py
"""
import datetime as dt
import json
import os
import pathlib
import shutil
import sys

import openpyxl

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "procesador"))
from depp_corte import cli  # noqa: E402

CORTES = ["2026-10-30", "2026-11-06", "2026-11-13"]
CLAVES = ["received", "request", "product", "kind", "requester", "owner", "due", "state", "delivered", "notes"]

# Cada registro: área, N°, datos base y estado en cada corte (None = aún no registrado).
R = []


def reg(area, n, base, por_corte):
    R.append((area, n, base, por_corte))


T = "Equipo territorial"
EN = "Equipo de encuestas"
EV = "Equipo de evaluación"
CP = "Equipo CPHDV"
# ---------------------------------------------------------------- Análisis Estadístico y Territorial
reg("AET", 1, dict(received="2026-10-26", request="Monitorear la situación delictual semanal", product="Informe semanal STOP (semana 44)",
                   kind="Programado", requester="Gabinete SPD", owner=T, due="2026-10-28"),
    {c: dict(state="Entregado", delivered="2026-10-28") for c in CORTES})
reg("AET", 2, dict(received="2026-11-02", request="Monitorear la situación delictual semanal", product="Informe semanal STOP (semana 45)",
                   kind="Programado", requester="Gabinete SPD", owner=T, due="2026-11-04"),
    {"2026-11-06": dict(state="Entregado", delivered="2026-11-04"), "2026-11-13": dict(state="Entregado", delivered="2026-11-04")})
reg("AET", 3, dict(received="2026-11-09", request="Monitorear la situación delictual semanal", product="Informe semanal STOP (semana 46)",
                   kind="Programado", requester="Gabinete SPD", owner=T, due="2026-11-11"),
    {"2026-11-13": dict(state="Entregado", delivered="2026-11-11")})
reg("AET", 4, dict(received="2026-11-10", request="Preparar antecedentes para una actividad territorial", product="Mapa delictual y minuta comunal",
                   kind="Contingencia", requester="Gabinete Ministerial", owner=T, due="2026-11-13"),
    {"2026-11-13": dict(state="En revisión", notes="Cartografía consolidada. Minuta en revisión.")})
reg("AET", 5, dict(received="2026-10-27", request="Caracterizar la situación delictual de una comuna para su plan local", product="Diagnóstico territorial comunal",
                   kind="A solicitud", requester="SEREMI", owner=T, due="2026-11-20"),
    {"2026-10-30": dict(state="En curso", notes="Levantamiento de fuentes en curso."),
     "2026-11-06": dict(state="En curso", notes="Base de casos policiales integrada."),
     "2026-11-13": dict(state="Bloqueado", notes="Falta la respuesta policial a la solicitud de datos. Apoyo Gabinete: oficiar a la jefatura regional.")})
# Registrado el viernes 06/11 después de las 12:00: aparece por primera vez en el corte del 13/11.
reg("AET", 6, dict(received="2026-11-06", request="Responder solicitud de acceso a la información", product="Tabulados de denuncias para Transparencia",
                   kind="A solicitud", requester="Transparencia", owner=T, due="2026-11-12"),
    {"2026-11-13": dict(state="Entregado", delivered="2026-11-06", notes="Enviado el mismo día de ingreso.")})
# ---------------------------------------------------------------- Encuestas y Estudios
reg("EE", 1, dict(received="2026-10-20", request="Consolidar resultados de capacidades municipales", product="Informe de la Consulta de Capacidades de Gestión Municipal",
                  kind="Programado", requester="DEPP (INTERNO)", owner=EN, due="2026-11-18"),
    {"2026-10-30": dict(state="En curso", notes="Tabulados en elaboración."),
     "2026-11-06": dict(state="En curso", notes="Tabulados listos. Sigue revisión del informe."),
     "2026-11-13": dict(state="En revisión", notes="Informe en revisión de jefatura.")})
# Entregado el viernes 06/11 a las 16:00: el corte del 06/11 lo muestra en revisión; el del 13/11, entregado.
reg("EE", 2, dict(received="2026-11-04", request="Preparar materiales para difusión de resultados", product="Ficha de resultados ENUSC",
                  kind="Programado", requester="Comunicaciones", owner=EN, due="2026-11-10"),
    {"2026-11-06": dict(state="En revisión", notes="Producto en preparación."),
     "2026-11-13": dict(state="Entregado", delivered="2026-11-06", notes="Producto en preparación.")})
reg("EE", 3, dict(received="2026-10-29", request="Documentar la construcción de un índice", product="Ficha metodológica del índice de victimización",
                  kind="Programado", requester="DEPP (INTERNO)", owner=EN, due="2026-11-27"),
    {"2026-10-30": dict(state="Pendiente"), "2026-11-06": dict(state="Pendiente"),
     "2026-11-13": dict(state="En curso", notes="Borrador de la sección de fuentes.")})
# Ingresado con fecha 05/11 pero registrado después del corte del 06/11 (registro tardío).
reg("EE", 4, dict(received="2026-11-05", request="Responder consulta sobre resultados de encuestas", product="Minuta técnica para División Jurídica",
                  kind="A solicitud", requester="DJUR", owner=EN, due="2026-11-16"),
    {"2026-11-13": dict(state="En curso", notes="Cifras validadas; falta redacción final.")})
# ---------------------------------------------------------------- Evaluación de Políticas Públicas
reg("EPP", 1, dict(received="2026-11-04", request="Revisar el diseño de una intervención", product="Minuta de evaluación de diseño",
                   kind="A solicitud", requester="DTPT", owner=EV, due="2026-11-11"),
    {"2026-11-06": dict(state="En curso"),
     "2026-11-13": dict(state="Bloqueado", notes="Requiere el diseño actualizado. Gabinete debe solicitarlo a la contraparte.")})
reg("EPP", 2, dict(received="2026-11-10", request="Actualizar el seguimiento de un programa", product="Reporte de indicadores",
                   kind="Programado", requester="DEPP (INTERNO)", owner=EV, due="2026-11-17"),
    {"2026-11-13": dict(state="En curso", notes="El equipo del programa confirmó el nuevo plazo.")})
reg("EPP", 3, dict(received="2026-10-15", request="Acompañar la formulación ex ante de un programa", product="Observaciones al formulario ex ante",
                   kind="Programado", requester="Gabinete SPD", owner=EV, due="2026-11-12"),
    {"2026-10-30": dict(state="En curso", notes="Revisión del diagnóstico."),
     "2026-11-06": dict(state="En curso", due="2026-11-20", notes="Plazo ajustado por nueva versión del formulario."),
     "2026-11-13": dict(state="En curso", due="2026-11-20", notes="Plazo ajustado por nueva versión del formulario.")})
reg("EPP", 4, dict(received="2026-10-22", request="Apoyar a un municipio en la medición de resultados", product="Asistencia técnica municipal",
                   kind="A solicitud", requester="Municipio", owner=EV, due="2026-10-29"),
    {c: dict(state="Entregado", delivered="2026-10-30") for c in CORTES})
reg("EPP", 5, dict(received="2026-11-02", request="Reunir evidencia sobre prevención situacional", product="Síntesis de evidencia",
                   kind="A solicitud", requester="DTPT", owner=EV, due="2026-11-09"),
    {"2026-11-06": dict(state="Pendiente"),
     "2026-11-13": dict(state="Cancelado", notes="El requirente desistió del encargo.")})
# ---------------------------------------------------------------- CPHDV
reg("CPHDV", 1, dict(received="2026-10-26", request="Actualizar el seguimiento semanal de homicidios", product="Caracterización semanal de víctimas de homicidio (semana 44)",
                     kind="Programado", requester="Gabinete SPD", owner=CP, due="2026-10-26"),
    {c: dict(state="Entregado", delivered="2026-10-26") for c in CORTES})
reg("CPHDV", 2, dict(received="2026-11-02", request="Actualizar el seguimiento semanal de homicidios", product="Caracterización semanal de víctimas de homicidio (semana 45)",
                     kind="Programado", requester="Gabinete SPD", owner=CP, due="2026-11-02"),
    {"2026-11-06": dict(state="Entregado", delivered="2026-11-02"), "2026-11-13": dict(state="Entregado", delivered="2026-11-02")})
reg("CPHDV", 3, dict(received="2026-11-09", request="Actualizar el seguimiento semanal de homicidios", product="Caracterización semanal de víctimas de homicidio (semana 46)",
                     kind="Programado", requester="Gabinete SPD", owner=CP, due="2026-11-09"),
    {"2026-11-13": dict(state="Entregado", delivered="2026-11-09")})
reg("CPHDV", 4, dict(received="2026-11-10", request="Preparar antecedentes sobre un delito violento", product="Minuta temática sobre secuestros",
                     kind="A solicitud", requester="Gabinete SPD", owner=CP, due="2026-11-18"),
    {"2026-11-13": dict(state="En curso", notes="Antecedentes integrados para la revisión técnica.")})
reg("CPHDV", 5, dict(received="2026-10-01", request="Elaborar el informe semestral de homicidios", product="Informe semestral de homicidios",
                     kind="Programado", requester="Gabinete SPD", owner=CP, due="2026-11-13"),
    {"2026-10-30": dict(state="En curso", notes="Series consolidadas."),
     "2026-11-06": dict(state="En curso", notes="Series consolidadas."),
     "2026-11-13": dict(state="En revisión", notes="Decisión Gabinete: definir si se publica con cifras preliminares del último trimestre.")})

LIBROS = {"AET": ("Seguimiento_Departamento_Estudios.xlsx", "Análisis Estad. y Territorial"),
          "EE": ("Seguimiento_Departamento_Estudios.xlsx", "Encuestas y Estudios"),
          "EPP": ("Seguimiento_Evaluacion_Politicas_Publicas.xlsx", "Evaluación de Políticas"),
          "CPHDV": ("Seguimiento_CPHDV.xlsx", "CPHDV")}


def escribir_captura(cut, destino: pathlib.Path):
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    libros = {}
    for archivo, _ in set(LIBROS.values()):
        shutil.copy(RAIZ / "plantillas" / archivo, destino / archivo)
        libros[archivo] = openpyxl.load_workbook(destino / archivo)
    for area, n, base, por_corte in R:
        estado = por_corte.get(cut)
        if estado is None:
            continue
        datos = {**dict.fromkeys(CLAVES, ""), **base, **estado}
        archivo, pestaña = LIBROS[area]
        ws = libros[archivo][pestaña]
        for i, clave in enumerate(CLAVES):
            v = datos[clave]
            if clave in ("received", "due", "delivered"):
                v = dt.datetime.strptime(v, "%Y-%m-%d") if v else None
            ws.cell(3 + n, 2 + i).value = v or None
    fijo = dt.datetime.fromisoformat(cut + "T11:00:00")
    for archivo, wb in libros.items():
        wb.properties.created = fijo
        wb.properties.modified = fijo
        wb.properties.lastModifiedBy = "DEPP (ficticio)"
        wb.save(destino / archivo)
    (destino / "captura.json").write_text(json.dumps({
        "scheduledAt": f"{cut}T12:00:00-03:00", "capturedAt": f"{cut}T12:00:40-03:00",
        "source": "Ejemplo ficticio (Power Automate)", "verified": True,
        "files": [{"file": f, "etag": "ficticio"} for f in sorted(libros)]}, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    capturas = RAIZ / "ejemplos" / "capturas"
    salidas = RAIZ / "ejemplos" / "salidas"
    if salidas.exists():
        shutil.rmtree(salidas)
    for cut in CORTES:
        escribir_captura(cut, capturas / cut)
        os.environ["DEPP_AHORA"] = f"{cut}T12:05:00-03:00"
        codigo = cli.main(["procesar", "--capturas", str(capturas), "--salidas", str(salidas), "--corte", cut])
        if codigo not in (0, 1):
            raise SystemExit(codigo)
    os.environ.pop("DEPP_AHORA", None)


if __name__ == "__main__":
    main()
