"""Escribe la minuta semanal en Word sobre la plantilla institucional.

El XML que produce es idéntico al de tablero/src/docx.js para la misma minuta
(pruebas/test_paridad.py lo verifica). Ambos usan plantillas/base_minuta_depp.docx.
"""
from __future__ import annotations

import pathlib
import re
import zipfile

FECHA_ZIP = (2026, 1, 1, 0, 0, 0)


def esc(texto) -> str:
    return str(texto or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _t(texto):
    return '<w:t xml:space="preserve">' + esc(texto) + "</w:t>"


def _ref(n):
    return f'<w:r><w:rPr><w:rStyle w:val="Refdenotaalpie"/></w:rPr><w:footnoteReference w:id="{n}"/></w:r>'


def p_centrado(texto, negrita=True):
    rpr = "<w:rPr><w:b/></w:rPr>" if negrita else ""
    return ('<w:p><w:pPr><w:keepNext/><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr>'
            f"<w:r>{rpr}{_t(texto)}</w:r></w:p>")


def p_titulo(texto):
    return ('<w:p><w:pPr><w:pStyle w:val="Ttulo"/><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr>'
            f"<w:r><w:rPr><w:b/></w:rPr>{_t(texto)}</w:r></w:p>")


def p_vacio():
    return '<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr></w:p>'


def p_banda(texto):
    return ('<w:p><w:pPr><w:pStyle w:val="Ttulo1"/><w:keepNext/><w:shd w:val="clear" w:color="auto" w:fill="0E2841"/>'
            '<w:spacing w:before="160" w:after="80"/><w:ind w:firstLine="96"/></w:pPr>'
            f'<w:r><w:rPr><w:b/><w:color w:val="FFFFFF"/></w:rPr>{_t(texto)}</w:r></w:p>')


def p_texto(texto, notas=()):
    refs = "".join(_ref(n) for n in notas)
    return ('<w:p><w:pPr><w:spacing w:after="100" w:line="240" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr>'
            f"<w:r>{_t(texto)}</w:r>{refs}</w:p>")


def p_grupo(titulo, conteo):
    return ('<w:p><w:pPr><w:keepNext/><w:spacing w:before="80" w:after="40"/><w:jc w:val="both"/></w:pPr>'
            f"<w:r><w:rPr><w:b/></w:rPr>{_t(titulo)}</w:r>"
            f'<w:r><w:rPr><w:color w:val="404040"/><w:sz w:val="16"/></w:rPr>{_t(" · " + conteo)}</w:r></w:p>')


def p_vineta(lead, texto):
    return ('<w:p><w:pPr><w:pStyle w:val="Sinespaciado"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="5"/></w:numPr>'
            '<w:spacing w:after="60"/><w:ind w:left="360"/><w:jc w:val="both"/></w:pPr>'
            f"<w:r><w:rPr><w:b/></w:rPr>{_t(lead)}</w:r><w:r>{_t(' ' + texto)}</w:r></w:p>")


def p_nota(texto):
    return ('<w:p><w:pPr><w:spacing w:after="80"/><w:ind w:left="360"/><w:jc w:val="both"/></w:pPr>'
            f'<w:r><w:rPr><w:i/><w:sz w:val="16"/></w:rPr>{_t(texto)}</w:r></w:p>')


def nota_pie(n, texto):
    return (f'<w:footnote w:id="{n}"><w:p><w:pPr><w:pStyle w:val="Textonotapie"/><w:jc w:val="both"/></w:pPr>'
            '<w:r><w:rPr><w:rStyle w:val="Refdenotaalpie"/></w:rPr><w:footnoteRef/></w:r>'
            '<w:r><w:rPr><w:rFonts w:ascii="Verdana" w:hAnsi="Verdana" w:cs="Verdana"/><w:sz w:val="14"/></w:rPr>'
            f"{_t(' ' + texto)}</w:r></w:p></w:footnote>")


def cuerpo_minuta(m):
    """Devuelve (xml_del_cuerpo, xml_de_notas_al_pie) para una minuta del motor."""
    partes = [p_centrado(m["kind"])]
    if m.get("draft"):
        partes.append(p_centrado("BORRADOR · CORTE EN REVISIÓN"))
    partes += [p_titulo(m["title"]), p_centrado(m["recipient"], negrita=False), p_vacio()]
    notas = list(m.get("notes") or [])
    ids = list(range(1, len(notas) + 1))
    for i, sec in enumerate(m["sections"], start=1):
        partes.append(p_banda(f"{i}. {sec['title'].upper()}"))
        for j, parrafo in enumerate(sec.get("paragraphs") or []):
            partes.append(p_texto(parrafo, ids if (i == 1 and j == 0) else ()))
        for g in sec.get("groups") or []:
            partes.append(p_grupo(g["title"], g["counts"]))
            for it in g["items"]:
                partes.append(p_vineta(it["lead"], it["text"]))
            if g.get("note"):
                partes.append(p_nota(g["note"]))
        for it in sec.get("items") or []:
            partes.append(p_vineta(it["lead"], it["text"]))
        if sec.get("note"):
            partes.append(p_nota(sec["note"]))
    pies = "".join(nota_pie(n, t) for n, t in zip(ids, notas))
    return "".join(partes), pies


def escribir(m, plantilla: pathlib.Path, salida: pathlib.Path):
    cuerpo, pies = cuerpo_minuta(m)
    with zipfile.ZipFile(plantilla) as z:
        partes = {n: z.read(n) for n in z.namelist()}
    doc = partes["word/document.xml"].decode("utf-8")
    inicio = doc.index("<w:body>") + len("<w:body>")
    sect = doc.rindex("<w:sectPr")
    partes["word/document.xml"] = (doc[:inicio] + cuerpo + doc[sect:]).encode("utf-8")
    fn = partes["word/footnotes.xml"].decode("utf-8")
    fn = re.sub(r'<w:footnote w:id="[1-9]\d*">.*?</w:footnote>', "", fn, flags=re.S)
    fn = fn.replace("</w:footnotes>", pies + "</w:footnotes>")
    partes["word/footnotes.xml"] = fn.encode("utf-8")
    salida.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, datos in partes.items():
            info = zipfile.ZipInfo(nombre, FECHA_ZIP)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, datos)
    return salida
