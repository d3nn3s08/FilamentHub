"""
AMS Weight Management System

Handles weight conflicts between AMS Lite, AMS Full, and Bambu Cloud.
Provides automatic conflict detection and user-guided resolution.

Key Features:
- AMS Lite (A1 Mini): Always use FilamentHub DB values (RFID read-only)
- AMS Full (X1C, P1P): Compare Cloud vs DB, detect conflicts
- Weight History Tracking with full audit trail
- Archive system for recycled spool numbers
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
import logging
from sqlmodel import Session, select

from app.models.spool import Spool
from app.models.weight_history import WeightHistory

logger = logging.getLogger("services")


class AMSType(Enum):
    """AMS Types"""
    AMS_LITE = "AMS_LITE"  # A1 Mini - RFID Read-only, no Cloud sync
    AMS_FULL = "AMS_FULL"  # X1C, P1P - RFID Read + Cloud sync


class WeightSource(Enum):
    """Source of weight data"""
    FILAMENTHUB_DB = "filamenthub_db"
    BAMBU_CLOUD = "bambu_cloud"
    AMS_RFID = "ams_rfid"
    PRINT_CONSUMED = "print_consumed"


# ========================================
# Settings Helpers
# ========================================

def is_ams_conflict_detection_enabled() -> bool:
    """Check if AMS conflict detection is enabled in settings"""
    try:
        from app.database import get_sync_session
        from app.models.settings import Setting

        with get_sync_session() as session:
            stmt = select(Setting).where(Setting.key == "ams_conflict_detection_enabled")
            setting = session.exec(stmt).first()
            if setting:
                return setting.value.lower() in ('true', '1', 'yes')
            return True  # Default: enabled
    except Exception as e:
        logger.warning(f"Could not read ams_conflict_detection_enabled setting: {e}")
        return True  # Default: enabled


def get_ams_conflict_tolerance() -> float:
    """Get AMS conflict tolerance in grams from settings"""
    try:
        from app.database import get_sync_session
        from app.models.settings import Setting

        with get_sync_session() as session:
            stmt = select(Setting).where(Setting.key == "ams_conflict_tolerance_g")
            setting = session.exec(stmt).first()
            if setting:
                return float(setting.value)
            return 5.0  # Default: 5g tolerance
    except Exception as e:
        logger.warning(f"Could not read ams_conflict_tolerance_g setting: {e}")
        return 5.0  # Default: 5g tolerance


def process_ams_spool_detection(
    spool_uuid: str,
    ams_type: AMSType,
    mqtt_data: Dict[str, Any],
    session: Session
) -> Dict[str, Any]:
    """
    Processes spool detection based on AMS type

    Args:
        spool_uuid: UUID of detected spool (tray_uuid from RFID)
        ams_type: AMS_LITE or AMS_FULL
        mqtt_data: MQTT data from AMS
        session: Database session

    Returns:
        Dict with weight, source and optional conflict info
    """
    # Find spool by tray_uuid
    stmt = select(Spool).where(Spool.tray_uuid == spool_uuid)
    spool = session.exec(stmt).first()

    if not spool:
        logger.warning(f"Unknown spool UUID: {spool_uuid}")
        return {"error": "Spool not found"}

    # Update: Where was spool last seen?
    spool.last_seen_in_ams_type = ams_type.value
    spool.last_seen_timestamp = datetime.utcnow().isoformat()
    session.commit()

    # ========================================
    # AMS LITE: Always use DB values
    # ========================================
    if ams_type == AMSType.AMS_LITE:
        logger.info(
            f"Spool #{spool.spool_number} detected in AMS Lite "
            f"- using DB values ({spool.weight_current}g)"
        )

        return {
            "spool_id": spool.id,
            "spool_uuid": spool.tray_uuid,
            "spool_number": spool.spool_number,
            "weight": spool.weight_current,
            "source": WeightSource.FILAMENTHUB_DB.value,
            "ams_type": ams_type.value,
            "auto_selected": True,  # No warning needed
            "conflict": False
        }

    # ========================================
    # NORMAL AMS: Compare Cloud vs DB
    # ========================================
    elif ams_type == AMSType.AMS_FULL:
        # Extract cloud weight from MQTT data
        cloud_weight = mqtt_data.get('tray_now', {}).get('remain', 0)
        db_weight = spool.weight_current or 0

        # Save cloud value for reference
        spool.cloud_weight = cloud_weight
        spool.cloud_last_sync = datetime.utcnow().isoformat()
        session.commit()

        difference = abs(cloud_weight - db_weight)

        # Get tolerance from settings (default 5g)
        tolerance = get_ams_conflict_tolerance()

        # Check if conflict detection is enabled
        if not is_ams_conflict_detection_enabled():
            # Conflict detection disabled - just return DB value
            return {
                "spool_id": spool.id,
                "spool_uuid": spool.tray_uuid,
                "spool_number": spool.spool_number,
                "weight": db_weight,
                "source": WeightSource.FILAMENTHUB_DB.value,
                "ams_type": ams_type.value,
                "cloud_weight": cloud_weight,
                "synced": True,
                "conflict": False
            }

        # Check threshold with configurable tolerance
        if difference > tolerance:
            logger.warning(
                f"Weight conflict for spool #{spool.spool_number}: "
                f"Cloud={cloud_weight}g, DB={db_weight}g, Diff={difference}g"
            )

            return {
                "spool_id": spool.id,
                "spool_uuid": spool.tray_uuid,
                "spool_number": spool.spool_number,
                "conflict": True,
                "cloud_weight": cloud_weight,
                "db_weight": db_weight,
                "difference": difference,
                "ams_type": ams_type.value,
                "recommendation": _determine_recommendation(spool, cloud_weight, db_weight)
            }

        else:
            # No conflict - use DB values (FilamentHub is authoritative)
            logger.info(
                f"Spool #{spool.spool_number} in AMS Full: "
                f"Cloud={cloud_weight}g, DB={db_weight}g - No conflict"
            )

            return {
                "spool_id": spool.id,
                "spool_uuid": spool.tray_uuid,
                "spool_number": spool.spool_number,
                "weight": db_weight,
                "source": WeightSource.FILAMENTHUB_DB.value,
                "ams_type": ams_type.value,
                "cloud_weight": cloud_weight,
                "synced": True,
                "conflict": False
            }


def _determine_recommendation(spool: Spool, cloud_weight: float, db_weight: float) -> str:
    """
    Determines which value should be recommended

    Returns:
        "use_db" or "use_cloud"
    """
    # If DB value is newer -> recommend DB
    if spool.last_manual_update and spool.cloud_last_sync:
        db_time = datetime.fromisoformat(spool.last_manual_update)
        cloud_time = datetime.fromisoformat(spool.cloud_last_sync)
        if db_time > cloud_time:
            return "use_db"

    # If cloud value is lower (more realistic due to consumption)
    if cloud_weight < db_weight:
        return "use_cloud"

    # Default: DB (FilamentHub is authoritative)
    return "use_db"


def resolve_weight_conflict(
    spool_uuid: str,
    selected_source: str,  # "db" or "cloud"
    cloud_weight: float,
    db_weight: float,
    user: str,
    session: Session
) -> Dict[str, Any]:
    """
    Resolves weight conflict based on user selection

    Args:
        spool_uuid: UUID of spool
        selected_source: "db" or "cloud"
        cloud_weight: Weight from cloud
        db_weight: Weight from DB
        user: Username for history
        session: Database session

    Returns:
        Dict with status and new weight
    """
    # Find spool by id or tray_uuid (supports both Bambu Lab and Manual spools)
    stmt = select(Spool).where(
        (Spool.id == spool_uuid) | (Spool.tray_uuid == spool_uuid)
    )
    spool = session.exec(stmt).first()

    if not spool:
        return {"error": "Spool not found"}

    old_weight = spool.weight_current or 0

    if selected_source == 'cloud':
        # Take cloud value -> UPDATE DB
        spool.weight_current = cloud_weight
        spool.weight_source = WeightSource.BAMBU_CLOUD.value

        logger.info(
            f"Spool #{spool.spool_number}: Cloud value {cloud_weight}g adopted "
            f"(was: {old_weight}g)"
        )

        # Create history entry
        # Wichtig: tray_uuid verwenden (Bambu AMS Spulen), Fallback auf interne id
        # Frontend-History-Abfrage nutzt ebenfalls tray_uuid or id
        _create_weight_history(
            spool_uuid=spool.tray_uuid or spool.id,
            spool_number=spool.spool_number,
            old_weight=old_weight,
            new_weight=cloud_weight,
            source=WeightSource.BAMBU_CLOUD,
            change_reason='conflict_resolution_user_choice',
            user=user,
            details='User chose Cloud value after conflict warning',
            session=session
        )

    elif selected_source == 'db':
        # Keep DB value -> NO CHANGE, only logging
        spool.weight_source = WeightSource.FILAMENTHUB_DB.value

        logger.info(
            f"Spool #{spool.spool_number}: DB value {db_weight}g kept "
            f"(Cloud had: {cloud_weight}g)"
        )

        # No history entry needed (weight unchanged)

    # Always save cloud value as reference
    spool.cloud_weight = cloud_weight
    spool.cloud_last_sync = datetime.utcnow().isoformat()

    session.commit()

    return {
        "success": True,
        "spool_number": spool.spool_number,
        "updated_weight": spool.weight_current,
        "source": spool.weight_source,
        "cloud_reference": cloud_weight
    }


def _create_weight_history(
    spool_uuid: str,
    spool_number: Optional[int],
    old_weight: float,
    new_weight: float,
    source: WeightSource,
    change_reason: str,
    user: str,
    details: str,
    session: Session
):
    """Creates weight history entry"""
    history = WeightHistory(
        spool_uuid=spool_uuid,
        spool_number=spool_number,
        old_weight=old_weight,
        new_weight=new_weight,
        source=source.value,
        change_reason=change_reason,
        user=user,
        details=details,
        timestamp=datetime.utcnow()
    )

    session.add(history)
    session.commit()
    logger.info(f"Weight history entry created for spool UUID {spool_uuid}")


# ========================================
# Spool Management (Number Recycling)
# ========================================

def mark_spool_empty(spool_uuid: str, user: str, session: Session) -> Dict[str, Any]:
    """
    Marks spool as empty and releases number

    Args:
        spool_uuid: UUID of empty spool
        user: Username for history
        session: Database session

    Returns:
        Dict with status and released number
    """
    # Find spool by id (works for all spools: Bambu Lab + Manual)
    stmt = select(Spool).where(Spool.id == spool_uuid)
    spool = session.exec(stmt).first()

    if not spool:
        return {"error": "Spool not found"}

    # Remember number before releasing
    freed_number = spool.spool_number

    # History entry: Spool is empty
    # Wichtig: tray_uuid verwenden (Bambu AMS Spulen), Fallback auf interne id
    _create_weight_history(
        spool_uuid=spool.tray_uuid or spool.id,
        spool_number=spool.spool_number,
        old_weight=spool.weight_current or 0,
        new_weight=0,
        source=WeightSource.FILAMENTHUB_DB,
        change_reason='spool_empty',
        user=user,
        details=f'Spool completely consumed, number {freed_number} released',
        session=session
    )

    # Release number
    spool.last_number = spool.spool_number  # For history/archive
    spool.spool_number = None               # Release number
    spool.weight_current = 0            # Use weight_current
    spool.is_active = False
    spool.emptied_at = datetime.utcnow().isoformat()

    session.commit()

    logger.info(
        f"Spool {spool.id} marked as empty, "  # Use id instead of tray_uuid
        f"number {freed_number} is now free"
    )

    return {
        "success": True,
        "message": f"Spool marked empty, number {freed_number} is now free",
        "freed_number": freed_number,
        "spool_uuid": spool_uuid
    }
