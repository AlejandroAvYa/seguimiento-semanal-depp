/* docx.js · Minuta semanal en Word desde el tablero.
 * Produce el mismo XML que procesador/depp_corte/minuta_docx.py (prueba de paridad).
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.DEPPDocx = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  const esc = t => String(t ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const t = texto => '<w:t xml:space="preserve">' + esc(texto) + "</w:t>";
  const ref = n => '<w:r><w:rPr><w:rStyle w:val="Refdenotaalpie"/></w:rPr><w:footnoteReference w:id="' + n + '"/></w:r>';

  const pCentrado = (texto, negrita = true) =>
    '<w:p><w:pPr><w:keepNext/><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr>'
    + "<w:r>" + (negrita ? "<w:rPr><w:b/></w:rPr>" : "") + t(texto) + "</w:r></w:p>";
  const pTitulo = texto =>
    '<w:p><w:pPr><w:pStyle w:val="Ttulo"/><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr>'
    + "<w:r><w:rPr><w:b/></w:rPr>" + t(texto) + "</w:r></w:p>";
  const pVacio = () => '<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr></w:p>';
  const pBanda = texto =>
    '<w:p><w:pPr><w:pStyle w:val="Ttulo1"/><w:keepNext/><w:shd w:val="clear" w:color="auto" w:fill="0E2841"/>'
    + '<w:spacing w:before="160" w:after="80"/><w:ind w:firstLine="96"/></w:pPr>'
    + '<w:r><w:rPr><w:b/><w:color w:val="FFFFFF"/></w:rPr>' + t(texto) + "</w:r></w:p>";
  const pTexto = (texto, notas = []) =>
    '<w:p><w:pPr><w:spacing w:after="100" w:line="240" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr>'
    + "<w:r>" + t(texto) + "</w:r>" + notas.map(ref).join("") + "</w:p>";
  const pGrupo = (titulo, conteo) =>
    '<w:p><w:pPr><w:keepNext/><w:spacing w:before="80" w:after="40"/><w:jc w:val="both"/></w:pPr>'
    + "<w:r><w:rPr><w:b/></w:rPr>" + t(titulo) + "</w:r>"
    + '<w:r><w:rPr><w:color w:val="404040"/><w:sz w:val="16"/></w:rPr>' + t(" · " + conteo) + "</w:r></w:p>";
  const pVineta = (lead, texto) =>
    '<w:p><w:pPr><w:pStyle w:val="Sinespaciado"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="5"/></w:numPr>'
    + '<w:spacing w:after="60"/><w:ind w:left="360"/><w:jc w:val="both"/></w:pPr>'
    + "<w:r><w:rPr><w:b/></w:rPr>" + t(lead) + "</w:r><w:r>" + t(" " + texto) + "</w:r></w:p>";
  const pNota = texto =>
    '<w:p><w:pPr><w:spacing w:after="80"/><w:ind w:left="360"/><w:jc w:val="both"/></w:pPr>'
    + '<w:r><w:rPr><w:i/><w:sz w:val="16"/></w:rPr>' + t(texto) + "</w:r></w:p>";
  const notaPie = (n, texto) =>
    '<w:footnote w:id="' + n + '"><w:p><w:pPr><w:pStyle w:val="Textonotapie"/><w:jc w:val="both"/></w:pPr>'
    + '<w:r><w:rPr><w:rStyle w:val="Refdenotaalpie"/></w:rPr><w:footnoteRef/></w:r>'
    + '<w:r><w:rPr><w:rFonts w:ascii="Verdana" w:hAnsi="Verdana" w:cs="Verdana"/><w:sz w:val="14"/></w:rPr>'
    + t(" " + texto) + "</w:r></w:p></w:footnote>";

  function cuerpoMinuta(m) {
    const partes = [pCentrado(m.kind)];
    if (m.draft) partes.push(pCentrado(m.draftLabel || "BORRADOR · CORTE EN REVISIÓN"));
    partes.push(pTitulo(m.title), pCentrado(m.recipient, false), pVacio());
    const notas = m.notes || [];
    const ids = notas.map((_, i) => i + 1);
    m.sections.forEach((sec, k) => {
      const i = k + 1;
      partes.push(pBanda(i + ". " + sec.title.toUpperCase()));
      (sec.paragraphs || []).forEach((p, j) => partes.push(pTexto(p, i === 1 && j === 0 ? ids : [])));
      for (const g of sec.groups || []) {
        partes.push(pGrupo(g.title, g.counts));
        for (const it of g.items) partes.push(pVineta(it.lead, it.text));
        if (g.note) partes.push(pNota(g.note));
      }
      for (const it of sec.items || []) partes.push(pVineta(it.lead, it.text));
      if (sec.note) partes.push(pNota(sec.note));
    });
    return [partes.join(""), ids.map((n, i) => notaPie(n, notas[i])).join("")];
  }

  /** plantilla: ArrayBuffer de base_minuta_depp.docx. Devuelve un Blob .docx. */
  async function escribir(m, plantilla) {
    const zip = DEPPZip.abrir(plantilla);
    const dec = new TextDecoder();
    const enc = new TextEncoder();
    const [cuerpo, pies] = cuerpoMinuta(m);
    const partes = [];
    for (const nombre of zip.nombres()) {
      let datos = await zip.leer(nombre);
      if (nombre === "word/document.xml") {
        const doc = dec.decode(datos);
        const ini = doc.indexOf("<w:body>") + "<w:body>".length;
        const sect = doc.lastIndexOf("<w:sectPr");
        datos = enc.encode(doc.slice(0, ini) + cuerpo + doc.slice(sect));
      } else if (nombre === "word/footnotes.xml") {
        const fn = dec.decode(datos).replace(/<w:footnote w:id="[1-9]\d*">[\s\S]*?<\/w:footnote>/g, "");
        datos = enc.encode(fn.replace("</w:footnotes>", pies + "</w:footnotes>"));
      }
      partes.push([nombre, datos]);
    }
    return DEPPZip.escribir(partes);
  }

  return { cuerpoMinuta, escribir };
});
