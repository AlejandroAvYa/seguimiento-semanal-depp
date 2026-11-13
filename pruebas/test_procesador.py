"""Pruebas de aceptación del corte semanal (procesador Python)."""
import datetime as dt
import hashlib
import json
import pathlib

import openpyxl

from conftest import MODELO, RAIZ, crear_captura, fila, indice, leer_corte, procesar
from depp_corte import cli, motor

V1, V2, V3 = "2026-11-06", "2026-11-13", "2026-11-20"


def base(tmp_path):
    cap, sal = tmp_path / "capturas", tmp_path / "salidas"
    filas = [fila("AET", 1, received="2026-11-02", state="En curso"),
             fila("EE", 1, received="2026-11-03", state="Pendiente"),
             fila("EPP", 1, received="2026-11-04", state="En curso", due="2026-11-10"),
             fila("CPHDV", 1, received="2026-11-05", state="Entregado", delivered="2026-11-05", due="2026-11-05")]
    crear_captura(cap / V1, filas)
    assert procesar(cap, sal, V1) == 0
    return cap, sal, filas


# ------------------------------------------------------------------ plantillas
def test_plantillas_estructura():
    for libro in MODELO["books"]:
        wb = openpyxl.load_workbook(RAIZ / "plantillas" / libro["file"])
        assert wb.sheetnames[1] == "Inicio"
        assert wb.active.title == wb.sheetnames[0]
        for p in libro["prefixes"]:
            area = next(a for a in MODELO["areas"] if a["prefix"] == p)
            ws = wb[area["tab"]]
            assert ws["A1"].value == area["name"] and ws["A2"].value == area["products"]
            assert [ws.cell(3, c).value for c in range(1, 12)] == [f[1] for f in MODELO["fields"]]
            assert area["table"] in ws.tables and ws.tables[area["table"]].ref == "A3:K1003"
            assert ws["A4"].value == '=IF(COUNTA(B4:K4)=0,"",1)'
            assert ws["A1003"].value == '=IF(COUNTA(B1003:K1003)=0,"",1000)'
            assert ws.protection.sheet and ws["A10"].protection.locked and not ws["B10"].protection.locked
            lista = next(dv for dv in ws.data_validations.dataValidation if str(dv.sqref).startswith("F4"))
            assert lista.formula1.strip('"').split(",") == MODELO["requesters"] and len(MODELO["requesters"]) == 13
            assert any(dv.type == "date" for dv in ws.data_validations.dataValidation)


# ------------------------------------------------------------------ lectura
def test_lee_cuatro_tablas_mas_de_256_filas_y_area_vacia(tmp_path):
    cap, sal = tmp_path / "c", tmp_path / "s"
    filas = [fila("AET", n, received="2026-11-09") for n in range(1, 301)]
    filas += [fila("EE", 1), fila("EPP", 1)]  # CPHDV sin registros
    crear_captura(cap / V2, filas)
    assert procesar(cap, sal, V2) == 0
    corte = leer_corte(sal, V2)
    assert len(corte["rows"]) == 302 and corte["status"] == "valido"
    assert corte["summary"]["porArea"]["CPHDV"]["registros"] == 0
    assert corte["summary"]["porArea"]["AET"]["registros"] == 300


def test_numero_desde_formula_si_falta_cache(tmp_path):
    # openpyxl no guarda el valor calculado: el procesador recupera el N° desde la fórmula.
    cap, sal = tmp_path / "c", tmp_path / "s"
    crear_captura(cap / V2, [fila("EPP", 7)])
    procesar(cap, sal, V2)
    assert [r["number"] for r in leer_corte(sal, V2)["rows"]] == ["7"]


# ------------------------------------------------------------------ comparación entre cortes
def test_viernes_despues_del_mediodia_aparece_una_vez(tmp_path):
    cap, sal, filas = base(tmp_path)
    # Registrado el viernes 06/11 a las 15:00 (después de la captura): entra en el corte del 13/11.
    tarde = fila("AET", 2, received="2026-11-06", state="Entregado", delivered="2026-11-06", due="2026-11-06")
    crear_captura(cap / V2, filas + [tarde])
    assert procesar(cap, sal, V2) == 0
    a = motor.analizar(MODELO, motor.leer_corte(MODELO, leer_corte(sal, V2)))
    f = next(r for r in a["rows"] if r["id"] == "AET-002")
    assert f["receivedNow"] and f["deliveredNow"]
    crear_captura(cap / V3, filas + [tarde])
    assert procesar(cap, sal, V3) == 0
    a3 = motor.analizar(MODELO, motor.leer_corte(MODELO, leer_corte(sal, V3)))
    f3 = next(r for r in a3["rows"] if r["id"] == "AET-002")
    assert not f3["movement"] and a3["summary"]["ingresos"] == 0 and a3["summary"]["entregas"] == 0


def test_cambio_de_estado_u_observaciones_es_avance(tmp_path):
    cap, sal, filas = base(tmp_path)
    cambiadas = [dict(f) for f in filas]
    cambiadas[0]["notes"] = "Borrador listo."           # solo observaciones
    cambiadas[1]["state"] = "En curso"                  # solo estado
    crear_captura(cap / V2, cambiadas)
    procesar(cap, sal, V2)
    s = leer_corte(sal, V2)["summary"]
    assert s["avances"] == 2 and s["ingresos"] == 0 and s["entregas"] == 0


def test_registro_tardio_se_cuenta_como_ingreso(tmp_path):
    cap, sal, filas = base(tmp_path)
    crear_captura(cap / V2, filas + [fila("EE", 2, received="2026-11-02")])
    procesar(cap, sal, V2)
    s = leer_corte(sal, V2)["summary"]
    assert s["ingresos"] == 1 and s["ingresosTardios"] == 1


def test_numero_se_mantiene_al_mover_filas(tmp_path):
    # El N° es una constante de la fórmula de cada fila: si la fila se mueve, el N° la acompaña.
    cap, sal, filas = base(tmp_path)
    movida = dict(filas[0], line=20, a_override='=IF(COUNTA(B20:K20)=0,"",1)')
    crear_captura(cap / V2, [movida] + filas[1:])
    assert procesar(cap, sal, V2) == 0
    corte = leer_corte(sal, V2)
    assert corte["status"] == "valido" and corte["summary"]["avances"] == 0


# ------------------------------------------------------------------ incidencias
def _revision(tmp_path, filas_v2, codigo, **kw):
    cap, sal, filas = base(tmp_path)
    crear_captura(cap / V2, filas_v2(filas), **kw)
    assert procesar(cap, sal, V2) == 1
    corte = leer_corte(sal, V2)
    assert corte["status"] == "en_revision"
    assert codigo in {i["code"] for i in corte["incidents"]}
    idx = indice(sal)
    assert idx["lastValid"] == V1  # se conserva el último corte válido
    return corte


def test_registro_eliminado_deja_corte_en_revision(tmp_path):
    _revision(tmp_path, lambda f: f[1:], "registro_eliminado")


def test_numero_duplicado_deja_corte_en_revision(tmp_path):
    copia = lambda f: f + [dict(f[0], line=10, a_override='=IF(COUNTA(B10:K10)=0,"",1)')]
    _revision(tmp_path, copia, "numero_duplicado")


def test_reutilizacion_de_numero_deja_corte_en_revision(tmp_path):
    def reutiliza(f):
        g = [dict(x) for x in f]
        g[0].update(received="2026-11-12", request="Otro encargo distinto", product="Otro producto")
        return g
    _revision(tmp_path, reutiliza, "posible_reutilizacion")


def test_archivo_faltante_deja_corte_en_revision(tmp_path):
    _revision(tmp_path, lambda f: f, "archivo_ausente", sin=("Seguimiento_CPHDV.xlsx",))


def test_tabla_ausente_deja_corte_en_revision(tmp_path):
    cap, sal, filas = base(tmp_path)
    carpeta = crear_captura(cap / V2, filas)
    ruta = carpeta / "Seguimiento_Evaluacion_Politicas_Publicas.xlsx"
    wb = openpyxl.load_workbook(ruta)
    del wb["Evaluación de Políticas"].tables["Carga_EPP"]
    wb.save(ruta)
    assert procesar(cap, sal, V2) == 1
    assert "tabla_ausente" in {i["code"] for i in leer_corte(sal, V2)["incidents"]}


def test_captura_demorada_sin_version_verificada(tmp_path):
    _revision(tmp_path, lambda f: f, "captura_demorada", capturada="13:10:00", verificada=False)


def test_captura_demorada_con_version_verificada_es_valida(tmp_path):
    cap, sal, filas = base(tmp_path)
    crear_captura(cap / V2, filas, capturada="13:10:00", verificada=True)
    assert procesar(cap, sal, V2) == 0


def test_fila_con_error_conserva_version_anterior(tmp_path):
    cap, sal, filas = base(tmp_path)
    con_error = [dict(f) for f in filas]
    con_error[0]["product"] = ""                       # falta un obligatorio
    crear_captura(cap / V2, con_error)
    assert procesar(cap, sal, V2) == 0
    corte = leer_corte(sal, V2)
    assert corte["status"] == "valido_con_observaciones"
    retenida = next(r for r in corte["rows"] if r["area"] == "AET")
    assert retenida.get("held") and retenida["product"] == "Producto AET-1"
    # Corregida en el corte siguiente: se compara contra la versión retenida, sin ingresos falsos.
    arreglada = [dict(f) for f in filas]
    arreglada[0]["notes"] = "Corregido."
    crear_captura(cap / V3, arreglada)
    procesar(cap, sal, V3)
    s = leer_corte(sal, V3)["summary"]
    assert s["ingresos"] == 0 and s["avances"] == 1


def test_aprobar_corte_en_revision(tmp_path):
    cap, sal, filas = base(tmp_path)
    crear_captura(cap / V2, filas[1:])
    procesar(cap, sal, V2)
    assert indice(sal)["lastValid"] == V1
    cli.main(["aprobar", "--salidas", str(sal), "--corte", V2, "--responsable", "Jefatura DEPP",
              "--motivo", "Registro AET-001 eliminado por duplicidad, confirmado con la unidad."])
    assert indice(sal)["lastValid"] == V2
    assert leer_corte(sal, V2)["approval"]["by"] == "Jefatura DEPP"


def test_falla_conserva_ultimo_valido(tmp_path):
    cap, sal, _ = base(tmp_path)
    assert procesar(cap, sal, V2) == 2   # no existe la captura del 13/11
    idx = indice(sal)
    assert idx["lastValid"] == V1 and idx["lastRun"]["status"] == "fallido"


# ------------------------------------------------------------------ repetición e idempotencia
def _huellas(carpeta: pathlib.Path):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in carpeta.iterdir() if "Manifiesto" not in p.name}


def test_repetir_corte_no_duplica(tmp_path):
    cap, sal, filas = base(tmp_path)
    crear_captura(cap / V2, filas + [fila("AET", 2)])
    procesar(cap, sal, V2)
    antes = _huellas(sal / "cortes" / V2)
    procesar(cap, sal, V2)
    procesar(cap, sal, V2)
    assert _huellas(sal / "cortes" / V2) == antes
    idx = indice(sal)
    assert [c["cut"] for c in idx["cuts"]] == [V1, V2]
    man = json.loads((sal / "cortes" / V2 / f"Manifiesto_DEPP_{V2}.json").read_text(encoding="utf-8"))
    assert [r["result"] for r in man["runs"]] == ["publicado", "sin cambios", "sin cambios"]
    assert leer_corte(sal, V2)["summary"]["ingresos"] == 1


def test_no_reprocesa_cortes_antiguos_sin_forzar(tmp_path):
    cap, sal, filas = base(tmp_path)
    crear_captura(cap / V2, filas)
    procesar(cap, sal, V2)
    assert procesar(cap, sal, V1) == 2


# ------------------------------------------------------------------ hora de Santiago
def test_hora_programada_respeta_horario_de_verano():
    invierno = cli.hora_programada("2026-07-10").astimezone(dt.timezone.utc)
    verano = cli.hora_programada("2026-11-13").astimezone(dt.timezone.utc)
    assert invierno.hour == 16 and verano.hour == 15   # UTC-4 en julio, UTC-3 en noviembre


def test_corte_por_defecto_segun_mediodia():
    s = cli.SANTIAGO
    assert cli.corte_por_defecto(dt.datetime(2026, 11, 13, 11, 59, tzinfo=s)) == "2026-11-06"
    assert cli.corte_por_defecto(dt.datetime(2026, 11, 13, 12, 1, tzinfo=s)) == "2026-11-13"
    assert cli.corte_por_defecto(dt.datetime(2026, 11, 16, 9, 0, tzinfo=s)) == "2026-11-13"
    assert cli.corte_por_defecto(dt.datetime(2026, 7, 10, 15, 30, tzinfo=dt.timezone.utc)) == "2026-07-03"
    assert cli.corte_por_defecto(dt.datetime(2026, 7, 10, 16, 30, tzinfo=dt.timezone.utc)) == "2026-07-10"


def test_ejemplos_ficticios_coinciden_con_lo_esperado():
    sal = RAIZ / "ejemplos" / "salidas"
    s = leer_corte(sal, "2026-11-13")["summary"]
    assert (s["ingresos"], s["entregas"], s["avances"], s["abiertos"]) == (7, 4, 6, 10)
    s6 = leer_corte(sal, "2026-11-06")["summary"]
    # La ficha ENUSC (entregada el 06/11 a las 16:00) no figura como entrega en el corte del 06/11.
    a6 = motor.analizar(MODELO, motor.leer_corte(MODELO, leer_corte(sal, "2026-11-06")))
    assert not next(r for r in a6["rows"] if r["id"] == "EE-002")["deliveredNow"]
    assert s6["entregas"] == 2
