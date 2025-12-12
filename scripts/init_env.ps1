<#
    Zentrales Setup-Skript für lokale Windows-Umgebungen.
    Schritte:
      - .venv erstellen (falls fehlt)
      - requirements.txt installieren
      - Ordner data, logs, data/backups anlegen
      - Alembic Migrationen ausführen (upgrade head)
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Write-Host "== FilamentHub Setup (Windows) ==" -ForegroundColor Cyan
Write-Host "Projektpfad: $ProjectRoot" -ForegroundColor DarkGray

# Verzeichnisse anlegen
foreach ($dir in @("data", "logs", "data\backups")) {
    $fullPath = Join-Path $ProjectRoot $dir
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath | Out-Null
        Write-Host "Ordner angelegt: $dir" -ForegroundColor Green
    }
}

# Venv erstellen falls nötig
if (-not (Test-Path $VenvPython)) {
    Write-Host ".venv nicht gefunden – erstelle virtuelles Environment..." -ForegroundColor Yellow
    $sysPython = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $sysPython) {
        throw "Kein 'python' im PATH gefunden."
    }
    & $sysPython -m venv (Join-Path $ProjectRoot ".venv")
}

# Dependencies installieren/aktualisieren
Write-Host "Installiere requirements.txt..." -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade pip | Out-Null
& $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")

# Alembic Migrationen
Write-Host "Führe alembic upgrade head aus..." -ForegroundColor Cyan
& $VenvPython -m alembic upgrade head

Write-Host "Setup fertig. DB-Pfad (Standard): data\filamenthub.db" -ForegroundColor Green
