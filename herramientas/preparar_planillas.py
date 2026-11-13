"""Aplica las protecciones, validaciones y la hoja Inicio a las planillas DEPP.

Uso: python herramientas/preparar_planillas.py <carpeta_origen> <carpeta_destino>

Se puede volver a ejecutar sobre las plantillas ya preparadas: el resultado es el mismo.
No modifica datos de registros; está pensado para plantillas vacías.
"""
import copy
import json
import pathlib
import sys

import openpyxl
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation

RAIZ = pathlib.Path(__file__).resolve().parents[1]
MODELO = json.loads((RAIZ / "tablero" / "src" / "modelo_depp.json").read_text(encoding="utf-8"))
PRIMERA, ULTIMA = 4, 1003

INSTRUCCIONES = [
    "1. Abre el Excel en OneDrive y entra a la pestaña de tu unidad. Escribe en la primera fila libre. El N° aparece solo y queda asociado a ese encargo.",
    "2. Completa fecha de ingreso, requerimiento, producto comprometido, tipo de encargo, requirente, responsable y estado. Registra el plazo cuando se acuerde.",
    "3. Actualiza siempre la misma fila. Al enviar el producto, marca Entregado y registra la fecha de entrega efectiva.",
    "4. Usa Observaciones generales para avances, próximos pasos, bloqueos y cambios de plazo. Si cambias el plazo, explica el motivo.",
    "5. Si varias unidades trabajan en un producto, lo registra la que lidera la entrega. Si el producto es periódico, usa una fila por entrega o ciclo.",
    "6. Deja el registro al día antes del viernes a las 12:00, hora de Santiago. A esa hora se toma el corte semanal; lo que se registre después entra en el corte siguiente.",
]
APOYO = [
    "Si necesitas una gestión de Gabinete SPD, inicia la observación con «Apoyo Gabinete:» y describe lo que se requiere. Si se necesita una decisión, usa «Decisión Gabinete:».",
    "Estos compromisos aparecen en la minuta semanal, en la sección de decisiones y apoyos solicitados, mientras sigan abiertos.",
]
CUIDADOS = [
    "La columna N° y los encabezados están protegidos. No copies ni pegues filas completas, no borres filas y no uses una fila para otro encargo: el N° identifica el encargo de un corte a otro.",
    "Si un encargo se cancela, cambia el estado a Cancelado y escribe el motivo. Las celdas en color indican datos por revisar: entrega sin fecha, fecha sin estado Entregado, plazo vencido o campos obligatorios pendientes.",
]
CAPACIDAD = "Cada pestaña tiene 1.000 filas numeradas. Cuando se acerque el límite, solicita la ampliación a la contraparte de seguimiento DEPP."

AZUL = "FF0E2841"
GRIS = "FFEDF2F7"


def estilo_texto(celda, relleno):
    celda.font = Font(name="Verdana", size=9, color="FF000000")
    celda.fill = PatternFill("solid", fgColor=relleno)
    celda.alignment = Alignment(wrap_text=True, vertical="center")


def estilo_banda(celda):
    celda.font = Font(name="Verdana", size=9, bold=True, color="FFFFFFFF")
    celda.fill = PatternFill("solid", fgColor=AZUL)
    celda.alignment = Alignment(wrap_text=True, vertical="center")


def rehacer_inicio(ws, areas):
    for rango in list(ws.merged_cells.ranges):
        if rango.min_row >= 4:
            ws.unmerge_cells(str(rango))
    for fila in range(4, 41):
        for col in range(1, 9):
            c = ws.cell(fila, col)
            c.value = None
            c.style = "Normal"
        ws.row_dimensions[fila].height = None
    fila = 4

    def banda(texto):
        nonlocal fila
        ws.cell(fila, 1).value = texto
        estilo_banda(ws.cell(fila, 1))
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=8)
        ws.row_dimensions[fila].height = 25
        fila += 1

    def textos(lista, alto=33):
        nonlocal fila
        for i, texto in enumerate(lista):
            ws.cell(fila, 1).value = texto
            estilo_texto(ws.cell(fila, 1), "FFFFFFFF" if i % 2 == 0 else GRIS)
            ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=8)
            ws.row_dimensions[fila].height = alto
            fila += 1
        fila += 1

    banda("CÓMO LLENAR EL REGISTRO")
    textos(INSTRUCCIONES)
    banda("CÓMO PEDIR APOYO O DECISIÓN A GABINETE")
    textos(APOYO)
    banda("CUIDADOS DEL REGISTRO")
    textos(CUIDADOS, 44)
    banda("EJEMPLOS DE PRODUCTOS")
    ejemplos = []
    for area in areas:
        ej = next((e for e in MODELO["examples"] if e[0] == area["prefix"]), None)
        if ej:
            ejemplos.append(f"{area['name']} · {ej[3]} → {ej[4]}.")
    textos(ejemplos, 31)
    ws.cell(fila, 1).value = CAPACIDAD
    estilo_texto(ws.cell(fila, 1), GRIS)
    ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=8)
    ws.row_dimensions[fila].height = 28


def preparar_registro(ws):
    # Celdas editables: B a K. N° y filas 1 a 3 quedan bloqueadas.
    for fila in ws.iter_rows(min_row=PRIMERA, max_row=ULTIMA, min_col=2, max_col=11):
        for c in fila:
            p = copy.copy(c.protection)
            p.locked = False
            c.protection = p
    for fila in range(PRIMERA, ULTIMA + 1):
        c = ws.cell(fila, 1)
        c.value = f'=IF(COUNTA(B{fila}:K{fila})=0,"",{fila - 3})'
        p = copy.copy(c.protection)
        p.locked = True
        c.protection = p

    # Validaciones: se conservan las listas y se agregan fechas y mensajes.
    existentes = [dv for dv in ws.data_validations.dataValidation
                  if str(dv.sqref).split(":")[0][0] in "EFI"]
    ws.data_validations.dataValidation = existentes
    for dv in existentes:
        dv.showErrorMessage = True
        dv.errorTitle = "Valor fuera de lista"
        dv.error = "Elige una opción de la lista."
    for col, titulo, mensaje in [
        ("B", "Fecha de ingreso", "Fecha en que se recibió o programó el encargo (dd/mm/aaaa)."),
        ("H", "Plazo acordado", "Si el plazo cambia, actualízalo y explica el cambio en Observaciones generales."),
        ("J", "Fecha de entrega efectiva", "Solo cuando el estado es Entregado. Debe ser igual o posterior a la fecha de ingreso."),
    ]:
        dv = DataValidation(type="date", operator="between", formula1="DATE(2020,1,1)",
                            formula2="DATE(2035,12,31)", allow_blank=True, showErrorMessage=True,
                            errorTitle="Fecha no válida", error="Ingresa una fecha con formato dd/mm/aaaa.",
                            showInputMessage=True, promptTitle=titulo, prompt=mensaje)
        dv.add(f"{col}{PRIMERA}:{col}{ULTIMA}")
        ws.data_validations.append(dv)
    dv = DataValidation(type="textLength", operator="lessThanOrEqual", formula1="1000", allow_blank=True,
                        showInputMessage=True, promptTitle="Observaciones generales",
                        prompt="Avance, próximo paso, bloqueo o cambio de plazo. Para pedir gestión de Gabinete inicia con «Apoyo Gabinete:» o «Decisión Gabinete:».",
                        showErrorMessage=True, errorTitle="Texto extenso", error="Resume la observación en hasta 1.000 caracteres.")
    dv.add(f"K{PRIMERA}:K{ULTIMA}")
    ws.data_validations.append(dv)

    # Formato condicional: alertas visibles para quien llena el registro.
    ws.conditional_formatting = type(ws.conditional_formatting)()
    rojo = PatternFill("solid", fgColor="FFF6D5D7", bgColor="FFF6D5D7")
    ambar = PatternFill("solid", fgColor="FFFBE8C5", bgColor="FFFBE8C5")
    verde = PatternFill("solid", fgColor="FFDDF0E6", bgColor="FFDDF0E6")
    r = PRIMERA
    reglas = [
        (f"J{r}:J{ULTIMA}", f'AND($I{r}="Entregado",$J{r}="")', ambar, None),
        (f"J{r}:J{ULTIMA}", f'AND($J{r}<>"",$I{r}<>"Entregado")', rojo, None),
        (f"J{r}:J{ULTIMA}", f'AND($J{r}<>"",$B{r}<>"",$J{r}<$B{r})', rojo, None),
        (f"H{r}:H{ULTIMA}", f'AND($H{r}<>"",$H{r}<TODAY(),$I{r}<>"Entregado",$I{r}<>"Cancelado")', rojo,
         Font(color="FF92383A", bold=True)),
        (f"A{r}:A{ULTIMA}", f'AND(COUNTA($B{r}:$K{r})>0,OR($B{r}="",$C{r}="",$D{r}="",$E{r}="",$F{r}="",$G{r}="",$I{r}=""))', ambar, None),
        (f"I{r}:I{ULTIMA}", f'$I{r}="Bloqueado"', rojo, Font(color="FF92383A", bold=True)),
        (f"I{r}:I{ULTIMA}", f'$I{r}="Entregado"', verde, None),
    ]
    for rango, formula, relleno, fuente in reglas:
        ws.conditional_formatting.add(rango, FormulaRule(formula=[formula], fill=relleno, font=fuente, stopIfTrue=False))

    # Protección sin contraseña: la jefatura puede desprotegerla para ampliar capacidad.
    pr = ws.protection
    pr.sheet = True
    pr.autoFilter = False      # False = permitido usar filtros
    pr.sort = True             # ordenar queda bloqueado: el N° se asigna por fila
    pr.formatColumns = False
    pr.formatRows = False
    pr.insertRows = True
    pr.deleteRows = True
    pr.selectLockedCells = False
    pr.selectUnlockedCells = False


def preparar(origen, destino):
    destino.mkdir(parents=True, exist_ok=True)
    for libro in MODELO["books"]:
        wb = openpyxl.load_workbook(origen / libro["file"])
        areas = [a for a in MODELO["areas"] if a["prefix"] in libro["prefixes"]]
        for area in areas:
            ws = wb[area["tab"]]
            assert area["table"] in ws.tables, f"Falta la tabla {area['table']}"
            preparar_registro(ws)
        inicio = wb["Inicio"]
        rehacer_inicio(inicio, areas)
        assert wb.sheetnames[1] == "Inicio", "Inicio debe ser la segunda hoja"
        wb.active = 0
        for ws in wb.worksheets:
            ws.sheet_view.tabSelected = ws is wb.worksheets[0]
        wb.save(destino / libro["file"])
        print("Preparado", libro["file"])


if __name__ == "__main__":
    preparar(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
