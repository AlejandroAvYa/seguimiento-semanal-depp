# Resultados de las pruebas

Ejecución: 13/11/2026, `python -m pytest -v pruebas`. **30 de 30 pruebas aprobadas** (Python 3.13, Node 22, Chrome mediante Playwright). Todas usan datos ficticios.

## Criterios de aceptación de la guía original

| Criterio | Prueba | Resultado |
|---|---|---|
| Tres plantillas con N° automático y 13 requirentes; registro primero e Inicio segunda | `test_plantillas_estructura` | Aprobada |
| Lectura de 4 tablas, más de 256 filas en una tabla y un área con cero registros | `test_lee_cuatro_tablas_mas_de_256_filas_y_area_vacia` (300 filas en AET, CPHDV vacío) | Aprobada |
| N° recuperado de la fórmula si la caché de Excel viene vacía | `test_numero_desde_formula_si_falta_cache` | Aprobada |
| El N° se mantiene asociado al mismo registro entre cortes | `test_numero_se_mantiene_al_mover_filas`, `test_reutilizacion_de_numero_deja_corte_en_revision` | Aprobadas |
| Entrega del viernes después de las 12:00 aparece una sola vez en el corte siguiente | `test_viernes_despues_del_mediodia_aparece_una_vez` (y EE-002 y AET-006 en los ejemplos) | Aprobada |
| Cambio de estado u observaciones aparece como avance aunque conserve la fecha de ingreso | `test_cambio_de_estado_u_observaciones_es_avance` | Aprobada |
| Archivo inaccesible, tabla ausente, registro eliminado o N° duplicado dejan el corte en revisión y conservan el último válido | `test_archivo_faltante…`, `test_tabla_ausente…`, `test_registro_eliminado…`, `test_numero_duplicado…`, `test_falla_conserva_ultimo_valido` | Aprobadas |
| Ejecución demorada | `test_captura_demorada_sin_version_verificada`, `test_captura_demorada_con_version_verificada_es_valida` | Aprobadas |
| Ejecución repetida no duplica registros ni resultados | `test_repetir_corte_no_duplica` (tres ejecuciones, archivos idénticos byte a byte) | Aprobada |
| Hora de Chile en dos fechas con distinto desfase UTC | `test_hora_programada_respeta_horario_de_verano` (10/07 → 16:00 UTC; 13/11 → 15:00 UTC), `test_corte_por_defecto_segun_mediodia` | Aprobadas |
| El JSON reproducido en el tablero muestra los mismos resultados que la minuta (ejecutiva, completa y exportación) | `test_paridad_con_cortes_publicados` ×3, `test_tablero_y_minuta_muestran_las_mismas_cifras` | Aprobadas |

## Pruebas adicionales

| Prueba | Qué verifica |
|---|---|
| `test_registro_tardio_se_cuenta_como_ingreso` | Un encargo con fecha anterior al período, registrado tarde, cuenta como ingreso con marca de registro tardío |
| `test_fila_con_error_conserva_version_anterior` | Una fila existente con un error mantiene su versión anterior y, al corregirse, se compara sin ingresos falsos |
| `test_aprobar_corte_en_revision` | La jefatura puede aprobar con observaciones un corte en revisión; queda registro de quién y por qué |
| `test_no_reprocesa_cortes_antiguos_sin_forzar` | No se reprocesa un corte si ya existen cortes posteriores |
| `test_paridad_construccion_del_corte_con_incidencias` | El tablero y el procesador construyen el mismo consolidado, con las mismas incidencias |
| `test_carga_manual_de_excel_reproduce_el_procesador` | La carga manual en el navegador de los tres viernes ficticios produce consolidados idénticos a los del procesador |
| `test_tablero_y_minuta_muestran_las_mismas_cifras` | El Word descargado desde el tablero es idéntico al que genera el procesador |
| `test_filtros_y_ficha` | Filtros por equipo, requirente y vista; ficha con cambios e historial; consulta de un corte anterior |
| `test_corte_en_revision_y_falla_visibles` | Con un corte en revisión, el tablero lo avisa, muestra el último válido y marca la minuta como borrador |
| `test_ejemplos_ficticios_coinciden_con_lo_esperado` | Cifras de los ejemplos verificadas a mano: 13/11 con 7 ingresos, 4 entregas, 6 avances y 10 abiertos |

## Prueba del flujo original (antes de los cambios)

Se cargó el tablero recibido con los Excel ficticios al 06/11 y al 13/11:

- Las cifras del tablero y de la minuta coincidieron, y la entrega del viernes 06/11 a las 16:00 apareció una vez en el corte del 13/11.
- Un encargo con ingreso 05/11 registrado después del corte del 06/11 no se contó como ingreso ni apareció en la minuta.
- Al reutilizar la fila de EE-002 para otro encargo, el tablero informó «Actualización de estado, plazo, observaciones, producto» sin aviso y permitió guardar el consolidado.
- El encabezado de la minuta indicó «6 ingresos · 3 entregas · 2 avances» para 8 registros: uno de los avances era una entrega.
- «Ver ejemplo» y el archivo de ejemplo del 13/11 dieron cifras distintas (4 y 6 ingresos).

## Lo que no se pudo probar aquí

- Conexión real con OneDrive, Power Automate y Microsoft Graph: requieren el tenant institucional. El procesador se probó con capturas en disco equivalentes a las que dejará el flujo.
- Apertura de las planillas en Excel para la web con la hoja protegida: se verificó la estructura con openpyxl y LibreOffice. Conviene confirmar en Excel en línea que los equipos editan B a K y que el filtro funciona.
