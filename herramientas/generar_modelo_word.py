"""Genera plantillas/Modelo_Minuta_Semanal_DEPP.docx: el modelo editable de la minuta.

Usa el mismo escritor que la minuta automática, con textos guía entre corchetes.
"""
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "procesador"))
from depp_corte import minuta_docx  # noqa: E402

modelo = json.loads((RAIZ / "tablero" / "src" / "modelo_depp.json").read_text(encoding="utf-8"))
item = lambda lead, text: {"ref": "", "lead": lead, "text": text}
grupos = [{"title": a["name"], "counts": "[n] entregas · [n] avances · [n] ingresos · [n] abiertos",
           "items": [item("[Producto comprometido].", "Entregado el [dd/mm/aaaa] a [requirente]. [Observación breve, si aporta.]"),
                     item("[Producto comprometido].", "[Estado]. Actualizó [estado, plazo u observaciones]. [Avance o próximo paso.]")],
           "note": "Además: [n] ingresos nuevos (ver detalle completo)."} for a in modelo["areas"]]
m = {
    "kind": "MINUTA",
    "title": "SEGUIMIENTO SEMANAL DE LA DIVISIÓN DE ESTUDIOS Y POLÍTICAS PÚBLICAS (DEPP)",
    "recipient": "Para: Gabinete SPD · Corte del [dd/mm/aaaa]",
    "draft": False,
    "sections": [
        {"title": "Período y resumen", "paragraphs": [
            "Del viernes [dd/mm/aaaa] a las 12:00 al viernes [dd/mm/aaaa] a las 12:00.",
            "En el período se registraron [n] ingresos y [n] entregas, y [n] compromisos tuvieron avance. Al corte hay [n] compromisos abiertos: [n] vencidos, [n] bloqueados y [n] con solicitudes a Gabinete. Vencen [n] compromisos entre el [dd/mm/aaaa] y el [dd/mm/aaaa]."]},
        {"title": "Principales entregas y avances por equipo", "groups": grupos},
        {"title": "Bloqueos y atrasos", "items": [
            item("[Producto comprometido].", "Bloqueado. Vencido desde el [dd/mm/aaaa]. [Responsable], [equipo]. [Causa del bloqueo o del atraso.]")],
         "note": "[Hasta seis compromisos; el resto queda en el detalle completo.]"},
        {"title": "Decisiones y apoyos solicitados a Gabinete", "items": [
            item("Decisión · [Producto comprometido].", "[Decisión que se solicita.] Responsable: [responsable], [equipo]. Plazo: [dd/mm/aaaa]."),
            item("Apoyo · [Producto comprometido].", "[Gestión que se solicita a Gabinete.] Responsable: [responsable], [equipo]. Plazo: [dd/mm/aaaa].")],
         "note": ""},
        {"title": "Próximos vencimientos ([dd/mm/aaaa] al [dd/mm/aaaa])", "items": [
            item("[dd/mm/aaaa].", "[Producto comprometido] · [Responsable] · [Requirente].")], "note": ""},
    ],
    "notes": ["Fuente: planillas de seguimiento de los equipos DEPP, corte del viernes [dd/mm/aaaa] a las 12:00 (hora de Santiago). Un compromiso puede registrar más de un movimiento en el período.",
              "Extensión máxima: dos páginas. La jefatura DEPP revisa la minuta antes de remitirla a Gabinete SPD."],
}
salida = RAIZ / "plantillas" / "Modelo_Minuta_Semanal_DEPP.docx"
minuta_docx.escribir(m, RAIZ / "plantillas" / "base_minuta_depp.docx", salida)
print("Modelo creado:", salida)
