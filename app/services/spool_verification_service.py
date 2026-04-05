"""
Spool Verification Service
==========================
Gleicht Cloud-Daten mit lokalen Spulen ab.
Verhindert stille Daten-Inkonsistenzen bei Bambu Cloud Integration.

Funktioniert wie AMS Lite/Normal Conflict Resolution, aber für Cloud vs Local.
"""
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from sqlmodel import Session, select

logger = logging.getLogger("spool_verification")


@dataclass
class CloudSpoolData:
    """Was die Bambu Cloud über die verwendete Spule sagt"""
    color_hex: str
    material: str
    weight_used: float
    timestamp: datetime
    confidence: float
    tray_id: Optional[int] = None
    job_id: Optional[str] = None
    tray_uuid: Optional[str] = None


@dataclass
class LocalSpoolData:
    """Was das lokale System über die eingelegte Spule weiß"""
    spool_id: str
    spool_uuid: Optional[str]
    spool_number: Optional[int]
    color_hex: Optional[str]
    material: str
    current_weight: float
    last_verified: Optional[datetime]
    printer_id: str
    ams_slot: Optional[int]


@dataclass
class VerificationResult:
    """Ergebnis der Spulen-Verifizierung"""
    is_match: bool
    confidence: float
    conflicts: List[str]
    suggested_action: str  # 'accept_cloud_data', 'ask_user_confirmation', 'reject_and_flag', 'assign_new_spool'
    needs_user_confirmation: bool
    cloud_data: Optional[CloudSpoolData] = None
    local_data: Optional[LocalSpoolData] = None


class SpoolVerificationService:
    """
    Intelligente Spulen-Verifizierung
    Wie AMS Lite/Normal Conflict Resolution, aber für Cloud vs Local

    GLOBAL für alle Bambu Lab Drucker, nicht nur AMS Lite!
    """

    # Matching Toleranzen
    COLOR_TOLERANCE = 30  # Delta E für Farbabweichung
    WEIGHT_TOLERANCE_PERCENT = 0.15  # 15%
    VERIFICATION_VALIDITY_HOURS = 24

    def __init__(self, session: Session):
        self.session = session

    def verify_spool_match(
        self,
        printer_id: str,
        ams_slot: Optional[int],
        cloud_data: CloudSpoolData
    ) -> VerificationResult:
        """
        Hauptfunktion: Prüft Cloud vs Local Match

        Args:
            printer_id: ID des Druckers
            ams_slot: AMS Slot (kann None sein bei externem Filament)
            cloud_data: Daten aus der Bambu Cloud

        Returns:
            VerificationResult mit Match-Infos und Aktionsempfehlung
        """

        # Lokale Spule holen
        local_spool = self._get_local_spool(printer_id, ams_slot, cloud_data.tray_uuid)

        if not local_spool:
            return VerificationResult(
                is_match=False,
                confidence=0.0,
                conflicts=["Keine lokale Spule für diesen Slot zugewiesen"],
                suggested_action="assign_new_spool",
                needs_user_confirmation=True,
                cloud_data=cloud_data,
                local_data=None
            )

        # Vergleiche Eigenschaften
        color_match = self._compare_colors(
            local_spool.color_hex,
            cloud_data.color_hex
        )

        material_match = self._compare_materials(
            local_spool.material,
            cloud_data.material
        )

        weight_plausible = self._check_weight_plausibility(
            local_spool.current_weight,
            cloud_data.weight_used
        )

        recently_verified = self._is_recently_verified(local_spool)

        # Konflikte sammeln
        conflicts = []
        confidence = 1.0

        if not color_match:
            conflicts.append(
                f"Farbabweichung: Lokal={local_spool.color_hex}, "
                f"Cloud={cloud_data.color_hex}"
            )
            confidence *= 0.3

        if not material_match:
            conflicts.append(
                f"Material stimmt nicht: Lokal={local_spool.material}, "
                f"Cloud={cloud_data.material}"
            )
            confidence *= 0.2

        if not weight_plausible:
            conflicts.append(
                f"Gewicht unplausibel: {cloud_data.weight_used}g Verbrauch "
                f"bei aktuellem Gewicht von {local_spool.current_weight}g"
            )
            confidence *= 0.1

        # Boost bei kürzlicher Verifizierung
        if recently_verified and len(conflicts) == 0:
            confidence = min(1.0, confidence * 1.2)

        # Entscheidung
        is_match = confidence > 0.7 and len(conflicts) == 0

        if is_match:
            suggested_action = "accept_cloud_data"
        elif confidence > 0.4:
            suggested_action = "ask_user_confirmation"
        else:
            suggested_action = "reject_and_flag"

        logger.info(
            f"Verification für Printer {printer_id}, Slot {ams_slot}: "
            f"match={is_match}, confidence={confidence:.2f}, conflicts={len(conflicts)}"
        )

        return VerificationResult(
            is_match=is_match,
            confidence=confidence,
            conflicts=conflicts,
            suggested_action=suggested_action,
            needs_user_confirmation=not is_match,
            cloud_data=cloud_data,
            local_data=local_spool
        )

    def _get_local_spool(
        self,
        printer_id: str,
        ams_slot: Optional[int],
        tray_uuid: Optional[str]
    ) -> Optional[LocalSpoolData]:
        """Hole aktuell eingelegte Spule"""
        from app.models.spool import Spool
        from app.models.printer import Printer

        # Versuche zuerst über tray_uuid zu matchen
        if tray_uuid:
            spool = self.session.exec(
                select(Spool).where(Spool.tray_uuid == tray_uuid)
            ).first()

            if spool:
                return self._spool_to_local_data(spool, printer_id, ams_slot)

        # Fallback: Über Printer + Slot
        if ams_slot is not None:
            spool = self.session.exec(
                select(Spool).where(
                    Spool.printer_id == printer_id,
                    Spool.ams_slot == ams_slot
                )
            ).first()

            if spool:
                return self._spool_to_local_data(spool, printer_id, ams_slot)

        return None

    def _spool_to_local_data(
        self,
        spool,
        printer_id: str,
        ams_slot: Optional[int]
    ) -> LocalSpoolData:
        """Konvertiert Spool zu LocalSpoolData"""
        # Lade Material-Info für Material-Type
        from app.models.material import Material

        material = self.session.get(Material, spool.material_id)
        material_type = material.material_type if material else "UNKNOWN"

        last_verified = None
        if spool.last_verified_at:
            try:
                last_verified = datetime.fromisoformat(spool.last_verified_at)
            except:
                pass

        return LocalSpoolData(
            spool_id=spool.id,
            spool_uuid=spool.tray_uuid,
            spool_number=spool.spool_number,
            color_hex=spool.color or spool.tray_color,
            material=material_type,
            current_weight=spool.weight_current or (spool.weight_full - spool.weight_empty),
            last_verified=last_verified,
            printer_id=printer_id,
            ams_slot=ams_slot
        )

    def _compare_colors(self, local_hex: Optional[str], cloud_hex: Optional[str]) -> bool:
        """Farbvergleich mit Delta E"""
        if not local_hex or not cloud_hex:
            return True  # Wenn Farbe unbekannt, ignorieren

        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            if len(hex_color) != 6:
                return (128, 128, 128)  # Fallback grau
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

        try:
            local_rgb = hex_to_rgb(local_hex)
            cloud_rgb = hex_to_rgb(cloud_hex)

            # Simplified Delta E (Euclidean distance in RGB space)
            delta = sum((a - b) ** 2 for a, b in zip(local_rgb, cloud_rgb)) ** 0.5

            return delta < self.COLOR_TOLERANCE
        except Exception as e:
            logger.warning(f"Farbvergleich fehlgeschlagen: {e}")
            return True  # Bei Fehler als Match werten

    def _compare_materials(self, local_mat: Optional[str], cloud_mat: Optional[str]) -> bool:
        """Material-Vergleich mit Normalisierung"""
        if not local_mat or not cloud_mat:
            return True  # Wenn Material unbekannt, ignorieren

        # Normalisiere Material-Namen
        def normalize(m):
            return m.upper().strip().replace('-', '').replace(' ', '').replace('_', '')

        return normalize(local_mat) == normalize(cloud_mat)

    def _check_weight_plausibility(self, current: Optional[float], used: float) -> bool:
        """Prüft ob Gewichtsverbrauch plausibel"""
        if current is None:
            return True  # Wenn Gewicht unbekannt, ignorieren

        if used < 0:
            return False

        remaining = current - used

        # Negativ = unmöglich
        if remaining < -10:  # Kleine Toleranz für Rundungsfehler
            return False

        # Zu viel Verbrauch?
        max_allowed = current * (1 + self.WEIGHT_TOLERANCE_PERCENT)
        if used > max_allowed:
            return False

        return True

    def _is_recently_verified(self, spool: LocalSpoolData) -> bool:
        """War Spule kürzlich verifiziert?"""
        if not spool.last_verified:
            return False

        age = datetime.now() - spool.last_verified
        return age < timedelta(hours=self.VERIFICATION_VALIDITY_HOURS)

    def get_conflict_resolution_options(
        self,
        verification: VerificationResult
    ) -> List[Dict[str, Any]]:
        """
        Gibt User-Optionen für Konfliktauflösung zurück
        Ähnlich wie AMS Lite Conflict Dialog
        """
        options = []

        if verification.suggested_action == "assign_new_spool":
            options.append({
                'action': 'create_new_spool',
                'label': 'Neue Spule wurde eingelegt (aus Cloud-Daten erstellen)',
                'description': 'Erstellt eine neue Spule mit Farbe/Material aus der Cloud',
                'data': {
                    'color': verification.cloud_data.color_hex if verification.cloud_data else None,
                    'material': verification.cloud_data.material if verification.cloud_data else None,
                    'initial_weight': (1000 - verification.cloud_data.weight_used) if verification.cloud_data else 1000
                }
            })

            # Ähnliche Spulen suchen
            if verification.cloud_data:
                similar = self._find_similar_spools(verification.cloud_data)
                if similar:
                    options.append({
                        'action': 'assign_existing',
                        'label': 'Mit existierender Spule verknüpfen',
                        'description': f'{len(similar)} ähnliche Spulen gefunden',
                        'suggestions': similar
                    })

        elif verification.suggested_action == "ask_user_confirmation":
            options.append({
                'action': 'accept_with_deviation',
                'label': f'Cloud-Daten akzeptieren (Konfidenz: {verification.confidence:.0%})',
                'description': 'Trotz Abweichungen akzeptieren',
                'conflicts': verification.conflicts
            })

            options.append({
                'action': 'reject_cloud',
                'label': 'Cloud-Daten ablehnen, manuelles Tracking behalten',
                'description': 'Weiter mit lokalem Gewichts-Tracking'
            })

        else:  # reject_and_flag
            options.append({
                'action': 'flag_for_review',
                'label': 'Daten-Mismatch - zur Prüfung markieren',
                'description': 'Für spätere Untersuchung markieren',
                'conflicts': verification.conflicts
            })

            options.append({
                'action': 'ignore_cloud',
                'label': 'Cloud für diesen Drucker deaktivieren',
                'description': 'Zurück zum manuellen Modus'
            })

        return options

    def _find_similar_spools(self, cloud_data: CloudSpoolData, limit: int = 5) -> List[Dict]:
        """Findet ähnliche existierende Spulen"""
        from app.models.spool import Spool
        from app.models.material import Material

        # Suche nach Material match
        materials = self.session.exec(
            select(Material).where(
                Material.material_type.ilike(f'%{cloud_data.material}%')
            )
        ).all()

        material_ids = [m.id for m in materials]

        if not material_ids:
            return []

        spools = self.session.exec(
            select(Spool).where(
                Spool.material_id.in_(material_ids),
                Spool.is_active == True
            ).limit(limit)
        ).all()

        results = []
        for spool in spools:
            color_match = self._compare_colors(
                spool.color or spool.tray_color,
                cloud_data.color_hex
            )
            results.append({
                'spool_id': spool.id,
                'spool_number': spool.spool_number,
                'color': spool.color or spool.tray_color,
                'material': materials[0].material_type if materials else "UNKNOWN",
                'weight': spool.weight_current,
                'color_match': color_match,
                'score': 1.0 if color_match else 0.5
            })

        return sorted(results, key=lambda x: x['score'], reverse=True)
