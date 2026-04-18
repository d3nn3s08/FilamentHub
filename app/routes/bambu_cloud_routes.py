"""
Bambu Cloud Integration API Routes
==================================
Endpunkte für die Bambu Cloud Integration:
- Konfiguration verwalten
- Sync auslösen
- Konflikte auflösen
- Status abfragen
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, col
from typing import Optional
from datetime import datetime
import logging

from app.database import get_session
from app.models.bambu_cloud_config import (
    BambuCloudConfig,
    BambuCloudConfigCreate,
    BambuCloudConfigRead,
    BambuCloudSyncStatus,
)
from app.models.cloud_conflict import (
    CloudConflict,
    CloudConflictRead,
    CloudConflictResolve,
)
from app.services.token_encryption import encrypt_token, decrypt_token
from app.services.bambu_cloud_service import (
    BambuCloudService,
    BambuCloudAuthError,
    BambuCloudAPIError,
    BambuCloudNetworkError,
)
from services.cloud_mqtt_client import (
    CloudMQTTClient,
    get_cloud_mqtt_client,
    init_cloud_mqtt,
    stop_cloud_mqtt,
)
from app.services.bambu_auth_service import (
    BambuAuthService,
    LoginState,
    LoginResult,
)
import asyncio

logger = logging.getLogger("bambu_cloud")

router = APIRouter(
    prefix="/api/bambu-cloud",
    tags=["bambu-cloud"],
)


# ============================================================
# CONFIGURATION ENDPOINTS
# ============================================================

@router.get("/config", response_model=BambuCloudConfigRead)
def get_cloud_config(session: Session = Depends(get_session)):
    """
    Gibt die aktuelle Bambu Cloud Konfiguration zurück.
    Erstellt automatisch einen leeren Eintrag falls keiner existiert.
    """
    config = session.exec(select(BambuCloudConfig)).first()

    if not config:
        # Erstelle Default-Konfiguration
        config = BambuCloudConfig(
            created_at=datetime.now().isoformat(),
        )
        session.add(config)
        session.commit()
        session.refresh(config)
        logger.info("Neue Bambu Cloud Konfiguration erstellt")

    # Token-Ablaufzeit nachträglich setzen falls noch nicht gespeichert
    # Bambu-Tokens sind opak (keine JWTs) – wir setzen eine 90-Tage-Schätzung ab jetzt
    if config.access_token_encrypted and not config.token_expires_at:
        try:
            from app.services.bambu_auth_service import compute_token_expiry
            config.token_expires_at = compute_token_expiry()  # 90-Tage-Fallback
            config.updated_at = datetime.now().isoformat()
            session.commit()
            logger.info(f"Bambu Cloud: Token-Ablaufzeit (Schätzung) gesetzt: {config.token_expires_at}")
        except Exception as e:
            logger.debug(f"Bambu Cloud: Token-Ablaufzeit konnte nicht gesetzt werden: {e}")

    # Erstelle Read-Schema mit has_token Flag
    config_read = BambuCloudConfigRead(
        id=config.id,
        bambu_user_id=config.bambu_user_id,
        bambu_username=config.bambu_username,
        region=config.region,
        has_token=bool(config.access_token_encrypted),
        token_expires_at=config.token_expires_at,
        sync_enabled=config.sync_enabled,
        sync_paused=config.sync_paused,
        dry_run_mode=config.dry_run_mode,
        auto_sync_interval_minutes=config.auto_sync_interval_minutes,
        sync_on_print_start=config.sync_on_print_start,
        sync_on_print_end=config.sync_on_print_end,
        conflict_resolution_mode=config.conflict_resolution_mode,
        auto_accept_cloud_weight=config.auto_accept_cloud_weight,
        weight_tolerance_percent=config.weight_tolerance_percent,
        last_sync_at=config.last_sync_at,
        last_sync_status=config.last_sync_status,
        last_error_message=config.last_error_message,
        connection_status=config.connection_status,
        cloud_mqtt_enabled=config.cloud_mqtt_enabled,
        cloud_mqtt_connected=config.cloud_mqtt_connected,
        cloud_mqtt_last_message=config.cloud_mqtt_last_message,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )

    return config_read


@router.put("/config", response_model=BambuCloudConfigRead)
def update_cloud_config(
    config_data: BambuCloudConfigCreate,
    session: Session = Depends(get_session)
):
    """
    Aktualisiert die Bambu Cloud Konfiguration.
    Token werden verschlüsselt gespeichert.
    """
    config = session.exec(select(BambuCloudConfig)).first()

    if not config:
        config = BambuCloudConfig(
            created_at=datetime.now().isoformat(),
        )
        session.add(config)

    # Aktualisiere Felder
    if config_data.bambu_username is not None:
        config.bambu_username = config_data.bambu_username
    if config_data.region:
        config.region = config_data.region

    # Token verschlüsseln mit Fernet
    if config_data.access_token:
        config.access_token_encrypted = encrypt_token(config_data.access_token)
        # Ablaufzeit setzen: Bambu-Tokens sind opak (keine JWTs) – 30-Tage-Fallback
        try:
            from app.services.bambu_auth_service import compute_token_expiry
            config.token_expires_at = compute_token_expiry()
            logger.info(f"Access Token aktualisiert, läuft voraussichtlich ab: {config.token_expires_at}")
        except Exception:
            pass

    if config_data.refresh_token:
        config.refresh_token_encrypted = encrypt_token(config_data.refresh_token)

    # Sync-Einstellungen
    config.sync_enabled = config_data.sync_enabled
    config.sync_paused = config_data.sync_paused
    config.dry_run_mode = config_data.dry_run_mode
    config.auto_sync_interval_minutes = config_data.auto_sync_interval_minutes
    config.sync_on_print_start = config_data.sync_on_print_start
    config.sync_on_print_end = config_data.sync_on_print_end

    # Konflikt-Einstellungen
    config.conflict_resolution_mode = config_data.conflict_resolution_mode
    config.auto_accept_cloud_weight = config_data.auto_accept_cloud_weight
    config.weight_tolerance_percent = config_data.weight_tolerance_percent

    config.updated_at = datetime.now().isoformat()

    session.commit()
    session.refresh(config)

    logger.info(f"Bambu Cloud Konfiguration aktualisiert: sync_enabled={config.sync_enabled}")
    
    # Aktualisiere Scheduler-Job wenn Intervall geändert wurde
    if config_data.auto_sync_interval_minutes is not None:
        try:
            from app.services.bambu_cloud_scheduler import update_sync_job
            update_sync_job(config.auto_sync_interval_minutes)
            logger.info(f"Bambu Cloud Scheduler aktualisiert: Intervall={config.auto_sync_interval_minutes} Minuten")
        except Exception as e:
            logger.warning(f"Bambu Cloud Scheduler konnte nicht aktualisiert werden: {e}")

    return get_cloud_config(session)


@router.delete("/config/token")
@router.post("/logout")
def delete_cloud_token(session: Session = Depends(get_session)):
    """
    Löscht den gespeicherten Token (Logout).
    """
    config = session.exec(select(BambuCloudConfig)).first()

    if config:
        config.access_token_encrypted = None
        config.refresh_token_encrypted = None
        config.token_expires_at = None
        config.bambu_user_id = None
        config.connection_status = "disconnected"
        config.sync_enabled = False  # Sync deaktivieren nach Logout
        config.updated_at = datetime.now().isoformat()
        session.commit()
        logger.info("Bambu Cloud Token gelöscht (Logout)")

    return {"status": "ok", "message": "Erfolgreich abgemeldet"}


# ============================================================
# PAUSE / RESUME / DRY-RUN
# ============================================================

@router.post("/sync/pause")
def pause_sync(session: Session = Depends(get_session)):
    """Pausiert den Cloud-Sync. Credentials bleiben erhalten."""
    config = session.exec(select(BambuCloudConfig)).first()
    if not config:
        raise HTTPException(status_code=404, detail="Keine Cloud-Konfiguration vorhanden")

    config.sync_paused = True
    config.updated_at = datetime.now().isoformat()
    session.commit()
    logger.info("Bambu Cloud Sync pausiert (Credentials bleiben erhalten)")
    return {"status": "ok", "sync_paused": True, "message": "Sync pausiert"}


@router.post("/sync/resume")
def resume_sync(session: Session = Depends(get_session)):
    """Setzt den Cloud-Sync fort."""
    config = session.exec(select(BambuCloudConfig)).first()
    if not config:
        raise HTTPException(status_code=404, detail="Keine Cloud-Konfiguration vorhanden")

    config.sync_paused = False
    config.updated_at = datetime.now().isoformat()
    session.commit()
    logger.info("Bambu Cloud Sync fortgesetzt")
    return {"status": "ok", "sync_paused": False, "message": "Sync fortgesetzt"}


@router.post("/sync/dry-run")
def toggle_dry_run(
    enable: bool = True,
    session: Session = Depends(get_session)
):
    """Aktiviert/Deaktiviert den Dry-Run (Test) Modus."""
    config = session.exec(select(BambuCloudConfig)).first()
    if not config:
        raise HTTPException(status_code=404, detail="Keine Cloud-Konfiguration vorhanden")

    config.dry_run_mode = enable
    config.updated_at = datetime.now().isoformat()
    session.commit()
    logger.info(f"Bambu Cloud Dry-Run Modus: {'aktiviert' if enable else 'deaktiviert'}")
    return {"status": "ok", "dry_run_mode": enable}


@router.post("/disable")
def disable_cloud_integration(
    keep_credentials: bool = True,
    session: Session = Depends(get_session)
):
    """
    Deaktiviert die Cloud-Integration permanent.
    Optional: Credentials behalten oder löschen.
    """
    config = session.exec(select(BambuCloudConfig)).first()
    if not config:
        raise HTTPException(status_code=404, detail="Keine Cloud-Konfiguration vorhanden")

    config.sync_enabled = False
    config.sync_paused = False
    config.dry_run_mode = False
    config.cloud_mqtt_enabled = False

    if not keep_credentials:
        config.access_token_encrypted = None
        config.refresh_token_encrypted = None
        config.token_expires_at = None
        config.bambu_user_id = None
        config.bambu_username = None
        config.connection_status = "disconnected"
        logger.info("Bambu Cloud Integration deaktiviert (Credentials gelöscht)")
    else:
        logger.info("Bambu Cloud Integration deaktiviert (Credentials beibehalten)")

    config.updated_at = datetime.now().isoformat()
    session.commit()

    return {
        "status": "ok",
        "credentials_kept": keep_credentials,
        "message": f"Cloud Integration deaktiviert{' (Credentials beibehalten)' if keep_credentials else ' (Credentials gelöscht)'}"
    }


# ============================================================
# LOGIN ENDPOINTS (Email + Passwort → Token)
# ============================================================

@router.post("/login")
async def bambu_cloud_login(
    email: str,
    password: str,
    region: str = "eu",
    tfa_code: Optional[str] = None,  # Optional: TFA Code direkt mitgeben
    session: Session = Depends(get_session)
):
    """
    Startet den Login bei Bambu Lab Cloud.

    Bei den meisten Accounts wird ein Verifikationscode per Email gesendet.
    In diesem Fall muss danach /login/verify aufgerufen werden.

    Falls tfa_code mitgegeben wird, wird versucht Login + TFA in einem Schritt zu machen.

    Returns:
        - state: "success" | "need_verification_code" | "need_tfa" | "failed"
        - message: Beschreibung des nächsten Schritts
    """
    auth = BambuAuthService(region=region)

    try:
        # Falls TFA-Code mitgegeben wurde, versuche kombinierten Login
        if tfa_code:
            print(f"[LOGIN] Combined login with TFA code")
            result = await auth.login_with_tfa(email, password, tfa_code)
        else:
            result = await auth.login(email, password)

        if result.state == LoginState.SUCCESS:
            # Direkter Login erfolgreich - Token speichern
            config = session.exec(select(BambuCloudConfig)).first()
            if not config:
                config = BambuCloudConfig(created_at=datetime.now().isoformat())
                session.add(config)

            if result.access_token:
                config.access_token_encrypted = encrypt_token(result.access_token)
                # Ablaufzeit speichern (aus expiresIn oder 30-Tage-Fallback)
                if result.expires_at:
                    config.token_expires_at = result.expires_at
            else:
                config.access_token_encrypted = None

            if result.refresh_token:
                config.refresh_token_encrypted = encrypt_token(result.refresh_token)
            else:
                config.refresh_token_encrypted = None
            config.bambu_user_id = result.user_id
            config.bambu_username = email
            config.region = region
            config.connection_status = "connected"
            config.sync_enabled = True  # Automatisch aktivieren nach erfolgreichem Login
            config.last_error_message = None
            config.updated_at = datetime.now().isoformat()
            session.commit()

            logger.info(f"Bambu Cloud Login erfolgreich für {email}, Token läuft ab: {config.token_expires_at}")

            return {
                "status": "ok",
                "state": "success",
                "message": "Login erfolgreich",
                "user_id": result.user_id,
            }

        elif result.state == LoginState.NEED_VERIFICATION_CODE:
            # Email-Verifikation erforderlich
            # Email temporär speichern für verify-Schritt
            config = session.exec(select(BambuCloudConfig)).first()
            if not config:
                config = BambuCloudConfig(created_at=datetime.now().isoformat())
                session.add(config)

            config.bambu_username = email
            config.region = region
            config.connection_status = "pending_verification"
            config.updated_at = datetime.now().isoformat()
            session.commit()

            return {
                "status": "ok",
                "state": "need_verification_code",
                "message": "Verifikationscode wurde per Email gesendet. Bitte /login/verify aufrufen.",
                "email": email,
            }

        elif result.state == LoginState.NEED_TFA:
            tfa_key = result.tfa_key
            tfa_key_len = len(tfa_key) if tfa_key else 0
            tfa_key_preview = tfa_key[:30] + "..." if tfa_key and len(tfa_key) > 30 else tfa_key
            logger.info(f"Login: TFA required, tfaKey length={tfa_key_len}, preview={tfa_key_preview}")
            print(f"[TFA DEBUG] tfaKey length={tfa_key_len}")
            print(f"[TFA DEBUG] tfaKey preview: {tfa_key_preview}")
            return {
                "status": "ok",
                "state": "need_tfa",
                "message": "2FA Code erforderlich",
                "tfa_key": tfa_key,
                "tfa_key_length": tfa_key_len,  # Debug: zeigt Länge im Frontend
            }

        else:
            return {
                "status": "error",
                "state": "failed",
                "message": result.message or "Login fehlgeschlagen",
            }

    except Exception as e:
        logger.error(f"Bambu Cloud Login Fehler: {e}", exc_info=True)
        return {
            "status": "error",
            "state": "failed",
            "message": str(e),
        }

    finally:
        await auth.close()


@router.post("/login/verify")
async def bambu_cloud_verify_code(
    email: str,
    code: str,
    region: str = "eu",
    session: Session = Depends(get_session)
):
    """
    Verifiziert den Email-Code und schließt den Login ab.

    Args:
        email: Email-Adresse (dieselbe wie beim Login)
        code: 6-stelliger Code aus der Email
        region: Region (eu, us, cn)

    Returns:
        Bei Erfolg wird der Token gespeichert.
    """
    auth = BambuAuthService(region=region)

    try:
        result = await auth.verify_code(email, code)

        if result.state == LoginState.SUCCESS:
            # Token speichern
            config = session.exec(select(BambuCloudConfig)).first()
            if not config:
                config = BambuCloudConfig(created_at=datetime.now().isoformat())
                session.add(config)

            if result.access_token:
                config.access_token_encrypted = encrypt_token(result.access_token)
                # Ablaufzeit speichern (aus expiresIn oder 30-Tage-Fallback)
                if result.expires_at:
                    config.token_expires_at = result.expires_at
            else:
                config.access_token_encrypted = None

            if result.refresh_token:
                config.refresh_token_encrypted = encrypt_token(result.refresh_token)
            else:
                config.refresh_token_encrypted = None
            config.bambu_user_id = result.user_id
            config.bambu_username = email
            config.region = region
            config.connection_status = "connected"
            config.sync_enabled = True  # Automatisch aktivieren nach erfolgreichem Login
            config.last_error_message = None
            config.updated_at = datetime.now().isoformat()
            session.commit()

            logger.info(f"Bambu Cloud Verifikation erfolgreich für {email}, user_id={result.user_id}, Token läuft ab: {config.token_expires_at}")

            return {
                "status": "ok",
                "state": "success",
                "message": "Verifikation erfolgreich - Token gespeichert",
                "user_id": result.user_id,
            }

        else:
            return {
                "status": "error",
                "state": "failed",
                "message": result.message or "Verifikation fehlgeschlagen",
            }

    except Exception as e:
        logger.error(f"Bambu Cloud Verify Fehler: {e}", exc_info=True)
        return {
            "status": "error",
            "state": "failed",
            "message": str(e),
        }

    finally:
        await auth.close()


@router.post("/login/tfa")
async def bambu_cloud_verify_tfa(
    tfa_key: str,
    tfa_code: str,
    email: str,
    region: str = "eu",
    session: Session = Depends(get_session)
):
    """
    Verifiziert den 2FA TOTP Code.

    Args:
        tfa_key: Key aus dem Login-Response
        tfa_code: 6-stelliger TOTP Code
        email: Email-Adresse
        region: Region

    Returns:
        Bei Erfolg wird der Token gespeichert.
    """
    auth = BambuAuthService(region=region)

    try:
        result = await auth.verify_tfa(tfa_key, tfa_code, email=email)

        if result.state == LoginState.SUCCESS:
            # Token speichern
            config = session.exec(select(BambuCloudConfig)).first()
            if not config:
                config = BambuCloudConfig(created_at=datetime.now().isoformat())
                session.add(config)

            if result.access_token:
                config.access_token_encrypted = encrypt_token(result.access_token)
                # Ablaufzeit speichern (aus expiresIn oder 30-Tage-Fallback)
                if result.expires_at:
                    config.token_expires_at = result.expires_at
            else:
                config.access_token_encrypted = None

            if result.refresh_token:
                config.refresh_token_encrypted = encrypt_token(result.refresh_token)
            else:
                config.refresh_token_encrypted = None
            config.bambu_user_id = result.user_id
            config.bambu_username = email
            config.region = region
            config.connection_status = "connected"
            config.sync_enabled = True  # Automatisch aktivieren nach erfolgreichem Login
            config.last_error_message = None
            config.updated_at = datetime.now().isoformat()
            session.commit()

            logger.info(f"Bambu Cloud TFA erfolgreich für {email}, Token läuft ab: {config.token_expires_at}")

            return {
                "status": "ok",
                "state": "success",
                "message": "TFA erfolgreich - Token gespeichert",
                "user_id": result.user_id,
            }

        else:
            return {
                "status": "error",
                "state": "failed",
                "message": result.message or "TFA fehlgeschlagen",
            }

    except Exception as e:
        logger.error(f"Bambu Cloud TFA Fehler: {e}", exc_info=True)
        return {
            "status": "error",
            "state": "failed",
            "message": str(e),
        }

    finally:
        await auth.close()


# ============================================================
# TASKS / PRINT JOBS ENDPOINTS
# ============================================================

@router.get("/tasks")
async def get_cloud_tasks(
    device_id: Optional[str] = None,
    limit: int = 20,
    session: Session = Depends(get_session)
):
    """
    Ruft Druck-Jobs/Tasks aus der Bambu Cloud ab.

    Args:
        device_id: Optional - nur Jobs von diesem Drucker
        limit: Maximale Anzahl (default: 20)

    Returns:
        Liste von Tasks mit Filament-Verbrauch, Druckzeit, etc.
    """
    config = session.exec(select(BambuCloudConfig)).first()

    if not config or not config.access_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kein Bambu Cloud Token konfiguriert"
        )

    try:
        access_token = decrypt_token(config.access_token_encrypted)
        service = BambuCloudService(
            access_token=access_token,
            region=config.region
        )

        try:
            tasks = await service.get_tasks(device_id=device_id, limit=limit)

            # Konvertiere zu Dict für JSON Response
            tasks_data = [
                {
                    "id": t.id,
                    "title": t.title,
                    "device_id": t.device_id,
                    "device_name": t.device_name,
                    "status": t.status,
                    "weight_g": t.weight,
                    "length_mm": t.length,
                    "cost_time_seconds": t.cost_time,
                    "cost_time_formatted": f"{t.cost_time // 3600}h {(t.cost_time % 3600) // 60}m" if t.cost_time else "-",
                    "start_time": t.start_time,
                    "end_time": t.end_time,
                    "cover_url": t.cover_url,
                    "thumbnail_url": t.thumbnail_url,
                    "plate_index": t.plate_index,
                    "ams_mapping": t.ams_mapping,
                }
                for t in tasks
            ]

            return {
                "status": "ok",
                "count": len(tasks_data),
                "tasks": tasks_data
            }

        finally:
            await service.close()

    except BambuCloudAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentifizierungsfehler: {e}"
        )
    except Exception as e:
        logger.error(f"Bambu Cloud Tasks Fehler: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fehler: {e}"
        )


# ============================================================
# CLOUD JOB MATCHING ENDPOINT
# ============================================================

@router.get("/tasks/match/{job_id}")
async def match_cloud_task_for_job(
    job_id: str,
    session: Session = Depends(get_session)
):
    """
    Sucht einen passenden Cloud-Task für einen lokalen Job.

    Matching-Logik:
    1. Job-Name (title) muss übereinstimmen
    2. Drucker-ID (deviceId) muss übereinstimmen
    3. Zeitfenster: Cloud-Task innerhalb ±24h des Job-Starts

    Returns:
        Cloud-Task mit amsDetailMapping für Filament-Verbrauch pro Spule
    """
    from app.models.job import Job
    from app.models.printer import Printer

    # Hole den lokalen Job
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job nicht gefunden"
        )

    # Hole den Drucker
    printer = session.get(Printer, job.printer_id) if job.printer_id else None
    if not printer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job hat keinen zugewiesenen Drucker"
        )

    # Cloud-Konfiguration prüfen
    config = session.exec(select(BambuCloudConfig)).first()
    if not config or not config.access_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kein Bambu Cloud Token konfiguriert"
        )

    try:
        access_token = decrypt_token(config.access_token_encrypted)
        service = BambuCloudService(
            access_token=access_token,
            region=config.region
        )

        try:
            # Hole Cloud-Tasks (mehr als default für besseres Matching)
            tasks = await service.get_tasks(limit=50)

            print(f"[CLOUD MATCH] Found {len(tasks)} cloud tasks for matching")

            # Finde passenden Task
            matched_task = None

            # Job-Startzeit robust parsen
            job_start = None
            if job.started_at:
                if isinstance(job.started_at, str):
                    try:
                        job_start = datetime.fromisoformat(job.started_at.replace('Z', '+00:00'))
                    except:
                        pass
                else:
                    job_start = job.started_at

            # Printer-Felder: cloud_serial, bambu_device_id, name
            printer_serial = printer.cloud_serial or printer.bambu_device_id or ""
            print(f"[CLOUD MATCH] Job: {job.name}, Printer: {printer.name}, Serial: {printer_serial}, Start: {job_start}")

            for task in tasks:
                # 1. Name-Matching (case-insensitive, partial match)
                task_title = task.title.lower() if task.title else ""
                job_name = job.name.lower() if job.name else ""

                name_match = (
                    task_title == job_name or
                    task_title in job_name or
                    job_name in task_title
                )

                # 2. Drucker-Matching (device_id, device_name, cloud_serial, bambu_device_id)
                device_match = False
                # Cloud device_id könnte Serial oder bambu_device_id sein
                if task.device_id and printer_serial:
                    device_match = task.device_id == printer_serial
                # Cloud device_name könnte Drucker-Name sein (z.B. "3DP-00M-070")
                if not device_match and task.device_name and printer.name:
                    device_match = (
                        task.device_name.lower() == printer.name.lower() or
                        task.device_name.lower() in printer.name.lower() or
                        printer.name.lower() in task.device_name.lower()
                    )

                # 3. Zeit-Matching (±24h Fenster)
                time_match = False
                if task.start_time and job_start:
                    try:
                        # Parse Cloud-Zeit (Format: 2026-01-30T16:06:49Z)
                        task_time_str = task.start_time.replace('Z', '')
                        task_start = datetime.fromisoformat(task_time_str)

                        # Job-Zeit ohne Timezone für Vergleich
                        job_start_cmp = job_start
                        if hasattr(job_start, 'tzinfo') and job_start.tzinfo:
                            job_start_cmp = job_start.replace(tzinfo=None)

                        time_diff = abs((task_start - job_start_cmp).total_seconds())
                        time_match = time_diff < 86400  # 24 Stunden
                        print(f"[CLOUD MATCH] Time diff: {time_diff}s ({time_diff/3600:.1f}h)")
                    except Exception as e:
                        print(f"[CLOUD MATCH] Time compare error: {e}")

                # Debug: Zeige Matching-Ergebnis für ersten paar Tasks
                print(f"[CLOUD MATCH] Task '{task.title}': name={name_match}, device={device_match}, time={time_match}")

                # Mindestens Name + (Drucker ODER Zeit) müssen matchen
                if name_match and (device_match or time_match):
                    matched_task = task
                    logger.info(f"Cloud-Task Match gefunden: {task.id} für Job {job.name}")
                    print(f"[CLOUD MATCH] ✅ MATCH FOUND: Task {task.id}")
                    break

            if not matched_task:
                return {
                    "status": "no_match",
                    "message": f"Kein passender Cloud-Task für '{job.name}' gefunden",
                    "job_name": job.name,
                    "printer_serial": printer_serial
                }

            # Extrahiere Filament-Daten aus amsDetailMapping
            filament_data = []
            if matched_task.ams_mapping:
                for mapping in matched_task.ams_mapping:
                    filament_data.append({
                        "ams_slot": mapping.get("ams", 0),
                        "slot_id": mapping.get("slotId", 0),
                        "filament_type": mapping.get("filamentType", ""),
                        "filament_id": mapping.get("filamentId", ""),
                        "color": mapping.get("sourceColor", mapping.get("targetColor", "")),
                        "weight_g": float(mapping.get("weight", 0) or 0),
                    })

            return {
                "status": "matched",
                "cloud_task": {
                    "id": matched_task.id,
                    "title": matched_task.title,
                    "device_id": matched_task.device_id,
                    "device_name": matched_task.device_name,
                    "start_time": matched_task.start_time,
                    "end_time": matched_task.end_time,
                    "total_weight_g": matched_task.weight,
                    "total_length_mm": matched_task.length,
                    "cost_time_seconds": matched_task.cost_time,
                },
                "filament_usage": filament_data,
                "total_weight_g": sum(f["weight_g"] for f in filament_data),
            }

        finally:
            await service.close()

    except BambuCloudAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Cloud-Authentifizierung fehlgeschlagen: {e}"
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Cloud-Task Matching Fehler: {e}\n{error_details}")
        print(f"[CLOUD MATCH] ❌ ERROR: {e}")
        print(f"[CLOUD MATCH] Traceback:\n{error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fehler beim Cloud-Abgleich: {e}"
        )


# ============================================================
# SYNC ENDPOINTS
# ============================================================

@router.get("/sync/status", response_model=BambuCloudSyncStatus)
def get_sync_status(session: Session = Depends(get_session)):
    """
    Gibt den aktuellen Sync-Status zurück.
    """
    config = session.exec(select(BambuCloudConfig)).first()

    # Zähle offene Konflikte
    conflicts_list = session.exec(
        select(CloudConflict).where(CloudConflict.status == "pending")
    ).all()
    conflicts_count = len(conflicts_list)

    # Zähle Drucker mit Cloud-Sync
    from app.models.printer import Printer
    printers_count = len(session.exec(select(Printer)).all())

    # Zähle Spulen mit Cloud-Status
    from app.models.spool import Spool
    spools_with_cloud = session.exec(
        select(Spool).where(Spool.cloud_sync_status != None)
    ).all()
    synced_spools = len(spools_with_cloud)

    # Zähle alle Spulen
    all_spools = len(session.exec(select(Spool)).all())

    # Prüfe ob Config existiert und Token vorhanden
    has_config = config is not None
    has_token = bool(config.access_token_encrypted) if config else False
    connection_status = config.connection_status if config else None

    # Verbunden wenn: Token vorhanden UND Status "connected"
    is_connected = has_config and has_token and connection_status == "connected"

    # Permissiver Fallback NUR für neue Configs ohne Status-Eintrag (noch nicht getestet):
    # KEIN Override wenn connection_status explizit "error" ist (z.B. Token-Entschlüsselung fehlgeschlagen)
    if has_config and has_token and config.sync_enabled and connection_status not in ("error", "disconnected"):
        is_connected = True

    is_paused = config.sync_paused if config else False
    is_dry_run = config.dry_run_mode if config else False

    return BambuCloudSyncStatus(
        is_syncing=False,  # TODO: Echten Sync-Status tracken
        is_connected=is_connected,
        is_paused=is_paused,
        is_dry_run=is_dry_run,
        has_config=has_config and has_token,
        last_sync=config.last_sync_at if config else None,
        last_sync_at=config.last_sync_at if config else None,
        last_sync_status=config.last_sync_status if config else None,
        synced_printers=printers_count,
        synced_spools_count=synced_spools if synced_spools > 0 else all_spools,
        pending_conflicts=conflicts_count,
        conflicts_count=conflicts_count,
        errors=[],
        connection_status=connection_status,
        last_error_message=config.last_error_message if config else None,
        token_expires_at=config.token_expires_at if config else None,
    )


@router.post("/sync/trigger")
async def trigger_sync(session: Session = Depends(get_session)):
    """
    Löst einen manuellen Sync mit der Bambu Cloud aus.
    Beachtet Pause- und Dry-Run-Modus.
    """
    config = session.exec(select(BambuCloudConfig)).first()

    if not config or not config.access_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kein Bambu Cloud Token konfiguriert"
        )

    if config.sync_paused:
        return {
            "status": "paused",
            "message": "Sync ist pausiert. Klicke 'Resume' um fortzufahren.",
            "timestamp": datetime.now().isoformat()
        }

    try:
        # Token entschlüsseln
        access_token = decrypt_token(config.access_token_encrypted)
        
        # Service erstellen
        service = BambuCloudService(
            access_token=access_token,
            region=config.region
        )
        
        try:
            # Vollständigen Sync durchführen
            sync_result = await service.perform_full_sync(
                session=session,
                conflict_resolution_mode=config.conflict_resolution_mode
            )
            
            # Config aktualisieren
            config.last_sync_at = datetime.now().isoformat()
            config.last_sync_status = "success"
            config.connection_status = "connected"
            config.last_error_message = None
            config.updated_at = datetime.now().isoformat()
            session.commit()
            
            logger.info(f"Bambu Cloud Sync erfolgreich: {sync_result}")
            
            return {
                "status": "ok",
                "message": "Sync erfolgreich",
                "timestamp": datetime.now().isoformat(),
                "result": sync_result
            }
            
        finally:
            await service.close()
            
    except BambuCloudAuthError as e:
        config.last_sync_status = "error"
        config.connection_status = "error"
        config.last_error_message = str(e)
        config.updated_at = datetime.now().isoformat()
        session.commit()
        
        logger.error(f"Bambu Cloud Sync Auth-Fehler: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentifizierungsfehler: {e}"
        )
        
    except (BambuCloudAPIError, BambuCloudNetworkError) as e:
        config.last_sync_status = "error"
        config.connection_status = "error"
        config.last_error_message = str(e)
        config.updated_at = datetime.now().isoformat()
        session.commit()
        
        logger.error(f"Bambu Cloud Sync Fehler: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync-Fehler: {e}"
        )
        
    except Exception as e:
        logger.error(f"Bambu Cloud Sync unerwarteter Fehler: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unerwarteter Fehler: {e}"
        )


# ============================================================
# CONFLICT ENDPOINTS
# ============================================================

@router.get("/conflicts", response_model=list[CloudConflictRead])
def get_conflicts(
    status_filter: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """
    Gibt alle Cloud-Konflikte zurück.
    Optional filterbar nach Status.
    """
    query = select(CloudConflict)

    if status_filter:
        query = query.where(CloudConflict.status == status_filter)

    query = query.order_by(col(CloudConflict.detected_at).desc())

    conflicts = session.exec(query).all()

    # Erweitere mit Spool/Printer-Namen
    result = []
    for conflict in conflicts:
        conflict_read = CloudConflictRead.model_validate(conflict)

        # Lade Spool-Name falls vorhanden
        if conflict.spool_id:
            from app.models.spool import Spool
            spool = session.get(Spool, conflict.spool_id)
            if spool:
                conflict_read.spool_name = spool.name
                conflict_read.spool_number = spool.spool_number

        # Lade Printer-Name falls vorhanden
        if conflict.printer_id:
            from app.models.printer import Printer
            printer = session.get(Printer, conflict.printer_id)
            if printer:
                conflict_read.printer_name = printer.name

        result.append(conflict_read)

    return result


@router.get("/conflicts/pending/count")
def get_pending_conflicts_count(session: Session = Depends(get_session)):
    """
    Gibt die Anzahl offener Konflikte zurück.
    Für Benachrichtigungen im UI.
    """
    count = len(session.exec(
        select(CloudConflict).where(CloudConflict.status == "pending")
    ).all())

    return {"count": count}


@router.post("/conflicts/{conflict_id}/resolve")
def resolve_conflict(
    conflict_id: str,
    resolution: CloudConflictResolve,
    session: Session = Depends(get_session)
):
    """
    Löst einen Konflikt auf.
    """
    conflict = session.get(CloudConflict, conflict_id)

    if not conflict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konflikt nicht gefunden"
        )

    if conflict.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Konflikt ist bereits {conflict.status}"
        )

    # Anwenden der Resolution
    conflict.status = "resolved"
    conflict.resolution = resolution.resolution
    conflict.resolved_at = datetime.now().isoformat()
    conflict.resolved_by = "user"
    conflict.updated_at = datetime.now().isoformat()

    # Je nach Resolution die Daten aktualisieren
    if resolution.resolution == "accept_cloud" and conflict.spool_id:
        from app.models.spool import Spool
        import json
        
        spool = session.get(Spool, conflict.spool_id)
        if spool:
            # Cloud-Wert parsen
            try:
                cloud_value_str = conflict.cloud_value or "0"
                cloud_remain_percent = float(cloud_value_str)
                
                # Wenn Spool weight_full vorhanden, berechne neues Gewicht
                if spool.weight_full and spool.weight_full > 0:
                    old_weight = spool.weight_current or (spool.weight_full - spool.weight_empty if spool.weight_full else 0)
                    new_weight = (cloud_remain_percent / 100.0) * spool.weight_full
                    spool.weight_current = max(0, new_weight)
                    spool.weight_source = "bambu_cloud"
                    spool.last_verified_at = datetime.now().isoformat()
                    spool.cloud_sync_status = "synced"
                    
                    # Weight History erstellen
                    from app.models.weight_history import WeightHistory
                    weight_entry = WeightHistory(
                        spool_uuid=spool.tray_uuid or spool.id,
                        spool_number=spool.spool_number,
                        old_weight=old_weight,
                        new_weight=spool.weight_current,
                        change_reason='bambu_cloud_conflict_resolution',
                        source='bambu_cloud',
                        user='user',
                        details=f"Konflikt aufgelöst: Cloud-Wert übernommen ({cloud_remain_percent}%)",
                        timestamp=datetime.now()
                    )
                    session.add(weight_entry)
                    
                    logger.info(
                        f"Konflikt {conflict_id}: Cloud-Wert übernommen - "
                        f"Gewicht: {old_weight}g -> {spool.weight_current}g"
                    )
                else:
                    logger.warning(f"Konflikt {conflict_id}: Spool hat kein weight_full, kann nicht berechnen")
            except (ValueError, TypeError) as e:
                logger.error(f"Konflikt {conflict_id}: Fehler beim Parsen des Cloud-Werts: {e}")

    elif resolution.resolution == "keep_local":
        # Lokaler Wert bleibt bestehen, nur Status aktualisieren
        if conflict.spool_id:
            from app.models.spool import Spool
            spool = session.get(Spool, conflict.spool_id)
            if spool:
                spool.cloud_sync_status = "local_preferred"
        logger.info(f"Konflikt {conflict_id}: Lokaler Wert behalten")

    elif resolution.resolution == "merge" and resolution.merge_value:
        from app.models.spool import Spool
        import json
        
        if conflict.spool_id:
            spool = session.get(Spool, conflict.spool_id)
            if spool:
                try:
                    # Merge-Wert parsen (erwartet als JSON-String oder direkt als Zahl)
                    merge_value = resolution.merge_value
                    if isinstance(merge_value, str):
                        merge_data = json.loads(merge_value)
                    else:
                        merge_data = merge_value
                    
                    # Wenn es ein Gewicht ist
                    if isinstance(merge_data, (int, float)) and spool.weight_full:
                        old_weight = spool.weight_current or (spool.weight_full - spool.weight_empty if spool.weight_full else 0)
                        new_weight = float(merge_data)
                        spool.weight_current = max(0, min(new_weight, spool.weight_full))
                        spool.weight_source = "bambu_cloud"
                        spool.last_verified_at = datetime.now().isoformat()
                        
                        # Weight History
                        from app.models.weight_history import WeightHistory
                        weight_entry = WeightHistory(
                            spool_uuid=spool.tray_uuid or spool.id,
                            spool_number=spool.spool_number,
                            old_weight=old_weight,
                            new_weight=spool.weight_current,
                            change_reason='bambu_cloud_conflict_merge',
                            source='bambu_cloud',
                            user='user',
                            details=f"Konflikt zusammengeführt: {merge_data}g",
                            timestamp=datetime.now()
                        )
                        session.add(weight_entry)
                        
                        logger.info(f"Konflikt {conflict_id}: Werte zusammengeführt - {merge_data}g")
                except (ValueError, TypeError, json.JSONDecodeError) as e:
                    logger.error(f"Konflikt {conflict_id}: Fehler beim Merge: {e}")

    elif resolution.resolution == "ignore":
        conflict.status = "ignored"
        logger.info(f"Konflikt {conflict_id}: Ignoriert")

    session.commit()

    return {"status": "ok", "message": f"Konflikt {resolution.resolution}"}


@router.post("/conflicts/resolve-all")
def resolve_all_conflicts(
    resolution: str,
    session: Session = Depends(get_session)
):
    """
    Löst alle offenen Konflikte mit derselben Strategie auf.
    """
    if resolution not in ["keep_local", "accept_cloud", "ignore"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ungültige Resolution"
        )

    pending = session.exec(
        select(CloudConflict).where(CloudConflict.status == "pending")
    ).all()

    now = datetime.now().isoformat()

    for conflict in pending:
        conflict.status = "resolved" if resolution != "ignore" else "ignored"
        conflict.resolution = resolution
        conflict.resolved_at = now
        conflict.resolved_by = "user"
        conflict.updated_at = now

    session.commit()

    logger.info(f"Alle {len(pending)} Konflikte aufgelöst: {resolution}")

    return {
        "status": "ok",
        "resolved_count": len(pending),
        "resolution": resolution
    }


# ============================================================
# CONNECTION TEST
# ============================================================

@router.post("/test-connection")
async def test_cloud_connection(session: Session = Depends(get_session)):
    """
    Testet die Verbindung zur Bambu Cloud.
    """
    config = session.exec(select(BambuCloudConfig)).first()

    if not config or not config.access_token_encrypted:
        return {
            "status": "error",
            "connected": False,
            "message": "Kein Token konfiguriert"
        }

    try:
        # Token entschlüsseln
        access_token = decrypt_token(config.access_token_encrypted)
        
        # Service erstellen
        service = BambuCloudService(
            access_token=access_token,
            region=config.region
        )
        
        try:
            # Verbindung testen
            is_connected = await service.test_connection()
            
            if is_connected:
                # User-Info abrufen für zusätzliche Validierung
                user_info = await service.get_user_info()
                
                # Config aktualisieren
                config.connection_status = "connected"
                config.last_error_message = None
                if user_info.get("user_id"):
                    config.bambu_user_id = str(user_info.get("user_id"))
                config.updated_at = datetime.now().isoformat()
                session.commit()
                
                return {
                    "status": "ok",
                    "connected": True,
                    "message": "Verbindung erfolgreich",
                    "region": config.region,
                    "username": config.bambu_username,
                    "user_id": config.bambu_user_id
                }
            else:
                config.connection_status = "error"
                config.last_error_message = "Verbindungstest fehlgeschlagen"
                config.updated_at = datetime.now().isoformat()
                session.commit()
                
                return {
                    "status": "error",
                    "connected": False,
                    "message": "Verbindungstest fehlgeschlagen"
                }
                
        finally:
            await service.close()
            
    except BambuCloudAuthError as e:
        config.connection_status = "error"
        config.last_error_message = str(e)
        config.updated_at = datetime.now().isoformat()
        session.commit()
        
        return {
            "status": "error",
            "connected": False,
            "message": f"Authentifizierungsfehler: {e}"
        }
        
    except Exception as e:
        logger.error(f"Bambu Cloud Connection Test Fehler: {e}", exc_info=True)
        return {
            "status": "error",
            "connected": False,
            "message": f"Fehler: {e}"
        }


# ============================================================
# CLOUD MQTT ENDPOINTS
# ============================================================

@router.get("/cloud-mqtt/status")
def get_cloud_mqtt_status(session: Session = Depends(get_session)):
    """
    Gibt den Status der Cloud MQTT Verbindung zurück.
    """
    client = get_cloud_mqtt_client()

    if not client:
        return {
            "enabled": False,
            "connected": False,
            "message": "Cloud MQTT nicht initialisiert"
        }

    status = client.get_status()
    return {
        "enabled": True,
        **status
    }


@router.post("/cloud-mqtt/start")
async def start_cloud_mqtt(session: Session = Depends(get_session)):
    """
    Startet die Cloud MQTT Verbindung.
    Verwendet den gespeicherten Token und User-ID.
    """
    config = session.exec(select(BambuCloudConfig)).first()

    if not config or not config.access_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kein Bambu Cloud Token konfiguriert"
        )

    if not config.bambu_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Keine User-ID vorhanden. Bitte zuerst Verbindung testen."
        )

    try:
        # Token entschlüsseln
        from app.services.token_encryption import decrypt_token
        access_token = decrypt_token(config.access_token_encrypted)

        # Drucker laden die Cloud-fähig sind
        from app.models.printer import Printer
        printers = session.exec(select(Printer)).all()

        devices = []
        for printer in printers:
            if printer.cloud_serial:
                devices.append({
                    "serial": printer.cloud_serial,
                    "model": printer.model or "UNKNOWN",
                    "name": printer.name,
                })

        if not devices:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Keine Drucker mit Cloud-Serial gefunden"
            )

        # PrinterService für Updates
        from services.printer_service import PrinterService
        printer_service = PrinterService()

        # Cloud MQTT starten
        client = init_cloud_mqtt(
            user_id=config.bambu_user_id,
            access_token=access_token,
            region=config.region,
            printer_service=printer_service,
            devices=devices,
        )

        # Config aktualisieren
        config.cloud_mqtt_enabled = True
        config.cloud_mqtt_connected = client.connected
        config.updated_at = datetime.now().isoformat()
        session.commit()

        logger.info(f"Cloud MQTT gestartet mit {len(devices)} Druckern")

        return {
            "status": "ok",
            "message": f"Cloud MQTT gestartet mit {len(devices)} Druckern",
            "devices": [d["serial"] for d in devices]
        }

    except Exception as e:
        logger.error(f"Cloud MQTT Start Fehler: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cloud MQTT Start fehlgeschlagen: {e}"
        )


@router.post("/cloud-mqtt/stop")
def stop_cloud_mqtt_endpoint(session: Session = Depends(get_session)):
    """
    Stoppt die Cloud MQTT Verbindung.
    """
    try:
        stop_cloud_mqtt()

        # Config aktualisieren
        config = session.exec(select(BambuCloudConfig)).first()
        if config:
            config.cloud_mqtt_enabled = False
            config.cloud_mqtt_connected = False
            config.updated_at = datetime.now().isoformat()
            session.commit()

        logger.info("Cloud MQTT gestoppt")

        return {
            "status": "ok",
            "message": "Cloud MQTT gestoppt"
        }

    except Exception as e:
        logger.error(f"Cloud MQTT Stop Fehler: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cloud MQTT Stop fehlgeschlagen: {e}"
        )


@router.post("/cloud-mqtt/add-device")
def add_cloud_mqtt_device(
    serial: str,
    model: str = "UNKNOWN",
    name: Optional[str] = None,
):
    """
    Fügt ein Gerät zur Cloud MQTT Überwachung hinzu.
    """
    client = get_cloud_mqtt_client()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cloud MQTT nicht gestartet"
        )

    client.add_device(serial=serial, model=model, name=name)

    return {
        "status": "ok",
        "message": f"Device {serial} hinzugefügt"
    }


@router.delete("/cloud-mqtt/device/{serial}")
def remove_cloud_mqtt_device(serial: str):
    """
    Entfernt ein Gerät aus der Cloud MQTT Überwachung.
    """
    client = get_cloud_mqtt_client()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cloud MQTT nicht gestartet"
        )

    client.remove_device(serial)

    return {
        "status": "ok",
        "message": f"Device {serial} entfernt"
    }


@router.post("/cloud-mqtt/pushall/{serial}")
def send_pushall_request(serial: str):
    """
    Sendet einen pushall Request an einen Drucker um alle Daten abzurufen.
    """
    client = get_cloud_mqtt_client()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cloud MQTT nicht gestartet"
        )

    if not client.connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cloud MQTT nicht verbunden"
        )

    client._send_pushall(serial)

    return {
        "status": "ok",
        "message": f"Pushall an {serial} gesendet"
    }
