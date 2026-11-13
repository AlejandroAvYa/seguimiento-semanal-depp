"""Arma el tablero en un solo archivo HTML.

Salidas:
  tablero/dist/Tablero_Seguimiento_Semanal_DEPP.html  (sin datos; el procesador le inserta los cortes)
  docs/index.html                                      (demostración con los cortes ficticios de ejemplos/)
Uso: python herramientas/construir_tablero.py
"""
import base64
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
SRC = RAIZ / "tablero" / "src"
sys.path.insert(0, str(RAIZ / "procesador"))
from depp_corte import salidas  # noqa: E402


def b64(ruta):
    return base64.b64encode(ruta.read_bytes()).decode("ascii")


def construir():
    html = (SRC / "plantilla.html").read_text(encoding="utf-8")
    fuentes = (
        "@font-face{font-family:'Public Sans';font-style:normal;font-weight:100 900;font-display:swap;"
        f"src:url(data:font/woff2;base64,{b64(SRC / 'fuentes' / 'PublicSans-latin.woff2')}) format('woff2')}}\n"
        "@font-face{font-family:'IBM Plex Mono';font-style:normal;font-weight:600;font-display:swap;"
        f"src:url(data:font/woff2;base64,{b64(SRC / 'fuentes' / 'IBMPlexMono-600-latin.woff2')}) format('woff2')}}"
    )
    modelo = json.loads((SRC / "modelo_depp.json").read_text(encoding="utf-8"))
    reemplazos = {
        "/*__FUENTES__*/": fuentes,
        "__LOGO__": "data:image/png;base64," + b64(SRC / "logo_spd.png"),
        "__MODELO__": json.dumps(modelo, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
        "__DOCX__": b64(RAIZ / "plantillas" / "base_minuta_depp.docx"),
        "__ZIP__": (SRC / "zip.js").read_text(encoding="utf-8"),
        "__MOTOR__": (SRC / "motor.js").read_text(encoding="utf-8"),
        "__LECTOR__": (SRC / "lector_xlsx.js").read_text(encoding="utf-8"),
        "__DOCXJS__": (SRC / "docx.js").read_text(encoding="utf-8"),
        "__APP__": (SRC / "app.js").read_text(encoding="utf-8"),
    }
    for marca, valor in reemplazos.items():
        if marca not in html:
            raise SystemExit(f"Falta la marca {marca} en plantilla.html")
        if "</script" in valor.lower() and marca not in ("__LOGO__", "/*__FUENTES__*/"):
            raise SystemExit(f"{marca} contiene </script>")
        html = html.replace(marca, valor)
    dist = RAIZ / "tablero" / "dist" / salidas.NOMBRE_TABLERO
    dist.parent.mkdir(parents=True, exist_ok=True)
    dist.write_text(html, encoding="utf-8")
    print("Tablero:", dist.relative_to(RAIZ), f"{dist.stat().st_size // 1024} KB")

    # Demostración pública: solo datos ficticios de ejemplos/salidas.
    ej = RAIZ / "ejemplos" / "salidas"
    indice = salidas.leer_indice(ej)
    cortes = {c["cut"]: json.loads((ej / c["files"]["corte"]).read_text(encoding="utf-8")) for c in indice["cuts"]}
    indice = dict(indice, lastRun=None, updatedAt=None)
    # Actualización intermedia ficticia (viernes 13/11 a las 17:00), comparada con el corte de las 12:00.
    from depp_corte import lectura, motor
    modelo_py = json.loads((SRC / "modelo_depp.json").read_text(encoding="utf-8"))
    intermedia = RAIZ / "ejemplos" / "capturas" / "2026-11-13_1700"
    if intermedia.is_dir():
        anterior = motor.leer_corte(modelo_py, cortes["2026-11-13"])
        datos = lectura.leer_carpeta(modelo_py, intermedia)
        meta = json.loads((intermedia / "captura.json").read_text(encoding="utf-8"))
        cortes["2026-11-13_1700"] = motor.construir_corte(
            modelo_py, datos, "2026-11-13", anterior, {"capturedAt": meta["capturedAt"], "late": False, "verified": False},
            {"kind": "actualizacion", "slot": "2026-11-13_1700"})
    demo = RAIZ / "docs" / "index.html"
    demo.parent.mkdir(parents=True, exist_ok=True)
    salidas.insertar_datos(dist, demo, {"index": indice, "cuts": cortes, "origin": "demo"})
    print("Demostración:", demo.relative_to(RAIZ))
    # Tablero operativo publicado sin datos: lee la carpeta de OneDrive en el navegador de quien lo abre.
    (RAIZ / "docs" / "tablero.html").write_text(dist.read_text(encoding="utf-8"), encoding="utf-8")
    # Copia para dejar dentro de OneDrive › DEPP_Seguimiento › Capturas (carga automática de datos.js).
    (RAIZ / "docs" / "Tablero_DEPP.html").write_text(dist.read_text(encoding="utf-8"), encoding="utf-8")
    print("Tablero operativo:", "docs/tablero.html")


if __name__ == "__main__":
    construir()
