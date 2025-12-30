"""Bambu Lab MQTT Service für Live-Sync von AMS Daten, RFID, Material-Verbrauch."""
from run import bambu_logger, error_logger
import paho.mqtt.client as mqtt
import json
from typing import Optional, Callable
from sqlmodel import Session, select
from sqlalchemy import or_
from app.models.spool import Spool
from app.models.material import Material
from app.database import get_session


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
            error_logger.exception(f"MQTT Verbindung fehlgeschlagen: {e}")

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
            error_logger.error(f"MQTT Verbindung fehlgeschlagen: RC={rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback wenn MQTT getrennt."""
        self.connected = False
        bambu_logger.warning(f"MQTT Verbindung getrennt: RC={rc}")

    def _on_message(self, client, userdata, msg):
        """Callback für eingehende MQTT Messages - Parse AMS Daten."""
        try:
            payload = json.loads(msg.payload.decode())
            
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
            error_logger.exception(f"Fehler beim Verarbeiten der MQTT Message: {e}")

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
                    
                    # Gewicht (in gramm * 1000, umrechnen)
                    remain_weight = tray.get("remain", 0) / 1000.0
                    
                    bambu_logger.debug(f"AMS Slot {ams_slot}: Type={tray_type}, Color={tray_color}, RFID={rfid}, Weight={remain_weight}g")
                    
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
            error_logger.exception(f"Fehler beim Verarbeiten der AMS Daten: {e}")

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
            error_logger.exception(f"Fehler beim Verarbeiten der Print Daten: {e}")

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
                ams_id_prefixed = f"AMS{ams_id}"
                existing_in_slot = session.exec(
                    select(Spool).where(
                        Spool.ams_slot == ams_slot,
                        Spool.is_active == True,
                        or_(Spool.ams_id == ams_id_str, Spool.ams_id == ams_id_prefixed, Spool.ams_id == ams_id)
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
                    error_logger.exception("Fehler beim Anlegen des AMS-Konflikts")
                finally:
                    session.close()
                # Abbrechen: keine weitere automatische Zuweisung
                return

            # Suche Spule mit diesem RFID oder AMS Slot
            spool = None
            if rfid:
                spool = session.exec(select(Spool).where(Spool.rfid_chip_id == rfid)).first()

            if not spool:
                # Suche nach AMS Slot
                spool = session.exec(select(Spool).where(Spool.ams_slot == ams_slot)).first()
            
            if spool:
                # Update existing spool
                bambu_logger.info(f"Update Spule {spool.id} - AMS Slot {ams_slot}, Weight: {remaining_weight}g")
                spool.ams_slot = ams_slot
                spool.remaining_weight = remaining_weight
                if rfid and not spool.rfid_chip_id:
                    spool.rfid_chip_id = rfid
                session.add(spool)
                session.commit()
            else:
                # Neue Spule anlegen
                bambu_logger.info(f"Neue Spule aus AMS - Slot {ams_slot}, Type: {material_type}")
                
                # Suche oder erstelle Material
                material_id = None
                if material_type:
                    material = session.exec(
                        select(Material).where(Material.material_type == material_type)
                    ).first()
                    
                    if not material:
                        # Neues Material anlegen
                        material = Material(
                            name=material_type,
                            material_type=material_type,
                            brand="Bambu Lab",
                            color=color or "#CCCCCC"
                        )
                        session.add(material)
                        session.commit()
                        session.refresh(material)
                        bambu_logger.info(f"Neues Material angelegt: {material_type}")
                    
                    material_id = material.id
                
                # Neue Spule anlegen
                new_spool = Spool(
                    material_id=material_id,
                    ams_slot=ams_slot,
                    rfid_chip_id=rfid,
                    full_weight=1000.0,  # Standard 1kg Spule
                    remaining_weight=remaining_weight,
                    location=f"AMS Slot {ams_slot}"
                )
                session.add(new_spool)
                session.commit()
                bambu_logger.info(f"Neue Spule angelegt: AMS Slot {ams_slot}")
            
            session.close()
            
        except Exception as e:
            error_logger.exception(f"Fehler beim Sync der Spule: {e}")

    def is_connected(self) -> bool:
        """Gibt zurück ob MQTT verbunden ist."""
        return self.connected
