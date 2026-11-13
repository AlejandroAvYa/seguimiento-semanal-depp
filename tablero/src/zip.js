/* zip.js · Lectura y escritura mínima de ZIP para .xlsx y .docx en el navegador. */
(function (root) {
  "use strict";
  const utf8 = new TextDecoder();

  /** Devuelve una función async leer(nombre, opcional) sobre el contenido del ZIP. */
  function abrir(buffer) {
    const bytes = new Uint8Array(buffer);
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const word = i => view.getUint16(i, true);
    const num = i => view.getUint32(i, true);
    let fin = bytes.length - 22;
    const minimo = Math.max(0, fin - 65535);
    while (fin >= minimo && (num(fin) !== 0x06054b50 || fin + 22 + word(fin + 20) !== bytes.length)) fin--;
    if (fin < minimo || word(fin + 4) || word(fin + 6)) throw new Error("El archivo no es un documento de Office válido.");
    const entradas = new Map();
    let i = num(fin + 16);
    for (let k = 0; k < word(fin + 10); k++) {
      if (i + 46 > fin || num(i) !== 0x02014b50) throw new Error("La estructura del archivo no es válida.");
      const largoNombre = word(i + 28);
      const largo = 46 + largoNombre + word(i + 30) + word(i + 32);
      const nombre = utf8.decode(bytes.subarray(i + 46, i + 46 + largoNombre));
      entradas.set(nombre, { metodo: word(i + 10), tam: num(i + 20), expandido: num(i + 24), local: num(i + 42) });
      i += largo;
    }
    async function leer(nombre, opcional) {
      const e = entradas.get(nombre);
      if (!e && opcional) return null;
      if (!e || num(e.local) !== 0x04034b50) throw new Error("Falta una parte del archivo (" + nombre + ").");
      const inicio = e.local + 30 + word(e.local + 26) + word(e.local + 28);
      if (inicio + e.tam > fin || e.expandido > 32000000) throw new Error("Una parte del archivo está dañada o es demasiado grande.");
      const comprimido = bytes.subarray(inicio, inicio + e.tam);
      if (e.metodo === 0) return comprimido;
      if (e.metodo !== 8 || typeof DecompressionStream === "undefined") {
        throw new Error("Abre el tablero con Chrome o Edge actualizado y usa archivos sin contraseña.");
      }
      const lector = new Blob([comprimido]).stream().pipeThrough(new DecompressionStream("deflate-raw")).getReader();
      const salida = new Uint8Array(e.expandido);
      let escrito = 0;
      try {
        while (true) {
          const { done, value } = await lector.read();
          if (done) break;
          if (escrito + value.length > salida.length) throw new Error("El contenido del archivo está dañado.");
          salida.set(value, escrito);
          escrito += value.length;
        }
      } finally {
        await lector.cancel().catch(() => {});
      }
      if (escrito !== salida.length) throw new Error("El contenido del archivo está incompleto.");
      return salida;
    }
    return { leer, nombres: () => Array.from(entradas.keys()) };
  }

  let tablaCRC = null;
  function crc32(datos) {
    if (!tablaCRC) {
      tablaCRC = new Uint32Array(256);
      for (let n = 0; n < 256; n++) {
        let c = n;
        for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
        tablaCRC[n] = c >>> 0;
      }
    }
    let crc = 0xffffffff;
    for (let i = 0; i < datos.length; i++) crc = tablaCRC[(crc ^ datos[i]) & 0xff] ^ (crc >>> 8);
    return (crc ^ 0xffffffff) >>> 0;
  }

  /** Escribe un ZIP sin compresión. partes: [[nombre, Uint8Array]]. */
  function escribir(partes) {
    const enc = new TextEncoder();
    const locales = [];
    const centrales = [];
    let desplazamiento = 0;
    const fecha = ((2026 - 1980) << 9) | (1 << 5) | 1;
    for (const [nombre, datos] of partes) {
      const n = enc.encode(nombre);
      const crc = crc32(datos);
      const cab = new DataView(new ArrayBuffer(30));
      cab.setUint32(0, 0x04034b50, true); cab.setUint16(4, 20, true); cab.setUint16(6, 0x0800, true);
      cab.setUint16(8, 0, true); cab.setUint16(10, 0, true); cab.setUint16(12, fecha, true);
      cab.setUint32(14, crc, true); cab.setUint32(18, datos.length, true); cab.setUint32(22, datos.length, true);
      cab.setUint16(26, n.length, true); cab.setUint16(28, 0, true);
      locales.push(new Uint8Array(cab.buffer), n, datos);
      const cen = new DataView(new ArrayBuffer(46));
      cen.setUint32(0, 0x02014b50, true); cen.setUint16(4, 20, true); cen.setUint16(6, 20, true); cen.setUint16(8, 0x0800, true);
      cen.setUint16(10, 0, true); cen.setUint16(12, 0, true); cen.setUint16(14, fecha, true);
      cen.setUint32(16, crc, true); cen.setUint32(20, datos.length, true); cen.setUint32(24, datos.length, true);
      cen.setUint16(28, n.length, true); cen.setUint32(42, desplazamiento, true);
      centrales.push(new Uint8Array(cen.buffer), n);
      desplazamiento += 30 + n.length + datos.length;
    }
    const largoCentral = centrales.reduce((s, b) => s + b.length, 0);
    const finCab = new DataView(new ArrayBuffer(22));
    finCab.setUint32(0, 0x06054b50, true);
    finCab.setUint16(8, partes.length, true); finCab.setUint16(10, partes.length, true);
    finCab.setUint32(12, largoCentral, true); finCab.setUint32(16, desplazamiento, true);
    return new Blob([...locales, ...centrales, new Uint8Array(finCab.buffer)]);
  }

  root.DEPPZip = { abrir, escribir, crc32 };
})(typeof self !== "undefined" ? self : this);
