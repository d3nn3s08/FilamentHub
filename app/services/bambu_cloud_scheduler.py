"""
Bambu Cloud Scheduler Service
==============================
Verwaltet automatische Sync-Jobs mit APScheduler.

Features:
- Automatischer Sync im konfigurierten Intervall
- Sofortiger Sync bei Druckstart (wird von job_tracking_service getriggert)
- Dynamische Anpassung des Intervalls bei Config-Änderung
"""
import asyncio
import logging
from typing import Optional
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlmodel import Session, select

from app.database import engine
from app.models.bambu_cloud_config import BambuCloudConfig
from app.services.bambu_cloud_service import BambuCloudService
from app.services.token_encryption import decrypt_token

logger = logging.getLogger("bambu_cloud_scheduler")

# Global Scheduler Instance
_scheduler: Optional[AsyncIOScheduler] = None
_current_job_id: Optional[str] = None


def get_scheduler() -> AsyncIOScheduler:
    """Gibt die globale Scheduler-Instanz zurück."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def _try_refresh_token(config: BambuCloudConfig, session: Session) -> Optional[str]:
    """
    Versucht den Access Token mit dem Refresh Token zu erneuern.
    Aktualisiert die Config in der DB bei Erfolg.

    Returns:
        Neuer Access Token bei Erfolg, None bei Fehler
    """
    if not config.refresh_token_encrypted:
        logger.warning("Bambu Cloud: Kein Refresh Token vorhanden – manueller Re-Login erforderlich")
        return None

    try:
        refresh_token = decrypt_token(config.refresh_token_encrypted)
    except Exception as e:
        logger.error(f"Bambu Cloud: Refresh-Token-Entschlüsselung fehlgeschlagen: {e}")
        return None

    from app.services.bambu_auth_service import BambuAuthService, LoginState
    from app.services.token_encryption import encrypt_token

    auth = BambuAuthService(region=config.region)
    try:
        result = await auth.refresh_access_token(refresh_token)
    finally:
        await auth.close()

    if result.state != LoginState.SUCCESS or not result.access_token:
        logger.warning(f"Bambu Cloud: Token-Refresh fehlgeschlagen: {result.message}")
        return None

    # Neuen Token in DB speichern
    config.access_token_encrypted = encrypt_token(result.access_token)
    if result.refresh_token:
        config.refresh_token_encrypted = encrypt_token(result.refresh_token)
    # Ablaufzeit speichern: aus expiresIn (via result.expires_at) oder 30-Tage-Fallback
    from app.services.bambu_auth_service import compute_token_expiry
    config.token_expires_at = result.expires_at if result.expires_at else compute_token_expiry()
    logger.info(f"Bambu Cloud: Neuer Token läuft ab: {config.token_expires_at}")
    config.updated_at = datetime.now().isoformat()
    session.commit()

    logger.info("Bambu Cloud: Token erfolgreich erneuert via Refresh Token")
    return result.access_token


async def perform_scheduled_sync():
    """
    Führt einen geplanten Sync durch.
    Wird vom Scheduler aufgerufen.
    Bei abgelaufenem Token wird automatisch ein Token-Refresh versucht.
    """
    try:
        with Session(engine) as session:
            config = session.exec(select(BambuCloudConfig)).first()

            if not config or not config.sync_enabled or not config.access_token_encrypted:
                logger.debug("Bambu Cloud Sync übersprungen: Nicht aktiviert oder kein Token")
                return

            # Token entschlüsseln
            try:
                access_token = decrypt_token(config.access_token_encrypted)
            except Exception as e:
                logger.error(f"Bambu Cloud Sync: Token-Entschlüsselung fehlgeschlagen - {e}")
                config.connection_status = "error"
                config.last_error_message = f"Token-Fehler: {e}"
                config.updated_at = datetime.now().isoformat()
                session.commit()
                return

            # Service erstellen
            service = BambuCloudService(
                access_token=access_token,
                region=config.region
            )

            try:
                # Sync durchführen
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

                logger.info(
                    f"Bambu Cloud Auto-Sync erfolgreich: "
                    f"{sync_result.get('matched', 0)} matches, "
                    f"{sync_result.get('conflicts', 0)} conflicts"
                )

            except Exception as e:
                err_str = str(e)
                # Prüfe ob es ein Token-Fehler (401) ist → Auto-Refresh versuchen
                if "401" in err_str or "ungültig" in err_str.lower() or "token" in err_str.lower() or "unauthorized" in err_str.lower():
                    logger.warning(f"Bambu Cloud Sync: Token-Fehler erkannt, versuche Auto-Refresh...")
                    await service.close()

                    new_token = await _try_refresh_token(config, session)
                    if new_token:
                        # Retry mit neuem Token
                        service = BambuCloudService(access_token=new_token, region=config.region)
                        try:
                            sync_result = await service.perform_full_sync(
                                session=session,
                                conflict_resolution_mode=config.conflict_resolution_mode
                            )
                            config.last_sync_at = datetime.now().isoformat()
                            config.last_sync_status = "success"
                            config.connection_status = "connected"
                            config.last_error_message = None
                            config.updated_at = datetime.now().isoformat()
                            session.commit()
                            logger.info("Bambu Cloud Sync nach Token-Refresh erfolgreich")
                            return
                        except Exception as retry_e:
                            logger.error(f"Bambu Cloud Sync nach Token-Refresh auch fehlgeschlagen: {retry_e}")
                            err_str = str(retry_e)
                        finally:
                            await service.close()
                    else:
                        # Refresh fehlgeschlagen → manuellen Login anfordern
                        config.last_sync_status = "error"
                        config.connection_status = "error"
                        config.last_error_message = "Token abgelaufen. Bitte erneut in der Cloud-Konfiguration einloggen."
                        config.updated_at = datetime.now().isoformat()
                        session.commit()
                        return

                logger.error(f"Bambu Cloud Auto-Sync Fehler: {e}", exc_info=True)
                config.last_sync_status = "error"
                config.connection_status = "error"
                config.last_error_message = err_str
                config.updated_at = datetime.now().isoformat()
                session.commit()

            finally:
                if not service._session or service._session.closed:
                    pass  # Bereits geschlossen (nach Refresh-Retry)
                else:
                    await service.close()

    except Exception as e:
        logger.error(f"Bambu Cloud Scheduler unerwarteter Fehler: {e}", exc_info=True)


async def perform_proactive_token_refresh():
    """
    Prüft täglich ob der Bambu Cloud Token bald abläuft und warnt den Nutzer.
    Läuft unabhängig vom Sync-Intervall – einmal pro Tag (03:00 Uhr).

    ⚠️ Bambu Lab Token-Fakten (Stand 2025):
    - Token-Laufzeit: 90 Tage (expiresIn: 7776000s)
    - Refresh-Endpoint ist DEAKTIVIERT (gibt 401 zurück)
    - refreshToken == accessToken (gleicher Wert, keine echte Erneuerung möglich)
    - Nach Ablauf: Manueller Re-Login in der Cloud-Konfiguration erforderlich
    - Quelle: https://github.com/Doridian/OpenBambuAPI/blob/main/cloud-http.md

    Warnung wird ausgegeben wenn weniger als 14 Tage verbleiben.
    """
    try:
        from datetime import timezone
        with Session(engine) as session:
            config = session.exec(select(BambuCloudConfig)).first()

            if not config or not config.access_token_encrypted:
                return

            # Ablaufzeit prüfen
            days_left = None
            if config.token_expires_at:
                try:
                    now = datetime.now(tz=timezone.utc)
                    expires = datetime.fromisoformat(config.token_expires_at)
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=timezone.utc)
                    days_left = (expires - now).days
                except Exception:
                    pass

            # ⚠️ Hinweis: Bambu Lab Refresh-Endpoint ist deaktiviert (gibt 401 zurück).
            # refreshToken == accessToken (gleicher Wert, 90 Tage Laufzeit).
            # Wir können den Token NICHT automatisch erneuern.
            # Stattdessen: Nutzer rechtzeitig warnen (< 14 Tage) damit er sich manuell neu einloggt.
            # Quelle: https://github.com/Doridian/OpenBambuAPI/blob/main/cloud-http.md

            # Warnen wenn < 14 Tage verbleiben (früh genug für manuellen Re-Login)
            should_warn = (days_left is not None and days_left < 14) or days_left is None

            if not should_warn:
                logger.debug(f"Bambu Cloud: Token gültig für noch {days_left} Tage – kein Handlungsbedarf")
                return

            if days_left is not None and days_left <= 0:
                # Token bereits abgelaufen
                logger.error(f"Bambu Cloud: Token ABGELAUFEN seit {abs(days_left)} Tag(en) – Re-Login erforderlich!")
                config.last_error_message = f"Token abgelaufen! Bitte in der Cloud-Konfiguration neu einloggen."
            elif days_left is not None:
                logger.warning(f"Bambu Cloud: Token läuft in {days_left} Tag(en) ab – bitte bald neu einloggen")
                config.last_error_message = f"Token läuft in {days_left} Tag(en) ab. Bitte in der Cloud-Konfiguration neu einloggen."
            else:
                logger.warning("Bambu Cloud: Token-Ablaufzeit unbekannt – bitte Verbindung prüfen")
                config.last_error_message = "Token-Ablaufzeit unbekannt. Bitte Verbindung in der Cloud-Konfiguration testen."

            config.updated_at = datetime.now().isoformat()
            session.commit()

    except Exception as e:
        logger.error(f"Bambu Cloud: Fehler im proaktiven Token-Refresh: {e}", exc_info=True)


async def trigger_immediate_sync():
    """
    Löst einen sofortigen Sync aus (z.B. bei Druckstart).
    Wird von job_tracking_service aufgerufen.
    """
    logger.info("Bambu Cloud: Sofortiger Sync angefordert (Druckstart)")
    await perform_scheduled_sync()


def start_scheduler():
    """Startet den Scheduler und konfiguriert den ersten Job."""
    global _current_job_id
    
    scheduler = get_scheduler()
    
    if scheduler.running:
        logger.warning("Bambu Cloud Scheduler läuft bereits")
        return
    
    # Lade Config für initiales Intervall
    with Session(engine) as session:
        config = session.exec(select(BambuCloudConfig)).first()
        interval_minutes = config.auto_sync_interval_minutes if config else 30
    
    # Starte Scheduler
    scheduler.start()
    logger.info("Bambu Cloud Scheduler gestartet")

    # Einmalig: token_expires_at setzen falls noch nicht vorhanden (30-Tage-Fallback)
    # Bambu-Tokens sind opak – wir können die Ablaufzeit nicht aus dem Token lesen
    try:
        with Session(engine) as session:
            config = session.exec(select(BambuCloudConfig)).first()
            if config and config.access_token_encrypted and not config.token_expires_at:
                from app.services.bambu_auth_service import compute_token_expiry
                config.token_expires_at = compute_token_expiry()  # 30-Tage-Schätzung
                config.updated_at = datetime.now().isoformat()
                session.commit()
                logger.info(f"Bambu Cloud: Token-Ablaufzeit (Schätzung) gesetzt: {config.token_expires_at}")
    except Exception as e:
        logger.warning(f"Bambu Cloud: Token-Ablaufzeit konnte nicht gesetzt werden: {e}")

    # Füge Sync-Job hinzu
    update_sync_job(interval_minutes)

    # Täglicher proaktiver Token-Refresh (läuft jeden Morgen um 03:00 Uhr)
    try:
        scheduler.add_job(
            perform_proactive_token_refresh,
            trigger="cron",
            hour=3,
            minute=0,
            id="bambu_token_expiry_check_daily",
            replace_existing=True,
            max_instances=1,
        )
        logger.info("Bambu Cloud: Täglicher Token-Ablauf-Prüf-Job registriert (03:00 Uhr, warnt bei < 14 Tage)")
    except Exception as e:
        logger.error(f"Bambu Cloud: Fehler beim Registrieren des Token-Refresh-Jobs: {e}")


def stop_scheduler():
    """Stoppt den Scheduler."""
    global _current_job_id
    
    scheduler = get_scheduler()
    
    if _current_job_id:
        try:
            scheduler.remove_job(_current_job_id)
            _current_job_id = None
        except Exception:
            pass
    
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Bambu Cloud Scheduler gestoppt")


def update_sync_job(interval_minutes: int):
    """
    Aktualisiert das Sync-Intervall.
    Wird aufgerufen wenn die Config geändert wird.
    
    Args:
        interval_minutes: Neues Intervall in Minuten (min 5, max 1440)
    """
    global _current_job_id
    
    scheduler = get_scheduler()
    
    if not scheduler.running:
        logger.warning("Bambu Cloud Scheduler läuft nicht, kann Job nicht aktualisieren")
        return
    
    # Validiere Intervall
    interval_minutes = max(5, min(1440, interval_minutes))
    
    # Entferne alten Job falls vorhanden
    if _current_job_id:
        try:
            scheduler.remove_job(_current_job_id)
        except Exception:
            pass
        _current_job_id = None
    
    # Prüfe ob Sync aktiviert ist
    with Session(engine) as session:
        config = session.exec(select(BambuCloudConfig)).first()
        if not config or not config.sync_enabled:
            logger.info("Bambu Cloud Auto-Sync deaktiviert, kein Job erstellt")
            return
    
    # Füge neuen Job hinzu
    try:
        job = scheduler.add_job(
            perform_scheduled_sync,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="bambu_cloud_auto_sync",
            replace_existing=True,
            max_instances=1,  # Verhindert parallele Syncs
            coalesce=True,    # Überspringt ausstehende Jobs wenn neuer startet
        )
        _current_job_id = job.id
        logger.info(f"Bambu Cloud Auto-Sync Job aktualisiert: Alle {interval_minutes} Minuten")
    except Exception as e:
        logger.error(f"Bambu Cloud: Fehler beim Erstellen des Sync-Jobs - {e}", exc_info=True)
