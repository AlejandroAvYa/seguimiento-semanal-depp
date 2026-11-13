# Crea la tarea programada "DEPP - Corte semanal" en el equipo institucional que sincroniza la carpeta.
# Corre los viernes a las 12:20, 13:30 y 16:00 (hora del equipo, que debe estar en "Santiago").
# Las repeticiones son seguras: reutilizan la misma captura y no duplican resultados.
param([string]$Repo = "C:\DEPP\seguimiento-semanal-depp")
$zona = (Get-TimeZone).Id
if ($zona -ne "Pacific SA Standard Time") { Write-Warning "La zona horaria del equipo es $zona. Configure 'Santiago' (Pacific SA Standard Time)." }
$accion = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Repo\automatizacion\ejecutar_corte.ps1`" -Repo `"$Repo`""
$disparadores = @("12:20", "13:30", "16:00") | ForEach-Object { New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At $_ }
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "DEPP - Corte semanal" -Action $accion -Trigger $disparadores -Settings $ajustes -Description "Seguimiento semanal DEPP: procesa la captura del viernes 12:00 y publica el tablero y la minuta." -Force
Write-Host "Tarea creada. Pruébela con: Start-ScheduledTask -TaskName 'DEPP - Corte semanal'"
