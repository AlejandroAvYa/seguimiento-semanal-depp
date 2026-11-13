# Ejecuta el corte semanal DEPP sobre la carpeta sincronizada de OneDrive.
# Se puede repetir sin riesgo: si la captura no cambió, no reescribe resultados.
param(
  [string]$Repo = "C:\DEPP\seguimiento-semanal-depp",
  [string]$Base = (Join-Path $env:OneDriveCommercial "DEPP_Seguimiento"),
  [string]$Corte = ""
)
$ErrorActionPreference = "Stop"
$py = Join-Path $Repo ".venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $Repo "procesador"
$env:PYTHONUTF8 = "1"
$registro = Join-Path $Base "Salidas\registro_ejecuciones.log"
New-Item -ItemType Directory -Force -Path (Join-Path $Base "Salidas") | Out-Null
$argumentos = @("-m", "depp_corte", "procesar", "--capturas", (Join-Path $Base "Capturas"), "--salidas", (Join-Path $Base "Salidas"))
if ($Corte) { $argumentos += @("--corte", $Corte) }
"==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ====" | Out-File -Append -Encoding utf8 $registro
& $py @argumentos 2>&1 | Out-File -Append -Encoding utf8 $registro
exit $LASTEXITCODE
