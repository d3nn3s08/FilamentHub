            # ========= UNTERMENÜ: LOGGING-STATUS ==========
            function Show-LoggingStatusSubmenu {
                Write-Host "================ Logging-Status ================" -ForegroundColor Yellow
                $yamlPath = "C:\Users\Denis\Desktop\FilamentHub_Projekt\FilamentHub\config.yaml"
                if (-not (Test-Path $yamlPath)) {
                    Write-Host "config.yaml nicht gefunden!" -ForegroundColor Red
                    return
                }
                $lines = Get-Content $yamlPath
                $level = "Unbekannt"
                $modStatus = @{ app = "AUS"; bambu = "AUS"; klipper = "AUS"; errors = "AUS" }
                $currentMod = ""
                foreach ($line in $lines) {
                    $tline = $line.Trim()
                    if ($tline -match "^level:\s*(\w+)") { $level = $Matches[1] }
                    if ($tline -match "^(app|bambu|klipper|errors):") { $currentMod = $Matches[1] }
                    if ($currentMod -ne "" -and $tline -match "^enabled:\s*(true|false)") {
                        $modStatus[$currentMod] = ($(if ($Matches[1] -eq "true") {"AN"} else {"AUS"}))
                        $currentMod = ""
                    }
                }
                Write-Host (" App:     " + $modStatus.app)
                Write-Host (" Bambu:   " + $modStatus.bambu)
                Write-Host (" Klipper: " + $modStatus.klipper)
                Write-Host (" Errors:  " + $modStatus.errors)
                Write-Host ""
                Write-Host (" Level:   " + $level)
                Write-Host "==============================================="
                Read-Host "Weiter mit [Enter]"
            }
### Alle Funktionsdefinitionen stehen jetzt oben
## (Hauptschleife entfernt, Menü kommt am Ende)
# FilamentHub - Pro Menu V3 (PowerShell)
# Entwickler-Menue fuer Denis

$ErrorActionPreference = "SilentlyContinue"

# ========= EINSTELLUNGEN ==========
$ProjectPath = "C:\Users\Denis\Desktop\FilamentHub_Projekt\FilamentHub"
$ConfigPath  = Join-Path $ProjectPath "config.yaml"
$LogsRoot    = Join-Path $ProjectPath "logs"

# ========= HILFSFUNKTIONEN ==========

function Read-ConfigLines {
    if (-not (Test-Path $ConfigPath)) {
        Write-Host "config.yaml nicht gefunden unter: $ConfigPath" -ForegroundColor Red
        return @()
    }
    return Get-Content $ConfigPath
}

function Write-ConfigLines($lines) {
    $lines | Set-Content -Path $ConfigPath -Encoding UTF8
}

function Get-GlobalLoggingLevel {
    $lines = Read-ConfigLines
    foreach ($line in $lines) {
        if ($line -match "global_level:\s*(\w+)") {
            return $Matches[1]
        }
    }
    return "INFO"
}


function Toggle-Module {
    param([string]$moduleName)
    
    $current = Get-ModuleEnabled $moduleName
    $newVal = -not $current
    Set-ModuleEnabled $moduleName $newVal
    $statusText = if ($newVal) { "AKTIV" } else { "DEAKTIVIERT" }
    Write-Host "Logging fuer Modul $moduleName ist jetzt: $statusText" -ForegroundColor Cyan
}

function Show-LoggingStatus {
    # Logging-Status bevorzugt aus API, Fallback config.yaml
    $url = "http://localhost:8080/api/system/status"
    $modStatus = @{ app = "AUS"; bambu = "AUS"; klipper = "AUS"; errors = "AUS" }
    $level = "Unbekannt"
    $usedApi = $false

    try {
        $response = Invoke-RestMethod -Uri $url -Method Get
        $logging = $response.logging
        if ($logging) {
            $level = $logging.level
            foreach ($key in $modStatus.Keys) {
                $enabled = $logging.modules[$key]
                $modStatus[$key] = ($(if ($enabled) {"AN"} else {"AUS"}))
            }
            $usedApi = $true
        }
    } catch {
        Write-Host "API nicht erreichbar, lese config.yaml..." -ForegroundColor DarkYellow
    }

    if (-not $usedApi) {
        if (-not (Test-Path $ConfigPath)) {
            Write-Host "[FEHLER] config.yaml nicht gefunden unter: $ConfigPath" -ForegroundColor Red
            return
        }
        $lines = Read-ConfigLines
        if ($lines.Count -eq 0) {
            Write-Host "[FEHLER] config.yaml ist leer oder konnte nicht gelesen werden!" -ForegroundColor Red
            return
        }
        $currentMod = ""
        foreach ($line in $lines) {
            $tline = $line.Trim()
            if ($tline -match "^level:\s*(\w+)") { $level = $Matches[1] }
            if ($tline -match "^(app|bambu|klipper|errors):") { $currentMod = $Matches[1] }
            if ($currentMod -ne "" -and $tline -match "^enabled:\s*(true|false)") {
                $modStatus[$currentMod] = ($(if ($Matches[1] -eq "true") {"AN"} else {"AUS"}))
                $currentMod = ""
            }
        }
    }

    Write-Host "============== Logging-Status =================" -ForegroundColor Yellow
    Write-Host (" App:     " + $modStatus.app)
    Write-Host (" Bambu:   " + $modStatus.bambu)
    Write-Host (" Klipper: " + $modStatus.klipper)
    Write-Host (" Errors:  " + $modStatus.errors)
    Write-Host ""
    Write-Host (" Level:   " + $level)
    Write-Host "==============================================="
}

function Show-SystemInfo {
    Write-Host "================ FilamentHub Menü ================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "███████╗██╗██╗      █████╗ ███╗   ███╗███████╗███╗   ██╗████████╗" -ForegroundColor Green
    Write-Host "██╔════╝██║██║     ██╔══██╗████╗ ████║██╔════╝████╗  ██║╚══██╔══╝" -ForegroundColor Green
    Write-Host "███████ ██║██║     ███████║██╔████╔██║█████╗  ██╔██╗ ██║   ██║   " -ForegroundColor Green
    Write-Host "██      ██║██║     ██╔══██║██║╚██╔╝██║██╔══╝  ██║╚██╗██║   ██║   " -ForegroundColor Green
    Write-Host "██      ██║███████╗██║  ██║██║ ╚═╝ ██║███████╗██║ ╚████║   ██║   " -ForegroundColor Green
    Write-Host "╚══     ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═══╝   ╚═╝   " -ForegroundColor Green
    Write-Host ""
    Show-LoggingStatus

    # Serverstatus pruefen (prueft ob Port 8080 offen ist)
    $serverRunning = $false
    $runScript = "C:\Users\Denis\Desktop\FilamentHub_Projekt\FilamentHub\run.py"
    $hubProcs = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "python.exe" -and $_.CommandLine -match [regex]::Escape($runScript)
    }
    if ($hubProcs) {
        $serverRunning = $true
    }
    if ($serverRunning) {
        Write-Host " Server Status: GESTARTET (FilamentHub läuft, Port 8080)" -ForegroundColor Green
    } else {
        Write-Host " Server Status: NICHT GESTARTET" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host ""
}
function Open-TodayLog {
    param([string]$moduleName)
    
    $moduleFolder = Join-Path $LogsRoot $moduleName
    $today = Get-Date -Format "yyyy-MM-dd"
    $logFile = Join-Path $moduleFolder "$today.log"
    
    if (Test-Path $logFile) {
        notepad $logFile
    } else {
        Write-Host "Keine Logdatei gefunden fuer Modul unter:" -ForegroundColor Yellow
        Write-Host $logFile
        Read-Host "Weiter mit [Enter]"
    }
}

function Get-PythonPath {
    # Bevorzugt .venv, faellt sonst auf System-Python zurueck
    $venvPython = Join-Path $ProjectPath ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }
    $sysPython = (Get-Command python -ErrorAction SilentlyContinue).Source
    return $sysPython
}

function Start-Server {
    Write-Host "Starte FilamentHub Server..." -ForegroundColor Cyan
    $python = Get-PythonPath
    $runScript = Join-Path $ProjectPath "run.py"
    
    if (-not $python) {
        Write-Host "Kein Python gefunden (.venv oder System). Bitte Python/venv installieren." -ForegroundColor Red
        Read-Host "Weiter mit [Enter]"
        return
    }
    $cmd = "cd /d `"$ProjectPath`" && `"$python`" `"$runScript`""
    Start-Process cmd.exe "/k $cmd"
}

function Show-ServerStatus {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8080/api/spools" -UseBasicParsing -TimeoutSec 10
        Write-Host "[DEBUG] HTTP-Status: $($resp.StatusCode)" -ForegroundColor DarkYellow
        if ($resp.StatusCode -eq 200) {
            Write-Host " Server Status: LAEUFT (Port 8080)" -ForegroundColor Green
        } else {
            Write-Host " Server Status: NICHT ERREICHBAR" -ForegroundColor Red
        }
    } catch {
        Write-Host "[DEBUG] Fehler: $_" -ForegroundColor DarkYellow
        Write-Host " Server Status: NICHT GESTARTET" -ForegroundColor Red
    }
}

function Stop-Server {
    Write-Host "Stoppe FilamentHub Server..." -ForegroundColor Cyan
    $hubProcs = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -like "*FilamentHub*python.exe" -or $_.Path -like "*FilamentHub_Projekt*python.exe"
    }
        Write-Host "Stoppe Python/FilamentHub Prozesse..." -ForegroundColor Cyan
        taskkill /F /IM python.exe > $null 2>&1
        Write-Host "Fertig." -ForegroundColor Green
        Read-Host "Weiter mit [Enter]"
}

function Run-Tests {
    Write-Host "Starte pytest in neuem Fenster..." -ForegroundColor Cyan
    $python = Join-Path $ProjectPath ".venv\Scripts\python.exe"
    if (Test-Path $python) {
        $batchFile = Join-Path $env:TEMP "run_pytest_filamenthub.bat"
        $batchContent = "cd /d $ProjectPath && $python -m pytest & echo. & echo Test abgeschlossen. Fenster mit beliebiger Taste schließen. & pause"
        Set-Content -Path $batchFile -Value $batchContent -Encoding ASCII
        cmd.exe /c start "Pytest" "$batchFile"
    } else {
        Write-Host "Python in .venv nicht gefunden. Bitte Venv prüfen." -ForegroundColor Red
    }
    Read-Host "Weiter mit [Enter]"
}

function Install-Dependencies {
    Write-Host "Installiere Dependencies ueber requirements.txt..." -ForegroundColor Cyan
    Push-Location $ProjectPath
    $venvPython = Join-Path $ProjectPath ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        $sysPython = (Get-Command python -ErrorAction SilentlyContinue).Source
        if ($sysPython) {
            Write-Host ".venv nicht gefunden – erstelle virtuelles Environment..." -ForegroundColor Yellow
            & $sysPython -m venv (Join-Path $ProjectPath ".venv")
        }
    }
    if (Test-Path $venvPython) {
        try {
            & $venvPython -m pip install -r requirements.txt
        } catch {
            Write-Host "Fehler beim Installieren der Dependencies!" -ForegroundColor Red
        }
    } else {
        Write-Host "Kein Python/.venv gefunden. Bitte Python installieren oder PATH pruefen." -ForegroundColor Red
    }
    Pop-Location
    Read-Host "Weiter mit [Enter]"
}

function Freeze-Requirements {
    Write-Host "Aktualisiere requirements.txt..." -ForegroundColor Cyan
    Push-Location $ProjectPath
    $python = Join-Path $ProjectPath ".venv\Scripts\python.exe"
    if (Test-Path $python) {
        try {
            & $python -m pip freeze > requirements.txt
            Write-Host "requirements.txt aktualisiert." -ForegroundColor Green
        } catch {
            Write-Host "Fehler beim Aktualisieren von requirements.txt!" -ForegroundColor Red
        }
    } else {
        Write-Host ".venv Python nicht gefunden." -ForegroundColor Red
    }
    Pop-Location
    Read-Host "Weiter mit [Enter]"
}

function Docker-Up {
    Write-Host "Starte Docker Compose (up -d)..." -ForegroundColor Cyan
    Push-Location $ProjectPath
    docker compose up -d
    Pop-Location
    Read-Host "Weiter mit [Enter]"
}

function Docker-Down {
    Write-Host "Stoppe Docker Compose (down)..." -ForegroundColor Cyan
    Push-Location $ProjectPath
    docker compose down
    Pop-Location
    Read-Host "Weiter mit [Enter]"
}

function Open-ProjectFolder {
    Start-Process explorer.exe $ProjectPath
}

# ========= HAUPTSCHLEIFE / MENUE ==========

while ($true) {
    Show-SystemInfo

    Write-Host "============= FilamentHub Pro Menue V3 =============" -ForegroundColor Cyan
    Write-Host "  1  - Server starten"
    Write-Host "  2  - Server stoppen"
    Write-Host "  3  - Tests starten (pytest)"
    Write-Host "  4  - Dependencies installieren"
    Write-Host "  5  - requirements.txt aktualisieren"
    Write-Host "  6  - Docker Compose starten (up -d)"
    Write-Host "  7  - Docker Compose stoppen (down)"
    Write-Host "  8  - Projektordner oeffnen"
    Write-Host "  9  - Server NEU STARTEN *"
    Write-Host ""
    Write-Host " 10  - App Log (heute) anzeigen"
    Write-Host " 11  - Bambu Log (heute) anzeigen"
    Write-Host " 12  - Klipper Log (heute) anzeigen"
    Write-Host " 13  - Error Log (heute) anzeigen"
    Write-Host ""
    Write-Host " 14  - Logging App an/aus"
    Write-Host " 15  - Logging Bambu an/aus"
    Write-Host " 16  - Logging Klipper an/aus"
    Write-Host " 17  - Logging Errors an/aus"
    Write-Host " 18  - Logging-Status anzeigen"
    Write-Host ""
    Write-Host " 99  - Beenden"
    Write-Host "==================================================="

    $choice = Read-Host "Auswahl"
    switch ($choice) {
        "1"  { Start-Server }
        "2"  { Stop-Server }
        "3"  { Run-Tests }
        "4"  { Install-Dependencies }
        "5"  { Freeze-Requirements }
        "6"  { Docker-Up }
        "7"  { Docker-Down }
        "8"  { Open-ProjectFolder }
        "9"  { Stop-Server; Start-Sleep -Seconds 2; Start-Server }

        "10" { Open-TodayLog "app" }
        "11" { Open-TodayLog "bambu" }
        "12" { Open-TodayLog "klipper" }
        "13" { Open-TodayLog "errors" }

        "14" { Toggle-Module "app";    Read-Host "Weiter mit [Enter]" }
        "15" { Toggle-Module "bambu";  Read-Host "Weiter mit [Enter]" }
        "16" { Toggle-Module "klipper";Read-Host "Weiter mit [Enter]" }
        "17" { Toggle-Module "errors"; Read-Host "Weiter mit [Enter]" }
        "18" { Show-LoggingStatus;     Read-Host "Weiter mit [Enter]" }

        "99" { break }
        default {
            Write-Host "Ungueltige Auswahl." -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }
}
