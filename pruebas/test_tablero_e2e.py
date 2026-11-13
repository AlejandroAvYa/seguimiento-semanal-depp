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
    for cut in ("2026-10-30", "2026-11-06", "2026-11-13"):
        pg.fill("#manual-cut", cut)
        pg.set_input_files("#file-xlsx", sorted(str(p) for p in (CAPTURAS / cut).glob("*.xlsx")))
        pg.wait_for_timeout(900)
        publicado = json.loads((SALIDAS / "cortes" / cut / f"Corte_DEPP_{cut}.json").read_text(encoding="utf-8"))
        # El consolidado armado en el navegador es idéntico al del procesador.
        with pg.expect_download() as d:
            pg.click('[data-act="guardar"]')
        armado = json.loads(pathlib.Path(d.value.path()).read_text(encoding="utf-8"))
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
    pg.select_option("#cut-select", "2026-11-06")
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
    assert pg.locator("#cut-select").input_value() == "2026-11-06"
    pg.select_option("#cut-select", "2026-11-13")
    assert "Corte en revisión" in pg.locator("#banners").inner_text()
    pg.click('.nav__item[data-view="minuta"]')
    assert "BORRADOR" in pg.locator("#paper").inner_text()
    assert not errores
