# Instala el procesador DEPP en un equipo Windows institucional (requiere Python 3.11 o superior).
param([string]$Repo = "C:\DEPP\seguimiento-semanal-depp")
Set-Location $Repo
py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
Write-Host "Listo. Pruebe con: .\automatizacion\ejecutar_corte.ps1 -Repo $Repo"
