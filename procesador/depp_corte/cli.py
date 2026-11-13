"""Línea de comandos del procesador DEPP.

  python -m depp_corte procesar --capturas <carpeta> --salidas <carpeta> [--corte AAAA-MM-DD]
  python -m depp_corte aprobar  --salidas <carpeta> --corte AAAA-MM-DD --responsable "Nombre" --motivo "..."
  python -m depp_corte tablero  --salidas <carpeta>
  python -m depp_corte capturar --config graph.json --capturas <carpeta> [--corte AAAA-MM-DD]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import pathlib
import sys
from zoneinfo import ZoneInfo

from . import lectura, motor, salidas

SANTIAGO = ZoneInfo("America/Santiago")
RAIZ = pathlib.Path(__file__).resolve().parents[2]
MODELO_POR_DEFECTO = RAIZ / "tablero" / "src" / "modelo_depp.json"
PLANTILLA_MINUTA = RAIZ / "plantillas" / "base_minuta_depp.docx"
PLANTILLA_TABLERO = RAIZ / "tablero" / "dist" / salidas.NOMBRE_TABLERO
TOLERANCIA_MIN = 30


def ahora() -> _dt.datetime:
    fijo = os.environ.get("DEPP_AHORA")  # solo para ejemplos reproducibles y pruebas
    if fijo:
        return _dt.datetime.fromisoformat(fijo).astimezone(SANTIAGO)
    return _dt.datetime.now(SANTIAGO).replace(microsecond=0)


def hora_programada(cut: str) -> _dt.datetime:
    """Viernes del corte a las 12:00 en Santiago (respeta el horario de verano)."""
    return _dt.datetime.fromisoformat(cut + "T12:00:00").replace(tzinfo=SANTIAGO)


def corte_por_defecto(momento: _dt.datetime | None = None) -> str:
    momento = momento or ahora()
    hoy = momento.astimezone(SANTIAGO).date().isoformat()
    viernes = motor.viernes_de_corte(hoy)
    # Antes de las 12:00 del viernes todavía corresponde el corte de la semana anterior.
    if viernes == hoy and momento.astimezone(SANTIAGO) < hora_programada(hoy):
        viernes = motor.desplazar(viernes, -7)
    return viernes


def cargar_modelo(ruta=None):
    return json.loads(pathlib.Path(ruta or MODELO_POR_DEFECTO).read_text(encoding="utf-8"))


def metadatos_captura(carpeta: pathlib.Path, cut: str) -> dict:
    """Lee captura.json (Power Automate o Graph). Sin él, usa la hora de los archivos."""
    programada = hora_programada(cut)
    ruta = carpeta / "captura.json"
    if ruta.exists():
        datos = json.loads(ruta.read_text(encoding="utf-8-sig"))
    else:
        tiempos = [p.stat().st_mtime for p in carpeta.glob("*.xlsx")]
        datos = {"capturedAt": _dt.datetime.fromtimestamp(max(tiempos), SANTIAGO).isoformat() if tiempos else None,
                 "source": "hora de los archivos", "verified": False}
    datos.setdefault("scheduledAt", programada.isoformat())
    capturada = datos.get("capturedAt")
    if capturada:
        momento = _dt.datetime.fromisoformat(capturada.replace("Z", "+00:00"))
        if momento.tzinfo is None:
            momento = momento.replace(tzinfo=SANTIAGO)
        local = momento.astimezone(SANTIAGO)
        datos["capturedAtLocal"] = local.strftime("%d/%m/%Y %H:%M")
        datos["late"] = local > programada + _dt.timedelta(minutes=TOLERANCIA_MIN)
        datos["early"] = local < programada - _dt.timedelta(minutes=TOLERANCIA_MIN)
    else:
        datos["late"] = False
    datos.setdefault("verified", False)
    return datos


def procesar(args) -> int:
    modelo = cargar_modelo(args.modelo)
    destino = pathlib.Path(args.salidas)
    cut = args.corte or corte_por_defecto()
    momento = ahora().isoformat()
    raiz_capturas = pathlib.Path(args.capturas)
    carpeta = raiz_capturas / f"{cut}_1200"  # nombre que deja el flujo de Power Automate
    if not carpeta.is_dir():
        carpeta = raiz_capturas / cut
    if not carpeta.is_dir() and any(raiz_capturas.glob("*.xlsx")):
        carpeta = raiz_capturas  # se indicó directamente la carpeta del corte
    try:
        if not motor.fecha_valida(cut):
            raise ValueError(f"Fecha de corte inválida: {cut}.")
        if _dt.date.fromisoformat(cut).weekday() != 4:
            raise ValueError(f"El corte {cut} no es viernes.")
        indice = salidas.leer_indice(destino)
        posteriores = [c["cut"] for c in indice["cuts"] if c["cut"] > cut]
        if posteriores and not args.forzar:
            raise ValueError(f"Ya existen cortes posteriores ({', '.join(posteriores)}). Usa --forzar solo si vas a reprocesarlos después.")
        if not carpeta.is_dir():
            raise FileNotFoundError(f"No existe la captura del corte {cut} en {raiz_capturas}.")
        captura = metadatos_captura(carpeta, cut)
        if captura.get("early"):
            raise ValueError(f"La captura ({captura['capturedAtLocal']}) es anterior al viernes {cut} a las 12:00.")
        datos = lectura.leer_carpeta(modelo, carpeta)
        anterior = salidas.ultimo_valido_anterior(destino, modelo, cut)
        corte = motor.construir_corte(modelo, datos, cut, anterior, captura)
        res = salidas.publicar(destino, modelo, corte, pathlib.Path(args.plantilla_minuta or PLANTILLA_MINUTA), {
            "at": momento, "capture": captura, "coverage": datos["coverage"],
            "rowsRead": len(datos["entries"]), "files": datos["files"]})
        if PLANTILLA_TABLERO.exists() or args.plantilla_tablero:
            salidas.escribir_tablero(destino, pathlib.Path(args.plantilla_tablero or PLANTILLA_TABLERO), modelo)
    except Exception as exc:  # se registra y se conserva el último corte válido
        salidas.registrar_falla(destino, cut, str(exc), momento)
        print(f"ERROR · corte {cut}: {exc}", file=sys.stderr)
        return 2
    s = corte["summary"]
    print(f"Corte {cut} · {corte['status']} · {'sin cambios' if res['unchanged'] else 'publicado'} · "
          f"{motor.plural(s['ingresos'], 'ingreso')}, {motor.plural(s['entregas'], 'entrega')}, "
          f"{motor.plural(s['avances'], 'avance')}, {motor.plural(s['abiertos'], 'abierto')} · "
          f"{motor.plural(len(corte['incidents']), 'incidencia')}")
    for i in corte["incidents"][:20]:
        print(f"  [{i['level']}] {i['area'] or '-'} {i['code']}: {i['message']}")
    if len(corte["incidents"]) > 20:
        print(f"  … {len(corte['incidents']) - 20} incidencias más en el manifiesto y el detalle.")
    return 0 if corte["status"] != "en_revision" else 1


def aprobar(args) -> int:
    modelo = cargar_modelo(args.modelo)
    destino = pathlib.Path(args.salidas)
    n = salidas.nombres(args.corte)
    ruta = salidas.carpeta_corte(destino, args.corte) / n["corte"]
    corte = json.loads(ruta.read_text(encoding="utf-8"))
    if corte["status"] != "en_revision":
        print(f"El corte {args.corte} ya está {corte['status']}.")
        return 0
    corte["status"] = "valido_con_observaciones"
    corte["approval"] = {"by": args.responsable, "at": ahora().isoformat(), "reason": args.motivo}
    momento = ahora().isoformat()
    salidas.publicar(destino, modelo, corte, pathlib.Path(args.plantilla_minuta or PLANTILLA_MINUTA),
                     {"at": momento, "capture": None})
    if PLANTILLA_TABLERO.exists():
        salidas.escribir_tablero(destino, PLANTILLA_TABLERO, modelo)
    print(f"Corte {args.corte} aprobado con observaciones por {args.responsable}.")
    return 0


def tablero(args) -> int:
    salidas.escribir_tablero(pathlib.Path(args.salidas), pathlib.Path(args.plantilla_tablero or PLANTILLA_TABLERO),
                             cargar_modelo(args.modelo))
    print("Tablero actualizado.")
    return 0


def capturar(args) -> int:
    from . import graph
    cut = args.corte or corte_por_defecto()
    return graph.capturar(json.loads(pathlib.Path(args.config).read_text(encoding="utf-8")),
                          pathlib.Path(args.capturas) / cut, hora_programada(cut), forzar=args.forzar)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="depp_corte", description="Corte semanal del seguimiento DEPP")
    p.add_argument("--modelo", help="Ruta a modelo_depp.json")
    sub = p.add_subparsers(dest="comando", required=True)
    a = sub.add_parser("procesar", help="Lee la captura, compara con el último corte válido y publica")
    a.add_argument("--capturas", required=True)
    a.add_argument("--salidas", required=True)
    a.add_argument("--corte")
    a.add_argument("--forzar", action="store_true")
    a.add_argument("--plantilla-minuta")
    a.add_argument("--plantilla-tablero")
    a.set_defaults(fn=procesar)
    b = sub.add_parser("aprobar", help="Aprueba con observaciones un corte en revisión")
    b.add_argument("--salidas", required=True)
    b.add_argument("--corte", required=True)
    b.add_argument("--responsable", required=True)
    b.add_argument("--motivo", required=True)
    b.add_argument("--plantilla-minuta")
    b.set_defaults(fn=aprobar)
    c = sub.add_parser("tablero", help="Regenera el tablero con los cortes publicados")
    c.add_argument("--salidas", required=True)
    c.add_argument("--plantilla-tablero")
    c.set_defaults(fn=tablero)
    d = sub.add_parser("capturar", help="Descarga desde Microsoft Graph las versiones del viernes a las 12:00")
    d.add_argument("--config", required=True)
    d.add_argument("--capturas", required=True)
    d.add_argument("--corte")
    d.add_argument("--forzar", action="store_true")
    d.set_defaults(fn=capturar)
    args = p.parse_args(argv)
    return args.fn(args)
