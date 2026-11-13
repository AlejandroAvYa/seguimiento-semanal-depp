"""Captura opcional desde Microsoft Graph (modalidad sin computador encendido).

Requiere una aplicación de Entra ID con el permiso de aplicación
Files.SelectedOperations.Selected y un permiso de lectura otorgado por un administrador
sobre cada uno de los tres Excel (POST /drives/{drive}/items/{item}/permissions).
El secreto o certificado se lee desde variables de entorno; nunca desde el repositorio.

Configuración (graph.json, fuera del repositorio):
{
  "tenant_id": "...", "client_id": "...",
  "secret_env": "DEPP_GRAPH_SECRET",
  "files": [{"file": "Seguimiento_CPHDV.xlsx", "drive_id": "b!...", "item_id": "01..."}, ...]
}
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import urllib.parse
import urllib.request

GRAPH = "https://graph.microsoft.com/v1.0"


def _peticion(url, token=None, datos=None):
    cab = {"Authorization": f"Bearer {token}"} if token else {}
    if datos is not None:
        datos = urllib.parse.urlencode(datos).encode()
        cab["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=datos, headers=cab)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def token(config) -> str:
    secreto = os.environ.get(config.get("secret_env", "DEPP_GRAPH_SECRET"))
    if not secreto:
        raise RuntimeError("Falta el secreto de la aplicación en la variable de entorno configurada.")
    url = f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token"
    r = json.loads(_peticion(url, datos={"client_id": config["client_id"], "client_secret": secreto,
                                         "scope": "https://graph.microsoft.com/.default", "grant_type": "client_credentials"}))
    return r["access_token"]


def _fecha(texto):
    return _dt.datetime.fromisoformat(texto.replace("Z", "+00:00"))


def version_al_corte(tk, archivo, programada):
    """Devuelve (url_contenido, metadatos) de la versión vigente a la hora programada."""
    base = f"{GRAPH}/drives/{archivo['drive_id']}/items/{archivo['item_id']}"
    item = json.loads(_peticion(base + "?$select=id,name,eTag,lastModifiedDateTime", tk))
    if _fecha(item["lastModifiedDateTime"]) <= programada:
        return base + "/content", {"version": "actual", "etag": item.get("eTag"), "modified": item["lastModifiedDateTime"]}
    versiones = json.loads(_peticion(base + "/versions", tk)).get("value", [])
    previas = [v for v in versiones if _fecha(v["lastModifiedDateTime"]) <= programada]
    if not previas:
        return None, {"version": None, "modified": item["lastModifiedDateTime"]}
    v = max(previas, key=lambda x: _fecha(x["lastModifiedDateTime"]))
    return f"{base}/versions/{v['id']}/content", {"version": v["id"], "modified": v["lastModifiedDateTime"]}


def capturar(config, carpeta: pathlib.Path, programada: _dt.datetime, forzar=False) -> int:
    if carpeta.exists() and any(carpeta.glob("*.xlsx")) and not forzar:
        print(f"La captura {carpeta.name} ya existe; se reutilizan las mismas copias.")
        return 0
    carpeta.mkdir(parents=True, exist_ok=True)
    tk = token(config)
    archivos, verificada = [], True
    for archivo in config["files"]:
        url, meta = version_al_corte(tk, archivo, programada)
        if url is None:
            verificada = False
            archivos.append({"file": archivo["file"], **meta, "error": "sin versión a las 12:00"})
            continue
        (carpeta / archivo["file"]).write_bytes(_peticion(url, tk))
        archivos.append({"file": archivo["file"], **meta})
    ahora = _dt.datetime.now(programada.tzinfo).replace(microsecond=0)
    (carpeta / "captura.json").write_text(json.dumps({
        "scheduledAt": programada.isoformat(), "capturedAt": ahora.isoformat(), "source": "Microsoft Graph",
        "verified": verificada, "files": archivos}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Captura {carpeta.name}: {len(archivos)} archivos · versión verificada: {'sí' if verificada else 'no'}")
    return 0 if verificada else 1
