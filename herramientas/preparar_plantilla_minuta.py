"""Crea plantillas/base_minuta_depp.docx a partir de un documento en formato SPD.

Toma estilos, numeración y pie de página del documento de origen (por ejemplo, la
metodología DEPP), deja el cuerpo vacío y agrega el logo institucional en el encabezado.
Uso: python herramientas/preparar_plantilla_minuta.py <docx_origen> <logo.png> <salida.docx>
"""
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm

origen, logo, salida = sys.argv[1:4]
doc = Document(origen)
cuerpo = doc.element.body
for hijo in list(cuerpo):
    if not hijo.tag.endswith("}sectPr"):
        cuerpo.remove(hijo)
seccion = doc.sections[0]
seccion.header.is_linked_to_previous = False
p = seccion.header.paragraphs[0]
p.alignment = WD_ALIGN_PARAGRAPH.LEFT
p.add_run().add_picture(logo, width=Cm(2.1))
seccion.header_distance = Cm(0.8)
seccion.top_margin = Cm(3.0)
props = doc.core_properties
props.title = "Minuta semanal DEPP"
props.author = "División de Estudios y Políticas Públicas"
props.comments = ""
props.keywords = ""
props.subject = ""
props.last_modified_by = "DEPP"
props.revision = 1
doc.save(salida)
print("Plantilla creada:", salida)
