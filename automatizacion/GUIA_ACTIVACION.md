# Guía de activación institucional

## Ruta recomendada: sin informática ni Python

Esta es la forma en operación. No requiere permisos de administrador, instalaciones ni servidores.

| Parte | Qué se hace | Quién |
|---|---|---|
| 1 | Carpeta `DEPP_Seguimiento` en OneDrive con `Planillas` y `Capturas`; cada Excel compartido solo con su equipo | Dueño de la carpeta |
| 2 | Flujo de nube «DEPP - Captura de planillas» en Power Automate: copia los tres Excel a `Capturas/AAAA-MM-DD_HHMM` cada hora de 8:00 a 19:00, de lunes a viernes, con zona horaria Santiago; la captura del viernes a las 12:00 es el corte semanal. Cada captura deja también `datos.js` | Dueño de la carpeta, con su cuenta |
| 3 | Compartir la carpeta `Capturas` con la jefatura con permiso de lectura y sincronizarla en su computador | Dueño de la carpeta y jefatura |
| 4 | Abrir el tablero (`https://alejandroavya.github.io/seguimiento-semanal-depp/tablero.html`), elegir una vez la carpeta sincronizada y pulsar «Actualizar» cuando se quiera ver lo último | Jefatura |

**Cómo funciona el tablero.** La página solo contiene código. Al elegir la carpeta, el navegador (Edge o Chrome) lee las capturas desde el disco del propio computador, arma cada corte del viernes a las 12:00 comparándolo con el anterior y agrega la última actualización intermedia (9:00 o 17:00) como avance desde el último corte. Los datos no salen del computador ni pasan por GitHub. Edge recuerda la carpeta: las veces siguientes basta con «Actualizar».

**Avisos que muestra el tablero.** Falta la captura que correspondía según el horario (por ejemplo, el flujo falló o OneDrive no ha sincronizado); un corte quedó en revisión (falta un Excel, N° duplicado, registro eliminado, posible reutilización de fila o captura atrasada más de 30 minutos), en cuyo caso la actualización siguiente se compara con el último corte válido.

**Formato de cada captura** (lo deja el flujo): carpeta `AAAA-MM-DD_HHMM` con los tres Excel y `captura.json` (`scheduledAt`, `capturedAt`, `slot`, `verified`).

Las secciones siguientes describen la **alternativa con procesador en Python** (archivos de minuta y detalle generados sin abrir el tablero, o captura por Microsoft Graph). Solo es necesaria si en el futuro se quiere publicar resultados sin intervención de nadie.

## 1. Arquitectura

```
OneDrive institucional (carpeta privada DEPP_Seguimiento, propietaria: contraparte DEPP)
├── Planillas/                      ← los equipos editan aquí (cada archivo compartido por separado)
│   ├── Seguimiento_Departamento_Estudios.xlsx   (AET + EE)
│   ├── Seguimiento_Evaluacion_Politicas_Publicas.xlsx (EPP)
│   └── Seguimiento_CPHDV.xlsx                   (CPHDV)
├── Capturas/AAAA-MM-DD/            ← Power Automate copia los tres Excel el viernes a las 12:00
│   ├── *.xlsx
│   └── captura.json                (hora real de captura y versión de cada archivo)
└── Salidas/                        ← el procesador publica aquí (lectura para la jefatura)
    ├── Tablero_Seguimiento_Semanal_DEPP.html   (todos los cortes incrustados)
    ├── indice.json                 (último corte válido y estado de la última ejecución)
    └── cortes/AAAA-MM-DD/
        ├── Corte_DEPP_AAAA-MM-DD.json      (consolidado fechado)
        ├── Manifiesto_DEPP_AAAA-MM-DD.json (captura, cobertura, incidencias, ejecuciones)
        ├── Minuta_DEPP_AAAA-MM-DD.docx     (minuta ejecutiva para revisión)
        └── Detalle_DEPP_AAAA-MM-DD.xlsx    (todos los movimientos, compromisos e incidencias)
```

Hay dos modalidades. Ambas usan el mismo procesador y producen los mismos archivos.

| | Modalidad A (recomendada para partir) | Modalidad B (sin equipo encendido) |
|---|---|---|
| Captura de las 12:00 | Flujo programado de Power Automate con la cuenta de la contraparte | Microsoft Graph con aplicación de Entra ID |
| Procesamiento | Tarea programada en un equipo institucional con OneDrive sincronizado | Azure Functions o servidor institucional |
| Permisos especiales | Ninguno fuera de OneDrive y Power Automate estándar | Registro de aplicación y permiso `Files.SelectedOperations.Selected` |
| Quién habilita | Contraparte DEPP y soporte DTI para instalar Python | Administración de Entra ID / M365 (DTI) |

## 2. Responsables

| Tarea | Responsable |
|---|---|
| Crear la carpeta, subir los Excel y compartir cada archivo | Contraparte de seguimiento DEPP (propietaria de la carpeta) |
| Crear los flujos de Power Automate | Contraparte DEPP, con su cuenta institucional |
| Instalar Python y el procesador en el equipo que procesa | Soporte DTI |
| Registrar la aplicación de Entra ID y otorgar permisos (solo modalidad B) | Administración de Entra ID / M365 (DTI) |
| Revisar la minuta antes de remitirla a Gabinete SPD | Jefatura DEPP |
| Revisar incidencias y aprobar un corte en revisión | Contraparte DEPP con visto bueno de la jefatura |

## 3. Carpeta y permisos en OneDrive

1. En el OneDrive institucional de la contraparte, crear `DEPP_Seguimiento` con las subcarpetas `Planillas`, `Capturas` y `Salidas`. La carpeta raíz no se comparte.
2. Subir las tres plantillas de `plantillas/` a `Planillas`.
3. Compartir **cada Excel por separado**: *Compartir › Personas específicas › Puede editar*, solo con el equipo correspondiente. Desactivar «Cualquier persona con el vínculo».
4. En *Administrar acceso* de cada archivo, confirmar que solo aparecen las personas autorizadas.
5. Compartir la carpeta `Salidas` con la jefatura DEPP con permiso **Puede ver**.
6. Prueba: con la cuenta de una persona de EPP, intentar abrir el Excel de CPHDV y el del Departamento de Estudios. Debe recibir «No tiene acceso».

Las planillas traen la columna N° y los encabezados protegidos (sin contraseña), validaciones de fecha y listas, y colores de alerta. Para ampliar la capacidad sobre 1.000 filas, la contraparte desprotege la hoja (*Revisar › Desproteger hoja*), extiende tabla, numeración y validaciones juntas y vuelve a proteger.

## 4. Flujo de captura en Power Automate (modalidad A)

Crear un **flujo de nube programado** llamado `DEPP - Captura semanal`, con la cuenta de la contraparte. Solo usa conectores estándar (OneDrive para la Empresa y Outlook).

**Desencadenador: Periodicidad**

| Campo | Valor |
|---|---|
| Intervalo / Frecuencia | 1 / Semana |
| Zona horaria | (UTC-04:00) Santiago |
| Hora de inicio | 2026-11-20T12:00:00 (el primer viernes de operación) |
| En estos días | Viernes |
| A estas horas / minutos | 12 / 0 |

La zona «Santiago» aplica el horario de verano chileno automáticamente; no se usa UTC fijo.

**Acciones**

1. *Redactar* `FechaCorte`: `formatDateTime(convertFromUtc(utcNow(), 'Pacific SA Standard Time'), 'yyyy-MM-dd')`
2. *Obtener metadatos de archivo mediante ruta* sobre `/DEPP_Seguimiento/Capturas/@{outputs('FechaCorte')}/captura.json`.
   - Configurar *Ejecutar después* de la acción 3 en «se ha producido un error». Si el archivo existe, el flujo termina: la captura del día ya existe y no se reemplaza.
3. *Terminar* (Correcto) si la acción 2 tuvo éxito.
4. Para cada uno de los tres Excel (puede ser un *Aplicar a cada uno* sobre una matriz con los tres nombres):
   - *Obtener metadatos de archivo mediante ruta*: `/DEPP_Seguimiento/Planillas/<archivo>`
   - *Obtener contenido de archivo mediante ruta*: misma ruta.
   - *Crear archivo*: carpeta `/DEPP_Seguimiento/Capturas/@{outputs('FechaCorte')}`, nombre `<archivo>`, contenido = contenido del paso anterior. La acción crea la carpeta del día si no existe.
   - *Anexar a variable de matriz* `Archivos`: `{"file": "<archivo>", "etag": "@{body('Metadatos')?['ETag']}", "modified": "@{body('Metadatos')?['LastModified']}"}`
5. *Crear archivo* `captura.json` en la misma carpeta, con este contenido:

   ```json
   {"capturedAt": "@{utcNow()}", "source": "Power Automate · DEPP - Captura semanal", "verified": false, "files": @{variables('Archivos')}}
   ```

6. Rama de error (configurar *Ejecutar después* = «se ha producido un error» o «se agotó el tiempo»): *Enviar un correo (V2)* a la contraparte con el asunto «Corte DEPP: la captura del viernes falló».

El procesador compara `capturedAt` con el viernes a las 12:00 de Santiago. Si la captura se hizo más de 30 minutos después y no hay versión verificada, deja el corte **en revisión** y mantiene el último corte válido. Para recuperar la versión exacta de las 12:00 cuando el flujo se retrasa, use la modalidad B o la acción *Enviar una solicitud HTTP a SharePoint* sobre `_api/web/GetFileByServerRelativeUrl('…')/Versions`.

## 5. Procesador programado (modalidad A)

En un equipo institucional que permanezca encendido los viernes, con el cliente de OneDrive sincronizando `DEPP_Seguimiento`:

1. Instalar Python 3.11 o superior y Git (soporte DTI).
2. Clonar el repositorio en `C:\DEPP\seguimiento-semanal-depp` y ejecutar `automatizacion\instalar_procesador.ps1`.
3. Confirmar que la zona horaria de Windows es «(UTC-04:00) Santiago».
4. Ejecutar `automatizacion\programar_tarea_windows.ps1`. Crea la tarea «DEPP - Corte semanal» los viernes a las 12:20, 13:30 y 16:00. Las repeticiones son seguras: si la captura no cambió, el procesador registra «sin cambios» y no reescribe nada.
5. Prueba manual: `Start-ScheduledTask -TaskName "DEPP - Corte semanal"` y revisar `Salidas\registro_ejecuciones.log`.

Comandos útiles:

```powershell
# Procesar un corte específico
.\automatizacion\ejecutar_corte.ps1 -Corte 2026-11-20
# Aprobar con observaciones un corte en revisión, después de revisarlo con la unidad
.\.venv\Scripts\python.exe -m depp_corte aprobar --salidas "$env:OneDriveCommercial\DEPP_Seguimiento\Salidas" `
  --corte 2026-11-20 --responsable "Jefatura DEPP" --motivo "Registro eliminado por duplicidad, confirmado con EPP."
```

Qué deja en revisión un corte: falta un archivo, una pestaña o la tabla; cambian los encabezados; hay un N° duplicado; desaparece un registro del corte anterior; un N° cambia a la vez fecha de ingreso y requerimiento (posible reutilización de fila); o la captura se atrasó sin versión verificada. Las filas incompletas no bloquean: se informan como observaciones y, si el registro ya existía, se conserva su versión anterior.

## 6. Aviso a la jefatura

Segundo flujo `DEPP - Aviso de corte` con el desencadenador *Cuando se modifica un archivo (solo propiedades)* sobre `/DEPP_Seguimiento/Salidas`, con condición `Nombre de archivo = indice.json`:

1. *Obtener contenido de archivo* de `indice.json` y *Analizar JSON*.
2. Si `lastRun.status` es `valido` o `valido_con_observaciones`: correo a la jefatura con el vínculo a `Salidas/cortes/<fecha>/Minuta_DEPP_<fecha>.docx` y al tablero.
3. Si es `en_revision` o `fallido`: correo a la contraparte con `lastRun.result`.

## 7. Acceso de la jefatura al tablero

- **Opción inmediata.** La jefatura sincroniza la carpeta compartida `Salidas` (*Agregar acceso directo a Mis archivos*) y abre `Tablero_Seguimiento_Semanal_DEPP.html` con Edge o Chrome. Los datos van dentro del archivo; el acceso queda controlado por los permisos de OneDrive y la cuenta institucional. OneDrive en el navegador no muestra archivos HTML como página, por eso se abre desde la carpeta sincronizada.
- **Opción con dirección web (DTI).** Publicar el contenido de `Salidas` en Azure Static Web Apps con autenticación de Entra ID, restringida a un grupo «Jefatura DEPP». El tablero detecta que está en un servidor y lee `indice.json` y los cortes de la misma dirección. No usar GitHub Pages para datos reales.

## 8. Modalidad B: Microsoft Graph (sin equipo encendido)

1. DTI registra una aplicación en Entra ID («DEPP Seguimiento semanal») con el permiso de aplicación **`Files.SelectedOperations.Selected`** y otorga consentimiento de administrador. Este permiso no da acceso a nada por sí solo.
2. Un administrador con `Sites.FullControl.All` (o con el rol de propietario sobre el sitio) concede acceso a cada archivo:

   ```http
   POST https://graph.microsoft.com/v1.0/drives/{drive-id}/items/{item-id}/permissions
   {"roles": ["read"], "grantedToV2": {"application": {"id": "<client-id>", "displayName": "DEPP Seguimiento semanal"}}}
   ```

   Repetir para los tres Excel. Para escribir resultados, conceder `write` solo sobre la carpeta `Salidas` (o publicar las salidas por otra vía institucional).
3. Guardar `automatizacion/config/graph.ejemplo.json` como `graph.json` fuera del repositorio con los identificadores reales. El secreto o certificado va en una variable de entorno (`DEPP_GRAPH_SECRET`) o en Azure Key Vault.
4. Programar: `python -m depp_corte capturar --config graph.json --capturas <ruta>` seguido de `procesar`. En Azure Functions, usar un temporizador `0 0 12 * * 5` con `WEBSITE_TIME_ZONE = Pacific SA Standard Time` (plan Windows) o `TZ = America/Santiago` (Linux). La captura busca la versión de cada archivo vigente a las 12:00, aunque se ejecute más tarde, y la marca como verificada.

## 9. Verificación del flujo completo

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | Una persona de cada equipo edita su archivo; prueba abrir los de los otros equipos | Edita el propio; no accede a los otros |
| 2 | Ingresar un registro en cada pestaña | Aparece el N° automático; la columna N° no se puede editar |
| 3 | Ejecutar el flujo de captura manualmente | Carpeta `Capturas/<fecha>` con tres Excel y `captura.json` |
| 4 | Ejecutar la tarea programada | `indice.json`, tablero y carpeta del corte en `Salidas`; correo de aviso |
| 5 | Repetir la tarea dos veces | El manifiesto registra «sin cambios»; no se duplican cortes ni cifras |
| 6 | Registrar una entrega el viernes a las 15:00 | No aparece en ese corte; aparece una sola vez en el siguiente |
| 7 | Quitar temporalmente un Excel de la captura | Corte en revisión; el tablero muestra el último corte válido y el aviso |
| 8 | Abrir el tablero con la cuenta de la jefatura | Cifras del resumen iguales a la minuta («coinciden con el consolidado publicado») |
| 9 | Descargar la minuta en Word desde el tablero | Igual a `Minuta_DEPP_<fecha>.docx` |

Las pruebas 5 a 9 ya se ejecutan de forma automática con datos ficticios (`pytest pruebas`).
