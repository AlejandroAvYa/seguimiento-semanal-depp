# Seguimiento semanal DEPP

Sistema de seguimiento semanal de la División de Estudios y Políticas Públicas (DEPP) de la Subsecretaría de Prevención del Delito. Los equipos registran sus compromisos en tres Excel compartidos en OneDrive; cada viernes a las 12:00 (hora de Santiago) se toma un corte, se compara con el anterior y se publican un tablero para la jefatura, una minuta en Word para Gabinete SPD y un detalle completo.

**Este repositorio contiene solo código, plantillas vacías y datos ficticios.** Los Excel reales, las capturas, los consolidados y cualquier credencial quedan en el OneDrive institucional (ver `.gitignore`).

- Demostración con datos ficticios: https://alejandroavya.github.io/seguimiento-semanal-depp/
- Tablero operativo (sin datos; lee la carpeta de capturas de OneDrive en el navegador): https://alejandroavya.github.io/seguimiento-semanal-depp/tablero.html

Flujo en operación: Power Automate copia los tres Excel a `Capturas/AAAA-MM-DD_HHMM` de lunes a viernes a las 9:00 y 17:00, y el viernes a las 12:00 para el corte semanal. El tablero lee esa carpeta desde el computador de la jefatura y arma cortes, actualizaciones y minuta sin enviar datos a ningún servidor.

## Estructura

| Carpeta | Contenido |
|---|---|
| `plantillas/` | Los tres Excel de carga (vacíos), la base Word con formato SPD y el modelo editable de la minuta |
| `tablero/src/` | Fuentes del tablero: `motor.js` (reglas del corte), `app.js` (interfaz), `lector_xlsx.js`, `docx.js`, `zip.js`, `plantilla.html` |
| `tablero/dist/` | Tablero armado en un solo HTML, sin datos. El procesador le inserta los cortes |
| `procesador/depp_corte/` | Procesador en Python: lectura de Excel, corte, comparación, minuta, detalle, índice y captura por Graph |
| `automatizacion/` | Guía de activación institucional, scripts de Windows y configuraciones de ejemplo |
| `ejemplos/` | Capturas ficticias de tres viernes y las salidas que produce el procesador |
| `pruebas/` | Pruebas de aceptación (Python), paridad tablero/procesador (Node) y del tablero en navegador (Playwright) |
| `herramientas/` | Scripts para preparar plantillas y reconstruir tablero, ejemplos y demostración |

## Uso rápido

```bash
pip install -r requirements.txt
# Procesar un corte: lee Capturas/<fecha>/ y publica en Salidas/
PYTHONPATH=procesador python -m depp_corte procesar --capturas <Capturas> --salidas <Salidas> --corte 2026-11-20
# Reconstruir tablero, ejemplos ficticios y demostración
python herramientas/construir_todo.py
# Pruebas
pip install -r requirements-dev.txt && python -m playwright install chromium
python -m pytest -q pruebas
```

La puesta en marcha con OneDrive, Power Automate y permisos está en [`automatizacion/GUIA_ACTIVACION.md`](automatizacion/GUIA_ACTIVACION.md). La publicación y actualización del código está en [`PUBLICACION.md`](PUBLICACION.md).

## Reglas del corte

- **Identidad.** Cada compromiso se identifica por área y N° (`EPP-001`). El N° es una constante en la fórmula de cada fila, por eso acompaña al registro aunque la fila se mueva. La columna N° y los encabezados están protegidos.
- **Período.** Del viernes anterior a las 12:00 al viernes del corte a las 12:00. Lo registrado después de la captura entra en el corte siguiente, una sola vez.
- **Ingreso.** Registro que no estaba en el corte anterior. Si su fecha de ingreso es anterior al período, se marca como registro tardío.
- **Entrega.** Registro que pasa a «Entregado» respecto del corte anterior.
- **Avance.** Registro existente, no entregado en el período, con cambios en estado, plazo, observaciones, responsable, producto, requerimiento, requirente, tipo o fechas.
- **Atención.** Abiertos vencidos (plazo anterior al corte), bloqueados o con solicitud a Gabinete. Las solicitudes se reconocen en Observaciones generales por «Apoyo Gabinete:», «Decisión Gabinete:», «Gabinete debe…» o «Requiere decisión».
- **Primer corte.** Cuenta ingresos y entregas por fecha desde el viernes anterior y fija la línea base.
- **Incidencias que dejan el corte en revisión:** archivo, pestaña o tabla ausente; encabezados alterados; N° duplicado; registro desaparecido; N° con fecha de ingreso y requerimiento cambiados a la vez; captura atrasada sin versión verificada. En esos casos se conserva el último corte válido.
- **Observaciones que no bloquean:** filas incompletas o con datos fuera de lista. Si el registro ya existía, se mantiene su versión anterior hasta que se corrija.

El tablero y el procesador aplican las mismas reglas (`tablero/src/motor.js` y `procesador/depp_corte/motor.py`). Las pruebas de paridad verifican que entreguen las mismas cifras, la misma minuta y el mismo Word.
