"""Bambu Lab MQTT Service für Live-Sync von AMS Daten, RFID, Material-Verbrauch."""
import logging
import paho.mqtt.client as mqtt
import json
from typing import Optional, Callable
from sqlmodel import Session, select, col
from app.models.spool import Spool
from app.models.material import Material
from app.database import get_session
from app.services.live_state import set_live_state
from app.services.ams_sync import bambu_start_delay_active

bambu_logger = logging.getLogger("bambu")


class BambuService:
    """MQTT Service für Bambu Lab Drucker - Auto-Sync von AMS Daten."""

    def __init__(self, printer_id: str, host: str, access_code: str, serial: str):
        self.printer_id = printer_id
        self.host = host
        self.access_code = access_code
        self.serial = serial
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        
        bambu_logger.info(f"BambuService initialisiert für {host} (Serial: {serial})")

    def connect(self):
        """MQTT Verbindung zum Bambu Lab Drucker aufbauen."""
        try:
            self.client = mqtt.Client(client_id=f"FilamentHub_{self.serial}")
            self.client.username_pw_set("bblp", self.access_code)
            
            # Callbacks
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect
            
            bambu_logger.info(f"Verbinde zu {self.host}:6000...")
            self.client.connect(self.host, 6000, 60)
            self.client.loop_start()
            
        except Exception as e:
            bambu_logger.exception("MQTT Verbindung fehlgeschlagen")

    def disconnect(self):
        """MQTT Verbindung trennen."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            bambu_logger.info("MQTT Verbindung getrennt")

    def _on_connect(self, client, userdata, flags, rc):
        """Callback wenn MQTT verbunden."""
        if rc == 0:
            self.connected = True
            bambu_logger.info(f"MQTT verbunden mit {self.host}")
            
            # Subscribe to report topic
            topic = f"device/{self.serial}/report"
            client.subscribe(topic)
            bambu_logger.info(f"Subscribed zu {topic}")
        else:
            bambu_logger.error(f"MQTT Verbindung fehlgeschlagenRC={rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback wenn MQTT getrennt."""
        self.connected = False
        bambu_logger.warning(f"MQTT Verbindung getrennt: RC={rc}")

    def _on_message(self, client, userdata, msg):
        """Callback für eingehende MQTT Messages - Parse AMS Daten."""
        try:
            payload = json.loads(msg.payload.decode())
            # Store full payload in live_state so normalization sees latest data
            try:
                set_live_state(self.serial, payload)
            except Exception:
                bambu_logger.exception("Fehler beim Setzen des live_state")

            # Parse AMS data (Automatic Material System)
            if "print" in payload and "ams" in payload["print"]:
                ams_data = payload["print"]["ams"]
                self._process_ams_data(ams_data)
            
            # Parse print job data
            if "print" in payload:
                print_data = payload["print"]
                self._process_print_data(print_data)
                
        except json.JSONDecodeError:
            bambu_logger.warning("Konnte MQTT Message nicht parsen")
        except Exception as e:
            bambu_logger.exception("Fehler beim Verarbeiten der MQTT Message")

    def _process_ams_data(self, ams_data: dict):
        """AMS Daten verarbeiten und Spulen auto-anlegen/updaten."""
        try:
            # AMS kann mehrere Units haben (AMS 1, AMS 2, etc.)
            ams_units = ams_data.get("ams", [])
            
            for ams_unit in ams_units:
                ams_id = ams_unit.get("id", 0)
                trays = ams_unit.get("tray", [])
                
                for tray in trays:
                    tray_id = tray.get("id")
                    if tray_id is None:
                        continue
                    
                    # AMS Slot berechnen (0-3 pro Unit, dann 4-7 für Unit 2, etc.)
                    ams_slot = ams_id * 4 + tray_id
                    
                    # RFID auslesen
                    rfid = tray.get("tray_uuid")
                    
                    # Material-Info
                    tray_type = tray.get("tray_type")  # PLA, ABS, PETG, etc.
                    tray_color = tray.get("tray_color")  # Hex color
                    
                    # Robustes Ermitteln des verbleibenden Gewichts (in Gramm)
                    remain_weight = None
                    # AMS Varianten: 'remain_weight' (grams), 'remain' (percent or grams or grams*1000),
                    # 'tray_weight' / 'total_grams' (total filament grams)
                    try:
                        if tray.get("remain_weight") is not None:
                            remain_weight = float(tray.get("remain_weight"))
                        elif tray.get("remain_weight_g") is not None:
                            remain_weight = float(tray.get("remain_weight_g"))
                        else:
                            raw_rem = tray.get("remain")
                            if raw_rem is not None:
                                # If it's clearly large (>1000) treat as grams*1000
                                try:
                                    rawf = float(raw_rem)
                                    if rawf > 1000:
                                        remain_weight = rawf / 1000.0
                                    elif rawf > 100:  # likely grams
                                        remain_weight = rawf
                                    else:
                                        # treat as percent (0-100)
                                        # remain = percent USED, so remaining = total * ((100 - remain) / 100)
                                        # e.g. remain:0 (0% used) = 100% full = tray_weight
                                        # e.g. remain:50 (50% used) = 50% remaining
                                        total_g = None
                                        total_g = tray.get("total_grams") or tray.get("tray_weight") or tray.get("total_g") or tray.get("total")
                                        try:
                                            total_g = float(total_g) if total_g is not None else None
                                        except Exception:
                                            total_g = None
                                        if total_g is not None:
                                            remain_weight = round(total_g * ((100 - rawf) / 100.0), 1)
                                        else:
                                            # cannot derive grams
                                            remain_weight = None
                                except Exception:
                                    remain_weight = None
                    except Exception:
                        remain_weight = None

                    bambu_logger.debug(f"AMS Slot {ams_slot}: Type={tray_type}, Color={tray_color}, RFID={rfid}, Weight={remain_weight}g (derived)")
                    
                    # Spule in DB anlegen/updaten
                    self._sync_spool(
                        ams_id=ams_id,
                        ams_slot=ams_slot,
                        rfid=rfid,
                        material_type=tray_type,
                        color=tray_color,
                        remaining_weight=remain_weight,
                        tray_payload=tray
                    )
                    
        except Exception as e:
            bambu_logger.exception("Fehler beim Verarbeiten der AMS Daten")

    def _process_print_data(self, print_data: dict):
        """Print Job Daten verarbeiten - Material-Verbrauch tracken."""
        try:
            # Aktueller AMS Slot in Benutzung
            ams_slot = print_data.get("ams_status")
            
            # Filament verbraucht (mm)
            filament_used = print_data.get("mc_print_line_number", 0)
            
            bambu_logger.debug(f"Print Status: AMS Slot {ams_slot}, Filament used: {filament_used}mm")
            
            # Hier könnte man Job-Tracking machen
            # z.B. laufenden Job updaten mit aktuellem Verbrauch
            
        except Exception as e:
            bambu_logger.exception("Fehler beim Verarbeiten der Print Daten")

    def _sync_spool(self, ams_id: int, ams_slot: int, rfid: Optional[str], material_type: Optional[str], 
                    color: Optional[str], remaining_weight: float, tray_payload: Optional[dict] = None):
        """Spule in Datenbank anlegen oder updaten basierend auf AMS Daten."""
        try:
            # DB Session holen
            session = next(get_session())

            # --- Konfliktprüfung: gibt es eine aktive Spule im Slot mit Quelle 'manual'? ---
            # Robust matching for ams_id: accept numeric, string or prefixed forms (e.g. 'AMS1')
            try:
                ams_id_str = str(ams_id)
                ams_id_prefixed = f"AMS{ams_id_str}"
                ams_id_variants = [ams_id_str, ams_id_prefixed]
                existing_in_slot = session.exec(
                    select(Spool).where(
                        Spool.ams_slot == ams_slot,
                        Spool.is_active == True,
                        col(Spool.ams_id).in_(ams_id_variants)
                    )
                ).first()
            except Exception:
                existing_in_slot = session.exec(
                    select(Spool).where(Spool.ams_slot == ams_slot, Spool.is_active == True)
                ).first()

            if existing_in_slot and existing_in_slot.ams_source == "manual":
                # Erzeuge einen Konflikt und breche die automatische RFID-Zuweisung ab
                try:
                    from app.models.ams_conflict import AmsConflict
                    conflict = AmsConflict(
                        printer_id=self.printer_id,
                        ams_id=str(ams_id),
                        slot=ams_slot,
                        manual_spool_id=existing_in_slot.id,
                        rfid_payload=json.dumps(tray_payload) if tray_payload is not None else None,
                    )
                    session.add(conflict)
                    session.commit()
                    bambu_logger.info(f"AMS-Konflikt erstellt: AMS {ams_id} Slot {ams_slot} (manuell belegt)")
                except Exception:
                    bambu_logger.exception("Fehler beim Anlegen des AMS-Konflikts")
                finally:
                    session.close()
                # Abbrechen: keine weitere automatische Zuweisung
                return

            # Suche Spule mit diesem RFID oder AMS Slot
            # WICHTIG: Wenn RFID vorhanden ist, nutze nur die RFID zum Matching (eindeutige UUID)
            # Wenn KEINE RFID vorhanden ist (leerer Slot), nutze AMS Slot als Fallback
            spool = None
            if rfid:
                spool = session.exec(select(Spool).where(Spool.rfid_chip_id == rfid)).first()

            if not spool and not rfid:
                # Nur bei fehlender RFID nach AMS Slot suchen (z.B. manuell eingelegte Spulen ohne RFID)
                spool = session.exec(select(Spool).where(Spool.ams_slot == ams_slot)).first()
            
            if spool:
                # Update existing spool
                bambu_logger.info(f"Update Spule {spool.id} - AMS Slot {ams_slot}, Weight: {remaining_weight}g")
                spool.ams_slot = ams_slot
                material = session.get(Material, spool.material_id) if spool.material_id else None
                is_bambu = bool(material and material.is_bambu is True)
                weight_empty = None
                if material and material.spool_weight_empty is not None:
                    weight_empty = material.spool_weight_empty
                if is_bambu and material and material.spool_weight_full is not None:
                    spool.weight_full = material.spool_weight_full
                if is_bambu and weight_empty is not None:
                    spool.weight_empty = weight_empty

                # Wenn AMS Gesamtgewicht (total_grams) im Tray-Payload vorhanden ist,
                # verwenden wir dieses als canonical `weight_full` (falls sinnvoll).
                ams_total = None
                if tray_payload:
                    ams_total = (
                        tray_payload.get("total_grams")
                        or tray_payload.get("tray_weight")
                        or tray_payload.get("tray_weight_g")
                        or tray_payload.get("total")
                        or tray_payload.get("totalGrams")
                        or tray_payload.get("total_g")
                    )
                    try:
                        if ams_total is not None:
                            ams_total = float(ams_total)
                    except Exception:
                        ams_total = None

                if ams_total and not is_bambu:
                    spool.weight_full = ams_total

                # weight_current is always the remaining filament weight (without empty spool weight)
                # Total spool weight = weight_empty + weight_current
                spool.weight_current = remaining_weight

                # Aktualisiere remain_percent kanalisiert, falls möglich
                try:
                    if is_bambu and spool.weight_full and spool.weight_empty and remaining_weight is not None:
                        total_filament = float(spool.weight_full) - float(spool.weight_empty)
                        if total_filament > 0:
                            spool.remain_percent = (remaining_weight / total_filament) * 100.0
                    elif ams_total and ams_total > 0:
                        spool.remain_percent = (remaining_weight / ams_total) * 100.0
                except Exception:
                    pass
                if rfid and not spool.rfid_chip_id:
                    spool.rfid_chip_id = rfid
                session.add(spool)
                session.commit()
            else:
                # Neue Spule anlegen
                bambu_logger.info(f"Neue Spule aus AMS - Slot {ams_slot}, Type: {material_type}")
                
                # Suche oder erstelle Material
                material_id = None
                material = None
                if material_type:
                    material = session.exec(
                        select(Material).where(Material.name == material_type, Material.brand == "Bambu Lab")
                    ).first()
                    
                    if not material:
                        # Neues Material anlegen
                        material = Material(
                            name=material_type,
                            brand="Bambu Lab",
                            is_bambu=True,
                            spool_weight_full=1000.0,
                            spool_weight_empty=209.0,
                        )
                        session.add(material)
                        session.commit()
                        session.refresh(material)
                        bambu_logger.info(f"Neues Material angelegt: {material_type}")
                    
                    material_id = material.id

                if not material_id:
                    bambu_logger.warning("Keine Material-ID fuer neue Spule gefunden, Abbruch (AMS Slot %s)", ams_slot)
                    session.close()
                    return
                is_bambu = bool(material and material.is_bambu is True)
                if is_bambu and bambu_start_delay_active():
                    bambu_logger.info("AMS auto-create delayed for Bambu material (slot=%s)", ams_slot)
                    session.close()
                    return
                
                # Neue Spule anlegen
                # Versuche, AMS-reported total grams als `weight_full` zu verwenden.
                ams_total = None
                if tray_payload:
                    ams_total = (
                        tray_payload.get("total_grams")
                        or tray_payload.get("tray_weight")
                        or tray_payload.get("tray_weight_g")
                        or tray_payload.get("total")
                        or tray_payload.get("totalGrams")
                        or tray_payload.get("total_g")
                    )
                    try:
                        if ams_total is not None:
                            ams_total = float(ams_total)
                    except Exception:
                        ams_total = None

                weight_full_val = material.spool_weight_full if material else None
                weight_empty_val = material.spool_weight_empty if material else None

                new_spool = Spool(
                    material_id=material_id,
                    ams_id=str(ams_id),
                    ams_slot=ams_slot,
                    rfid_chip_id=rfid,
                    weight_full=weight_full_val,
                    weight_empty=weight_empty_val,
                    weight_current=remaining_weight,
                    tray_uuid=rfid,  # tray_uuid = RFID eindeutige ID
                    tray_color=color,
                    tray_type=material_type,
                    location=f"AMS Slot {ams_slot}",
                    status="Aktiv",
                    is_open=True,
                    ams_source="rfid",
                    assigned=True,
                    is_active=True,
                )
                session.add(new_spool)
                session.commit()
                bambu_logger.info(f"Neue Spule angelegt: AMS Slot {ams_slot}, RFID={rfid}, Weight={remaining_weight}g")
            
            session.close()
            
        except Exception as e:
            bambu_logger.exception("Fehler beim Sync der Spule")

    def is_connected(self) -> bool:
        """Gibt zurück ob MQTT verbunden ist."""
        return self.connected
