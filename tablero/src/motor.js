/* motor.js · Reglas del corte semanal DEPP.
 * Mismo comportamiento que procesador/depp_corte/motor.py. Las pruebas de paridad
 * (pruebas/test_paridad.py) comparan ambos con los mismos datos.
 * Funciona en el navegador (window.DEPPMotor) y en Node (require).
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.DEPPMotor = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const FORMATO = "DEPP-CORTE-3";
  const FORMATOS_ACEPTADOS = ["DEPP-CORTE-2", "DEPP-CORTE-3"];
  const DIA = 86400000;
  const FECHAS = ["received", "due", "delivered"];
  const CAMPOS_CAMBIO = ["state", "due", "notes", "owner", "product", "request", "requester", "kind", "received", "delivered"];
  const ETIQUETAS_CAMBIO = {
    state: "estado", due: "plazo", notes: "observaciones", owner: "responsable", product: "producto",
    request: "requerimiento", requester: "requirente", kind: "tipo de encargo", received: "fecha de ingreso",
    delivered: "fecha de entrega"
  };
  const CERRADOS = ["Entregado", "Cancelado"];
  // Se comparan sobre texto sin tildes y en minúsculas (ver plegar).
  const PATRON_APOYO = /apoyo (de |del )?gabinete|decision (de |del )?gabinete|gabinete (debe|debera|deberia)|se solicitan? (a |al )gabinete|requiere (una )?decision/;
  const PATRON_DECISION = /decision (de |del )?gabinete|requiere (una )?decision/;
  const DIAS_PROXIMOS = 7;
  const CODIGOS_SIN_DATOS = ["area_sin_datos", "archivo_ausente", "archivo_ilegible", "tabla_ausente", "encabezados_alterados", "pestana_repetida"];

  // ------------------------------------------------------------------ utilidades
  const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
  function plegar(texto) {
    return String(texto ?? "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  }
  function desplazar(dia, n) {
    return new Date(Date.parse(dia + "T00:00:00Z") + n * DIA).toISOString().slice(0, 10);
  }
  function fechaTexto(valor) {
    return valor ? valor.split("-").reverse().join("/") : "";
  }
  function fechaValida(dia) {
    if (typeof dia !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(dia)) return false;
    const ms = Date.parse(dia + "T00:00:00Z");
    return Number.isFinite(ms) && new Date(ms).toISOString().slice(0, 10) === dia;
  }
  function esViernes(dia) {
    return new Date(dia + "T00:00:00Z").getUTCDay() === 5;
  }
  function viernesDeCorte(hoy) {
    // Viernes más reciente (hoy incluido) para una fecha local de Santiago.
    return desplazar(hoy, -((new Date(hoy + "T00:00:00Z").getUTCDay() + 2) % 7));
  }
  const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
  /** «lunes 16/11/2026 a las 09:00» a partir de un turno AAAA-MM-DD_HHMM. */
  function momentoSlot(slot, dia) {
    const d = slot ? slot.slice(0, 10) : dia;
    const nombre = DIAS[new Date(d + "T00:00:00Z").getUTCDay()];
    const hora = slot && /_\d{4}$/.test(slot) ? " a las " + slot.slice(11, 13) + ":" + slot.slice(13, 15) : "";
    return nombre + " " + fechaTexto(d) + hora;
  }
  function plural(n, singular, pluralTxt) {
    return n + " " + (n === 1 ? singular : (pluralTxt || singular + "s"));
  }
  function enumerar(lista) {
    if (lista.length <= 1) return lista.join("");
    return lista.slice(0, -1).join(", ") + " y " + lista[lista.length - 1];
  }
  function cerrarFrase(texto) {
    const t = String(texto ?? "").trim();
    if (!t) return "";
    return /[.!?…]$/.test(t) ? t : t + ".";
  }

  // ------------------------------------------------------------------ fechas de Excel
  function fechaExcel(valor, epoca1904) {
    const v = String(valor ?? "").trim();
    if (!v) return "";
    if (/^\d+(\.\d+)?$/.test(v)) {
      const serial = Math.floor(Number(v));
      if (serial < 0 || serial > 2958465 || (!epoca1904 && serial < 61)) return null;
      return desplazar(epoca1904 ? "1904-01-01" : "1899-12-30", serial);
    }
    const iso = /^(\d{4}-\d{2}-\d{2})(?:[T ].*)?$/.exec(v);
    const local = /^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/.exec(v);
    const normal = iso ? iso[1] : local ? [local[3], local[2].padStart(2, "0"), local[1].padStart(2, "0")].join("-") : "";
    return fechaValida(normal) ? normal : null;
  }

  // ------------------------------------------------------------------ registros
  /** Normaliza una fila (valores A–K en el orden del modelo) y la valida. */
  function registro(modelo, valores, area, linea, epoca1904) {
    const fila = {};
    modelo.fields.forEach(([clave], i) => { fila[clave] = String(valores[i] ?? "").trim(); });
    fila.area = area.prefix;
    const errores = [];
    for (const [clave, etiqueta] of modelo.fields) {
      if (!FECHAS.includes(clave)) continue;
      const f = fechaExcel(fila[clave], epoca1904);
      if (f === null) { errores.push(etiqueta.toLowerCase() + " no válida"); fila[clave] = ""; }
      else fila[clave] = f;
    }
    if (/^\d+\.0+$/.test(fila.number)) fila.number = fila.number.replace(/\.0+$/, "");
    for (const [clave, etiqueta] of modelo.fields.slice(0, 9)) {
      if (!["due", "number"].includes(clave) && !fila[clave]) errores.push("falta " + etiqueta.toLowerCase());
    }
    if (/^[1-9]\d{0,7}$/.test(fila.number)) fila.id = area.prefix + "-" + fila.number.padStart(3, "0");
    else errores.push("N° automático ausente o inválido");
    for (const [clave, opciones, etiqueta] of [["kind", modelo.kinds, "tipo de encargo"],
      ["requester", modelo.requesters, "requirente"], ["state", modelo.states, "estado"]]) {
      if (fila[clave] && !opciones.includes(fila[clave])) errores.push(etiqueta + " fuera de lista");
    }
    if (fila.state === "Entregado" && !fila.delivered) errores.push("falta fecha de entrega efectiva");
    if (fila.state !== "Entregado" && fila.delivered) errores.push("fecha de entrega efectiva sin estado Entregado");
    if (fila.received && fila.delivered && fila.delivered < fila.received) errores.push("entrega anterior al ingreso");
    return { row: fila, errors: errores, line: linea, location: area.tab + ", fila " + linea };
  }

  function serializar(modelo, fila) {
    const out = { area: fila.area };
    for (const [clave] of modelo.fields) out[clave] = fila[clave] ?? "";
    if (fila.held) out.held = true;
    return out;
  }

  function filasDesdeJSON(modelo, filas, contexto) {
    const areas = new Map(modelo.areas.map(a => [a.prefix, a]));
    return filas.map((f, i) => {
      const area = areas.get(f && f.area);
      if (!area) throw new Error("El consolidado " + contexto + " contiene un área no reconocida.");
      const r = registro(modelo, modelo.fields.map(([k]) => f[k]), area, i + 1, false);
      if (r.errors.length) throw new Error("El consolidado " + contexto + " contiene un registro inválido (" + (r.row.id || "sin N°") + ": " + r.errors.join(", ") + ").");
      if (f.held) r.row.held = true;
      return r.row;
    });
  }

  // ------------------------------------------------------------------ construcción del corte
  /**
   * Arma el consolidado de un corte.
   * lectura: {entries:[registro()], coverage:[prefijos], problems:[{area, code, message}]}
   * anterior: consolidado válido previo o null.  captura: metadatos opcionales.
   */
  function construirCorte(modelo, lectura, cut, anterior, captura, opciones) {
    const op = opciones || {};
    const actualizacion = op.kind === "actualizacion";
    if (!fechaValida(cut)) throw new Error("Fecha de corte inválida.");
    if (anterior && (actualizacion ? anterior.cut > cut : anterior.cut >= cut)) throw new Error("El corte anterior debe ser previo a la fecha de corte.");
    const incidencias = [];
    const agregar = (nivel, codigo, area, mensaje) => incidencias.push({ level: nivel, code: codigo, area: area || "", message: mensaje });
    for (const p of lectura.problems || []) agregar("bloqueante", p.code, p.area, p.message);

    const previas = anterior ? anterior.rows : null;
    const mapaPrevio = new Map((previas || []).map(f => [f.area + "-" + String(f.number).padStart(3, "0"), f]));
    const conteo = new Map();
    for (const e of lectura.entries) if (e.row.id) conteo.set(e.row.id, (conteo.get(e.row.id) || 0) + 1);

    const validas = [];
    const rechazadas = [];
    const idsVistos = new Set();
    const duplicadosAvisados = new Set();
    for (const e of lectura.entries) {
      const errores = e.errors.slice();
      const fila = e.row;
      if (fila.received && fila.received > cut) errores.push("fecha de ingreso posterior al corte");
      if (fila.delivered && fila.delivered > cut) errores.push("fecha de entrega posterior al corte");
      if (fila.id && conteo.get(fila.id) > 1) {
        errores.push("N° duplicado");
        if (!duplicadosAvisados.has(fila.id)) {
          duplicadosAvisados.add(fila.id);
          agregar("bloqueante", "numero_duplicado", fila.area, "El N° " + fila.id + " aparece en " + conteo.get(fila.id) + " filas.");
        }
      }
      if (fila.id) idsVistos.add(fila.id);
      if (errores.length) {
        rechazadas.push({ area: fila.area, number: fila.number || "", line: e.line, location: e.location, errors: errores });
      } else {
        validas.push(fila);
      }
    }
    // Filas con error que ya existían: se conserva la versión del corte anterior.
    const retenidas = [];
    const idsValidos = new Set(validas.map(f => f.id));
    for (const r of rechazadas) {
      const id = /^[1-9]\d{0,7}$/.test(r.number) ? r.area + "-" + r.number.padStart(3, "0") : "";
      const previa = id && mapaPrevio.get(id);
      if (previa && !idsValidos.has(id) && !retenidas.some(f => f.id === id)) {
        retenidas.push(Object.assign({}, previa, { id: id, held: true }));
        agregar("observacion", "registro_con_error", r.area, r.location + " (" + id + "): " + r.errors.join(", ") + ". Se mantiene la versión del corte anterior.");
      } else {
        agregar("observacion", "fila_excluida", r.area, r.location + (id ? " (" + id + ")" : "") + ": " + r.errors.join(", ") + ".");
      }
    }
    // Identidad del N°: si cambian a la vez fecha de ingreso y requerimiento, probablemente se reutilizó la fila.
    for (const f of validas) {
      const previa = mapaPrevio.get(f.id);
      if (previa && previa.received !== f.received && previa.request !== f.request) {
        agregar("bloqueante", "posible_reutilizacion", f.area, "El N° " + f.id + " cambió fecha de ingreso y requerimiento respecto del corte anterior. Verifica si la fila se usó para otro encargo.");
      }
    }
    const cobertura = new Set(lectura.coverage);
    for (const area of modelo.areas) {
      if (!cobertura.has(area.prefix) && !incidencias.some(i => i.area === area.prefix && i.level === "bloqueante")) agregar("bloqueante", "area_sin_datos", area.prefix, "No se pudo leer la pestaña «" + area.tab + "».");
    }
    if (previas) {
      for (const [id, f] of mapaPrevio) {
        if (cobertura.has(f.area) && !idsVistos.has(id)) {
          agregar("bloqueante", "registro_eliminado", f.area, "El registro " + id + " estaba en el corte anterior y ya no aparece en el Excel.");
        }
      }
    }
    if (captura && captura.late && !captura.verified) {
      agregar("bloqueante", "captura_demorada", "", "La captura se realizó a las " + (captura.capturedAtLocal || "?") + " y no se pudo verificar la versión de la hora programada.");
    }
    const filas = validas.concat(retenidas).sort((a, b) =>
      modelo.areas.findIndex(x => x.prefix === a.area) - modelo.areas.findIndex(x => x.prefix === b.area) || Number(a.number) - Number(b.number));
    const bloqueantes = incidencias.filter(i => i.level === "bloqueante").length;
    const corte = {
      format: FORMATO,
      from: anterior ? anterior.cut : desplazar(cut, -7),
      cut: cut,
      previousCut: anterior ? anterior.cut : null,
      status: bloqueantes ? "en_revision" : incidencias.length ? "valido_con_observaciones" : "valido",
      previousRows: previas ? previas.map(f => serializar(modelo, f)) : null,
      rows: filas.map(f => serializar(modelo, f)),
      rejected: rechazadas,
      incidents: incidencias
    };
    if (op.kind) corte.kind = op.kind;
    if (op.slot) corte.slot = op.slot;
    if (captura && captura.capturedAt) corte.capturedAt = captura.capturedAt;
    corte.summary = analizar(modelo, corte).summary;
    return corte;
  }

  /** Valida y normaliza un consolidado leído desde JSON. */
  function leerCorte(modelo, datos) {
    if (!datos || !FORMATOS_ACEPTADOS.includes(datos.format) || !fechaValida(datos.cut) || !fechaValida(datos.from)
      || datos.from > datos.cut || !Array.isArray(datos.rows)
      || (datos.previousRows !== null && datos.previousRows !== undefined && !Array.isArray(datos.previousRows))) {
      throw new Error("El archivo no corresponde a un consolidado DEPP compatible.");
    }
    const filas = filasDesdeJSON(modelo, datos.rows, "actual");
    const previas = Array.isArray(datos.previousRows) ? filasDesdeJSON(modelo, datos.previousRows, "anterior") : null;
    const ids = new Set();
    for (const f of filas) {
      if (ids.has(f.id)) throw new Error("El consolidado contiene el N° " + f.id + " repetido.");
      ids.add(f.id);
      if (f.received > datos.cut || (f.delivered && f.delivered > datos.cut)) throw new Error("El consolidado contiene fechas posteriores al corte (" + f.id + ").");
    }
    return {
      format: datos.format,
      from: datos.from,
      cut: datos.cut,
      previousCut: datos.previousCut ?? (previas ? datos.from : null),
      status: datos.status || "valido",
      previousRows: previas,
      rows: filas,
      rejected: datos.rejected || [],
      incidents: datos.incidents || [],
      summary: datos.summary || null,
      approval: datos.approval || null,
      kind: datos.kind || "semanal",
      slot: datos.slot || null,
      capturedAt: datos.capturedAt || null
    };
  }

  // ------------------------------------------------------------------ análisis del período
  function analizar(modelo, corte) {
    const cut = corte.cut;
    const from = corte.from;
    const comparando = Array.isArray(corte.previousRows);
    const idDe = f => f.id || (f.area + "-" + String(f.number).padStart(3, "0"));
    const mapaPrevio = new Map((corte.previousRows || []).map(f => [idDe(f), f]));
    const proximo = desplazar(cut, DIAS_PROXIMOS);
    const filas = corte.rows.map(original => {
      const f = Object.assign({}, original, { id: idDe(original) });
      const previa = mapaPrevio.get(f.id);
      const activo = !CERRADOS.includes(f.state);
      const notas = plegar(f.notes);
      const apoyo = activo && PATRON_APOYO.test(notas);
      const decision = apoyo && PATRON_DECISION.test(notas);
      const vencido = Boolean(activo && f.due && f.due < cut);
      let ingreso, entrega, cambios = [];
      if (comparando) {
        ingreso = !previa;
        entrega = f.state === "Entregado" && (!previa || previa.state !== "Entregado");
        if (previa) cambios = CAMPOS_CAMBIO.filter(k => (previa[k] ?? "") !== (f[k] ?? ""));
      } else {
        ingreso = Boolean(f.received && f.received >= from && f.received <= cut);
        entrega = Boolean(f.state === "Entregado" && f.delivered >= from && f.delivered <= cut);
      }
      const avance = Boolean(previa) && !entrega && cambios.length > 0;
      return Object.assign(f, {
        active: activo,
        late: vencido,
        blocked: f.state === "Bloqueado",
        support: apoyo,
        decision: decision,
        attention: vencido || f.state === "Bloqueado" || apoyo,
        upcoming: Boolean(activo && f.due && f.due >= cut && f.due <= proximo),
        undated: activo && !f.due,
        receivedNow: ingreso,
        lateEntry: comparando && ingreso && f.received < from,
        deliveredNow: entrega,
        deliveredLate: entrega && Boolean(f.due) && f.delivered > f.due,
        advancedNow: avance,
        cancelledNow: avance && f.state === "Cancelado" && cambios.includes("state"),
        changed: cambios,
        movement: ingreso || entrega || avance,
        held: Boolean(original.held)
      });
    });
    const contar = (lista, k) => lista.filter(f => f[k]).length;
    const resumenDe = lista => ({
      registros: lista.length,
      ingresos: contar(lista, "receivedNow"),
      ingresosTardios: contar(lista, "lateEntry"),
      entregas: contar(lista, "deliveredNow"),
      entregasFueraPlazo: contar(lista, "deliveredLate"),
      avances: contar(lista, "advancedNow"),
      cancelados: contar(lista, "cancelledNow"),
      abiertos: contar(lista, "active"),
      vencidos: contar(lista, "late"),
      bloqueados: lista.filter(f => f.active && f.blocked).length,
      apoyos: contar(lista, "support"),
      decisiones: contar(lista, "decision"),
      atencion: contar(lista, "attention"),
      proximos: contar(lista, "upcoming"),
      sinPlazo: contar(lista, "undated")
    });
    const resumen = resumenDe(filas);
    resumen.porArea = {};
    for (const area of modelo.areas) resumen.porArea[area.prefix] = resumenDe(filas.filter(f => f.area === area.prefix));
    return { rows: filas, summary: resumen, from: from, cut: cut, next: proximo, comparing: comparando };
  }

  // ------------------------------------------------------------------ minuta (modelo común)
  const ordenPlazo = (a, b) => cmp((a.due || "9999-99-99"), b.due || "9999-99-99") || cmp(a.id, b.id);

  function lineaMovimiento(f) {
    let texto;
    if (f.deliveredNow) {
      texto = "Entregado el " + fechaTexto(f.delivered) + " a " + f.requester + ".";
      if (f.deliveredLate) texto += " Fuera de plazo (plazo " + fechaTexto(f.due) + ").";
      if (f.receivedNow) texto += " Ingresó en el período.";
    } else if (f.advancedNow) {
      texto = f.state + ". Actualizó " + enumerar(f.changed.map(k => ETIQUETAS_CAMBIO[k])) + ".";
      if (f.changed.includes("due") && f.due) texto += " Nuevo plazo: " + fechaTexto(f.due) + ".";
    } else {
      texto = "Ingresó el " + fechaTexto(f.received) + " (" + f.kind + ", " + f.requester + "). Estado: " + f.state + ".";
      if (f.lateEntry) texto += " Registro tardío.";
      if (f.due) texto += " Plazo: " + fechaTexto(f.due) + ".";
    }
    const notas = cerrarFrase(f.notes);
    return { ref: f.id, lead: f.product + ".", text: texto + (notas ? " " + notas : "") };
  }

  function lineaAlerta(modelo, f) {
    const area = modelo.areas.find(a => a.prefix === f.area);
    const marcas = [];
    if (f.blocked) marcas.push("Bloqueado");
    if (f.late) marcas.push("Vencido desde el " + fechaTexto(f.due));
    const notas = cerrarFrase(f.notes);
    return { ref: f.id, lead: f.product + ".", text: marcas.join(". ") + ". " + f.owner + ", " + area.name + "." + (notas ? " " + notas : "") };
  }

  function lineaSolicitud(modelo, f) {
    const area = modelo.areas.find(a => a.prefix === f.area);
    return { ref: f.id, lead: (f.decision ? "Decisión" : "Apoyo") + " · " + f.product + ".",
      text: cerrarFrase(f.notes) + " Responsable: " + f.owner + ", " + area.name + "." + (f.due ? " Plazo: " + fechaTexto(f.due) + "." : "") };
  }

  function lineaProxima(f) {
    return { ref: f.id, lead: fechaTexto(f.due) + ".", text: f.product + " · " + f.owner + " · " + f.requester + (f.state !== "Pendiente" && f.state !== "En curso" ? " · " + f.state : "") + "." };
  }

  function recortar(lista, limite) {
    if (lista.length <= limite) return { items: lista, rest: 0 };
    return { items: lista.slice(0, limite), rest: lista.length - limite };
  }

  /**
   * Devuelve la minuta como estructura neutra. El tablero la dibuja en HTML y en Word;
   * el procesador la escribe en Word con el mismo contenido.
   * completo = true incluye todos los movimientos (detalle completo).
   */
  function minuta(modelo, corte, completo) {
    const a = analizar(modelo, corte);
    const s = a.summary;
    const actualizacion = corte.kind === "actualizacion";
    const momento = momentoSlot(corte.slot, a.cut);
    const periodo = actualizacion
      ? "Avance desde el corte del viernes " + fechaTexto(a.from) + " a las 12:00 hasta el " + momento + ". Es una actualización intermedia; la minuta oficial usa el corte del viernes a las 12:00."
      : a.comparing
      ? "Del viernes " + fechaTexto(a.from) + " a las 12:00 al viernes " + fechaTexto(a.cut) + " a las 12:00."
      : "Corte inicial al viernes " + fechaTexto(a.cut) + " a las 12:00. Considera ingresos y entregas desde el " + fechaTexto(a.from) + " y fija la línea base para comparar el corte siguiente.";
    const resumen = [
      "En el período se registraron " + plural(s.ingresos, "ingreso") + " y " + plural(s.entregas, "entrega")
        + (s.entregasFueraPlazo ? " (" + s.entregasFueraPlazo + " fuera de plazo)" : "")
        + (a.comparing ? ", y " + plural(s.avances, "compromiso tuvo avance", "compromisos tuvieron avance") : "") + ".",
      "Al corte hay " + plural(s.abiertos, "compromiso abierto", "compromisos abiertos") + ": "
        + plural(s.vencidos, "vencido") + ", " + plural(s.bloqueados, "bloqueado") + " y "
        + plural(s.apoyos, "con solicitud a Gabinete", "con solicitudes a Gabinete") + ".",
      (s.proximos ? "Vencen " + plural(s.proximos, "compromiso") : "No vencen compromisos") + " entre el " + fechaTexto(a.cut) + " y el " + fechaTexto(a.next) + "."
    ].join(" ");

    const equipos = [];
    for (const area of modelo.areas) {
      const propios = a.rows.filter(f => f.area === area.prefix && f.movement);
      const destacados = propios.filter(f => f.deliveredNow || f.advancedNow).sort((x, y) =>
        Number(y.deliveredNow) - Number(x.deliveredNow) || cmp((y.delivered || ""), x.delivered || "") || cmp(x.id, y.id));
      const ingresos = propios.filter(f => !f.deliveredNow && !f.advancedNow).sort((x, y) => cmp(y.received, x.received) || cmp(x.id, y.id));
      const r = area.prefix;
      const sa = s.porArea[r];
      let lista;
      let nota = "";
      if (completo) {
        lista = destacados.concat(ingresos);
      } else {
        const corte3 = recortar(destacados, 3);
        lista = corte3.items;
        const omitidos = corte3.rest;
        const ingresosResumen = ingresos.length;
        const partes = [];
        if (omitidos) partes.push(plural(omitidos, "entrega o avance adicional", "entregas o avances adicionales"));
        if (ingresosResumen) partes.push(plural(ingresosResumen, "ingreso nuevo", "ingresos nuevos"));
        if (partes.length) nota = "Además: " + enumerar(partes) + " (ver detalle completo).";
        if (!lista.length && ingresosResumen) { lista = recortar(ingresos, 2).items; nota = ingresosResumen > 2 ? "Además: " + plural(ingresosResumen - 2, "ingreso nuevo", "ingresos nuevos") + " (ver detalle completo)." : ""; }
      }
      const vacio = (corte.incidents || []).some(i => CODIGOS_SIN_DATOS.includes(i.code) && i.area === r)
        ? "Planilla del equipo no disponible en este corte."
        : "Sin movimientos registrados en el período.";
      equipos.push({
        title: area.name,
        counts: plural(sa.entregas, "entrega") + " · " + plural(sa.avances, "avance") + " · " + plural(sa.ingresos, "ingreso") + " · " + plural(sa.abiertos, "abierto"),
        items: lista.map(lineaMovimiento),
        note: lista.length ? nota : vacio
      });
    }
    const alertas = a.rows.filter(f => f.active && (f.blocked || f.late)).sort((x, y) =>
      Number(y.blocked) - Number(x.blocked) || ordenPlazo(x, y));
    const solicitudes = a.rows.filter(f => f.support).sort((x, y) => Number(y.decision) - Number(x.decision) || ordenPlazo(x, y));
    const proximos = a.rows.filter(f => f.upcoming).sort(ordenPlazo);
    const rAl = recortar(alertas, completo ? Infinity : 6);
    const rSo = recortar(solicitudes, completo ? Infinity : 6);
    const rPr = recortar(proximos, completo ? Infinity : 6);
    const mas = (n, sing, pl) => n ? "Además: " + plural(n, sing, pl) + " (ver detalle completo)." : "";
    const secciones = [
      { title: "Período y resumen", paragraphs: [periodo, resumen] },
      { title: "Principales entregas y avances por equipo", groups: equipos },
      { title: "Bloqueos y atrasos", items: rAl.items.map(f => lineaAlerta(modelo, f)), note: rAl.items.length ? mas(rAl.rest, "compromiso", "compromisos") : "Sin compromisos bloqueados ni vencidos al corte." },
      { title: "Decisiones y apoyos solicitados a Gabinete", items: rSo.items.map(f => lineaSolicitud(modelo, f)), note: rSo.items.length ? mas(rSo.rest, "solicitud", "solicitudes") : "Los equipos no registraron solicitudes de decisión o apoyo." },
      { title: "Próximos vencimientos (" + fechaTexto(a.cut) + " al " + fechaTexto(a.next) + ")", items: rPr.items.map(lineaProxima), note: rPr.items.length ? mas(rPr.rest, "vencimiento", "vencimientos") : "Sin vencimientos de compromisos abiertos en ese período." }
    ];
    const notas = [];
    if (corte.status === "en_revision") notas.push("Corte en revisión: " + enumerar([...new Set((corte.incidents || []).filter(i => i.level === "bloqueante").map(i => i.message))]));
    const obs = (corte.incidents || []).filter(i => i.level === "observacion").length;
    if (obs) notas.push("El corte registra " + plural(obs, "observación de carga", "observaciones de carga") + "; el detalle completo las identifica por equipo y fila.");
    notas.push("Fuente: planillas de seguimiento de los equipos DEPP, " + (actualizacion ? "captura del " + momento : "corte del viernes " + fechaTexto(a.cut) + " a las 12:00") + " (hora de Santiago). Un compromiso puede registrar más de un movimiento en el período.");
    return {
      institution: "SUBSECRETARÍA DE PREVENCIÓN DEL DELITO",
      kind: "MINUTA",
      title: "SEGUIMIENTO SEMANAL DE LA DIVISIÓN DE ESTUDIOS Y POLÍTICAS PÚBLICAS (DEPP)",
      recipient: actualizacion ? "Para: Jefatura DEPP · Actualización del " + momento : "Para: Gabinete SPD · Corte del " + fechaTexto(a.cut),
      draft: corte.status === "en_revision" || actualizacion,
      draftLabel: actualizacion ? "AVANCE INTERMEDIO · NO ES EL CORTE SEMANAL" : "BORRADOR · CORTE EN REVISIÓN",
      full: Boolean(completo),
      sections: secciones,
      notes: notas,
      summary: s
    };
  }

  /** Lista de movimientos para el detalle completo (una fila por movimiento). */
  function movimientos(modelo, corte) {
    const a = analizar(modelo, corte);
    const salida = [];
    for (const f of a.rows) {
      if (f.receivedNow) salida.push({ tipo: f.lateEntry ? "Ingreso (registro tardío)" : "Ingreso", fila: f, fecha: f.received, cambios: "" });
      if (f.deliveredNow) salida.push({ tipo: f.deliveredLate ? "Entrega fuera de plazo" : "Entrega", fila: f, fecha: f.delivered, cambios: "" });
      if (f.advancedNow) salida.push({ tipo: f.cancelledNow ? "Cancelación" : "Avance", fila: f, fecha: "", cambios: enumerar(f.changed.map(k => ETIQUETAS_CAMBIO[k])) });
    }
    const orden = { "Entrega": 0, "Entrega fuera de plazo": 0, "Avance": 1, "Cancelación": 1, "Ingreso": 2, "Ingreso (registro tardío)": 2 };
    salida.sort((x, y) => modelo.areas.findIndex(z => z.prefix === x.fila.area) - modelo.areas.findIndex(z => z.prefix === y.fila.area)
      || orden[x.tipo] - orden[y.tipo] || cmp(x.fila.id, y.fila.id));
    return salida;
  }

  return {
    FORMATO, FORMATOS_ACEPTADOS, CAMPOS_CAMBIO, ETIQUETAS_CAMBIO, DIAS_PROXIMOS,
    plegar, desplazar, fechaTexto, momentoSlot, fechaValida, fechaExcel, esViernes, viernesDeCorte, plural, enumerar,
    registro, serializar, construirCorte, leerCorte, analizar, minuta, movimientos
  };
});
