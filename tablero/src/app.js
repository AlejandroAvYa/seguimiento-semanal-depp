/* app.js · Interfaz del tablero de seguimiento semanal DEPP. */
(function () {
  "use strict";
  const M = DEPPMotor;
  const modelo = JSON.parse(document.getElementById("modelo").textContent);
  const embebidos = JSON.parse(document.getElementById("datos-cortes").textContent);
  const $ = id => document.getElementById(id);
  const AREAS = new Map(modelo.areas.map(a => [a.prefix, a]));
  const ESTADOS_TXT = { valido: "Válido", valido_con_observaciones: "Válido con observaciones", en_revision: "En revisión", manual: "Carga manual sin publicar" };
  const VISTAS = {
    resumen: ["Resumen", "Qué se entregó, qué avanzó y qué requiere atención"],
    compromisos: ["Compromisos", "Todos los compromisos de los equipos. Haz clic en una fila para ver su ficha"],
    minuta: ["Minuta semanal", "Documento para Gabinete SPD, armado con los mismos datos del tablero"],
    calidad: ["Estado de los datos", "Capturas recibidas, avisos e historial de cortes"]
  };
  const FILTROS_VACIOS = { area: "", state: "", requester: "", view: "all", q: "" };

  const st = {
    raw: {},          // corte → consolidado tal como se publicó o se cargó
    norm: {},         // corte → consolidado validado
    manual: new Set(),
    index: null,
    origin: null,     // procesador | demo | http | manual
    cut: null,
    view: "resumen",
    filters: Object.assign({}, FILTROS_VACIOS),
    full: false,
    cache: {}
  };

  // ------------------------------------------------------------------ utilidades
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const ft = M.fechaTexto;
  const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
  const fechaLarga = d => { const [y, m, dd] = d.split("-").map(Number); return dd + " de " + MESES[m - 1] + " de " + y; };
  const diasEntre = (a, b) => Math.round((Date.parse(b + "T00:00:00Z") - Date.parse(a + "T00:00:00Z")) / 86400000);
  const claseEstado = s => "b-" + String(s).replace(/ /g, "-");
  const PARAMS = new URLSearchParams(location.search);
  function hoySantiago() {
    const fijo = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})$/.exec(PARAMS.get("ahora") || "");
    if (fijo) return { dia: fijo[1], hora: Number(fijo[2]) * 60 + Number(fijo[3]) };
    const p = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Santiago", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date());
    const g = n => p.find(x => x.type === n).value;
    return { dia: g("year") + "-" + g("month") + "-" + g("day"), hora: Number(g("hour")) * 60 + Number(g("minute")) };
  }
  function corteEsperado() {
    const h = hoySantiago();
    let v = M.viernesDeCorte(h.dia);
    if (v === h.dia && h.hora < 12 * 60 + 45) v = M.desplazar(v, -7);
    return v;
  }
  function momentoTexto(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    const p = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Santiago", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(d);
    const g = n => p.find(x => x.type === n).value;
    return g("day") + "/" + g("month") + "/" + g("year") + " " + g("hour") + ":" + g("minute");
  }
  function descargar(blob, nombre) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = nombre; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }
  function analisis() {
    if (!st.cut) return null;
    if (!st.cache[st.cut]) st.cache[st.cut] = M.analizar(modelo, st.norm[st.cut]);
    return st.cache[st.cut];
  }
  // Cada corte se identifica por su turno AAAA-MM-DD_HHMM (el corte semanal es el del viernes a las 12:00).
  const claveDe = c => c.slot || (c.cut + "_1200");
  const fechaClave = k => k.slice(0, 10);
  const esIntermedio = k => Boolean(st.norm[k] && st.norm[k].kind === "actualizacion");
  function etiquetaClave(k) {
    return esIntermedio(k) ? "Actualización · " + M.momentoSlot(k) : "Corte semanal · vie " + ft(fechaClave(k)) + " 12:00";
  }
  function estadoDe(k) { return st.manual.has(k) ? "manual" : (st.norm[k]?.status || "valido"); }
  function cortesOrdenados() { return Object.keys(st.norm).sort(); }

  // ------------------------------------------------------------------ carga de datos
  function agregarCorte(raw, manual) {
    const norm = M.leerCorte(modelo, raw);
    const k = claveDe(norm);
    st.raw[k] = raw;
    st.norm[k] = norm;
    delete st.cache[k];
    if (manual) st.manual.add(k); else st.manual.delete(k);
    return k;
  }
  function cargarEmbebidos(datos) {
    st.index = datos.index || null;
    st.origin = datos.origin || "procesador";
    for (const raw of Object.values(datos.cuts || {})) {
      try { agregarCorte(raw, false); } catch (e) { console.warn(e); }
    }
    const ultimoValido = st.index && st.index.lastValid ? st.index.lastValid + "_1200" : null;
    st.cut = ultimoValido && st.norm[ultimoValido] ? ultimoValido : cortesOrdenados().slice(-1)[0] || null;
  }
  async function cargarRemoto() {
    // Tablero publicado junto a las salidas (servidor institucional con autenticación).
    try {
      const r = await fetch("indice.json", { cache: "no-store", credentials: "same-origin" });
      if (!r.ok) return false;
      const indice = await r.json();
      const cortes = {};
      await Promise.all(indice.cuts.map(async c => {
        const rc = await fetch(c.files.corte, { cache: "no-store", credentials: "same-origin" });
        if (rc.ok) cortes[c.cut] = await rc.json();
      }));
      cargarEmbebidos({ index: indice, cuts: cortes, origin: "http" });
      return true;
    } catch (e) { return false; }
  }

  // ------------------------------------------------------------------ carpeta de capturas en OneDrive
  const RE_TURNO = /^(\d{4}-\d{2}-\d{2})_(\d{4})$/;
  const idb = {
    abrir: () => new Promise((ok, mal) => {
      const r = indexedDB.open("depp-seguimiento", 1);
      r.onupgradeneeded = () => r.result.createObjectStore("kv");
      r.onsuccess = () => ok(r.result);
      r.onerror = () => mal(r.error);
    }),
    async get(k) {
      try {
        const db = await idb.abrir();
        return await new Promise(ok => { const t = db.transaction("kv").objectStore("kv").get(k); t.onsuccess = () => ok(t.result || null); t.onerror = () => ok(null); });
      } catch (e) { return null; }
    },
    async set(k, v) {
      try {
        const db = await idb.abrir();
        await new Promise(ok => { const t = db.transaction("kv", "readwrite").objectStore("kv").put(v, k); t.onsuccess = ok; t.onerror = ok; });
      } catch (e) { /* sin almacenamiento: se vuelve a elegir la carpeta */ }
    }
  };
  async function entradasDesdeHandle(handle) {
    let raiz = handle;
    try { raiz = await handle.getDirectoryHandle("Capturas"); } catch (e) { /* se eligió Capturas directamente */ }
    const salida = [];
    const leerTurno = async (nombre, h) => {
      for await (const [archivo, h2] of h.entries()) if (h2.kind === "file") salida.push({ turno: nombre, nombre: archivo, file: () => h2.getFile() });
    };
    if (RE_TURNO.test(raiz.name)) await leerTurno(raiz.name, raiz);
    else for await (const [nombre, h] of raiz.entries()) if (h.kind === "directory" && RE_TURNO.test(nombre)) await leerTurno(nombre, h);
    return salida;
  }
  function entradasDesdeLista(archivos) {
    return archivos.map(f => {
      const partes = (f.webkitRelativePath || f.name).split("/");
      return { turno: partes[partes.length - 2] || "", nombre: partes[partes.length - 1], file: async () => f };
    }).filter(e => RE_TURNO.test(e.turno));
  }
  function metaCaptura(meta) {
    if (!meta || !meta.capturedAt) return { capturedAt: null, late: false, verified: false };
    const cap = Date.parse(meta.capturedAt);
    const prog = meta.scheduledAt ? Date.parse(meta.scheduledAt) : NaN;
    return { capturedAt: meta.capturedAt, capturedAtLocal: momentoTexto(meta.capturedAt), late: isFinite(prog) && cap - prog > 30 * 60000, verified: Boolean(meta.verified) };
  }
  async function construirTurno(entradas, turno, anterior, kind) {
    const xlsx = [];
    let meta = null;
    for (const e of entradas) {
      if (/\.xlsx$/i.test(e.nombre) && !e.nombre.startsWith("~$")) {
        const f = await conLimite(e.file(), 30000, turno + "/" + e.nombre);
        await conLimite(f.slice(0, 4).arrayBuffer(), 30000, turno + "/" + e.nombre);
        xlsx.push(f);
      } else if (e.nombre === "captura.json") {
        try { meta = JSON.parse(await (await conLimite(e.file(), 30000, turno + "/captura.json")).text()); } catch (err) { meta = null; }
      }
    }
    const conocidos = xlsx.filter(f => modelo.books.some(b => b.file === f.name));
    const lectura = conocidos.length ? await DEPPLectorXlsx.leerArchivos(modelo, M, conocidos) : { entries: [], coverage: [], problems: [], files: [] };
    for (const libro of modelo.books) {
      if (!conocidos.some(f => f.name === libro.file)) {
        for (const p of libro.prefixes) lectura.problems.push({ code: "archivo_ausente", area: p, message: "Falta " + libro.file + " en la captura " + turno + "." });
      }
    }
    return M.construirCorte(modelo, lectura, fechaClave(turno), anterior, metaCaptura(meta), { kind: kind, slot: turno });
  }
  async function procesarCapturas(entradas, nombreCarpeta) {
    const porTurno = {};
    for (const e of entradas) (porTurno[e.turno] = porTurno[e.turno] || []).push(e);
    const turnos = Object.keys(porTurno).sort();
    if (!turnos.length) throw new Error("No encontré capturas en esa carpeta. Debe ser DEPP_Seguimiento (o su subcarpeta Capturas), que contiene carpetas con nombres como 2026-11-13_1700.");
    const semanales = turnos.filter(t => t.endsWith("_1200") && M.esViernes(fechaClave(t)));
    const ultimoSemanal = semanales[semanales.length - 1] || "";
    const intermedios = turnos.filter(t => !semanales.includes(t) && t > ultimoSemanal);
    st.raw = {}; st.norm = {}; st.cache = {}; st.manual = new Set(); st.index = null;
    st.origin = "carpeta";
    const errores = [];
    let anterior = null;
    let n = 0;
    const total = semanales.length + (intermedios.length ? 1 : 0);
    for (const t of semanales) {
      estadoCarpeta("Leyendo captura " + (++n) + " de " + total + " (" + M.momentoSlot(t) + ")…");
      try {
        const corte = await construirTurno(porTurno[t], t, anterior, "semanal");
        const k = agregarCorte(corte, false);
        if (corte.status !== "en_revision") anterior = st.norm[k];
      } catch (e) { errores.push(t + ": " + e.message); }
    }
    const ultimoIntermedio = intermedios[intermedios.length - 1];
    if (ultimoIntermedio) {
      estadoCarpeta("Leyendo captura " + (++n) + " de " + total + " (" + M.momentoSlot(ultimoIntermedio) + ")…");
      try { agregarCorte(await construirTurno(porTurno[ultimoIntermedio], ultimoIntermedio, anterior, "actualizacion"), false); }
      catch (e) { errores.push(ultimoIntermedio + ": " + e.message); }
    }
    const previo = st.cutPrevio;
    st.cutPrevio = null;
    st.carpeta = { nombre: nombreCarpeta || "", turnos: turnos, leidaEn: new Date().toISOString(), errores: errores };
    const ultimo = cortesOrdenados().slice(-1)[0] || null;
    // Al refrescar se mantiene la vista; si se miraba la última captura, se pasa a la nueva.
    st.cut = previo && st.norm[previo] && !esIntermedio(previo) ? previo : ultimo;
    render();
  }
  async function leerHandle(handle) {
    estadoCarpeta("Buscando capturas en «" + handle.name + "»…");
    try {
      const entradas = await conLimite(entradasDesdeHandle(handle), 60000, handle.name);
      estadoCarpeta("Encontré " + M.plural(new Set(entradas.map(e => e.turno)).size, "captura") + " en «" + handle.name + "». Procesando…");
      await procesarCapturas(entradas, handle.name);
    } catch (e) {
      console.error(e);
      estadoCarpeta("No se pudo leer la carpeta «" + handle.name + "»: " + e.message, "bad");
    }
  }
  function estadoCarpeta(texto, tipo) {
    const el = $("folder-status");
    if (el) el.textContent = texto;
    const b = $("banners");
    if (texto) b.innerHTML = '<div class="banner ' + (tipo || "info") + '">' + esc(texto) + "</div>";
  }
  /** Espera un archivo con un tiempo límite: en OneDrive un archivo «solo en la nube» puede tardar en descargarse. */
  function conLimite(promesa, ms, nombre) {
    return Promise.race([promesa, new Promise((_, mal) => setTimeout(() => mal(new Error(
      "No se pudo leer «" + nombre + "» en " + Math.round(ms / 1000) + " segundos. En el Explorador de Windows haz clic derecho sobre la carpeta Capturas › «Mantener siempre en este dispositivo» y vuelve a intentarlo.")), ms))]);
  }
  async function conectarCarpeta() {
    if (!window.showDirectoryPicker) { $("file-dir").click(); return; }
    let h;
    try {
      h = await window.showDirectoryPicker({ id: "depp-seguimiento", mode: "read" });
    } catch (e) {
      const detalle = " [Detalle técnico: " + e.name + " · " + (e.message || "sin mensaje") + " · " + navigator.userAgent.replace(/^.*(Edg|Chrome)\/(\d+).*$/, "$1 $2") + "]";
      estadoCarpeta((e.name === "AbortError"
        ? "No se recibió la carpeta. Si el navegador preguntó si permites ver los archivos, hay que aceptar «Ver archivos» (View files). Vuelve a pulsar «Conectar carpeta de OneDrive»."
        : "El navegador no permitió abrir la carpeta: " + e.message + " Prueba con «Elegir carpeta (método alternativo)».") + detalle, "warn");
      return;
    }
    await idb.set("carpeta", h);
    await leerHandle(h);
  }
  async function actualizarCarpeta() {
    const h = await idb.get("carpeta");
    if (!h || !h.queryPermission) { conectarCarpeta(); return; }
    let permiso = await h.queryPermission({ mode: "read" });
    if (permiso !== "granted") permiso = await h.requestPermission({ mode: "read" });
    if (permiso === "granted") await leerHandle(h);
  }
  // ------------------------------------------------------------------ carga automática (tablero dentro de Capturas)
  /** Turnos que pudo dejar el flujo: viernes 12:00 de las últimas 26 semanas y todos los turnos de los últimos 8 días. */
  const HORAS_CAPTURA = ["0800", "0900", "1000", "1100", "1200", "1300", "1400", "1500", "1600", "1700", "1800", "1900"];
  function turnosCandidatos() {
    const h = hoySantiago();
    const salida = new Set();
    for (let i = 0; i <= 26 * 7; i++) {
      const dia = M.desplazar(h.dia, -i);
      const ds = new Date(dia + "T00:00:00Z").getUTCDay();
      if (ds === 0 || ds === 6) continue;
      const horas = i <= 8 ? HORAS_CAPTURA : (ds === 5 ? ["1200"] : []);
      for (const hh of horas) {
        if (i === 0 && Number(hh.slice(0, 2)) * 60 + Number(hh.slice(2)) > h.hora) continue;
        salida.add(dia + "_" + hh);
      }
    }
    for (const extra of (PARAMS.get("prueba") || "").split(",")) if (RE_TURNO.test(extra)) salida.add(extra);
    return Array.from(salida).sort();
  }
  function cargarScript(ruta) {
    return new Promise(ok => {
      const el = document.createElement("script");
      el.src = ruta;
      el.onload = () => { el.remove(); ok(true); };
      el.onerror = () => { el.remove(); ok(false); };
      document.head.appendChild(el);
    });
  }
  function base64ABytes(b64) {
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  /** Lee los datos.js que deja el flujo junto a cada captura. Devuelve false si no encontró ninguno. */
  async function cargarAutomatico() {
    window.DEPP_CAPTURAS = [];
    const candidatos = turnosCandidatos();
    estadoCarpeta("Buscando capturas en la carpeta…");
    for (let i = 0; i < candidatos.length; i += 12) {
      await Promise.all(candidatos.slice(i, i + 12).map(t => cargarScript(t + "/datos.js?v=" + Date.now())));
    }
    const capturas = (window.DEPP_CAPTURAS || []).filter(c => c && RE_TURNO.test(c.turno || "") && Array.isArray(c.archivos));
    if (!capturas.length) { $("banners").innerHTML = ""; return false; }
    const entradas = [];
    for (const c of capturas) {
      for (const a of c.archivos) {
        if (!a || !a.file || !a.b64) continue;
        const archivo = new File([base64ABytes(a.b64)], a.file, { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
        entradas.push({ turno: c.turno, nombre: a.file, file: async () => archivo });
      }
      const meta = new File([JSON.stringify({ capturedAt: c.capturedAt, scheduledAt: c.scheduledAt, verified: false })], "captura.json");
      entradas.push({ turno: c.turno, nombre: "captura.json", file: async () => meta });
    }
    await procesarCapturas(entradas, "Capturas");
    st.origin = "carpeta";
    st.automatico = true;
    st.sinCapturas = false;
    render();
    if (!st.refrescoAuto) st.refrescoAuto = setInterval(() => { st.cutPrevio = st.cut; cargarAutomatico(); }, 30 * 60000);
    return true;
  }

  /** Último turno programado que ya debería estar en la carpeta (con 45 minutos de margen). */
  function turnoEsperado() {
    const h = hoySantiago();
    for (let i = 0; i < 8; i++) {
      const dia = M.desplazar(h.dia, -i);
      const ds = new Date(dia + "T00:00:00Z").getUTCDay();
      if (ds === 0 || ds === 6) continue;
      for (const hh of HORAS_CAPTURA.slice().reverse()) {
        const minutos = Number(hh.slice(0, 2)) * 60 + Number(hh.slice(2)) + 30;
        if (i > 0 || h.hora >= minutos) return dia + "_" + hh;
      }
    }
    return null;
  }

  // ------------------------------------------------------------------ navegación (botón Volver y atrás del navegador)
  const posicion = () => (history.state && history.state.depp ? history.state.i : 0);
  const estadoNav = extra => Object.assign({ depp: true, i: posicion(), view: st.view, filters: Object.assign({}, st.filters) }, extra || {});
  /** Cambia de pantalla dejando un paso en el historial, para poder volver. */
  function ir(cambios) {
    // Desde una ficha abierta se reemplaza su paso: «Volver» lleva a la pantalla de antes y no reabre la ficha.
    const enPanel = Boolean(history.state && history.state.depp && (history.state.ficha || history.state.ayuda));
    cerrarPanel();
    if (cambios.view) st.view = cambios.view;
    if (cambios.filters) st.filters = Object.assign({}, FILTROS_VACIOS, cambios.filters);
    const nuevo = estadoNav({ i: posicion() + (enPanel ? 0 : 1) });
    if (enPanel) history.replaceState(nuevo, "", "#" + st.view);
    else history.pushState(nuevo, "", "#" + st.view);
    render();
    window.scrollTo(0, 0);
  }
  function volver() {
    if (st.panel) { cerrarPanelUsuario(); return; }
    if (posicion() > 0) history.back();
    else ir({ view: "resumen", filters: FILTROS_VACIOS });
  }
  function alVolverHistorial(e) {
    if (st.ignorarPop) { st.ignorarPop = false; return; }
    const s = e.state && e.state.depp ? e.state : { view: "resumen", filters: FILTROS_VACIOS };
    st.view = VISTAS[s.view] ? s.view : "resumen";
    st.filters = Object.assign({}, FILTROS_VACIOS, s.filters);
    cerrarPanel();
    render();
    if (s.ficha && st.cut) abrirFicha(s.ficha, true);
    else if (s.ayuda) abrirAyuda(true);
  }
  /** Panel lateral (ficha o ayuda). */
  function abrirPanel(html, tipo, desdeHistorial, extra) {
    const root = $("drawer-root");
    if (!st.panel) st.focoPrevio = document.activeElement;
    root.innerHTML = html;
    st.panel = tipo;
    if (!desdeHistorial) {
      // Si ya hay un panel abierto se reemplaza el paso, para que «Volver» lleve a la lista y no a la ficha anterior.
      const reemplazar = history.state && history.state.depp && (history.state.ficha || history.state.ayuda);
      const nuevo = estadoNav(Object.assign({ i: posicion() + (reemplazar ? 0 : 1) }, extra));
      if (reemplazar) history.replaceState(nuevo, "", location.hash || "#" + st.view);
      else history.pushState(nuevo, "", location.hash || "#" + st.view);
    }
    for (const el of root.querySelectorAll("[data-close]")) el.addEventListener("click", cerrarPanelUsuario);
    for (const el of root.querySelectorAll("[data-open]")) el.addEventListener("click", () => abrirFicha(el.dataset.open));
    const foco = root.querySelector(".drawer__back") || root.querySelector(".drawer__close");
    if (foco) foco.focus();
    renderTopbar();
  }
  function cerrarPanel() {
    if (!st.panel) return;
    $("drawer-root").innerHTML = "";
    st.panel = null;
    if (st.focoPrevio && st.focoPrevio.isConnected && st.focoPrevio.focus) st.focoPrevio.focus();
    st.focoPrevio = null;
    renderTopbar();
  }
  function cerrarPanelUsuario() {
    cerrarPanel();
    if (history.state && history.state.depp && (history.state.ficha || history.state.ayuda)) { st.ignorarPop = true; history.back(); }
  }

  // ------------------------------------------------------------------ marco
  function render() {
    for (const b of document.querySelectorAll(".nav__item")) b.setAttribute("aria-current", b.dataset.view === st.view ? "page" : "false");
    $("view-title").textContent = VISTAS[st.view][0];
    $("view-sub").textContent = VISTAS[st.view][1];
    renderTopbar();
    renderBanners();
    const page = $("page");
    if (!st.cut) { page.innerHTML = vistaInicio(); enlazarInicio(); return; }
    const a = analisis();
    if (st.view === "resumen") page.innerHTML = vistaResumen(a);
    else if (st.view === "compromisos") page.innerHTML = vistaCompromisos(a);
    else if (st.view === "minuta") page.innerHTML = vistaMinuta();
    else page.innerHTML = vistaCalidad(a);
    enlazarVista();
  }
  function renderTopbar() {
    const sel = $("cut-select");
    const cortes = cortesOrdenados();
    $("cutpick").hidden = !cortes.length;
    $("statusbar").hidden = !cortes.length;
    sel.innerHTML = cortes.slice().reverse().map(c =>
      '<option value="' + c + '"' + (c === st.cut ? " selected" : "") + ">" + esc(etiquetaClave(c)) + " · " + esc(ESTADOS_TXT[estadoDe(c)]) + "</option>").join("");
    $("cut-dot").className = "dot " + (st.cut ? estadoDe(st.cut) : "");
    const meta = $("update-meta");
    $("btn-actualizar").hidden = st.origin !== "carpeta";
    $("btn-volver").hidden = !st.cut || (st.view === "resumen" && !st.panel && posicion() === 0);
    if (st.origin === "carpeta" && st.carpeta) {
      meta.hidden = false;
      const ultimo = st.carpeta.turnos[st.carpeta.turnos.length - 1];
      $("update-label").textContent = "Captura del " + M.momentoSlot(ultimo) + " · revisado a las " + momentoTexto(st.carpeta.leidaEn).slice(11);
    } else if (st.index && st.index.lastRun) {
      meta.hidden = false;
      const lr = st.index.lastRun;
      $("update-label").textContent = momentoTexto(lr.at) + " · " + (lr.status === "fallido" ? "falló" : ESTADOS_TXT[lr.status] || lr.status);
    } else if (st.origin === "demo") {
      meta.hidden = false; $("update-label").textContent = "Datos ficticios";
    } else meta.hidden = true;
    const n = st.cut ? (st.norm[st.cut].incidents || []).length : 0;
    $("nav-inc").hidden = !n; $("nav-inc").textContent = n;
  }
  function renderBanners() {
    const out = [];
    const ban = (tipo, html) => out.push('<div class="banner ' + tipo + '">' + html + "</div>");
    if (st.origin === "demo") ban("info", "<strong>Demostración con datos ficticios.</strong> Los registros, nombres y cifras son ilustrativos. El tablero operativo lee la carpeta institucional de capturas en OneDrive.");
    if (st.cut && st.manual.has(st.cut)) ban("info", "<strong>Carga manual sin publicar.</strong> Este corte se armó en el navegador con los Excel seleccionados. Puedes guardarlo como consolidado desde «Estado de los datos».");
    if (st.cut && esIntermedio(st.cut)) ban("info", "<strong>Actualización intermedia: estás viendo los datos del " + esc(M.momentoSlot(st.cut)) + ".</strong> Muestra lo que cambió desde el último corte semanal. La minuta oficial para Gabinete se arma con el corte del viernes a las 12:00 (elígelo en «Ver datos de»).");
    const lr = st.index && st.index.lastRun;
    if (lr && lr.status === "fallido") ban("bad", "<strong>La actualización del corte del " + ft(lr.cut) + " falló</strong> (" + esc(momentoTexto(lr.at)) + "): " + esc(lr.result) + " Se mantiene el último corte válido.");
    else if (lr && lr.status === "en_revision" && fechaClave(st.cut || "") !== lr.cut) ban("warn", "<strong>El corte del " + ft(lr.cut) + " quedó en revisión.</strong> Se muestra el último corte válido (" + ft(st.index.lastValid || "") + "). Revisa los avisos en «Estado de los datos».");
    if (st.cut && st.norm[st.cut].status === "en_revision") {
      const bloq = (st.norm[st.cut].incidents || []).filter(i => i.level === "bloqueante");
      ban("bad", "<strong>Corte en revisión: cifras preliminares.</strong> " + esc(bloq.slice(0, 2).map(i => i.message).join(" ")) + (bloq.length > 2 ? " (+" + (bloq.length - 2) + " más)" : ""));
    }
    if (st.origin === "carpeta" && st.carpeta) {
      const esperado = turnoEsperado();
      if (esperado && !st.carpeta.turnos.includes(esperado) && esperado > st.carpeta.turnos[st.carpeta.turnos.length - 1]) {
        ban("warn", "<strong>Falta la captura del " + esc(M.momentoSlot(esperado)) + ".</strong> Se muestran los datos de la captura anterior. Puede ser que OneDrive aún esté sincronizando: espera unos minutos y pulsa «↻ Actualizar». Si el aviso sigue por más de una hora, avisa a quien administra el flujo «DEPP - Captura de planillas».");
      }
      if (st.carpeta.errores.length) ban("bad", "<strong>No se pudieron leer algunas capturas:</strong> " + esc(st.carpeta.errores.join(" · ")));
    }
    if (st.index && (st.origin === "procesador" || st.origin === "http")) {
      const esperado = corteEsperado();
      if (!st.index.cuts.some(c => c.cut === esperado) && (!lr || lr.cut !== esperado)) {
        ban("warn", "<strong>Corte del viernes " + ft(esperado) + " pendiente.</strong> La actualización programada a las 12:00 aún no se publica. Se muestra el corte del " + ft(st.index.lastValid || fechaClave(st.cut || "")) + ".");
      }
    }
    $("banners").innerHTML = out.join("");
  }

  // ------------------------------------------------------------------ vista inicial sin datos
  function vistaInicio() {
    const pendiente = st.carpetaPendiente;
    const conectar = '<div class="toolbar" style="justify-content:center;margin-top:14px">'
      + (pendiente ? '<button class="btn primary" data-act="actualizar">Actualizar desde «' + esc(pendiente) + '»</button><button class="btn" data-act="carpeta">Elegir otra carpeta</button>'
        : '<button class="btn primary" data-act="carpeta">Conectar carpeta de OneDrive</button>')
      + '<button class="btn" data-act="carpeta-alt">Elegir carpeta (método alternativo)</button></div>'
      + '<p class="status-msg" id="folder-status" aria-live="polite"></p>';
    const otras = '<details><summary>Otras formas de cargar datos</summary>'
      + '<div class="toolbar" style="align-items:end;margin-top:12px"><label class="field">Fecha de corte (viernes)<input type="date" id="manual-cut" value="' + corteEsperado() + '"></label><button class="btn" data-act="xlsx">Cargar los tres Excel</button><button class="btn" data-act="json">Abrir consolidado (.json)</button></div>'
      + '<p style="font-size:13px">¿Solo quieres ver cómo funciona? <a href="https://alejandroavya.github.io/seguimiento-semanal-depp/">Abrir la demostración con datos ficticios</a>.</p></details>';
    if (st.sinCapturas) {
      // Tablero abierto desde el escritorio (dentro de Capturas) sin capturas a la vista.
      return '<div class="start"><div class="page__eyebrow">Seguimiento semanal DEPP</div><h1>Aún no hay datos para mostrar</h1>'
        + "<p>Este tablero lee las capturas guardadas en su misma carpeta (<strong>Capturas</strong>, en OneDrive) y no encontró ninguna. Revisa:</p>"
        + "<ol><li>Que el archivo <strong>Tablero_DEPP.html</strong> esté dentro de la carpeta <strong>Capturas</strong>.</li>"
        + "<li>Que la carpeta esté marcada con <strong>«Mantener siempre en este dispositivo»</strong> (clic derecho › OneDrive).</li>"
        + "<li>Que OneDrive haya terminado de sincronizar (ícono de nube en la barra de tareas).</li></ol>"
        + '<div class="toolbar" style="justify-content:center;margin-top:18px"><button class="btn primary" data-act="reintentar">↻ Buscar de nuevo</button></div>'
        + '<details><summary>Conecta la carpeta de seguimiento de otra forma</summary>' + conectar + "</details>" + otras + "</div>";
    }
    return '<div class="start"><div class="page__eyebrow">Seguimiento semanal DEPP</div><h1>' + (pendiente ? "Actualiza la información" : "Conecta la carpeta de seguimiento") + "</h1>"
      + "<p>Elige la carpeta <strong>DEPP_Seguimiento</strong> de OneDrive sincronizada en este computador. El tablero lee las capturas que se toman cada hora de lunes a viernes, usa la del viernes a las 12:00 como corte semanal y arma los cortes y la minuta en este navegador. Los datos no se envían a ningún servidor.</p>"
      + conectar + otras + "</div>";
  }
  function enlazarInicio() {
    for (const b of $("page").querySelectorAll("[data-act]")) b.addEventListener("click", accion);
  }

  // ------------------------------------------------------------------ resumen
  function li(f, derecha, claseDer, extra) {
    return '<li><button class="li" data-open="' + esc(f.id) + '"><span class="chip area" title="' + esc(AREAS.get(f.area).name) + '">' + esc(f.area) + '</span><span class="li__main"><span class="li__t" style="display:block">'
      + esc(f.product) + '</span><span class="li__s" style="display:block">' + esc(extra) + '</span></span><span class="li__r ' + (claseDer || "") + '">' + esc(derecha) + "</span></button></li>";
  }
  function vistaResumen(a) {
    const s = a.summary;
    const corte = st.norm[st.cut];
    const alertas = a.rows.filter(f => f.active && (f.blocked || f.late)).sort((x, y) => Number(y.blocked) - Number(x.blocked) || (x.due || "9").localeCompare(y.due || "9"));
    const solicitudes = a.rows.filter(f => f.support).sort((x, y) => Number(y.decision) - Number(x.decision));
    const proximos = a.rows.filter(f => f.upcoming).sort((x, y) => x.due.localeCompare(y.due));
    const movs = M.movimientos(modelo, corte);
    const intermedio = esIntermedio(st.cut);
    const periodo = intermedio && !a.comparing ? "Línea base al " + M.momentoSlot(st.cut) + ": aún no hay un corte semanal anterior para comparar"
      : intermedio ? "Avance desde el corte del viernes " + ft(a.from) + " a las 12:00 hasta el " + M.momentoSlot(st.cut)
      : a.comparing ? "Del viernes " + ft(a.from) + " a las 12:00 al viernes " + ft(a.cut) + " a las 12:00" : "Corte inicial · línea base desde el " + ft(a.from);
    const hstat = (n, l, sub, vista, hot) => '<button class="hstat' + (hot && n ? " is-hot" : "") + '" data-preset="' + vista + '"><div class="hstat__n tnum">' + n + '</div><div class="hstat__l">' + l + '</div><div class="hstat__s">' + sub + '</div><div class="hstat__go">Ver lista →</div></button>';
    let html = '<section class="hero" aria-label="Cifras del corte"><div class="hero__top"><div><div class="hero__k">' + (intermedio ? "Actualización intermedia DEPP · " + esc(M.momentoSlot(st.cut)) : "Corte semanal DEPP · viernes " + ft(a.cut) + " · 12:00") + "</div>"
      + '<div class="hero__t">Estado de los compromisos al ' + fechaLarga(a.cut) + '</div><div class="hero__meta">' + periodo + "</div></div>"
      + '<div class="hero__side"><b class="tnum">' + s.abiertos + "</b> compromisos abiertos · <b class=\"tnum\">" + s.registros + "</b> registrados<br>" + modelo.areas.length + " equipos · estado: " + esc(ESTADOS_TXT[estadoDe(st.cut)]) + "</div></div>"
      + '<div class="hero__stats">'
      + hstat(s.entregas, "Entregados", s.entregasFueraPlazo ? M.plural(s.entregasFueraPlazo, "fuera de plazo", "fuera de plazo") : "en el período", "entregas")
      + hstat(s.avances, "Con avance", a.comparing ? "cambios respecto del corte anterior" : "se calcula desde el 2.º corte", "avances")
      + hstat(s.ingresos, "Ingresos", s.ingresosTardios ? M.plural(s.ingresosTardios, "con registro tardío", "con registro tardío") : "encargos nuevos", "ingresos")
      + hstat(alertas.length, "Atrasados o bloqueados", M.plural(s.vencidos, "vencido") + " · " + M.plural(s.bloqueados, "bloqueado"), "alertas", true)
      + hstat(s.apoyos, "Requieren decisión o apoyo", M.plural(s.decisiones, "decisión", "decisiones") + " · " + M.plural(s.apoyos - s.decisiones, "apoyo"), "solicitudes", true)
      + "</div></section>";
    // Atención y decisiones
    html += '<div class="grid g2">';
    html += '<section class="card"><div class="card__head"><h2 class="card__title red" style="margin:0">Bloqueos y atrasos</h2><span class="card__sub">' + alertas.length + ' al corte</span></div><div class="card__body"><ul class="list">'
      + (alertas.slice(0, 5).map(f => li(f, f.blocked && !f.late ? "Bloqueado" : "Vencido hace " + M.plural(diasEntre(f.due, a.cut), "día"), "red", (f.blocked && f.late ? "Bloqueado · " : "") + f.owner + " · " + f.requester)).join("") || '<li class="empty-note">Sin compromisos bloqueados ni vencidos.</li>')
      + "</ul>" + (alertas.length > 5 ? '<button class="more" data-preset="alertas">Ver los ' + alertas.length + " →</button>" : "") + "</div></section>";
    html += '<section class="card"><div class="card__head"><h2 class="card__title amber" style="margin:0">Decisiones y apoyos solicitados</h2><span class="card__sub">' + solicitudes.length + ' abiertos</span></div><div class="card__body"><ul class="list">'
      + (solicitudes.slice(0, 5).map(f => '<li><button class="li" data-open="' + esc(f.id) + '"><span class="chip ' + (f.decision ? "dec" : "apo") + '">' + (f.decision ? "Decisión" : "Apoyo") + '</span><span class="li__main"><span class="li__t" style="display:block">' + esc(f.product) + '</span><span class="li__s" style="display:block">' + esc(f.notes) + '</span></span><span class="li__r">' + esc(f.area) + "</span></button></li>").join("") || '<li class="empty-note">Los equipos no registraron solicitudes a Gabinete.</li>')
      + "</ul>" + (solicitudes.length > 5 ? '<button class="more" data-preset="solicitudes">Ver las ' + solicitudes.length + " →</button>" : "") + "</div></section>";
    html += "</div>";
    // Por equipo y próximos
    html += '<div class="grid g2" style="margin-top:16px">';
    html += '<section class="card"><div class="card__head"><h2 class="card__title" style="margin:0">Compromisos abiertos por equipo</h2><span class="card__sub">clic en un equipo para ver su lista</span></div><div class="card__body"><div class="legend" aria-hidden="true"><span><i class="s-pend"></i>Pendiente</span><span><i class="s-curso"></i>En curso</span><span><i class="s-rev"></i>En revisión</span><span><i class="s-bloq"></i>Bloqueado</span><span><i class="s-venc"></i>Vencido</span></div>';
    for (const area of modelo.areas) {
      const propios = a.rows.filter(f => f.area === area.prefix && f.active);
      const sa = s.porArea[area.prefix];
      const seg = [["s-venc", propios.filter(f => f.late && !f.blocked).length, "vencidos"], ["s-bloq", propios.filter(f => f.blocked).length, "bloqueados"],
        ["s-pend", propios.filter(f => !f.late && f.state === "Pendiente").length, "pendientes"], ["s-curso", propios.filter(f => !f.late && f.state === "En curso").length, "en curso"],
        ["s-rev", propios.filter(f => !f.late && f.state === "En revisión").length, "en revisión"]];
      const total = propios.length || 1;
      html += '<button class="srow" data-area="' + area.prefix + '"><span class="srow__l">' + esc(area.name.replace(/^Unidad de |^Centro para la /, "")) + "<small>" + M.plural(sa.entregas, "entrega") + " · " + M.plural(sa.avances, "avance") + " en la semana</small></span>"
        + '<span class="stack" role="img" aria-label="' + esc(seg.filter(x => x[1]).map(x => x[1] + " " + x[2]).join(", ") || "sin compromisos abiertos") + '">'
        + seg.filter(x => x[1]).map(x => '<span class="' + x[0] + '" style="width:' + (100 * x[1] / total) + '%">' + x[1] + "</span>").join("") + "</span>"
        + '<span class="srow__n"><b class="tnum">' + propios.length + "</b>abiertos</span></button>";
    }
    html += "</div></section>";
    html += '<section class="card"><div class="card__head"><h2 class="card__title" style="margin:0">Próximos vencimientos</h2><span class="card__sub">' + ft(a.cut) + " al " + ft(a.next) + '</span></div><div class="card__body"><ul class="list">'
      + (proximos.slice(0, 6).map(f => li(f, f.due === a.cut ? "Hoy" : ft(f.due).slice(0, 5), "blue", f.owner + " · " + f.state)).join("") || '<li class="empty-note">Sin vencimientos de compromisos abiertos en los próximos 7 días.</li>')
      + "</ul>" + (proximos.length > 6 ? '<button class="more" data-preset="proximos">Ver los ' + proximos.length + " →</button>" : "") + "</div></section></div>";
    // Movimientos
    const tipoChip = t => t.startsWith("Entrega") ? "mov-e" : t.startsWith("Ingreso") ? "mov-i" : t === "Cancelación" ? "mov-c" : "mov-a";
    html += '<section class="card" style="margin-top:16px"><div class="card__head"><h2 class="card__title" style="margin:0">Movimientos del período</h2><span class="card__sub">' + M.plural(movs.length, "movimiento") + " en " + M.plural(a.rows.filter(f => f.movement).length, "compromiso") + '</span></div><div class="card__body"><ul class="list feed">'
      + (movs.slice(0, 12).map(m => '<li><button class="li" data-open="' + esc(m.fila.id) + '"><span class="chip ' + tipoChip(m.tipo) + '">' + esc(m.tipo) + '</span><span class="li__main"><span class="li__t" style="display:block">' + esc(m.fila.product) + '</span><span class="li__s" style="display:block">' + esc(m.fila.id) + " · " + esc(m.cambios ? "Actualizó " + m.cambios : (m.fecha ? ft(m.fecha) : "")) + "</span></span></button></li>").join("") || '<li class="empty-note">Sin movimientos en el período.</li>')
      + "</ul>" + (movs.length > 12 ? '<button class="more" data-preset="movement">Ver todos los movimientos →</button>' : "") + "</div></section>";
    return html;
  }

  // ------------------------------------------------------------------ compromisos
  const PRESETS = {
    all: ["Todos los registros al corte", () => true],
    movement: ["Con movimiento en el período", f => f.movement],
    entregas: ["Entregados en el período", f => f.deliveredNow],
    avances: ["Con avance en el período", f => f.advancedNow],
    ingresos: ["Ingresados en el período", f => f.receivedNow],
    abiertos: ["Compromisos abiertos", f => f.active],
    alertas: ["Atrasados o bloqueados", f => f.active && (f.late || f.blocked)],
    solicitudes: ["Requieren decisión o apoyo", f => f.support],
    proximos: ["Vencen en los próximos 7 días", f => f.upcoming],
    sinplazo: ["Abiertos sin plazo", f => f.undated]
  };
  function filtrar(a) {
    const F = st.filters;
    const q = M.plegar(F.q.trim());
    return a.rows.filter(f => (!F.area || f.area === F.area) && (!F.state || f.state === F.state) && (!F.requester || f.requester === F.requester)
      && PRESETS[F.view][1](f) && (!q || M.plegar([f.id, f.product, f.request, f.owner, f.requester, f.notes].join(" ")).includes(q)));
  }
  function movChip(f) {
    const out = [];
    if (f.deliveredNow) out.push('<span class="chip mov-e">Entrega</span>');
    if (f.advancedNow) out.push('<span class="chip ' + (f.cancelledNow ? "mov-c" : "mov-a") + '">' + (f.cancelledNow ? "Cancelación" : "Avance") + "</span>");
    if (f.receivedNow) out.push('<span class="chip mov-i">Ingreso</span>');
    return out.join(" ");
  }
  function badge(f) {
    let h = '<span class="badge ' + claseEstado(f.state) + '">' + esc(f.state) + "</span>";
    if (f.late) h += '<span class="late">Vencido hace ' + M.plural(diasEntre(f.due, st.norm[st.cut].cut), "día") + "</span>";
    else if (f.deliveredNow && f.deliveredLate) h += '<span class="late">Fuera de plazo</span>';
    return h;
  }
  function vistaCompromisos(a) {
    const F = st.filters;
    const filas = filtrar(a);
    const opt = (v, t, sel) => '<option value="' + esc(v) + '"' + (v === sel ? " selected" : "") + ">" + esc(t) + "</option>";
    const partes = [];
    if (F.view !== "all") partes.push(PRESETS[F.view][0]);
    if (F.area) partes.push(AREAS.get(F.area).name);
    if (F.state) partes.push("estado «" + F.state + "»");
    if (F.requester) partes.push("requirente " + F.requester);
    if (F.q.trim()) partes.push("búsqueda «" + F.q.trim() + "»");
    let html = partes.length
      ? '<div class="context no-print"><div class="context__t"><span class="context__k">Estás viendo</span><strong>' + esc(partes.join(" · ")) + "</strong> · " + M.plural(filas.length, "compromiso")
        + '</div><button class="backbtn" data-act="volver"><span aria-hidden="true">←</span>Volver</button><button class="btn" data-act="limpiar">Ver todos los compromisos</button></div>'
      : "";
    html += '<div class="filterbar" role="search"><span class="filterbar__label">Filtros</span>'
      + '<select class="fsel' + (F.area ? " is-set" : "") + '" data-f="area" aria-label="Equipo">' + opt("", "Todos los equipos", F.area) + modelo.areas.map(x => opt(x.prefix, x.name, F.area)).join("") + "</select>"
      + '<select class="fsel' + (F.state ? " is-set" : "") + '" data-f="state" aria-label="Estado">' + opt("", "Todos los estados", F.state) + modelo.states.map(x => opt(x, x, F.state)).join("") + "</select>"
      + '<select class="fsel' + (F.requester ? " is-set" : "") + '" data-f="requester" aria-label="Requirente">' + opt("", "Todos los requirentes", F.requester) + modelo.requesters.map(x => opt(x, x, F.requester)).join("") + "</select>"
      + '<select class="fsel' + (F.view !== "all" ? " is-set" : "") + '" data-f="view" aria-label="Vista">' + Object.entries(PRESETS).map(([k, v]) => opt(k, v[0], F.view)).join("") + "</select>"
      + '<input class="fsearch" type="search" data-f="q" value="' + esc(F.q) + '" placeholder="Buscar referencia, producto, responsable u observación" aria-label="Buscar">'
      + '<span class="count" aria-live="polite">' + filas.length + " de " + a.rows.length + "</span>"
      + '<button class="linkbtn" data-act="limpiar">Quitar filtros</button><button class="linkbtn" data-act="csv">Descargar lista (CSV para Excel)</button></div>';
    html += '<div class="tablewrap"><table><thead><tr><th scope="col">Ref.</th><th scope="col">Producto y requerimiento</th><th scope="col">Requirente</th><th scope="col">Responsable</th><th scope="col">Plazo</th><th scope="col">Entrega</th><th scope="col">Estado</th><th scope="col">Movimiento</th></tr></thead><tbody>';
    html += filas.length ? filas.map(f => '<tr data-open="' + esc(f.id) + '" tabindex="0"><td class="nowrap mono">' + esc(f.id) + '</td><td><div class="cell-t">' + esc(f.product) + '</div><div class="cell-s">' + esc(f.request) + "</div></td><td>" + esc(f.requester)
      + "</td><td>" + esc(f.owner) + '</td><td class="nowrap tnum">' + (ft(f.due) || "—") + '</td><td class="nowrap tnum">' + (ft(f.delivered) || "—") + "</td><td>" + badge(f) + "</td><td>" + movChip(f) + "</td></tr>").join("")
      : '<tr><td colspan="8" class="empty-note">Sin registros para estos filtros.</td></tr>';
    return html + "</tbody></table></div>";
  }

  // ------------------------------------------------------------------ ficha de detalle
  function abrirFicha(id, desdeHistorial) {
    const a = analisis();
    const f = a.rows.find(x => x.id === id);
    if (!f) return;
    const area = AREAS.get(f.area);
    const prev = (st.norm[st.cut].previousRows || []).find(x => x.id === id);
    const filas = [["Equipo", area.name], ["Fecha de ingreso", ft(f.received)], ["Requerimiento", f.request], ["Producto comprometido", f.product], ["Tipo de encargo", f.kind],
      ["Requirente", f.requester], ["Responsable", f.owner], ["Plazo acordado", ft(f.due) || "Sin plazo"], ["Estado", f.state], ["Entrega efectiva", ft(f.delivered) || "—"], ["Observaciones generales", f.notes || "—"]];
    const destino = st.view === "compromisos" ? "Volver a la lista" : st.view === "minuta" ? "Volver a la minuta" : st.view === "calidad" ? "Volver" : "Volver al resumen";
    let html = '<div class="drawer-bg" data-close></div><aside class="drawer" role="dialog" aria-modal="true" aria-labelledby="ficha-t"><div class="drawer__head"><div style="min-width:0">'
      + '<button class="drawer__back" data-close><span aria-hidden="true">←</span>' + destino + "</button>"
      + '<div class="drawer__k">Ficha del compromiso · ' + esc(f.id) + " · " + esc(area.name)
      + '</div><div class="drawer__t" id="ficha-t">' + esc(f.product) + '</div><div style="margin-top:8px">' + badge(f) + " " + movChip(f) + (f.support ? ' <span class="chip ' + (f.decision ? "dec" : "apo") + '">' + (f.decision ? "Decisión de Gabinete" : "Apoyo de Gabinete") + "</span>" : "")
      + '</div></div><button class="drawer__close" data-close aria-label="Cerrar ficha">×</button></div><div class="drawer__body"><dl class="dl">'
      + filas.map(([k, v]) => "<dt>" + esc(k) + "</dt><dd>" + esc(v) + "</dd>").join("") + "</dl>";
    if (f.held) html += '<p class="empty-note">La fila tiene un error en el Excel; se muestra la versión del corte anterior.</p>';
    if (prev && f.changed.length) {
      html += '<div class="sub">Qué cambió desde el corte del ' + ft(st.norm[st.cut].from) + '</div><div class="diff">'
        + f.changed.map(k => {
          const fecha = ["due", "received", "delivered"].includes(k);
          const v = x => (fecha ? ft(x) : x) || "(vacío)";
          return "<div><strong>" + esc(M.ETIQUETAS_CAMBIO[k][0].toUpperCase() + M.ETIQUETAS_CAMBIO[k].slice(1)) + "</strong><span><del>" + esc(v(prev[k])) + "</del> → <ins>" + esc(v(f[k])) + "</ins></span></div>";
        }).join("") + "</div>";
    } else if (f.receivedNow) html += '<div class="sub">Movimiento</div><p style="font-size:13px;margin:0">Ingresó en este período' + (f.lateEntry ? " (registro tardío: la fecha de ingreso es anterior al período)." : ".") + "</p>";
    const hist = cortesOrdenados().filter(c => c <= st.cut).map(c => [c, st.norm[c].rows.find(x => x.id === id)]).filter(x => x[1]);
    if (hist.length > 1) {
      html += '<div class="sub">Historial en los cortes disponibles</div><div class="hist">' + hist.map(([c, r]) => "<div><strong>" + esc(etiquetaClave(c)) + "</strong> · " + esc(r.state) + (r.due ? " · plazo " + ft(r.due) : "") + (r.notes ? '<span class="cell-s" style="display:block">' + esc(r.notes) + "</span>" : "") + "</div>").join("") + "</div>";
    }
    html += '</div><div class="drawer__foot"><button class="backbtn" data-close><span aria-hidden="true">←</span>' + destino + "</button></div></aside>";
    abrirPanel(html, "ficha", desdeHistorial, { ficha: id });
  }

  // ------------------------------------------------------------------ ayuda
  function abrirAyuda(desdeHistorial) {
    const html = '<div class="drawer-bg" data-close></div><aside class="drawer" role="dialog" aria-modal="true" aria-labelledby="ayuda-t"><div class="drawer__head"><div>'
      + '<button class="drawer__back" data-close><span aria-hidden="true">←</span>Volver al tablero</button>'
      + '<div class="drawer__k">Ayuda</div><div class="drawer__t" id="ayuda-t">Cómo leer este tablero</div></div><button class="drawer__close" data-close aria-label="Cerrar ayuda">×</button></div>'
      + '<div class="drawer__body help">'
      + "<h3>De dónde salen los datos</h3><p>Los equipos registran sus compromisos en tres planillas Excel. Cada hora, de 8:00 a 19:00 y de lunes a viernes, se guarda una copia (una <strong>captura</strong>) y el tablero la lee sola.</p>"
      + "<dl><dt>Corte semanal</dt><dd>La captura del <strong>viernes a las 12:00</strong>. Se compara con la del viernes anterior y con ella se arma la minuta para Gabinete.</dd>"
      + "<dt>Actualización</dt><dd>La captura más reciente de la semana. Muestra lo que ha cambiado desde el último corte semanal.</dd></dl>"
      + "<p style=\"margin-top:8px\">Para mirar otra semana, usa el selector <strong>«Ver datos de»</strong> arriba.</p>"
      + "<h3>Qué significa cada número</h3><dl>"
      + "<dt>Entregados</dt><dd>Compromisos que pasaron a «Entregado» en el período.</dd>"
      + "<dt>Con avance</dt><dd>Compromisos que cambiaron algo (estado, plazo, observaciones u otro dato) sin entregarse todavía.</dd>"
      + "<dt>Ingresos</dt><dd>Encargos nuevos registrados en el período.</dd>"
      + "<dt>Atrasados o bloqueados</dt><dd>Abiertos con el plazo vencido, o que el equipo marcó como «Bloqueado».</dd>"
      + "<dt>Requieren decisión o apoyo</dt><dd>El equipo pidió en Observaciones una decisión o una gestión de Gabinete.</dd>"
      + "<dt>Próximos vencimientos</dt><dd>Compromisos abiertos que vencen en los próximos 7 días.</dd></dl>"
      + "<h3>Cómo moverse</h3><ul>"
      + "<li>Haz clic en cualquier número, equipo o fila para ver el detalle.</li>"
      + "<li>Usa <strong>«← Volver»</strong> (arriba a la izquierda), la flecha atrás del navegador o la tecla <strong>Esc</strong> para regresar.</li>"
      + "<li><strong>«↻ Actualizar»</strong> trae la captura más reciente. Si dejas la página abierta, se actualiza sola cada 30 minutos.</li>"
      + "<li>La minuta en Word está en <strong>Minuta semanal › Descargar Word</strong>.</li></ul>"
      + "<h3>Si algo se ve raro</h3><p>Los avisos amarillos o rojos bajo la barra superior explican qué pasa (por ejemplo, una captura que no llegó). El detalle técnico está en <strong>Estado de los datos</strong>.</p>"
      + '</div><div class="drawer__foot"><button class="backbtn" data-close><span aria-hidden="true">←</span>Volver al tablero</button></div></aside>';
    abrirPanel(html, "ayuda", desdeHistorial, { ayuda: true });
  }

  // ------------------------------------------------------------------ minuta
  function minutaHTML(m) {
    const notas = m.notes || [];
    let h = '<article class="paper" id="paper" aria-label="Minuta semanal"><img class="plogo" src="' + document.querySelector(".sidebar__logo").src + '" alt="Subsecretaría de Prevención del Delito">'
      + '<div class="pk">' + esc(m.kind) + "</div>" + (m.draft ? '<div class="pdraft">' + esc(m.draftLabel || "BORRADOR · CORTE EN REVISIÓN") + "</div>" : "")
      + '<div class="pt">' + esc(m.title) + '</div><div class="pr">' + esc(m.recipient) + "</div>";
    m.sections.forEach((s, i) => {
      h += "<h3>" + (i + 1) + ". " + esc(s.title) + "</h3>";
      (s.paragraphs || []).forEach((p, j) => { h += "<p>" + esc(p) + (i === 0 && j === 0 ? notas.map((_, k) => "<sup>" + (k + 1) + "</sup>").join("") : "") + "</p>"; });
      for (const g of s.groups || []) {
        h += '<div class="pg">' + esc(g.title) + " <span>· " + esc(g.counts) + "</span></div>";
        if (g.items.length) h += "<ul>" + g.items.map(it => "<li><strong>" + esc(it.lead) + "</strong> " + esc(it.text) + "</li>").join("") + "</ul>";
        if (g.note) h += '<div class="pn">' + esc(g.note) + "</div>";
      }
      if ((s.items || []).length) h += "<ul>" + s.items.map(it => "<li><strong>" + esc(it.lead) + "</strong> " + esc(it.text) + "</li>").join("") + "</ul>";
      if (s.note) h += '<div class="pn">' + esc(s.note) + "</div>";
    });
    if (notas.length) h += '<div class="pfoot">' + notas.map((n, k) => "<div><sup>" + (k + 1) + "</sup> " + esc(n) + "</div>").join("") + "</div>";
    return h + "</article>";
  }
  function minutaTexto(m) {
    const l = [m.kind, m.draft ? (m.draftLabel || "BORRADOR · CORTE EN REVISIÓN") : "", m.title, m.recipient, ""].filter((x, i) => x || i === 4);
    m.sections.forEach((s, i) => {
      l.push((i + 1) + ". " + s.title.toUpperCase());
      for (const p of s.paragraphs || []) l.push(p);
      for (const g of s.groups || []) { l.push(g.title + " · " + g.counts); for (const it of g.items) l.push("• " + it.lead + " " + it.text); if (g.note) l.push("  " + g.note); }
      for (const it of s.items || []) l.push("• " + it.lead + " " + it.text);
      if (s.note) l.push("  " + s.note);
      l.push("");
    });
    (m.notes || []).forEach((n, k) => l.push("(" + (k + 1) + ") " + n));
    return l.join("\n");
  }
  function vistaMinuta() {
    const corte = st.norm[st.cut];
    const m = M.minuta(modelo, corte, st.full);
    const s = m.summary;
    let html = '<div class="toolbar no-print"><div class="seg" role="group" aria-label="Versión de la minuta"><button data-full="0" aria-pressed="' + !st.full + '">Ejecutiva (hasta 2 páginas)</button><button data-full="1" aria-pressed="' + st.full + '">Detalle completo</button></div>'
      + '<button class="btn primary" data-act="word">Descargar Word</button><button class="btn" data-act="copiar">Copiar texto</button><button class="btn" data-act="imprimir">Imprimir o PDF</button>'
      + '<span class="status-msg" id="minuta-status">Cifras: ' + s.ingresos + " ingresos · " + s.entregas + " entregas · " + s.avances + " avances · " + s.abiertos + " abiertos" + verificacion(corte, s) + "</span></div>";
    if (esIntermedio(st.cut)) {
      const semanal = cortesOrdenados().filter(k => !esIntermedio(k) && st.norm[k].status !== "en_revision").slice(-1)[0];
      html += '<div class="context no-print"><div class="context__t"><span class="context__k">Ojo</span>Esta es una minuta de avance intermedio, no la minuta semanal oficial.</div>'
        + (semanal ? '<button class="btn primary" data-act="ir-semanal" data-k="' + semanal + '">Ver la minuta del ' + esc(etiquetaClave(semanal).replace("Corte semanal · ", "corte del ")) + "</button>" : "") + "</div>";
    }
    html += minutaHTML(m);
    if (st.full) {
      const movs = M.movimientos(modelo, corte);
      html += '<section class="card movtable no-print"><div class="card__head"><h2 class="card__title" style="margin:0">Todos los movimientos detectados</h2><span class="card__sub">' + movs.length + ' movimientos</span></div><div class="card__body" style="padding:0"><div style="overflow:auto"><table><thead><tr><th>Ref.</th><th>Movimiento</th><th>Producto</th><th>Equipo</th><th>Fecha</th><th>Cambios</th><th>Estado</th></tr></thead><tbody>'
        + (movs.map(x => '<tr data-open="' + esc(x.fila.id) + '"><td class="mono nowrap">' + esc(x.fila.id) + "</td><td>" + esc(x.tipo) + "</td><td>" + esc(x.fila.product) + "</td><td>" + esc(x.fila.area) + '</td><td class="nowrap">' + (ft(x.fecha) || "—") + "</td><td>" + esc(x.cambios || "—") + "</td><td>" + badge(x.fila) + "</td></tr>").join("") || '<tr><td colspan="7" class="empty-note">Sin movimientos.</td></tr>')
        + "</tbody></table></div></div></section>";
    }
    return html;
  }
  function verificacion(corte, s) {
    if (!corte.summary) return "";
    const claves = ["ingresos", "entregas", "avances", "abiertos", "vencidos", "bloqueados", "apoyos", "proximos"];
    const ok = claves.every(k => corte.summary[k] === s[k]);
    return ok ? " · coinciden con el consolidado publicado" : " · ATENCIÓN: no coinciden con el resumen del consolidado";
  }
  function base64(b64) {
    const bin = atob(b64.trim());
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out.buffer;
  }

  // ------------------------------------------------------------------ calidad y carga
  function vistaCalidad(a) {
    const corte = st.norm[st.cut];
    const inc = corte.incidents || [];
    const entrada = st.index && st.index.cuts && !esIntermedio(st.cut) ? st.index.cuts.find(c => c.cut === corte.cut) : null;
    const capturada = corte.capturedAt || (entrada && entrada.capturedAt);
    const sinDatos = new Set(inc.filter(i => i.level === "bloqueante" && ["area_sin_datos", "archivo_ausente", "archivo_ilegible", "tabla_ausente", "encabezados_alterados"].includes(i.code)).map(i => i.area));
    let html = '<div class="grid g2"><section class="card"><div class="card__head"><h2 class="card__title" style="margin:0">Estado del corte</h2><span class="card__sub"><span class="dot ' + estadoDe(st.cut) + '"></span> ' + esc(ESTADOS_TXT[estadoDe(st.cut)]) + '</span></div><div class="card__body"><dl class="kv">'
      + "<dt>" + (esIntermedio(st.cut) ? "Actualización" : "Corte") + "</dt><dd>" + esc(esIntermedio(st.cut) ? M.momentoSlot(st.cut) : "Viernes " + ft(corte.cut) + " a las 12:00") + " (hora de Santiago)</dd>"
      + "<dt>Comparado con</dt><dd>" + (corte.previousRows ? "Corte del " + ft(corte.from) : "Sin corte anterior (línea base)") + "</dd>"
      + "<dt>Captura</dt><dd>" + (capturada ? esc(momentoTexto(capturada)) : st.manual.has(st.cut) ? "Carga manual en el navegador" : "Sin registro") + "</dd>"
      + "<dt>Registros válidos</dt><dd>" + corte.rows.length + (corte.rows.some(r => r.held) ? " (incluye " + corte.rows.filter(r => r.held).length + " con versión anterior)" : "") + "</dd>"
      + "<dt>Filas excluidas</dt><dd>" + (corte.rejected || []).length + "</dd>"
      + "<dt>Cobertura</dt><dd>" + modelo.areas.map(x => (sinDatos.has(x.prefix) ? "✗ " : "✓ ") + esc(x.prefix)).join(" · ") + "</dd>"
      + (corte.approval ? "<dt>Aprobación</dt><dd>" + esc(corte.approval.by) + " · " + esc(momentoTexto(corte.approval.at)) + "<br>" + esc(corte.approval.reason) + "</dd>" : "")
      + "</dl>";
    if (entrada && entrada.files && (st.origin === "procesador" || st.origin === "http")) {
      html += '<div class="sub">Archivos del corte</div><div class="toolbar">' + [["minuta", "Minuta en Word"], ["detalle", "Detalle completo (Excel)"], ["corte", "Consolidado (JSON)"], ["manifiesto", "Manifiesto"]]
        .map(([k, t]) => '<a class="btn" href="' + esc(entrada.files[k]) + '" download>' + t + "</a>").join("") + "</div>";
    }
    html += '</div></section><section class="card"><div class="card__head"><h2 class="card__title" style="margin:0">Incidencias</h2><span class="card__sub">' + inc.filter(i => i.level === "bloqueante").length + " bloquean · " + inc.filter(i => i.level === "observacion").length + ' observaciones</span></div><div class="card__body">'
      + (inc.length ? '<ul class="inc">' + inc.map(i => '<li><span class="lvl ' + i.level + '">' + (i.level === "bloqueante" ? "Bloquea" : "Observación") + "</span><span><strong>" + esc(i.area || "General") + "</strong> · " + esc(i.message) + "</span></li>").join("") + "</ul>" : '<p class="empty-note">Sin incidencias. Los cuatro registros se leyeron completos.</p>')
      + "</div></section></div>";
    // Historial
    const cortes = cortesOrdenados().slice().reverse();
    html += '<section class="card" style="margin-top:16px"><div class="card__head"><h2 class="card__title" style="margin:0">Historial de cortes</h2><span class="card__sub">' + cortes.length + ' disponibles · clic en una fila para verla</span></div><div class="card__body" style="padding:0"><div style="overflow:auto"><table><thead><tr><th>Corte</th><th>Estado</th><th>Ingresos</th><th>Entregas</th><th>Avances</th><th>Abiertos</th><th>Atrasados o bloqueados</th><th>Incidencias</th></tr></thead><tbody>'
      + cortes.map(c => {
        const x = st.cache[c] || (st.cache[c] = M.analizar(modelo, st.norm[c]));
        const s = x.summary;
        return '<tr data-cut="' + c + '"' + (c === st.cut ? ' style="background:var(--c-blue-soft)"' : "") + '><td class="nowrap"><strong>' + esc(etiquetaClave(c)) + '</strong></td><td><span class="dot ' + estadoDe(c) + '"></span> ' + esc(ESTADOS_TXT[estadoDe(c)]) + '</td><td class="tnum">' + s.ingresos + '</td><td class="tnum">' + s.entregas + '</td><td class="tnum">' + s.avances + '</td><td class="tnum">' + s.abiertos + '</td><td class="tnum">' + x.rows.filter(f => f.active && (f.late || f.blocked)).length + '</td><td class="tnum">' + (st.norm[c].incidents || []).length + "</td></tr>";
      }).join("") + "</tbody></table></div></div></section>";
    // Carga manual
    if (st.origin === "carpeta" && st.carpeta) {
      const c = st.carpeta;
      html += '<section class="card" style="margin-top:16px"><div class="card__head"><h2 class="card__title" style="margin:0">Capturas recibidas</h2><span class="card__sub">' + M.plural(c.turnos.length, "captura") + '</span></div><div class="card__body"><dl class="kv">'
        + "<dt>Carpeta</dt><dd>" + esc(c.nombre || "seleccionada") + "</dd>"
        + "<dt>Revisada</dt><dd>" + esc(momentoTexto(c.leidaEn)) + "</dd>"
        + "<dt>Primera captura</dt><dd>" + esc(M.momentoSlot(c.turnos[0])) + "</dd>"
        + "<dt>Última captura</dt><dd>" + esc(M.momentoSlot(c.turnos[c.turnos.length - 1])) + "</dd>"
        + "<dt>Cortes semanales</dt><dd>" + cortesOrdenados().filter(k => !esIntermedio(k)).length + "</dd>"
        + "</dl>" + (c.errores.length ? '<ul class="inc" style="margin-top:10px">' + c.errores.map(e => '<li><span class="lvl bloqueante">Error</span><span>' + esc(e) + "</span></li>").join("") + "</ul>" : "")
        + '<div class="toolbar" style="margin-top:12px"><button class="btn primary" data-act="actualizar">↻ Actualizar ahora</button>' + (st.automatico ? "" : '<button class="btn" data-act="carpeta">Cambiar carpeta</button>') + "</div></div></section>";
    }
    const puedeGuardar = st.manual.has(st.cut) && corte.status !== "en_revision";
    html += '<details class="adv"' + (st.manual.size || st.origin === "manual" ? " open" : "") + '><summary>Opciones avanzadas: carga manual de respaldo (solo si la captura automática falla)</summary>'
      + '<section class="card"><div class="card__head"><h2 class="card__title" style="margin:0">Carga manual (respaldo)</h2><span class="card__sub">para pruebas o si la automatización no corre</span></div><div class="card__body">'
      + '<p style="margin:0 0 12px;font-size:13px;color:var(--ink-2)">Selecciona las tres copias de los Excel tomadas al corte del viernes a las 12:00. El tablero las compara con el último corte válido cargado anterior a esa fecha y genera la misma minuta que la automatización.</p>'
      + '<div style="display:flex;gap:14px;flex-wrap:wrap;align-items:end"><label class="field">Fecha de corte (viernes)<input type="date" id="manual-cut" value="' + corteEsperado() + '"></label>'
      + '<div class="drop" id="drop" style="flex:1;min-width:260px">Arrastra aquí los tres Excel o <button class="linkbtn" data-act="xlsx">selecciónalos</button></div></div>'
      + '<div class="toolbar" style="margin-top:12px"><button class="btn" data-act="json">Abrir consolidado (.json)</button><button class="btn" data-act="guardar"' + (puedeGuardar ? "" : " disabled") + '>Guardar consolidado del corte seleccionado</button><span class="status-msg" id="manual-status">'
      + (st.manual.has(st.cut) && !puedeGuardar ? "El corte está en revisión: corrige las incidencias antes de guardarlo." : "") + "</span></div></div></section></details>";
    return html;
  }

  // ------------------------------------------------------------------ acciones
  async function cargarExcel(archivos) {
    const msg = $("manual-status");
    const cutInput = $("manual-cut");
    const cut = cutInput ? cutInput.value : corteEsperado();
    try {
      if (!M.fechaValida(cut) || !M.esViernes(cut)) throw new Error("La fecha de corte debe ser un viernes.");
      if (msg) msg.textContent = "Leyendo " + archivos.length + " archivos…";
      const lectura = await DEPPLectorXlsx.leerArchivos(modelo, M, archivos);
      const previos = cortesOrdenados().filter(c => fechaClave(c) < cut && !esIntermedio(c) && st.norm[c].status !== "en_revision");
      const anterior = previos.length ? st.norm[previos[previos.length - 1]] : null;
      const corte = M.construirCorte(modelo, lectura, cut, anterior, null);
      if (!st.origin) st.origin = "manual";
      st.cut = agregarCorte(corte, true);
      st.view = "calidad";
      render();
      const m2 = $("manual-status");
      if (m2) m2.textContent = "Corte armado con " + lectura.files.length + " archivos" + (anterior ? ", comparado con el corte del " + ft(anterior.cut) : ", sin corte anterior (línea base)") + ".";
    } catch (e) {
      if (msg) msg.textContent = e.message; else alertaSimple(e.message);
    }
  }
  function alertaSimple(texto) {
    $("banners").insertAdjacentHTML("afterbegin", '<div class="banner bad">' + esc(texto) + "</div>");
  }
  async function abrirJSON(archivo) {
    try {
      const raw = JSON.parse(await archivo.text());
      if (!st.origin) st.origin = "manual";
      st.cut = agregarCorte(raw, false);
      render();
    } catch (e) {
      alertaSimple(e.message || "No se pudo leer el consolidado.");
    }
  }
  function csv() {
    const filas = filtrar(analisis());
    const cab = ["Referencia", "Equipo", ...modelo.fields.slice(1).map(f => f[1]), "Movimiento en el período", "Alertas"];
    const q = v => '"' + String(v ?? "").replace(/"/g, '""') + '"';
    const lineas = [cab.map(q).join(";")].concat(filas.map(f => [f.id, AREAS.get(f.area).name, ft(f.received), f.request, f.product, f.kind, f.requester, f.owner, ft(f.due), f.state, ft(f.delivered), f.notes,
      [f.receivedNow && "Ingreso", f.deliveredNow && "Entrega", f.advancedNow && "Avance"].filter(Boolean).join(", "),
      [f.late && "Vencido", f.blocked && f.active && "Bloqueado", f.support && (f.decision ? "Decisión" : "Apoyo")].filter(Boolean).join(", ")].map(q).join(";")));
    descargar(new Blob(["﻿" + lineas.join("\r\n")], { type: "text/csv;charset=utf-8" }), "Compromisos_DEPP_" + nombreArchivo() + ".csv");
  }
  function nombreArchivo() { return esIntermedio(st.cut) ? st.cut : fechaClave(st.cut); }
  async function accion(e) {
    const act = e.currentTarget.dataset.act;
    if (act === "carpeta") conectarCarpeta();
    else if (act === "carpeta-alt") $("file-dir").click();
    else if (act === "actualizar") refrescar();
    else if (act === "volver") volver();
    else if (act === "reintentar") { estadoCarpeta("Buscando capturas…"); if (!(await cargarAutomatico())) { render(); estadoCarpeta("Sigo sin encontrar capturas junto a este archivo.", "warn"); } }
    else if (act === "ir-semanal") { st.cut = e.currentTarget.dataset.k; render(); window.scrollTo(0, 0); }
    else if (act === "xlsx") $("file-xlsx").click();
    else if (act === "json") $("file-json").click();
    else if (act === "limpiar") ir({ view: "compromisos", filters: FILTROS_VACIOS });
    else if (act === "csv") csv();
    else if (act === "imprimir") window.print();
    else if (act === "copiar") {
      const texto = minutaTexto(M.minuta(modelo, st.norm[st.cut], st.full));
      try { await navigator.clipboard.writeText(texto); $("minuta-status").textContent = "Minuta copiada al portapapeles."; }
      catch (err) { $("minuta-status").textContent = "El navegador no permitió copiar. Usa «Descargar Word»."; }
    } else if (act === "word") {
      const m = M.minuta(modelo, st.norm[st.cut], st.full);
      const blob = await DEPPDocx.escribir(m, base64(document.getElementById("plantilla-docx").textContent));
      descargar(new Blob([blob], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }), "Minuta_DEPP_" + nombreArchivo() + (st.full ? "_detalle" : "") + ".docx");
      $("minuta-status").textContent = "Minuta descargada. Revísala antes de remitirla a Gabinete SPD.";
    } else if (act === "guardar") {
      descargar(new Blob([JSON.stringify(st.raw[st.cut], null, 1)], { type: "application/json" }), "Corte_DEPP_" + nombreArchivo() + ".json");
    }
  }
  function enlazarVista() {
    const page = $("page");
    for (const b of page.querySelectorAll("[data-act]")) b.addEventListener("click", accion);
    for (const b of page.querySelectorAll("[data-open]")) {
      b.addEventListener("click", () => abrirFicha(b.dataset.open));
      if (b.tagName === "TR") b.addEventListener("keydown", e => { if (e.key === "Enter") abrirFicha(b.dataset.open); });
    }
    for (const b of page.querySelectorAll("[data-preset]")) b.addEventListener("click", () => ir({ view: "compromisos", filters: { view: b.dataset.preset } }));
    for (const b of page.querySelectorAll("[data-area]")) b.addEventListener("click", () => ir({ view: "compromisos", filters: { area: b.dataset.area, view: "abiertos" } }));
    for (const b of page.querySelectorAll("[data-full]")) b.addEventListener("click", () => { st.full = b.dataset.full === "1"; render(); });
    for (const r of page.querySelectorAll("tr[data-cut]")) r.addEventListener("click", () => { st.cut = r.dataset.cut; ir({ view: "resumen" }); });
    for (const el of page.querySelectorAll("[data-f]")) {
      const ev = el.tagName === "INPUT" ? "input" : "change";
      el.addEventListener(ev, () => {
        st.filters[el.dataset.f] = el.value;
        const pos = el.selectionStart;
        if (history.state && history.state.depp) history.replaceState(estadoNav(), "", location.hash);
        render();
        if (el.tagName === "INPUT") { const n = $("page").querySelector('[data-f="q"]'); n.focus(); n.setSelectionRange(pos, pos); }
      });
    }
    const drop = $("drop");
    if (drop) {
      drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
      drop.addEventListener("dragleave", () => drop.classList.remove("over"));
      drop.addEventListener("drop", e => { e.preventDefault(); drop.classList.remove("over"); const fs = Array.from(e.dataTransfer.files).filter(f => /\.xlsx$/i.test(f.name)); if (fs.length) cargarExcel(fs); });
    }
  }

  /** Botón «↻ Actualizar»: vuelve a leer las capturas sin recargar la página. */
  async function refrescar() {
    const b = $("btn-actualizar");
    b.disabled = true; b.textContent = "Actualizando…";
    try {
      if (st.automatico) { st.cutPrevio = st.cut; await cargarAutomatico(); }
      else await actualizarCarpeta();
    } finally { b.disabled = false; b.textContent = "↻ Actualizar"; }
  }

  // ------------------------------------------------------------------ arranque
  async function iniciar() {
    $("version-label").textContent = "Versión 1.1 · formato " + M.FORMATO;
    for (const b of document.querySelectorAll(".nav__item")) b.addEventListener("click", () => { if (b.dataset.view !== st.view || st.panel) ir({ view: b.dataset.view }); });
    $("logo-inicio").addEventListener("click", () => ir({ view: "resumen", filters: FILTROS_VACIOS }));
    $("btn-volver").addEventListener("click", volver);
    $("btn-ayuda").addEventListener("click", () => { if (st.panel !== "ayuda") abrirAyuda(); });
    window.addEventListener("popstate", alVolverHistorial);
    document.addEventListener("keydown", e => { if (e.key === "Escape" && st.panel) cerrarPanelUsuario(); });
    // Al abrir (o recargar) se parte en la sección que indique la dirección, p. ej. …/Tablero_DEPP.html#minuta.
    const inicial = location.hash.slice(1);
    if (VISTAS[inicial]) st.view = inicial;
    history.replaceState(Object.assign(estadoNav(), { i: 0 }), "", location.hash || "#" + st.view);
    $("cut-select").addEventListener("change", e => { st.cut = e.target.value; render(); });
    $("file-xlsx").addEventListener("change", e => { const fs = Array.from(e.target.files); e.target.value = ""; if (fs.length) cargarExcel(fs); });
    $("file-json").addEventListener("change", e => { const f = e.target.files[0]; e.target.value = ""; if (f) abrirJSON(f); });
    $("file-dir").addEventListener("change", async e => {
      const fs = Array.from(e.target.files);
      e.target.value = "";
      if (!fs.length) { estadoCarpeta("La carpeta elegida no tiene archivos o el navegador no los entregó.", "warn"); return; }
      const nombre = (fs[0].webkitRelativePath || "").split("/")[0];
      estadoCarpeta("Recibí " + M.plural(fs.length, "archivo") + " de «" + nombre + "». Procesando…");
      try { await procesarCapturas(entradasDesdeLista(fs), nombre); }
      catch (err) { console.error(err); estadoCarpeta(err.message, "bad"); }
    });
    $("btn-actualizar").addEventListener("click", refrescar);
    if (embebidos) cargarEmbebidos(embebidos);
    else if (/^https?:$/.test(location.protocol) && await cargarRemoto()) { /* datos publicados en el servidor */ }
    else if (location.protocol === "file:" && await cargarAutomatico()) return;
    else if (location.protocol === "file:" && /(\/Capturas\/|Tablero_DEPP\.html$)/i.test(decodeURIComponent(location.pathname))) st.sinCapturas = true;
    else {
      const h = await idb.get("carpeta");
      if (h && h.queryPermission) {
        if (await h.queryPermission({ mode: "read" }) === "granted") { await leerHandle(h); return; }
        st.carpetaPendiente = h.name;
      }
    }
    render();
  }
  iniciar();
})();
