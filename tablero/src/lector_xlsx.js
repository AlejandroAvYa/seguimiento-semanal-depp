/* lector_xlsx.js · Carga manual de las planillas DEPP en el navegador (respaldo). */
(function (root) {
  "use strict";
  const utf8 = new TextDecoder();

  function nodos(el, nombre) { return Array.from(el.getElementsByTagNameNS("*", nombre)); }
  function xml(bytes, nombre) {
    const doc = new DOMParser().parseFromString(utf8.decode(bytes), "application/xml");
    if (nodos(doc, "parsererror").length) throw new Error("No se pudo leer " + nombre + ".");
    return doc;
  }
  function textoCelda(c, compartidos) {
    if (c.getAttribute("t") === "inlineStr") return nodos(c, "t").map(t => t.textContent).join("");
    const v = nodos(c, "v")[0]?.textContent ?? "";
    return c.getAttribute("t") === "s" ? compartidos[Number(v)] ?? "" : v;
  }
  function columna(ref) {
    const letras = /^[A-Z]+/.exec(ref ?? "")?.[0] ?? "";
    return Array.from(letras).reduce((s, l) => s * 26 + l.charCodeAt(0) - 64, 0) - 1;
  }
  function ruta(base, destino) {
    if (!destino) return "";
    if (destino.startsWith("/")) return destino.slice(1);
    const partes = base.split("/").slice(0, -1);
    for (const p of destino.split("/")) {
      if (p === "..") partes.pop(); else if (p !== ".") partes.push(p);
    }
    return partes.join("/");
  }
  function relaciones(doc) {
    return new Map(nodos(doc, "Relationship").filter(r => r.getAttribute("TargetMode") !== "External")
      .map(r => [r.getAttribute("Id"), r.getAttribute("Target")]));
  }

  /** Lee un .xlsx y devuelve {entries, coverage, problems} con el mismo criterio del procesador. */
  async function leerLibro(modelo, motor, archivo) {
    if (!/\.xlsx$/i.test(archivo.name) || archivo.size > 20000000) throw new Error("Selecciona archivos .xlsx de hasta 20 MB.");
    const zip = DEPPZip.abrir(await archivo.arrayBuffer());
    const [bLibro, bRel, bTextos] = await Promise.all([zip.leer("xl/workbook.xml"), zip.leer("xl/_rels/workbook.xml.rels"), zip.leer("xl/sharedStrings.xml", true)]);
    const libro = xml(bLibro, "la estructura del libro");
    const epoca1904 = ["1", "true"].includes(nodos(libro, "workbookPr")[0]?.getAttribute("date1904"));
    const rels = relaciones(xml(bRel, "las referencias del libro"));
    const compartidos = bTextos ? nodos(xml(bTextos, "los textos del libro"), "si").map(si => nodos(si, "t").map(t => t.textContent).join("")) : [];
    const hojas = new Map(nodos(libro, "sheet").map(h => {
      const id = Array.from(h.attributes).find(a => a.localName === "id")?.value;
      return [h.getAttribute("name"), ruta("xl/workbook.xml", rels.get(id))];
    }));
    const entries = [], coverage = [], problems = [];
    const encabezados = modelo.fields.map(f => f[1]);
    for (const area of modelo.areas) {
      if (!hojas.has(area.tab)) continue;
      const rutaHoja = hojas.get(area.tab);
      const hoja = xml(await zip.leer(rutaHoja), area.tab);
      // Tabla de Excel esperada (Carga_AET, Carga_EE, ...).
      const relHoja = await zip.leer(rutaHoja.replace(/([^/]+)$/, "_rels/$1.rels"), true);
      const tablas = [];
      if (relHoja) {
        for (const destino of relaciones(xml(relHoja, "las referencias de " + area.tab)).values()) {
          if (!/tables\//.test(destino)) continue;
          const t = await zip.leer(ruta(rutaHoja, destino), true);
          if (t) tablas.push(xml(t, "una tabla").documentElement.getAttribute("displayName") || xml(t, "una tabla").documentElement.getAttribute("name"));
        }
      }
      if (!tablas.includes(area.table)) {
        problems.push({ code: "tabla_ausente", area: area.prefix, message: "La pestaña «" + area.tab + "» no contiene la tabla " + area.table + "." });
        continue;
      }
      const filas = nodos(hoja, "row");
      const valores = fila => {
        const v = Array(modelo.fields.length).fill("");
        for (const c of nodos(fila, "c")) {
          const i = columna(c.getAttribute("r"));
          if (i >= 0 && i < v.length) v[i] = textoCelda(c, compartidos);
        }
        return v;
      };
      const cab = filas.find(f => f.getAttribute("r") === "3");
      if (!cab || valores(cab).some((t, i) => t.trim() !== encabezados[i])) {
        problems.push({ code: "encabezados_alterados", area: area.prefix, message: "Los encabezados de «" + area.tab + "» cambiaron. Restituye la fila 3 de la plantilla." });
        continue;
      }
      coverage.push(area.prefix);
      for (const fila of filas) {
        const linea = Number(fila.getAttribute("r"));
        if (linea < 4) continue;
        const v = valores(fila);
        if (!v.slice(1).some(x => x.trim())) continue;
        if (!v[0]) {
          // Si Excel no guardó el valor calculado, el N° está en la fórmula de la plantilla.
          const celdaA = nodos(fila, "c").find(c => columna(c.getAttribute("r")) === 0);
          const m = /,(\d+)\)$/.exec(nodos(celdaA ?? fila, "f")[0]?.textContent ?? "");
          v[0] = m ? m[1] : "";
        }
        entries.push(motor.registro(modelo, v, area, linea, epoca1904));
      }
    }
    if (!coverage.length && !problems.length) throw new Error(archivo.name + " no contiene pestañas de carga DEPP.");
    return { entries, coverage, problems, file: archivo.name };
  }

  async function leerArchivos(modelo, motor, archivos) {
    const libros = await Promise.all(archivos.map(a => leerLibro(modelo, motor, a)));
    const lectura = { entries: [], coverage: [], problems: [], files: [] };
    for (const l of libros) {
      for (const p of l.coverage) {
        if (lectura.coverage.includes(p)) lectura.problems.push({ code: "pestana_repetida", area: p, message: "La pestaña de " + p + " aparece en más de un archivo." });
        else lectura.coverage.push(p);
      }
      lectura.entries.push(...l.entries);
      lectura.problems.push(...l.problems);
      lectura.files.push(l.file);
    }
    return lectura;
  }

  root.DEPPLectorXlsx = { leerArchivos };
})(typeof self !== "undefined" ? self : this);
