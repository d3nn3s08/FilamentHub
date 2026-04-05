"""
Bambu Cloud Service
===================
Service für die Kommunikation mit der Bambu Lab Cloud API.

Features:
- Token-basierte Authentifizierung
- Abruf von Spulen-Daten aus der Cloud
- Sync zwischen Cloud und lokaler Datenbank
- Konflikt-Erkennung und -Behandlung
"""
import aiohttp
import asyncio
import logging
import json
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

logger = logging.getLogger("bambu_cloud")


# ============================================================
# BAMBU CLOUD API ENDPOINTS
# ============================================================

BAMBU_API_REGIONS = {
    "eu": "https://api.bambulab.com",
    "us": "https://api.bambulab.com",  # Selber Endpoint, Region im Header
    "cn": "https://api.bambulab.cn",
}

BAMBU_API_ENDPOINTS = {
    # User Endpoints (aktualisiert 2026)
    "user_profile": "/v1/user-service/my/profile",
    "user_info": "/v1/design-user-service/my/preference",  # Enthält UID für MQTT

    # Device Endpoints
    "devices": "/v1/iot-service/api/user/bind",
    "device_info": "/v1/iot-service/api/user/device/info",
    "device_versions": "/v1/iot-service/api/user/device/version",  # Enthält AMS/Filament Daten!

    # Print/Task Endpoints - WICHTIG für Job-History!
    "print_status": "/v1/iot-service/api/user/print",
    "print_tasks": "/v1/iot-service/api/user/task",
    "my_tasks": "/v1/user-service/my/tasks",  # Alle eigenen Druck-Jobs mit Filament-Verbrauch!

    # Files/Projects
    "projects": "/v1/iot-service/api/user/project",

    # Legacy (für Kompatibilität)
    "slicer_resources": "/v1/iot-service/api/slicer/resource",
}


@dataclass
class BambuCloudSpool:
    """Repräsentiert eine Spule aus der Bambu Cloud"""
    tray_uuid: str
    tray_id: str
    tray_type: str
    tray_sub_brands: str
    tray_color: str
    nozzle_temp_min: int
    nozzle_temp_max: int
    remain: int  # Prozent
    k: float
    tag_uid: Optional[str] = None
    tray_info_idx: Optional[str] = None
    tray_weight: Optional[int] = None  # Gewicht in Gramm (falls verfügbar)


@dataclass
class BambuCloudDevice:
    """Repräsentiert ein Gerät aus der Bambu Cloud"""
    dev_id: str
    name: str
    online: bool
    print_status: str
    dev_model_name: str
    dev_product_name: str
    dev_access_code: Optional[str] = None


@dataclass
class BambuCloudTask:
    """Repräsentiert einen Druck-Job aus der Bambu Cloud"""
    id: str
    title: str
    device_id: str
    device_name: Optional[str] = None
    status: str = "unknown"  # 'failed', 'finished', 'running', etc.
    weight: float = 0.0  # Verbrauchtes Filament in Gramm
    length: float = 0.0  # Verbrauchtes Filament in mm
    cost_time: int = 0  # Druckzeit in Sekunden
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    cover_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    plate_index: int = 1
    ams_mapping: Optional[List[Dict]] = None  # AMS-Slot-Zuordnung


class BambuCloudService:
    """
    Service für die Bambu Cloud API Kommunikation.

    Verwendung:
        service = BambuCloudService(access_token="...", region="eu")
        user = await service.get_user_info()
        devices = await service.get_devices()
        spools = await service.get_cloud_spools(device_id="...")
    """

    def __init__(
        self,
        access_token: str,
        region: str = "eu",
        refresh_token: Optional[str] = None
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.region = region
        self.base_url = BAMBU_API_REGIONS.get(region, BAMBU_API_REGIONS["eu"])
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Gibt eine aiohttp Session zurück (lazy init)."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    # Gleiche Headers wie Auth-Service (OrcaSlicer/BambuStudio)
                    "User-Agent": "bambu_network_agent/01.09.05.01",
                    "X-BBL-Client-Name": "OrcaSlicer",
                    "X-BBL-Client-Type": "slicer",
                    "X-BBL-Client-Version": "01.09.05.01",
                    "X-BBL-Language": "en-US",
                    "X-BBL-OS-Type": "windows",
                    "X-BBL-OS-Version": "10.0",
                    "X-BBL-Executable-info": "{}",
                    "X-BBL-Agent-OS-Type": "windows",
                }
            )
        return self._session

    async def close(self):
        """Schließt die Session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Führt einen API-Request aus."""
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"

        try:
            async with session.request(
                method,
                url,
                json=data,
                params=params
            ) as response:
                response_text = await response.text()

                if response.status == 401:
                    logger.error("Bambu Cloud: Unauthorized - Token ungültig")
                    raise BambuCloudAuthError("Token ungültig oder abgelaufen")

                if response.status == 403:
                    logger.error("Bambu Cloud: Forbidden")
                    raise BambuCloudAuthError("Zugriff verweigert")

                if response.status >= 400:
                    logger.error(f"Bambu Cloud API Error: {response.status} - {response_text}")
                    raise BambuCloudAPIError(f"API Error: {response.status}")

                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    logger.warning(f"Bambu Cloud: Konnte Response nicht parsen: {response_text[:200]}")
                    return {"raw": response_text}

        except aiohttp.ClientError as e:
            logger.error(f"Bambu Cloud: Netzwerkfehler - {e}")
            raise BambuCloudNetworkError(f"Netzwerkfehler: {e}")

    # ============================================================
    # USER & DEVICES
    # ============================================================

    async def get_user_info(self) -> Dict[str, Any]:
        """Gibt Benutzerinformationen zurück (inkl. UID für MQTT)."""
        try:
            # Versuche zuerst den neuen Endpunkt
            result = await self._request("GET", BAMBU_API_ENDPOINTS["user_info"])
            logger.info(f"Bambu Cloud: User Info abgerufen (preference endpoint)")
            return result
        except BambuCloudAPIError:
            # Fallback auf Profil-Endpunkt
            try:
                result = await self._request("GET", BAMBU_API_ENDPOINTS["user_profile"])
                logger.info(f"Bambu Cloud: User Info abgerufen (profile endpoint)")
                return result
            except Exception as e:
                logger.error(f"Bambu Cloud: User Info fehlgeschlagen: {e}")
                raise

    async def get_devices(self) -> List[BambuCloudDevice]:
        """Gibt alle registrierten Geräte zurück."""
        try:
            result = await self._request("GET", BAMBU_API_ENDPOINTS["devices"])
            # Debug: Zeige was die API zurückgibt
            logger.info(f"Bambu Cloud devices response: {result}")
            print(f"[CLOUD DEBUG] devices response keys: {result.keys() if isinstance(result, dict) else type(result)}")
            print(f"[CLOUD DEBUG] devices response: {result}")
        except BambuCloudAuthError:
            logger.warning("Bambu Cloud: devices Endpunkt nicht verfügbar (401) - Token hat eingeschränkte Berechtigungen")
            return []
        except BambuCloudAPIError as e:
            logger.warning(f"Bambu Cloud: devices Endpunkt Fehler: {e}")
            return []

        devices = []
        device_list = result.get("devices", result.get("data", []))

        for dev in device_list:
            devices.append(BambuCloudDevice(
                dev_id=dev.get("dev_id", ""),
                name=dev.get("name", "Unknown"),
                online=dev.get("online", False),
                print_status=dev.get("print_status", "unknown"),
                dev_model_name=dev.get("dev_model_name", ""),
                dev_product_name=dev.get("dev_product_name", ""),
                dev_access_code=dev.get("dev_access_code"),
            ))

        logger.info(f"Bambu Cloud: {len(devices)} Geräte gefunden")
        return devices

    async def test_connection(self) -> bool:
        """Testet die Verbindung zur Bambu Cloud."""
        try:
            await self.get_user_info()
            return True
        except Exception as e:
            logger.warning(f"Bambu Cloud: Connection test failed - {e}")
            return False

    # ============================================================
    # TASKS / PRINT JOBS
    # ============================================================

    async def get_tasks(
        self,
        device_id: Optional[str] = None,
        limit: int = 20,
        after: Optional[str] = None
    ) -> List[BambuCloudTask]:
        """
        Ruft Druck-Jobs/Tasks aus der Cloud ab.

        Args:
            device_id: Optional - nur Jobs von diesem Drucker
            limit: Maximale Anzahl (default: 20)
            after: Pagination cursor (task_id)

        Returns:
            Liste von BambuCloudTask Objekten mit Filament-Verbrauch
        """
        tasks = []

        try:
            # Build URL with parameters
            params = {"limit": limit}
            if device_id:
                params["deviceId"] = device_id
            if after:
                params["after"] = after

            result = await self._request(
                "GET",
                BAMBU_API_ENDPOINTS["my_tasks"],
                params=params
            )

            # Debug: Log response structure
            logger.info(f"Bambu Cloud Tasks response keys: {result.keys() if isinstance(result, dict) else type(result)}")
            print(f"[CLOUD DEBUG] Tasks response type: {type(result)}, preview: {str(result)[:500]}")

            # Parse tasks - API kann verschiedene Formate zurückgeben:
            # 1. Liste direkt: [task1, task2, ...]
            # 2. Dict mit "tasks": {"tasks": [...], "total": N}
            # 3. Dict mit "hits": {"hits": [...], "total": N}
            if isinstance(result, list):
                # API gibt direkt eine Liste zurück
                task_list = result
                total = len(result)
            elif isinstance(result, dict):
                # Format: {"total": 32, "hits": [task1, task2, ...]}
                task_list = result.get("tasks") or result.get("hits") or []

                # total ist direkt im result, nicht in hits
                total = result.get("total", 0)

                # Falls task_list noch ein Dict ist (verschachtelte Struktur)
                if isinstance(task_list, dict):
                    total = task_list.get("total", {}).get("value", 0) if isinstance(task_list.get("total"), dict) else task_list.get("total", 0)
                    task_list = task_list.get("hits", [])
            else:
                logger.warning(f"Bambu Cloud: Unerwartetes Tasks-Format: {type(result)}")
                task_list = []
                total = 0

            logger.info(f"Bambu Cloud: {len(task_list)} Tasks gefunden (total: {total})")

            for task in task_list:
                # Status mapping
                status_raw = task.get("status", "unknown")
                if isinstance(status_raw, int):
                    # Numerischer Status: 2 = finished, etc.
                    status_map = {0: "pending", 1: "running", 2: "finished", 3: "failed", 4: "cancelled"}
                    status = status_map.get(status_raw, "unknown")
                else:
                    status = str(status_raw).lower()

                tasks.append(BambuCloudTask(
                    id=str(task.get("id", "")),
                    title=task.get("title", task.get("designTitle", "Untitled")),
                    device_id=task.get("deviceId", ""),
                    device_name=task.get("deviceName", ""),
                    status=status,
                    weight=float(task.get("weight", 0) or 0),
                    length=float(task.get("length", 0) or 0),
                    cost_time=int(task.get("costTime", 0) or 0),
                    start_time=task.get("startTime"),
                    end_time=task.get("endTime"),
                    cover_url=task.get("cover"),
                    thumbnail_url=task.get("thumbnail"),
                    plate_index=int(task.get("plateIndex", 1) or 1),
                    ams_mapping=task.get("amsDetailMapping", []),
                ))

            return tasks

        except BambuCloudAuthError as e:
            logger.warning(f"Bambu Cloud: Tasks Endpunkt nicht verfügbar (401): {e}")
            print(f"[CLOUD DEBUG] Tasks Auth Error: {e}")
            return []
        except BambuCloudAPIError as e:
            logger.warning(f"Bambu Cloud: Tasks Endpunkt Fehler: {e}")
            print(f"[CLOUD DEBUG] Tasks API Error: {e}")
            return []
        except Exception as e:
            logger.error(f"Bambu Cloud: Unerwarteter Fehler beim Abrufen der Tasks: {e}")
            print(f"[CLOUD DEBUG] Tasks Exception: {e}")
            import traceback
            traceback.print_exc()
            return []

    # ============================================================
    # SPOOL / FILAMENT DATA
    # ============================================================

    async def get_cloud_spools(self, device_id: Optional[str] = None) -> List[BambuCloudSpool]:
        """
        Ruft Spulen-Daten aus der Cloud ab.

        Die Bambu Cloud speichert Filament-Informationen in den Geräte-Daten.
        Wir verwenden den devices Endpunkt als primäre Quelle.
        """
        spools = []

        try:
            # Zuerst Geräte abrufen (dieser Endpunkt funktioniert immer)
            devices = await self.get_devices()
            logger.info(f"Bambu Cloud: {len(devices)} Geräte gefunden")

            # Wenn keine Geräte, direkt zurück
            if not devices:
                logger.warning("Bambu Cloud: Keine Geräte gefunden")
                return spools

            # Für jetzt: Gib die Geräte-Info zurück ohne AMS-Daten abzurufen
            # (da device_versions 401 zurückgibt)
            # Die AMS-Daten werden später über MQTT lokal synchronisiert
            logger.info(f"Bambu Cloud: Sync abgeschlossen - {len(devices)} Geräte verbunden")
            logger.info("Bambu Cloud: AMS/Spulen-Daten werden über MQTT lokal synchronisiert")

            # Optional: Versuche device_versions (kann fehlschlagen)
            try:
                result = await self._request("GET", BAMBU_API_ENDPOINTS["device_versions"])
                logger.debug(f"Bambu Cloud device_versions: {result.keys() if isinstance(result, dict) else 'no dict'}")

                # Parse AMS-Daten wenn vorhanden
                devices_data = result.get("devices", result.get("data", []))
                if isinstance(devices_data, dict):
                    devices_data = [devices_data]

                for device in devices_data:
                    ams_data = device.get("ams", device.get("ams_status", []))
                    if isinstance(ams_data, dict):
                        ams_data = [ams_data]

                    for ams in ams_data:
                        trays = ams.get("tray", ams.get("trays", []))
                        if isinstance(trays, dict):
                            trays = [trays]

                        for tray in trays:
                            tray_uuid = tray.get("tray_uuid", tray.get("id", ""))
                            if not tray_uuid:
                                continue

                            spools.append(BambuCloudSpool(
                                tray_uuid=tray_uuid,
                                tray_id=str(tray.get("tray_id", tray.get("id", ""))),
                                tray_type=tray.get("tray_type", tray.get("type", "")),
                                tray_sub_brands=tray.get("tray_sub_brands", tray.get("brand", "")),
                                tray_color=tray.get("tray_color", tray.get("color", "")),
                                nozzle_temp_min=tray.get("nozzle_temp_min", 0),
                                nozzle_temp_max=tray.get("nozzle_temp_max", 0),
                                remain=tray.get("remain", tray.get("remain_percent", 0)),
                                k=tray.get("k", 0.0),
                                tag_uid=tray.get("tag_uid"),
                                tray_info_idx=tray.get("tray_info_idx"),
                                tray_weight=tray.get("tray_weight", tray.get("weight")),
                            ))

                if spools:
                    logger.info(f"Bambu Cloud: {len(spools)} Spulen aus Cloud abgerufen")

            except BambuCloudAuthError:
                # 401 - Token hat keine Berechtigung für diesen Endpunkt
                # Das ist OK - wir nutzen MQTT für AMS-Daten
                logger.info("Bambu Cloud: device_versions nicht verfügbar (401) - nutze MQTT für AMS-Daten")
            except Exception as e:
                logger.warning(f"Bambu Cloud: device_versions fehlgeschlagen: {e} - nutze MQTT für AMS-Daten")

        except Exception as e:
            logger.error(f"Bambu Cloud: Fehler beim Abrufen der Spulen - {e}")
            raise

        return spools

    # ============================================================
    # PRINT JOBS
    # ============================================================

    async def get_print_jobs(
        self,
        device_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Ruft Print-Job-Historie aus der Cloud ab.

        Args:
            device_id: Optional - spezifisches Gerät, sonst alle
            limit: Anzahl der Jobs (max 50)
            offset: Pagination Offset

        Returns:
            Liste von Print-Jobs mit Filament-Verbrauch
        """
        params = {"limit": min(limit, 50), "offset": offset}
        if device_id:
            params["device_id"] = device_id

        result = await self._request("GET", BAMBU_API_ENDPOINTS["print_tasks"], params=params)

        jobs = result.get("tasks", result.get("prints", result.get("data", [])))
        logger.info(f"Bambu Cloud: {len(jobs)} Print-Jobs abgerufen")

        return jobs

    async def get_job_details(self, job_id: str) -> Dict[str, Any]:
        """
        Ruft detaillierte Informationen zu einem Print-Job ab.
        Enthält Filament-Verbrauch pro Tray/Slot.

        Args:
            job_id: Die Task-ID des Jobs (aus MQTT oder Print-History)

        Returns:
            Job-Details mit Filament-Verbrauch
        """
        params = {"task_id": job_id}
        result = await self._request("GET", BAMBU_API_ENDPOINTS["print_status"], params=params)

        logger.info(f"Bambu Cloud: Job-Details für {job_id} abgerufen")
        return result

    async def get_device_status(self, device_id: str) -> Dict[str, Any]:
        """
        Ruft aktuellen Status eines Geräts ab.
        Enthält AMS-Informationen und aktuelle Spulen-Daten.

        Args:
            device_id: Die Device-ID des Druckers

        Returns:
            Device-Status mit AMS-Daten
        """
        params = {"device_id": device_id}
        result = await self._request("GET", BAMBU_API_ENDPOINTS["device_info"], params=params)

        logger.info(f"Bambu Cloud: Device-Status für {device_id} abgerufen")
        return result

    # ============================================================
    # SYNC LOGIC
    # ============================================================

    async def sync_spools_with_local(
        self,
        local_spools: List[Dict],
        weight_tolerance_percent: float = 5.0
    ) -> Dict[str, Any]:
        """
        Synchronisiert Cloud-Spulen mit lokalen Spulen.

        Returns:
            Dict mit:
            - matched: Liste von Matches (cloud_spool, local_spool, diff)
            - conflicts: Liste von Konflikten
            - cloud_only: Spulen nur in Cloud
            - local_only: Spulen nur lokal
        """
        cloud_spools = await self.get_cloud_spools()

        result = {
            "matched": [],
            "conflicts": [],
            "cloud_only": [],
            "local_only": [],
            "synced_at": datetime.now().isoformat()
        }

        # Index lokale Spulen nach tray_uuid
        local_by_uuid = {
            s.get("tray_uuid"): s
            for s in local_spools
            if s.get("tray_uuid")
        }

        cloud_uuids = set()

        for cloud_spool in cloud_spools:
            cloud_uuids.add(cloud_spool.tray_uuid)

            local_spool = local_by_uuid.get(cloud_spool.tray_uuid)

            if not local_spool:
                # Nur in Cloud vorhanden
                result["cloud_only"].append({
                    "cloud": cloud_spool.__dict__,
                    "suggested_action": "import"
                })
                continue

            # Match gefunden - prüfe auf Konflikte
            match_info = {
                "cloud": cloud_spool.__dict__,
                "local": local_spool,
            }

            # Gewichts-Vergleich
            cloud_remain = cloud_spool.remain  # Prozent
            local_remain = local_spool.get("remain_percent", 0) or 0

            if abs(cloud_remain - local_remain) > weight_tolerance_percent:
                result["conflicts"].append({
                    "type": "weight",
                    "cloud_spool": cloud_spool.__dict__,
                    "local_spool": local_spool,
                    "cloud_value": cloud_remain,
                    "local_value": local_remain,
                    "difference_percent": abs(cloud_remain - local_remain)
                })
            else:
                result["matched"].append(match_info)

        # Lokale Spulen ohne Cloud-Match
        for uuid, local_spool in local_by_uuid.items():
            if uuid not in cloud_uuids:
                result["local_only"].append({
                    "local": local_spool,
                    "suggested_action": "keep_local"
                })

        logger.info(
            f"Bambu Cloud Sync: {len(result['matched'])} matches, "
            f"{len(result['conflicts'])} conflicts, "
            f"{len(result['cloud_only'])} cloud-only, "
            f"{len(result['local_only'])} local-only"
        )

        return result

    async def perform_full_sync(
        self,
        session,  # SQLModel Session
        conflict_resolution_mode: str = "ask"
    ) -> Dict[str, Any]:
        """
        Führt einen vollständigen Sync durch:
        1. Testet Verbindung
        2. Ruft Cloud-Spulen ab (wenn verfügbar)
        3. Vergleicht mit lokalen Spulen
        4. Erstellt Konflikte falls nötig

        Args:
            session: SQLModel Session für DB-Zugriff
            conflict_resolution_mode: 'ask', 'prefer_local', 'prefer_cloud'

        Returns:
            Sync-Report mit Statistiken
        """
        from app.models.spool import Spool
        from app.models.cloud_conflict import CloudConflict
        from sqlmodel import select

        # 0. Teste erst die Verbindung
        is_connected = await self.test_connection()
        if not is_connected:
            raise BambuCloudAuthError("Verbindung zur Bambu Cloud fehlgeschlagen")

        # 0.5 Drucker abrufen
        devices = await self.get_devices()
        logger.info(f"Bambu Cloud Sync: {len(devices)} Drucker gefunden")

        # 1. Cloud-Spulen abrufen (kann leer sein wenn Token eingeschränkt)
        cloud_spools = await self.get_cloud_spools()
        
        # 2. Lokale Spulen abrufen
        local_spools_query = select(Spool)
        local_spools_list = session.exec(local_spools_query).all()
        
        # 3. Lokale Spulen in Dict-Format konvertieren
        local_spools_dict = []
        for spool in local_spools_list:
            # Berechne remain_percent aus Gewicht
            remain_percent = 0
            if spool.weight_full and spool.weight_full > 0:
                current = spool.weight_current or (spool.weight_full - spool.weight_empty)
                remain_percent = max(0, min(100, (current / spool.weight_full) * 100))
            
            local_spools_dict.append({
                "id": spool.id,
                "spool_number": spool.spool_number,
                "name": spool.name,
                "tray_uuid": spool.cloud_tray_uuid,
                "remain_percent": remain_percent,
                "weight_current": spool.weight_current,
                "weight_full": spool.weight_full,
                "color": spool.color or spool.tray_color,
                "material": spool.name or spool.tray_type or "Unknown",
            })
        
        # 4. Sync durchführen
        sync_result = await self.sync_spools_with_local(
            local_spools_dict,
            weight_tolerance_percent=5.0
        )
        
        # 5. Konflikte in DB speichern
        conflicts_created = 0
        for conflict_data in sync_result.get("conflicts", []):
            cloud_spool = conflict_data.get("cloud_spool", {})
            local_spool = conflict_data.get("local_spool", {})
            
            # Finde lokale Spool-ID
            spool_id = local_spool.get("id")
            
            # Erstelle CloudConflict
            conflict = CloudConflict(
                spool_id=spool_id,
                conflict_type="weight",
                severity="medium",
                local_value=str(local_spool.get("remain_percent", 0)),
                cloud_value=str(cloud_spool.get("remain", 0)),
                difference_percent=conflict_data.get("difference_percent", 0),
                status="pending",
                detected_at=datetime.now().isoformat(),
                description=f"Gewichtsabweichung: Lokal {local_spool.get('remain_percent', 0)}% vs Cloud {cloud_spool.get('remain', 0)}%"
            )
            session.add(conflict)
            conflicts_created += 1
        
        if conflicts_created > 0:
            session.commit()
            logger.info(f"Bambu Cloud Sync: {conflicts_created} Konflikte erstellt")
        
        # Info-Nachricht wenn keine Cloud-Spulen
        message = None
        if len(cloud_spools) == 0:
            message = "Verbunden, aber Token hat keine Berechtigung für Spulen-Daten. AMS-Daten werden über MQTT synchronisiert."
            logger.info(f"Bambu Cloud Sync: {message}")

        # Drucker-Daten für Response konvertieren
        devices_data = [
            {
                "dev_id": d.dev_id,
                "name": d.name,
                "online": d.online,
                "print_status": d.print_status,
                "model": d.dev_product_name,
                "model_code": d.dev_model_name,
                "access_code": d.dev_access_code,
            }
            for d in devices
        ]

        return {
            "status": "completed",
            "synced_at": datetime.now().isoformat(),
            "devices": devices_data,
            "devices_count": len(devices),
            "cloud_spools_count": len(cloud_spools),
            "local_spools_count": len(local_spools_list),
            "matched": len(sync_result.get("matched", [])),
            "conflicts": len(sync_result.get("conflicts", [])),
            "conflicts_created": conflicts_created,
            "cloud_only": len(sync_result.get("cloud_only", [])),
            "local_only": len(sync_result.get("local_only", [])),
            "message": message,
        }


# ============================================================
# EXCEPTIONS
# ============================================================

class BambuCloudError(Exception):
    """Basis-Exception für Bambu Cloud Fehler"""
    pass


class BambuCloudAuthError(BambuCloudError):
    """Authentifizierungsfehler"""
    pass


class BambuCloudAPIError(BambuCloudError):
    """API-Fehler"""
    pass


class BambuCloudNetworkError(BambuCloudError):
    """Netzwerkfehler"""
    pass


# ============================================================
# SINGLETON / FACTORY
# ============================================================

_cloud_service_instance: Optional[BambuCloudService] = None


async def get_bambu_cloud_service(
    access_token: str,
    region: str = "eu",
    refresh_token: Optional[str] = None
) -> BambuCloudService:
    """
    Factory-Funktion für BambuCloudService.
    Kann für Dependency Injection verwendet werden.
    """
    return BambuCloudService(
        access_token=access_token,
        region=region,
        refresh_token=refresh_token
    )
