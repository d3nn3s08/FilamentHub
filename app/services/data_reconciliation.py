"""
Data Reconciliation Manager
===========================
Verhindert ungewolltes Überschreiben von lokalen Daten.
GLOBAL für alle Bambu Lab Drucker, nicht nur AMS Lite!

Priority-Modi:
- CLOUD_ONLY: Cloud überschreibt direkt (gefährlich!)
- CLOUD_VERIFIED: Cloud nur nach Verifizierung (empfohlen)
- LOCAL_PRIORITY: Local hat Vorrang, Cloud = Info
- MANUAL_ONLY: Cloud komplett ignorieren
"""
import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime

from sqlmodel import Session, select

from app.services.spool_verification_service import (
    SpoolVerificationService,
    CloudSpoolData,
    VerificationResult,
)

logger = logging.getLogger("data_reconciliation")


class DataPriority(Enum):
    """Prioritäts-Modi für Cloud vs Local Daten"""
    CLOUD_ONLY = "cloud_only"           # Cloud überschreibt direkt (gefährlich!)
    CLOUD_VERIFIED = "cloud_verified"   # Cloud nur nach Verifizierung (empfohlen)
    LOCAL_PRIORITY = "local_priority"   # Local hat Vorrang, Cloud = Info
    MANUAL_ONLY = "manual_only"         # Cloud komplett ignorieren


class DataReconciliationManager:
    """
    Intelligentes Merging von Cloud und Local Daten
    GLOBAL für alle Bambu Lab Drucker

    Verhindert dass Cloud-Daten lokale Daten ungewollt überschreiben!
    """

    def __init__(self, session: Session, priority_mode: DataPriority = DataPriority.CLOUD_VERIFIED):
        self.session = session
        self.priority_mode = priority_mode
        self.verification_service = SpoolVerificationService(session)

    async def reconcile_job_data(
        self,
        printer_id: str,
        cloud_spools: List[CloudSpoolData],
        local_job_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Hauptfunktion: Reconcile Job von Cloud mit lokalem System
        GLOBAL - funktioniert für alle Bambu Drucker

        Args:
            printer_id: ID des Druckers
            cloud_spools: Liste von Spulen-Daten aus der Cloud
            local_job_id: Optionale lokale Job-ID

        Returns:
            Dict mit Ergebnissen, Konflikten und ausstehenden User-Actions
        """

        results = {
            'success': False,
            'conflicts': [],
            'updates': [],
            'pending_user_action': [],
            'timestamp': datetime.now().isoformat()
        }

        # Für jede Spule die im Job verwendet wurde
        for cloud_spool in cloud_spools:
            try:
                result = await self._reconcile_spool_data(
                    printer_id=printer_id,
                    ams_slot=cloud_spool.tray_id,
                    cloud_data=cloud_spool,
                    job_id=local_job_id or cloud_spool.job_id
                )

                results['updates'].append(result)

                if result.get('needs_user_confirmation'):
                    results['pending_user_action'].append(result)

            except Exception as e:
                logger.error(f"Failed to reconcile tray {cloud_spool.tray_id}: {e}")
                results['conflicts'].append({
                    'tray_id': cloud_spool.tray_id,
                    'error': str(e)
                })

        results['success'] = len(results['conflicts']) == 0
        return results

    async def _reconcile_spool_data(
        self,
        printer_id: str,
        ams_slot: Optional[int],
        cloud_data: CloudSpoolData,
        job_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Reconcile für eine einzelne Spule
        """

        # 1. Verifiziere Match
        verification = self.verification_service.verify_spool_match(
            printer_id, ams_slot, cloud_data
        )

        # 2. Entscheide basierend auf Priority Mode
        if self.priority_mode == DataPriority.MANUAL_ONLY:
            # Cloud ignorieren
            logger.info(f"MANUAL_ONLY mode: Cloud data ignored for printer {printer_id}")
            return {
                'action': 'ignored',
                'source': 'manual_only_mode',
                'cloud_data_saved': await self._save_cloud_reference(
                    cloud_data, verification, job_id
                )
            }

        elif self.priority_mode == DataPriority.CLOUD_ONLY:
            # Direkt übernehmen (RISKANT!)
            logger.warning(f"CLOUD_ONLY mode: Applying unverified cloud data for printer {printer_id}")
            return await self._apply_cloud_data(
                cloud_data, verification.local_data, job_id, verified=False
            )

        elif self.priority_mode == DataPriority.CLOUD_VERIFIED:
            # Standard: Nur nach Verifizierung
            if verification.is_match:
                # Perfect match!
                logger.info(f"Verification passed for printer {printer_id}, slot {ams_slot}")
                return await self._apply_cloud_data(
                    cloud_data, verification.local_data, job_id, verified=True
                )
            else:
                # Konflikt - User muss entscheiden
                conflict_id = await self._save_conflict_for_resolution(
                    verification, job_id, printer_id
                )

                logger.warning(
                    f"Verification conflict for printer {printer_id}, slot {ams_slot}: "
                    f"{verification.conflicts}"
                )

                return {
                    'action': 'conflict_detected',
                    'needs_user_confirmation': True,
                    'conflict_id': conflict_id,
                    'confidence': verification.confidence,
                    'conflicts': verification.conflicts,
                    'options': self.verification_service.get_conflict_resolution_options(
                        verification
                    )
                }

        else:  # LOCAL_PRIORITY
            # Cloud als Referenz speichern, nicht überschreiben
            await self._save_cloud_reference(cloud_data, verification, job_id)

            logger.info(f"LOCAL_PRIORITY mode: Cloud data archived for printer {printer_id}")

            return {
                'action': 'local_priority',
                'source': 'manual_tracking',
                'cloud_data_archived': True
            }

    async def _apply_cloud_data(
        self,
        cloud_data: CloudSpoolData,
        local_spool,  # LocalSpoolData
        job_id: Optional[str],
        verified: bool
    ) -> Dict[str, Any]:
        """
        Wendet Cloud-Daten auf lokale Spule an
        GLOBAL - funktioniert für alle Drucker (nicht nur AMS Lite)
        """
        from app.models.spool import Spool
        from app.models.weight_history import WeightHistory

        if not local_spool:
            logger.warning(f"Cannot apply cloud data: No local spool found")
            return {'action': 'failed', 'reason': 'no_local_spool'}

        spool = self.session.get(Spool, local_spool.spool_id)
        if not spool:
            return {'action': 'failed', 'reason': 'spool_not_found'}

        old_weight = spool.weight_current or (spool.weight_full - spool.weight_empty)
        new_weight = max(0, old_weight - cloud_data.weight_used)

        # Weight History erstellen
        weight_entry = WeightHistory(
            spool_uuid=spool.tray_uuid or spool.id,
            spool_number=spool.spool_number,
            old_weight=old_weight,
            new_weight=new_weight,
            change_reason='bambu_cloud_sync',
            source='bambu_cloud',
            ams_type=None,
            user='system',
            details=f"Cloud Job: {job_id}, Verified: {verified}, Confidence: {cloud_data.confidence}",
            timestamp=datetime.now()
        )
        self.session.add(weight_entry)

        # Spool aktualisieren
        spool.weight_current = new_weight
        spool.last_verified_at = datetime.now().isoformat()
        spool.cloud_last_sync = datetime.now().isoformat()
        spool.cloud_weight = new_weight
        spool.cloud_sync_status = 'synced'
        spool.weight_source = 'bambu_cloud'

        # Color Drift Detection
        if not self.verification_service._compare_colors(
            spool.color or spool.tray_color, cloud_data.color_hex
        ):
            logger.info(
                f"Color drift detected for spool {spool.id}: "
                f"{spool.color or spool.tray_color} -> {cloud_data.color_hex}"
            )
            # Optional: Color History Log oder Warnung

        self.session.commit()

        logger.info(
            f"Cloud data applied to spool {spool.id}: "
            f"{old_weight}g -> {new_weight}g (used: {cloud_data.weight_used}g)"
        )

        return {
            'action': 'applied',
            'source': 'bambu_cloud',
            'verified': verified,
            'weight_updated': True,
            'spool_id': spool.id,
            'spool_number': spool.spool_number,
            'old_weight': old_weight,
            'new_weight': new_weight,
            'weight_change': cloud_data.weight_used
        }

    async def _save_conflict_for_resolution(
        self,
        verification: VerificationResult,
        job_id: Optional[str],
        printer_id: str
    ) -> str:
        """
        Speichert Konflikt für spätere User-Resolution
        Ähnlich wie AMS Lite Conflicts
        """
        from app.models.cloud_conflict import CloudConflict
        import json

        conflict = CloudConflict(
            spool_id=verification.local_data.spool_id if verification.local_data else None,
            printer_id=printer_id,
            conflict_type='cloud_vs_local',
            severity='medium' if verification.confidence > 0.4 else 'high',
            local_value=json.dumps({
                'spool_id': verification.local_data.spool_id if verification.local_data else None,
                'spool_number': verification.local_data.spool_number if verification.local_data else None,
                'color': verification.local_data.color_hex if verification.local_data else None,
                'material': verification.local_data.material if verification.local_data else None,
                'weight': verification.local_data.current_weight if verification.local_data else None,
            }) if verification.local_data else None,
            cloud_value=json.dumps({
                'color': verification.cloud_data.color_hex,
                'material': verification.cloud_data.material,
                'weight_used': verification.cloud_data.weight_used,
                'confidence': verification.cloud_data.confidence,
            }) if verification.cloud_data else None,
            difference_percent=(1 - verification.confidence) * 100,
            status='pending',
            detected_at=datetime.now().isoformat(),
            sync_session_id=job_id,
            description='; '.join(verification.conflicts),
            created_at=datetime.now().isoformat(),
        )

        self.session.add(conflict)
        self.session.commit()
        self.session.refresh(conflict)

        logger.info(f"Created conflict {conflict.id} for spool verification")

        return conflict.id

    async def _save_cloud_reference(
        self,
        cloud_data: CloudSpoolData,
        verification: VerificationResult,
        job_id: Optional[str]
    ) -> bool:
        """
        Speichert Cloud-Daten als Referenz ohne zu überschreiben
        Nützlich für LOCAL_PRIORITY und MANUAL_ONLY Modi
        """
        from app.models.spool import Spool

        if verification.local_data:
            spool = self.session.get(Spool, verification.local_data.spool_id)
            if spool:
                # Speichere Cloud-Daten als Referenz
                spool.cloud_weight = (verification.local_data.current_weight - cloud_data.weight_used)
                spool.cloud_last_sync = datetime.now().isoformat()
                spool.cloud_sync_status = 'reference_only'
                self.session.commit()
                return True

        return False

    async def resolve_conflict(
        self,
        conflict_id: str,
        resolution: str,
        merge_value: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Löst einen gespeicherten Konflikt auf

        Args:
            conflict_id: ID des Konflikts
            resolution: 'keep_local', 'accept_cloud', 'merge', 'ignore'
            merge_value: Bei 'merge': der gewünschte Gewichtswert

        Returns:
            Dict mit Ergebnis
        """
        from app.models.cloud_conflict import CloudConflict
        from app.models.spool import Spool
        import json

        conflict = self.session.get(CloudConflict, conflict_id)
        if not conflict:
            return {'success': False, 'error': 'Konflikt nicht gefunden'}

        if conflict.status != 'pending':
            return {'success': False, 'error': f'Konflikt ist bereits {conflict.status}'}

        result = {'success': True, 'action': resolution}

        if resolution == 'accept_cloud':
            # Cloud-Wert übernehmen
            if conflict.spool_id and conflict.cloud_value:
                spool = self.session.get(Spool, conflict.spool_id)
                cloud_data = json.loads(conflict.cloud_value)

                if spool:
                    old_weight = spool.weight_current
                    new_weight = max(0, old_weight - cloud_data.get('weight_used', 0))
                    spool.weight_current = new_weight
                    spool.cloud_weight = new_weight
                    spool.cloud_sync_status = 'synced'
                    spool.last_verified_at = datetime.now().isoformat()
                    result['weight_updated'] = True
                    result['new_weight'] = new_weight

        elif resolution == 'merge' and merge_value is not None:
            # User-definierter Wert
            if conflict.spool_id:
                spool = self.session.get(Spool, conflict.spool_id)
                if spool:
                    spool.weight_current = merge_value
                    spool.cloud_sync_status = 'merged'
                    result['weight_updated'] = True
                    result['new_weight'] = merge_value

        elif resolution == 'keep_local':
            # Lokalen Wert behalten
            if conflict.spool_id:
                spool = self.session.get(Spool, conflict.spool_id)
                if spool:
                    spool.cloud_sync_status = 'local_priority'
                    result['weight_kept'] = spool.weight_current

        # Konflikt als gelöst markieren
        conflict.status = 'resolved' if resolution != 'ignore' else 'ignored'
        conflict.resolution = resolution
        conflict.resolved_at = datetime.now().isoformat()
        conflict.resolved_by = 'user'
        conflict.updated_at = datetime.now().isoformat()

        self.session.commit()

        logger.info(f"Conflict {conflict_id} resolved: {resolution}")

        return result


# ============================================================
# FACTORY / HELPER
# ============================================================

def get_reconciliation_manager(
    session: Session,
    config=None
) -> DataReconciliationManager:
    """
    Factory-Funktion für DataReconciliationManager.
    Lädt Priority-Mode aus der Config.
    """
    from app.models.bambu_cloud_config import BambuCloudConfig

    priority = DataPriority.CLOUD_VERIFIED  # Default

    if config:
        mode = config.conflict_resolution_mode
        if mode == 'prefer_cloud':
            priority = DataPriority.CLOUD_ONLY
        elif mode == 'prefer_local':
            priority = DataPriority.LOCAL_PRIORITY
        elif mode == 'manual':
            priority = DataPriority.MANUAL_ONLY
    else:
        # Lade aus DB
        cloud_config = session.exec(select(BambuCloudConfig)).first()
        if cloud_config:
            mode = cloud_config.conflict_resolution_mode
            if mode == 'prefer_cloud':
                priority = DataPriority.CLOUD_ONLY
            elif mode == 'prefer_local':
                priority = DataPriority.LOCAL_PRIORITY
            elif mode == 'manual':
                priority = DataPriority.MANUAL_ONLY

    return DataReconciliationManager(session, priority)
