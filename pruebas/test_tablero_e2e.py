"""Pruebas del tablero en un navegador real (Chrome o Chromium mediante Playwright).

Verifican la carga manual de los Excel, que las cifras del tablero coincidan con la minuta
y con el procesador, y que el Word descargado sea idéntico al que genera el procesador.
"""
import json
import os
import pathlib
import re
import shutil
import zipfile

import pytest

from conftest import MODELO, RAIZ
from depp_corte import minuta_docx, motor

playwright = pytest.importorskip("playwright.sync_api")
CHROME = os.environ.get("DEPP_CHROME") or shutil.which("google-chrome") or shutil.which("chromium")
TABLERO = RAIZ / "tablero" / "dist" / "Tablero_Seguimiento_Semanal_DEPP.html"
SALIDAS = RAIZ / "ejemplos" / "salidas"
CAPTURAS = RAIZ / "ejemplos" / "capturas"


@pytest.fixture(scope="module")
def navegador():
    with playwright.sync_playwright() as p:
        opciones = {"args": ["--no-sandbox"]}
        if CHROME:
            opciones["executable_path"] = CHROME
        b = p.chromium.launch(**opciones)
        yield b
        b.close()


def pagina(navegador, url):
    pg = navegador.new_page(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    errores = []
    pg.on("pageerror", lambda e: errores.append(str(e)))
    pg.goto(url)
    pg.wait_for_timeout(400)
    return pg, errores


def cifras_hero(pg):
    nums = pg.locator(".hstat__n").all_inner_texts()
    return dict(zip(["entregas", "avances", "ingresos", "alertas", "apoyos"], map(int, nums)))


def test_carga_manual_de_excel_reproduce_el_procesador(navegador, tmp_path):
    pg, errores = pagina(navegador, TABLERO.as_uri())
    pg.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
    for cut in ("2026-10-30", "2026-11-06", "2026-11-13"):
        pg.fill("#manual-cut", cut)
        pg.set_input_files("#file-xlsx", sorted(str(p) for p in (CAPTURAS / f"{cut}_1200").glob("*.xlsx")))
        pg.wait_for_timeout(900)
        publicado = json.loads((SALIDAS / "cortes" / cut / f"Corte_DEPP_{cut}.json").read_text(encoding="utf-8"))
        # El consolidado armado en el navegador es idéntico al del procesador.
        with pg.expect_download() as d:
            pg.click('[data-act="guardar"]')
        armado = json.loads(pathlib.Path(d.value.path()).read_text(encoding="utf-8"))
        publicado.pop("capturedAt", None)  # la carga manual no tiene registro de captura
        assert armado == publicado, cut
    assert not errores


def test_tablero_y_minuta_muestran_las_mismas_cifras(navegador, tmp_path):
    pg, errores = pagina(navegador, (SALIDAS / "Tablero_Seguimiento_Semanal_DEPP.html").as_uri())
    corte = json.loads((SALIDAS / "cortes" / "2026-11-13" / "Corte_DEPP_2026-11-13.json").read_text(encoding="utf-8"))
    s = corte["summary"]
    hero = cifras_hero(pg)
    assert (hero["entregas"], hero["avances"], hero["ingresos"], hero["apoyos"]) == (s["entregas"], s["avances"], s["ingresos"], s["apoyos"])
    pg.click('.nav__item[data-view="minuta"]')
    texto = pg.locator("#paper").inner_text()
    assert f"se registraron {s['ingresos']} ingresos y {s['entregas']} entregas" in texto
    assert f"{s['avances']} compromisos tuvieron avance" in texto
    assert "coinciden con el consolidado publicado" in pg.locator("#minuta-status").inner_text()
    # El Word del tablero es el mismo que escribe el procesador.
    with pg.expect_download() as d:
        pg.click('[data-act="word"]')
    ruta = pathlib.Path(d.value.path())
    with zipfile.ZipFile(ruta) as z:
        doc_js = z.read("word/document.xml").decode("utf-8")
        notas_js = z.read("word/footnotes.xml").decode("utf-8")
    with zipfile.ZipFile(SALIDAS / "cortes" / "2026-11-13" / "Minuta_DEPP_2026-11-13.docx") as z:
        assert doc_js == z.read("word/document.xml").decode("utf-8")
        assert notas_js == z.read("word/footnotes.xml").decode("utf-8")
    # Detalle completo: todos los movimientos.
    pg.click('[data-full="1"]')
    filas = pg.locator(".movtable tbody tr").count()
    assert filas == len(motor.movimientos(MODELO, motor.leer_corte(MODELO, corte)))
    assert not errores


def test_filtros_y_ficha(navegador):
    pg, errores = pagina(navegador, (SALIDAS / "Tablero_Seguimiento_Semanal_DEPP.html").as_uri())
    pg.click('.hstat[data-preset="solicitudes"]')
    assert re.match(r"3 de 20", pg.locator(".count").inner_text())
    pg.select_option('[data-f="view"]', "all")
    pg.select_option('[data-f="area"]', "EPP")
    assert pg.locator(".count").inner_text().startswith("5 de")
    pg.select_option('[data-f="requester"]', "DTPT")
    assert pg.locator(".count").inner_text().startswith("2 de")
    pg.click('tr[data-open="EPP-001"]')
    ficha = pg.locator(".drawer").inner_text().lower()
    assert "en curso" in ficha and "bloqueado" in ficha and "historial" in ficha
    pg.keyboard.press("Escape")
    assert pg.locator(".drawer").count() == 0
    # Consulta de un corte anterior.
    pg.select_option("#cut-select", "2026-11-06_1200")
    assert pg.locator(".count").inner_text().endswith("de 13")
    assert not errores


def test_corte_en_revision_y_falla_visibles(navegador, tmp_path):
    from depp_corte import salidas
    datos = json.loads((SALIDAS / "cortes" / "2026-11-13" / "Corte_DEPP_2026-11-13.json").read_text(encoding="utf-8"))
    datos["status"] = "en_revision"
    datos["incidents"] = [{"level": "bloqueante", "code": "archivo_ausente", "area": "CPHDV", "message": "Falta Seguimiento_CPHDV.xlsx en la captura."}]
    indice = salidas.leer_indice(SALIDAS)
    indice = json.loads(json.dumps(indice))
    for c in indice["cuts"]:
        if c["cut"] == "2026-11-13":
            c["status"] = "en_revision"
    indice["lastValid"] = "2026-11-06"
    indice["lastRun"] = {"cut": "2026-11-13", "at": "2026-11-13T12:01:00-03:00", "status": "en_revision", "result": "publicado"}
    cortes = {c["cut"]: json.loads((SALIDAS / c["files"]["corte"]).read_text(encoding="utf-8")) for c in indice["cuts"]}
    cortes["2026-11-13"] = datos
    destino = tmp_path / "t.html"
    salidas.insertar_datos(TABLERO, destino, {"index": indice, "cuts": cortes, "origin": "procesador"})
    pg, errores = pagina(navegador, destino.as_uri())
    banners = pg.locator("#banners").inner_text()
    assert "quedó en revisión" in banners and "06/11/2026" in banners
    assert pg.locator("#cut-select").input_value() == "2026-11-06_1200"
    pg.select_option("#cut-select", "2026-11-13_1200")
    assert "Corte en revisión" in pg.locator("#banners").inner_text()
    pg.click('.nav__item[data-view="minuta"]')
    assert "BORRADOR" in pg.locator("#paper").inner_text()
    assert not errores


# ------------------------------------------------------------------ carpeta de capturas de OneDrive
def carpeta_onedrive(tmp_path, quitar=None):
    """Copia ejemplos/capturas con la misma estructura que deja el flujo: DEPP_Seguimiento/Capturas/AAAA-MM-DD_HHMM/."""
    raiz = tmp_path / "DEPP_Seguimiento"
    shutil.copytree(CAPTURAS, raiz / "Capturas")
    (raiz / "Planillas").mkdir()
    shutil.copy(RAIZ / "plantillas" / "Seguimiento_CPHDV.xlsx", raiz / "Planillas" / "Seguimiento_CPHDV.xlsx")
    if quitar:
        (raiz / "Capturas" / quitar[0] / quitar[1]).unlink()
    return raiz


def resumen_intermedio():
    from depp_corte import lectura
    anterior = motor.leer_corte(MODELO, json.loads((SALIDAS / "cortes" / "2026-11-13" / "Corte_DEPP_2026-11-13.json").read_text(encoding="utf-8")))
    datos = lectura.leer_carpeta(MODELO, CAPTURAS / "2026-11-13_1700")
    return motor.construir_corte(MODELO, datos, "2026-11-13", anterior, None, {"kind": "actualizacion", "slot": "2026-11-13_1700"})["summary"]


def test_tablero_lee_la_carpeta_de_capturas(navegador, tmp_path):
    raiz = carpeta_onedrive(tmp_path)
    pg, errores = pagina(navegador, (RAIZ / "docs" / "tablero.html").as_uri())
    assert "Conecta la carpeta" in pg.locator("#page").inner_text()
    pg.set_input_files("#file-dir", str(raiz))
    pg.wait_for_timeout(2500)
    opciones = pg.locator("#cut-select option").all_inner_texts()
    assert len(opciones) == 4 and opciones[0].startswith("Actualización · viernes 13/11/2026 a las 17:00")
    # Actualización intermedia: avance desde el corte del viernes 12:00.
    s = resumen_intermedio()
    hero = cifras_hero(pg)
    assert (hero["entregas"], hero["avances"], hero["ingresos"]) == (s["entregas"], s["avances"], s["ingresos"]) == (1, 1, 1)
    assert "Actualización intermedia" in pg.locator("#banners").inner_text()
    pg.click('.nav__item[data-view="minuta"]')
    assert "AVANCE INTERMEDIO" in pg.locator("#paper").inner_text()
    # Corte semanal del viernes 12:00: mismas cifras que el procesador y que la minuta oficial.
    pg.select_option("#cut-select", "2026-11-13_1200")
    texto = pg.locator("#paper").inner_text()
    assert "se registraron 7 ingresos y 4 entregas" in texto and "6 compromisos tuvieron avance" in texto
    with pg.expect_download() as d:
        pg.click('[data-act="word"]')
    with zipfile.ZipFile(pathlib.Path(d.value.path())) as z:
        doc_js = z.read("word/document.xml").decode("utf-8")
    with zipfile.ZipFile(SALIDAS / "cortes" / "2026-11-13" / "Minuta_DEPP_2026-11-13.docx") as z:
        assert doc_js == z.read("word/document.xml").decode("utf-8")
    assert d.value.suggested_filename == "Minuta_DEPP_2026-11-13.docx"
    assert not errores


def test_captura_incompleta_queda_en_revision_y_se_usa_la_anterior(navegador, tmp_path):
    raiz = carpeta_onedrive(tmp_path, quitar=("2026-11-13_1200", "Seguimiento_CPHDV.xlsx"))
    pg, errores = pagina(navegador, (RAIZ / "docs" / "tablero.html").as_uri())
    pg.set_input_files("#file-dir", str(raiz))
    pg.wait_for_timeout(2500)
    pg.select_option("#cut-select", "2026-11-13_1200")
    assert "Corte en revisión" in pg.locator("#banners").inner_text()
    # La actualización de las 17:00 se compara con el último corte válido (06/11).
    pg.select_option("#cut-select", "2026-11-13_1700")
    assert "06/11/2026" in pg.locator(".hero__meta").inner_text()
    assert not errores


def test_carga_automatica_desde_datos_js(navegador, tmp_path):
    """El tablero dentro de Capturas carga solo las capturas que dejó el flujo (datos.js), sin elegir carpeta."""
    capturas = tmp_path / "Capturas"
    shutil.copytree(CAPTURAS, capturas)
    shutil.copy(RAIZ / "docs" / "Tablero_DEPP.html", capturas / "Tablero_DEPP.html")
    pg, errores = pagina(navegador, (capturas / "Tablero_DEPP.html").as_uri() + "?ahora=2026-11-13T18:00")
    pg.wait_for_timeout(3000)
    opciones = pg.locator("#cut-select option").all_inner_texts()
    assert len(opciones) == 4 and opciones[0].startswith("Actualización · viernes 13/11/2026 a las 17:00")
    pg.select_option("#cut-select", "2026-11-13_1200")
    hero = cifras_hero(pg)
    assert (hero["entregas"], hero["avances"], hero["ingresos"]) == (4, 6, 7)
    # A las 15:00 la captura de las 17:00 todavía no corresponde: no se busca.
    pg2, _ = pagina(navegador, (capturas / "Tablero_DEPP.html").as_uri() + "?ahora=2026-11-13T15:00")
    pg2.wait_for_timeout(3000)
    assert pg2.locator("#cut-select option").count() == 3
    assert not errores
