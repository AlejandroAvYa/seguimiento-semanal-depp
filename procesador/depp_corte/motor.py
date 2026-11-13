"""Reglas del corte semanal DEPP.

Traducción directa de tablero/src/motor.js. Si se cambia una regla, se cambia en
ambos archivos; pruebas/test_paridad.py verifica que entreguen lo mismo.
"""
from __future__ import annotations

import datetime as _dt
import functools
import re
import unicodedata

FORMATO = "DEPP-CORTE-3"
FORMATOS_ACEPTADOS = ("DEPP-CORTE-2", "DEPP-CORTE-3")
FECHAS = ("received", "due", "delivered")
CAMPOS_CAMBIO = ("state", "due", "notes", "owner", "product", "request", "requester", "kind", "received", "delivered")
ETIQUETAS_CAMBIO = {
    "state": "estado", "due": "plazo", "notes": "observaciones", "owner": "responsable", "product": "producto",
    "request": "requerimiento", "requester": "requirente", "kind": "tipo de encargo", "received": "fecha de ingreso",
    "delivered": "fecha de entrega",
}
CERRADOS = ("Entregado", "Cancelado")
PATRON_APOYO = re.compile(r"apoyo (de |del )?gabinete|decision (de |del )?gabinete|gabinete (debe|debera|deberia)|se solicitan? (a |al )gabinete|requiere (una )?decision")
PATRON_DECISION = re.compile(r"decision (de |del )?gabinete|requiere (una )?decision")
DIAS_PROXIMOS = 7
CODIGOS_SIN_DATOS = ("area_sin_datos", "archivo_ausente", "archivo_ilegible", "tabla_ausente", "encabezados_alterados", "pestana_repetida")
_NUM = re.compile(r"^[1-9]\d{0,7}$")
INF = float("inf")


# ---------------------------------------------------------------------------- utilidades
def cmp(a, b):
    return -1 if a < b else 1 if a > b else 0


def plegar(texto) -> str:
    t = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in t if not ("̀" <= c <= "ͯ"))


def desplazar(dia: str, n: int) -> str:
    return (_dt.date.fromisoformat(dia) + _dt.timedelta(days=n)).isoformat()


def fecha_texto(valor: str) -> str:
    return "/".join(reversed(valor.split("-"))) if valor else ""


def fecha_valida(dia) -> bool:
    if not isinstance(dia, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dia):
        return False
    try:
        return _dt.date.fromisoformat(dia).isoformat() == dia
    except ValueError:
        return False


def viernes_de_corte(hoy: str) -> str:
    d = _dt.date.fromisoformat(hoy)
    js_dia = (d.weekday() + 1) % 7  # domingo = 0, como getUTCDay
    return desplazar(hoy, -((js_dia + 2) % 7))


DIAS = ("domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado")


def momento_slot(slot, dia) -> str:
    """«lunes 16/11/2026 a las 09:00» a partir de un turno AAAA-MM-DD_HHMM."""
    d = slot[:10] if slot else dia
    nombre = DIAS[(_dt.date.fromisoformat(d).weekday() + 1) % 7]
    hora = f" a las {slot[11:13]}:{slot[13:15]}" if slot and re.search(r"_\d{4}$", slot) else ""
    return f"{nombre} {fecha_texto(d)}{hora}"


def plural(n: int, singular: str, plural_txt: str | None = None) -> str:
    return f"{n} {singular if n == 1 else (plural_txt or singular + 's')}"


def enumerar(lista) -> str:
    lista = list(lista)
    if len(lista) <= 1:
        return "".join(lista)
    return ", ".join(lista[:-1]) + " y " + lista[-1]


def cerrar_frase(texto) -> str:
    t = str(texto or "").strip()
    if not t:
        return ""
    return t if t[-1] in ".!?…" else t + "."


def _numero_texto(n) -> str:
    """Convierte valores leídos de Excel a texto como lo hace el tablero."""
    if n is None:
        return ""
    if isinstance(n, bool):
        return "TRUE" if n else "FALSE"
    if isinstance(n, float) and n.is_integer():
        return str(int(n))
    return str(n)


# ---------------------------------------------------------------------------- fechas de Excel
def fecha_excel(valor, epoca1904: bool = False):
    if isinstance(valor, _dt.datetime):
        return valor.date().isoformat()
    if isinstance(valor, _dt.date):
        return valor.isoformat()
    v = _numero_texto(valor).strip()
    if not v:
        return ""
    if re.fullmatch(r"\d+(\.\d+)?", v):
        serial = int(float(v))
        if serial < 0 or serial > 2958465 or (not epoca1904 and serial < 61):
            return None
        return desplazar("1904-01-01" if epoca1904 else "1899-12-30", serial)
    iso = re.fullmatch(r"(\d{4}-\d{2}-\d{2})(?:[T ].*)?", v)
    local = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", v)
    if iso:
        normal = iso.group(1)
    elif local:
        normal = f"{local.group(3)}-{local.group(2).zfill(2)}-{local.group(1).zfill(2)}"
    else:
        normal = ""
    return normal if fecha_valida(normal) else None


# ---------------------------------------------------------------------------- registros
def registro(modelo, valores, area, linea, epoca1904=False):
    fila = {}
    for i, (clave, *_rest) in enumerate(modelo["fields"]):
        v = valores[i] if i < len(valores) else None
        fila[clave] = v if isinstance(v, (_dt.date, _dt.datetime)) else _numero_texto(v).strip()
    fila["area"] = area["prefix"]
    errores = []
    for clave, etiqueta, *_rest in modelo["fields"]:
        if clave not in FECHAS:
            continue
        f = fecha_excel(fila[clave], epoca1904)
        if f is None:
            errores.append(etiqueta.lower() + " no válida")
            fila[clave] = ""
        else:
            fila[clave] = f
    if re.fullmatch(r"\d+\.0+", fila["number"]):
        fila["number"] = re.sub(r"\.0+$", "", fila["number"])
    for clave, etiqueta, *_rest in modelo["fields"][:9]:
        if clave not in ("due", "number") and not fila[clave]:
            errores.append("falta " + etiqueta.lower())
    if _NUM.fullmatch(fila["number"]):
        fila["id"] = area["prefix"] + "-" + fila["number"].zfill(3)
    else:
        errores.append("N° automático ausente o inválido")
    for clave, opciones, etiqueta in (("kind", modelo["kinds"], "tipo de encargo"),
                                      ("requester", modelo["requesters"], "requirente"),
                                      ("state", modelo["states"], "estado")):
        if fila[clave] and fila[clave] not in opciones:
            errores.append(etiqueta + " fuera de lista")
    if fila["state"] == "Entregado" and not fila["delivered"]:
        errores.append("falta fecha de entrega efectiva")
    if fila["state"] != "Entregado" and fila["delivered"]:
        errores.append("fecha de entrega efectiva sin estado Entregado")
    if fila["received"] and fila["delivered"] and fila["delivered"] < fila["received"]:
        errores.append("entrega anterior al ingreso")
    return {"row": fila, "errors": errores, "line": linea, "location": f"{area['tab']}, fila {linea}"}


def _id(f) -> str:
    return f.get("id") or f"{f['area']}-{str(f['number']).zfill(3)}"


def serializar(modelo, fila):
    out = {"area": fila["area"]}
    for clave, *_rest in modelo["fields"]:
        out[clave] = fila.get(clave, "") or ""
    if fila.get("held"):
        out["held"] = True
    return out


def filas_desde_json(modelo, filas, contexto):
    areas = {a["prefix"]: a for a in modelo["areas"]}
    salida = []
    for i, f in enumerate(filas):
        area = areas.get((f or {}).get("area"))
        if not area:
            raise ValueError(f"El consolidado {contexto} contiene un área no reconocida.")
        r = registro(modelo, [f.get(k) for k, *_ in modelo["fields"]], area, i + 1)
        if r["errors"]:
            raise ValueError(f"El consolidado {contexto} contiene un registro inválido ({r['row'].get('id', 'sin N°')}: {', '.join(r['errors'])}).")
        if f.get("held"):
            r["row"]["held"] = True
        salida.append(r["row"])
    return salida


# ---------------------------------------------------------------------------- construcción del corte
def construir_corte(modelo, lectura, cut, anterior=None, captura=None, opciones=None):
    op = opciones or {}
    actualizacion = op.get("kind") == "actualizacion"
    if not fecha_valida(cut):
        raise ValueError("Fecha de corte inválida.")
    if anterior and (anterior["cut"] > cut if actualizacion else anterior["cut"] >= cut):
        raise ValueError("El corte anterior debe ser previo a la fecha de corte.")
    incidencias = []

    def agregar(nivel, codigo, area, mensaje):
        incidencias.append({"level": nivel, "code": codigo, "area": area or "", "message": mensaje})

    for p in lectura.get("problems", []):
        agregar("bloqueante", p["code"], p.get("area", ""), p["message"])

    previas = anterior["rows"] if anterior else None
    mapa_previo = {}
    for f in previas or []:
        mapa_previo[f"{f['area']}-{str(f['number']).zfill(3)}"] = f
    conteo = {}
    for e in lectura["entries"]:
        if e["row"].get("id"):
            conteo[e["row"]["id"]] = conteo.get(e["row"]["id"], 0) + 1

    validas, rechazadas = [], []
    ids_vistos, avisados = set(), set()
    for e in lectura["entries"]:
        errores = list(e["errors"])
        fila = e["row"]
        if fila.get("received") and fila["received"] > cut:
            errores.append("fecha de ingreso posterior al corte")
        if fila.get("delivered") and fila["delivered"] > cut:
            errores.append("fecha de entrega posterior al corte")
        fid = fila.get("id")
        if fid and conteo[fid] > 1:
            errores.append("N° duplicado")
            if fid not in avisados:
                avisados.add(fid)
                agregar("bloqueante", "numero_duplicado", fila["area"], f"El N° {fid} aparece en {conteo[fid]} filas.")
        if fid:
            ids_vistos.add(fid)
        if errores:
            rechazadas.append({"area": fila["area"], "number": fila.get("number") or "", "line": e["line"],
                               "location": e["location"], "errors": errores})
        else:
            validas.append(fila)

    retenidas = []
    ids_validos = {f["id"] for f in validas}
    for r in rechazadas:
        rid = f"{r['area']}-{r['number'].zfill(3)}" if _NUM.fullmatch(r["number"]) else ""
        previa = mapa_previo.get(rid) if rid else None
        if previa and rid not in ids_validos and not any(f["id"] == rid for f in retenidas):
            retenidas.append({**previa, "id": rid, "held": True})
            agregar("observacion", "registro_con_error", r["area"],
                    f"{r['location']} ({rid}): {', '.join(r['errors'])}. Se mantiene la versión del corte anterior.")
        else:
            agregar("observacion", "fila_excluida", r["area"],
                    f"{r['location']}{' (' + rid + ')' if rid else ''}: {', '.join(r['errors'])}.")

    for f in validas:
        previa = mapa_previo.get(f["id"])
        if previa and previa["received"] != f["received"] and previa["request"] != f["request"]:
            agregar("bloqueante", "posible_reutilizacion", f["area"],
                    f"El N° {f['id']} cambió fecha de ingreso y requerimiento respecto del corte anterior. Verifica si la fila se usó para otro encargo.")
    cobertura = set(lectura["coverage"])
    for area in modelo["areas"]:
        if area["prefix"] not in cobertura and not any(i["area"] == area["prefix"] and i["level"] == "bloqueante" for i in incidencias):
            agregar("bloqueante", "area_sin_datos", area["prefix"], f"No se pudo leer la pestaña «{area['tab']}».")
    if previas is not None:
        for rid, f in mapa_previo.items():
            if f["area"] in cobertura and rid not in ids_vistos:
                agregar("bloqueante", "registro_eliminado", f["area"],
                        f"El registro {rid} estaba en el corte anterior y ya no aparece en el Excel.")
    if captura and captura.get("late") and not captura.get("verified"):
        agregar("bloqueante", "captura_demorada", "",
                f"La captura se realizó a las {captura.get('capturedAtLocal') or '?'} y no se pudo verificar la versión de la hora programada.")

    orden_area = [a["prefix"] for a in modelo["areas"]]
    filas = sorted(validas + retenidas, key=lambda f: (orden_area.index(f["area"]), int(f["number"])))
    bloqueantes = sum(1 for i in incidencias if i["level"] == "bloqueante")
    corte = {
        "format": FORMATO,
        "from": anterior["cut"] if anterior else desplazar(cut, -7),
        "cut": cut,
        "previousCut": anterior["cut"] if anterior else None,
        "status": "en_revision" if bloqueantes else ("valido_con_observaciones" if incidencias else "valido"),
        "previousRows": [serializar(modelo, f) for f in previas] if previas is not None else None,
        "rows": [serializar(modelo, f) for f in filas],
        "rejected": rechazadas,
        "incidents": incidencias,
    }
    if op.get("kind"):
        corte["kind"] = op["kind"]
    if op.get("slot"):
        corte["slot"] = op["slot"]
    if captura and captura.get("capturedAt"):
        corte["capturedAt"] = captura["capturedAt"]
    corte["summary"] = analizar(modelo, corte)["summary"]
    return corte


def leer_corte(modelo, datos):
    if (not isinstance(datos, dict) or datos.get("format") not in FORMATOS_ACEPTADOS
            or not fecha_valida(datos.get("cut")) or not fecha_valida(datos.get("from"))
            or datos["from"] > datos["cut"] or not isinstance(datos.get("rows"), list)
            or (datos.get("previousRows") is not None and not isinstance(datos["previousRows"], list))):
        raise ValueError("El archivo no corresponde a un consolidado DEPP compatible.")
    filas = filas_desde_json(modelo, datos["rows"], "actual")
    previas = filas_desde_json(modelo, datos["previousRows"], "anterior") if isinstance(datos.get("previousRows"), list) else None
    ids = set()
    for f in filas:
        if f["id"] in ids:
            raise ValueError(f"El consolidado contiene el N° {f['id']} repetido.")
        ids.add(f["id"])
        if f["received"] > datos["cut"] or (f["delivered"] and f["delivered"] > datos["cut"]):
            raise ValueError(f"El consolidado contiene fechas posteriores al corte ({f['id']}).")
    return {
        "format": datos["format"], "from": datos["from"], "cut": datos["cut"],
        "previousCut": datos.get("previousCut", datos["from"] if previas is not None else None),
        "status": datos.get("status") or "valido",
        "previousRows": previas, "rows": filas,
        "rejected": datos.get("rejected") or [], "incidents": datos.get("incidents") or [],
        "summary": datos.get("summary"), "approval": datos.get("approval"),
        "kind": datos.get("kind") or "semanal", "slot": datos.get("slot"), "capturedAt": datos.get("capturedAt"),
    }


# ---------------------------------------------------------------------------- análisis del período
def analizar(modelo, corte):
    cut, frm = corte["cut"], corte["from"]
    comparando = isinstance(corte.get("previousRows"), list)
    mapa_previo = {_id(f): f for f in (corte.get("previousRows") or [])}
    proximo = desplazar(cut, DIAS_PROXIMOS)
    filas = []
    for original in corte["rows"]:
        f = dict(original)
        f["id"] = _id(original)
        previa = mapa_previo.get(f["id"])
        activo = f["state"] not in CERRADOS
        notas = plegar(f.get("notes"))
        apoyo = activo and bool(PATRON_APOYO.search(notas))
        decision = apoyo and bool(PATRON_DECISION.search(notas))
        vencido = bool(activo and f["due"] and f["due"] < cut)
        cambios = []
        if comparando:
            ingreso = previa is None
            entrega = f["state"] == "Entregado" and (previa is None or previa["state"] != "Entregado")
            if previa is not None:
                cambios = [k for k in CAMPOS_CAMBIO if (previa.get(k) or "") != (f.get(k) or "")]
        else:
            ingreso = bool(f["received"] and frm <= f["received"] <= cut)
            entrega = bool(f["state"] == "Entregado" and frm <= (f["delivered"] or "") <= cut)
        avance = previa is not None and not entrega and len(cambios) > 0
        f.update({
            "active": activo, "late": vencido, "blocked": f["state"] == "Bloqueado",
            "support": apoyo, "decision": decision,
            "attention": vencido or f["state"] == "Bloqueado" or apoyo,
            "upcoming": bool(activo and f["due"] and cut <= f["due"] <= proximo),
            "undated": activo and not f["due"],
            "receivedNow": ingreso,
            "lateEntry": comparando and ingreso and f["received"] < frm,
            "deliveredNow": entrega,
            "deliveredLate": entrega and bool(f["due"]) and f["delivered"] > f["due"],
            "advancedNow": avance,
            "cancelledNow": avance and f["state"] == "Cancelado" and "state" in cambios,
            "changed": cambios,
            "movement": ingreso or entrega or avance,
            "held": bool(original.get("held")),
        })
        filas.append(f)

    def resumen_de(lista):
        c = lambda k: sum(1 for f in lista if f[k])
        return {
            "registros": len(lista), "ingresos": c("receivedNow"), "ingresosTardios": c("lateEntry"),
            "entregas": c("deliveredNow"), "entregasFueraPlazo": c("deliveredLate"), "avances": c("advancedNow"),
            "cancelados": c("cancelledNow"), "abiertos": c("active"), "vencidos": c("late"),
            "bloqueados": sum(1 for f in lista if f["active"] and f["blocked"]),
            "apoyos": c("support"), "decisiones": c("decision"), "atencion": c("attention"),
            "proximos": c("upcoming"), "sinPlazo": c("undated"),
        }

    resumen = resumen_de(filas)
    resumen["porArea"] = {a["prefix"]: resumen_de([f for f in filas if f["area"] == a["prefix"]]) for a in modelo["areas"]}
    return {"rows": filas, "summary": resumen, "from": frm, "cut": cut, "next": proximo, "comparing": comparando}


# ---------------------------------------------------------------------------- minuta (modelo común)
def _orden_plazo(a, b):
    return cmp(a["due"] or "9999-99-99", b["due"] or "9999-99-99") or cmp(a["id"], b["id"])


def _ordenar(lista, comparador):
    return sorted(lista, key=functools.cmp_to_key(comparador))


def _area(modelo, prefijo):
    return next(a for a in modelo["areas"] if a["prefix"] == prefijo)


def linea_movimiento(f):
    if f["deliveredNow"]:
        texto = f"Entregado el {fecha_texto(f['delivered'])} a {f['requester']}."
        if f["deliveredLate"]:
            texto += f" Fuera de plazo (plazo {fecha_texto(f['due'])})."
        if f["receivedNow"]:
            texto += " Ingresó en el período."
    elif f["advancedNow"]:
        texto = f"{f['state']}. Actualizó {enumerar(ETIQUETAS_CAMBIO[k] for k in f['changed'])}."
        if "due" in f["changed"] and f["due"]:
            texto += f" Nuevo plazo: {fecha_texto(f['due'])}."
    else:
        texto = f"Ingresó el {fecha_texto(f['received'])} ({f['kind']}, {f['requester']}). Estado: {f['state']}."
        if f["lateEntry"]:
            texto += " Registro tardío."
        if f["due"]:
            texto += f" Plazo: {fecha_texto(f['due'])}."
    notas = cerrar_frase(f["notes"])
    return {"ref": f["id"], "lead": f["product"] + ".", "text": texto + (" " + notas if notas else "")}


def linea_alerta(modelo, f):
    area = _area(modelo, f["area"])
    marcas = []
    if f["blocked"]:
        marcas.append("Bloqueado")
    if f["late"]:
        marcas.append("Vencido desde el " + fecha_texto(f["due"]))
    notas = cerrar_frase(f["notes"])
    return {"ref": f["id"], "lead": f["product"] + ".",
            "text": ". ".join(marcas) + ". " + f["owner"] + ", " + area["name"] + "." + (" " + notas if notas else "")}


def linea_solicitud(modelo, f):
    area = _area(modelo, f["area"])
    return {"ref": f["id"], "lead": ("Decisión" if f["decision"] else "Apoyo") + " · " + f["product"] + ".",
            "text": cerrar_frase(f["notes"]) + " Responsable: " + f["owner"] + ", " + area["name"] + "."
            + (" Plazo: " + fecha_texto(f["due"]) + "." if f["due"] else "")}


def linea_proxima(f):
    extra = " · " + f["state"] if f["state"] not in ("Pendiente", "En curso") else ""
    return {"ref": f["id"], "lead": fecha_texto(f["due"]) + ".",
            "text": f"{f['product']} · {f['owner']} · {f['requester']}{extra}."}


def _recortar(lista, limite):
    if len(lista) <= limite:
        return lista, 0
    return lista[:int(limite)], len(lista) - int(limite)


def minuta(modelo, corte, completo=False):
    a = analizar(modelo, corte)
    s = a["summary"]
    actualizacion = corte.get("kind") == "actualizacion"
    momento = momento_slot(corte.get("slot"), a["cut"])
    if actualizacion and not a["comparing"]:
        periodo = f"Actualización del {momento}. Aún no hay un corte semanal anterior para comparar; muestra la línea base."
    elif actualizacion:
        periodo = (f"Avance desde el corte del viernes {fecha_texto(a['from'])} a las 12:00 hasta el {momento}. "
                   "Es una actualización intermedia; la minuta oficial usa el corte del viernes a las 12:00.")
    elif a["comparing"]:
        periodo = f"Del viernes {fecha_texto(a['from'])} a las 12:00 al viernes {fecha_texto(a['cut'])} a las 12:00."
    else:
        periodo = (f"Corte inicial al viernes {fecha_texto(a['cut'])} a las 12:00. Considera ingresos y entregas desde el "
                   f"{fecha_texto(a['from'])} y fija la línea base para comparar el corte siguiente.")
    resumen = " ".join([
        "En el período se registraron " + plural(s["ingresos"], "ingreso") + " y " + plural(s["entregas"], "entrega")
        + (f" ({s['entregasFueraPlazo']} fuera de plazo)" if s["entregasFueraPlazo"] else "")
        + (", y " + plural(s["avances"], "compromiso tuvo avance", "compromisos tuvieron avance") if a["comparing"] else "") + ".",
        "Al corte hay " + plural(s["abiertos"], "compromiso abierto", "compromisos abiertos") + ": "
        + plural(s["vencidos"], "vencido") + ", " + plural(s["bloqueados"], "bloqueado") + " y "
        + plural(s["apoyos"], "con solicitud a Gabinete", "con solicitudes a Gabinete") + ".",
        ("Vencen " + plural(s["proximos"], "compromiso") if s["proximos"] else "No vencen compromisos")
        + f" entre el {fecha_texto(a['cut'])} y el {fecha_texto(a['next'])}.",
    ])

    equipos = []
    for area in modelo["areas"]:
        r = area["prefix"]
        propios = [f for f in a["rows"] if f["area"] == r and f["movement"]]
        destacados = _ordenar([f for f in propios if f["deliveredNow"] or f["advancedNow"]], lambda x, y:
                              int(y["deliveredNow"]) - int(x["deliveredNow"]) or cmp(y["delivered"] or "", x["delivered"] or "") or cmp(x["id"], y["id"]))
        ingresos = _ordenar([f for f in propios if not f["deliveredNow"] and not f["advancedNow"]],
                            lambda x, y: cmp(y["received"], x["received"]) or cmp(x["id"], y["id"]))
        sa = s["porArea"][r]
        nota = ""
        if completo:
            lista = destacados + ingresos
        else:
            lista, omitidos = _recortar(destacados, 3)
            partes = []
            if omitidos:
                partes.append(plural(omitidos, "entrega o avance adicional", "entregas o avances adicionales"))
            if ingresos:
                partes.append(plural(len(ingresos), "ingreso nuevo", "ingresos nuevos"))
            if partes:
                nota = "Además: " + enumerar(partes) + " (ver detalle completo)."
            if not lista and ingresos:
                lista = _recortar(ingresos, 2)[0]
                nota = ("Además: " + plural(len(ingresos) - 2, "ingreso nuevo", "ingresos nuevos") + " (ver detalle completo).") if len(ingresos) > 2 else ""
        sin_datos = any(i["code"] in CODIGOS_SIN_DATOS and i["area"] == r for i in corte.get("incidents") or [])
        vacio = "Planilla del equipo no disponible en este corte." if sin_datos else "Sin movimientos registrados en el período."
        equipos.append({
            "title": area["name"],
            "counts": " · ".join([plural(sa["entregas"], "entrega"), plural(sa["avances"], "avance"),
                                  plural(sa["ingresos"], "ingreso"), plural(sa["abiertos"], "abierto")]),
            "items": [linea_movimiento(f) for f in lista],
            "note": nota if lista else vacio,
        })
    alertas = _ordenar([f for f in a["rows"] if f["active"] and (f["blocked"] or f["late"])],
                       lambda x, y: int(y["blocked"]) - int(x["blocked"]) or _orden_plazo(x, y))
    solicitudes = _ordenar([f for f in a["rows"] if f["support"]],
                           lambda x, y: int(y["decision"]) - int(x["decision"]) or _orden_plazo(x, y))
    proximos = _ordenar([f for f in a["rows"] if f["upcoming"]], _orden_plazo)
    lim = INF if completo else 6
    al, al_r = _recortar(alertas, lim)
    so, so_r = _recortar(solicitudes, lim)
    pr, pr_r = _recortar(proximos, lim)

    def mas(n, sing, pl):
        return "Además: " + plural(n, sing, pl) + " (ver detalle completo)." if n else ""

    secciones = [
        {"title": "Período y resumen", "paragraphs": [periodo, resumen]},
        {"title": "Principales entregas y avances por equipo", "groups": equipos},
        {"title": "Bloqueos y atrasos", "items": [linea_alerta(modelo, f) for f in al],
         "note": mas(al_r, "compromiso", "compromisos") if al else "Sin compromisos bloqueados ni vencidos al corte."},
        {"title": "Decisiones y apoyos solicitados a Gabinete", "items": [linea_solicitud(modelo, f) for f in so],
         "note": mas(so_r, "solicitud", "solicitudes") if so else "Los equipos no registraron solicitudes de decisión o apoyo."},
        {"title": f"Próximos vencimientos ({fecha_texto(a['cut'])} al {fecha_texto(a['next'])})",
         "items": [linea_proxima(f) for f in pr],
         "note": mas(pr_r, "vencimiento", "vencimientos") if pr else "Sin vencimientos de compromisos abiertos en ese período."},
    ]
    notas = []
    incid = corte.get("incidents") or []
    if corte.get("status") == "en_revision":
        mensajes = list(dict.fromkeys(i["message"] for i in incid if i["level"] == "bloqueante"))
        notas.append("Corte en revisión: " + enumerar(mensajes))
    obs = sum(1 for i in incid if i["level"] == "observacion")
    if obs:
        notas.append(f"El corte registra {plural(obs, 'observación de carga', 'observaciones de carga')}; el detalle completo las identifica por equipo y fila.")
    origen = f"captura del {momento}" if actualizacion else f"corte del viernes {fecha_texto(a['cut'])} a las 12:00"
    notas.append(f"Fuente: planillas de seguimiento de los equipos DEPP, {origen} (hora de Santiago). Un compromiso puede registrar más de un movimiento en el período.")
    return {
        "institution": "SUBSECRETARÍA DE PREVENCIÓN DEL DELITO",
        "kind": "MINUTA",
        "title": "SEGUIMIENTO SEMANAL DE LA DIVISIÓN DE ESTUDIOS Y POLÍTICAS PÚBLICAS (DEPP)",
        "recipient": f"Para: Jefatura DEPP · Actualización del {momento}" if actualizacion else f"Para: Gabinete SPD · Corte del {fecha_texto(a['cut'])}",
        "draft": corte.get("status") == "en_revision" or actualizacion,
        "draftLabel": "AVANCE INTERMEDIO · NO ES EL CORTE SEMANAL" if actualizacion else "BORRADOR · CORTE EN REVISIÓN",
        "full": bool(completo),
        "sections": secciones,
        "notes": notas,
        "summary": s,
    }


def movimientos(modelo, corte):
    a = analizar(modelo, corte)
    salida = []
    for f in a["rows"]:
        if f["receivedNow"]:
            salida.append({"tipo": "Ingreso (registro tardío)" if f["lateEntry"] else "Ingreso", "fila": f, "fecha": f["received"], "cambios": ""})
        if f["deliveredNow"]:
            salida.append({"tipo": "Entrega fuera de plazo" if f["deliveredLate"] else "Entrega", "fila": f, "fecha": f["delivered"], "cambios": ""})
        if f["advancedNow"]:
            salida.append({"tipo": "Cancelación" if f["cancelledNow"] else "Avance", "fila": f, "fecha": "",
                           "cambios": enumerar(ETIQUETAS_CAMBIO[k] for k in f["changed"])})
    orden = {"Entrega": 0, "Entrega fuera de plazo": 0, "Avance": 1, "Cancelación": 1, "Ingreso": 2, "Ingreso (registro tardío)": 2}
    areas = [a_["prefix"] for a_ in modelo["areas"]]
    return _ordenar(salida, lambda x, y: areas.index(x["fila"]["area"]) - areas.index(y["fila"]["area"])
                    or orden[x["tipo"]] - orden[y["tipo"]] or cmp(x["fila"]["id"], y["fila"]["id"]))
