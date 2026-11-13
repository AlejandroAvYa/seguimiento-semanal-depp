# Publicación y actualización

## Qué va al repositorio y qué no

| Va a GitHub | Queda en el entorno institucional |
|---|---|
| Código del tablero y del procesador | Excel con registros reales |
| Plantillas vacías y modelo Word | Carpetas `Capturas/` y `Salidas/` |
| Datos ficticios (`ejemplos/`) y demostración (`docs/`) | Consolidados, minutas y detalles reales |
| Guía de activación y configuraciones de ejemplo | `graph.json`, secretos y certificados |

El repositorio puede ser público solo mientras contenga exclusivamente lo de la columna izquierda. Antes de cada publicación, revisar `git status` y confirmar que no aparecen archivos de `Capturas` o `Salidas`.

## Demostración en GitHub Pages

1. En GitHub: *Settings › Pages › Build and deployment › Source: GitHub Actions*.
2. El flujo `.github/workflows/pages.yml` publica la carpeta `docs/` (tablero con datos ficticios) cada vez que cambia.
3. La demostración muestra un aviso permanente de datos ficticios. El tablero operativo nunca se publica en Pages.

## Cambiar el tablero o las reglas

1. Editar las fuentes en `tablero/src/` o `procesador/depp_corte/`. Si cambia una regla del corte, cambiarla en `motor.js` y en `motor.py`.
2. Ejecutar `python herramientas/construir_todo.py`. Regenera el modelo Word, el tablero (`tablero/dist/`), los ejemplos ficticios y la demostración (`docs/`).
3. Ejecutar `python -m pytest -q pruebas`. Las pruebas de paridad fallan si el tablero y el procesador dejan de coincidir.
4. Confirmar los cambios y abrir una solicitud de cambio. El flujo «Pruebas» repite la construcción y las pruebas.

## Actualizar el equipo institucional

```powershell
cd C:\DEPP\seguimiento-semanal-depp
git pull
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m depp_corte tablero --salidas "$env:OneDriveCommercial\DEPP_Seguimiento\Salidas"
```

El último comando regenera el tablero de `Salidas` con la nueva versión sin tocar los cortes publicados.

## Cambiar listas o nombres

Requirentes, estados, tipos de encargo, nombres de unidades y productos habituales están en `tablero/src/modelo_depp.json`. Después de modificarlo:

1. `python herramientas/preparar_planillas.py plantillas plantillas` para actualizar listas e instrucciones de las plantillas.
2. Aplicar el mismo cambio en las listas de validación de los Excel que ya están en uso (la herramienta trabaja sobre plantillas vacías).
3. `python herramientas/construir_todo.py` y pruebas.
