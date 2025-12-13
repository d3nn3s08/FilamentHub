"""
Printer Scanner & Discovery Routes
Network Scanner für Bambu Lab und Klipper/Moonraker
"""
import socket
import asyncio
import time
import logging
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import ipaddress

router = APIRouter(prefix="/api/scanner", tags=["Printer Scanner"])
debug_printer_router = APIRouter(prefix="/api/debug/printer", tags=["Debug Printer"])
log = logging.getLogger(__name__)


# -----------------------------
# MODELS
# -----------------------------
class ScanRequest(BaseModel):
    ip_range: str = "192.168.1.0/24"
    ports: Optional[List[int]] = None
    timeout: float = 0.5


class PrinterInfo(BaseModel):
    ip: str
    hostname: Optional[str] = None
    type: str  # bambu, klipper, unknown
    port: int
    accessible: bool
    response_time: Optional[float] = None


class PrinterTestRequest(BaseModel):
    ip: str
    port: int = 6000
    timeout_ms: int = 1500


def _validate_ipv4(ip: str) -> str:
    try:
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.version != 4:
            raise HTTPException(status_code=400, detail="ip must be ipv4")
        return ip
    except ValueError:
        raise HTTPException(status_code=400, detail="ip must be ipv4")


# -----------------------------
# NETWORK UTILITIES
# -----------------------------
async def check_port(ip: str, port: int, timeout: float = 0.3) -> bool:
    """Prüft ob ein Port offen ist (async)"""
    try:
        # Run in executor um nicht zu blockieren
        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = await loop.run_in_executor(None, sock.connect_ex, (ip, port))
        sock.close()
        return result == 0
    except:
        return False


def get_hostname(ip: str) -> Optional[str]:
    """Versucht den Hostname aufzulösen"""
    try:
        return socket.gethostbyaddr(ip)[0]
    except:
        return None


async def scan_host(ip: str, ports: List[int], timeout: float = 0.5) -> Optional[PrinterInfo]:
    """Scannt einen Host auf offene Ports - priorisiert Drucker-Ports"""
    
    # Priorisiere Drucker-Ports (6000 für Bambu, 7125 für Klipper)
    priority_ports = [6000, 7125]
    other_ports = [p for p in ports if p not in priority_ports]
    scan_order = priority_ports + other_ports
    
    for port in scan_order:
        if port not in ports:
            continue
            
        if await check_port(ip, port, timeout):
            # Erkenne Drucker-Typ anhand des Ports
            printer_type = "unknown"
            
            if port in [990, 8883, 322, 6000]:
                printer_type = "bambu"
            elif port == 7125:
                printer_type = "klipper"
            elif port == 80:
                # Port 80 könnte Klipper oder Router sein - prüfe ob andere Drucker-Ports auch offen
                if await check_port(ip, 7125, timeout):
                    printer_type = "klipper"
                    port = 7125
                else:
                    # Wahrscheinlich kein Drucker (Router/FritzBox)
                    continue
            
            hostname = get_hostname(ip)
            
            return PrinterInfo(
                ip=ip,
                hostname=hostname,
                type=printer_type,
                port=port,
                accessible=True,
                response_time=timeout
            )
    
    return None


# -----------------------------
# SCAN ENDPOINTS
# -----------------------------
@router.post("/scan/network")
async def scan_network(request: ScanRequest):
    """
    Scannt ein Netzwerk nach Druckern
    Standard Ports:
    - Bambu Lab: 6000 (MQTT)
    - Klipper/Moonraker: 7125 (API)
    """
    
    # Default Ports wenn nicht angegeben
    ports: List[int] = request.ports or [6000, 7125, 80]
    
    try:
        # IP Range parsen
        network = ipaddress.ip_network(request.ip_range, strict=False)
        
        # Limit: Max 254 IPs scannen
        hosts = [str(h) for h in list(network.hosts())]
        if len(hosts) > 254:
            raise HTTPException(
                status_code=400,
                detail="IP Range zu groß. Max 254 Hosts erlaubt."
            )
        
        # Parallel scannen, aber mit Limit um das Event-Loop nicht zu blockieren
        sem = asyncio.Semaphore(50)

        async def limited_scan(ip: str):
            async with sem:
                return await scan_host(ip, ports, request.timeout)

        tasks = [limited_scan(ip) for ip in hosts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        found_printers = [r for r in results if isinstance(r, PrinterInfo)]
        
        return {
            "success": True,
            "scanned_hosts": len(hosts),
            "found_printers": len(found_printers),
            "printers": found_printers
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan Fehler: {str(e)}")


@router.get("/scan/quick")
async def quick_scan():
    """
    Schneller Scan des lokalen Netzwerks.
    Nutzt haeufige IPs, erweitert um einen begrenzten /24-Sweep als Fallback.
    """
    common_ips = []
    subnet_base = None

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()

        subnet_parts = local_ip.split('.')
        subnet_base = f"{subnet_parts[0]}.{subnet_parts[1]}.{subnet_parts[2]}"

        host_numbers = [1, 2, 10, 20, 30, 40, 41, 42, 50, 100, 110, 120, 150, 200, 250, 254]
        own_host = int(subnet_parts[3])
        for offset in range(-5, 6):
            nearby_host = own_host + offset
            if 1 <= nearby_host <= 254 and nearby_host not in host_numbers:
                host_numbers.append(nearby_host)

        for host in sorted(set(host_numbers)):
            common_ips.append(f"{subnet_base}.{host}")
    except Exception:
        base = "192.168."
        for subnet in ["0", "1", "2", "178"]:
            common_ips.extend([
                f"{base}{subnet}.1",
                f"{base}{subnet}.2",
                f"{base}{subnet}.10",
                f"{base}{subnet}.100",
            ])

    ports = [990, 8883, 7125, 322, 6000]

    tasks = [scan_host(ip, ports, timeout=0.3) for ip in common_ips]
    results = asyncio.gather(*tasks, return_exceptions=True)
    results = await results

    def to_lite(printer: PrinterInfo):
        detected_type = printer.type or "generic"
        if detected_type == "klipper":
            detected_type = "klipper (Moonraker detected)"
        return {
            "ip": printer.ip,
            "port": printer.port,
            "type": detected_type,
            "status": "idle"
        }

    found_printers = []
    for result in results:
        if isinstance(result, PrinterInfo):
            found_printers.append(to_lite(result))

    if not found_printers and subnet_base:
        sweep_hosts = [f"{subnet_base}.{i}" for i in range(1, 255)]
        sweep_hosts = sweep_hosts[:120]
        tasks = [scan_host(ip, ports, timeout=0.25) for ip in sweep_hosts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, PrinterInfo):
                found_printers.append(to_lite(result))
        return {
            "success": True,
            "scanned_hosts": len(common_ips) + len(sweep_hosts),
            "found_printers": len(found_printers),
            "printers": found_printers
        }

    return {
        "success": True,
        "scanned_hosts": len(common_ips),
        "found_printers": len(found_printers),
        "printers": found_printers
    }

@router.get("/test/connection")
async def test_connection(ip: str, port: int = 6000):
    """Testet die Verbindung zu einem spezifischen Drucker"""
    
    import time
    start = time.time()
    is_open = await check_port(ip, port, timeout=2.0)
    response_time = time.time() - start
    
    if not is_open:
        return {
            "success": False,
            "message": f"Port {port} auf {ip} nicht erreichbar",
            "ip": ip,
            "port": port,
            "response_time": response_time
        }
    
    # Erkenne Typ
    printer_type = "unknown"
    message = f"Port {port} ist erreichbar"
    
    if port == 6000:
        printer_type = "bambu"
        message = "✓ Bambu Lab MQTT Port erreichbar (Port 6000 offen, MQTT Login erforderlich)"
    elif port == 990:
        printer_type = "bambu"
        message = "✓ Bambu Lab FTP Port erreichbar (Port 990)"
    elif port == 8883:
        printer_type = "bambu"
        message = "✓ Bambu Lab MQTT SSL Port erreichbar (Port 8883)"
    elif port in [7125, 80]:
        printer_type = "klipper"
        message = f"✓ Klipper API erreichbar (Port {port})"
    
    hostname = get_hostname(ip)
    
    return {
        "success": True,
        "message": message,
        "ip": ip,
        "port": port,
        "hostname": hostname,
        "type": printer_type,
        "response_time": round(response_time * 1000, 2)  # ms
    }


@router.get("/detect/bambu")
async def detect_bambu_printers():
    """Schnelle Erkennung von Bambu Lab Druckern im lokalen Netzwerk
    
    Bambu Lab Ports:
    - 990: FTP (File Transfer)
    - 8883: MQTT over SSL
    - 322: FTP Data
    - 50000-50100: FTP Passive Mode Range
    """
    
    # Lokales Subnetz ermitteln
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        # Subnetz extrahieren
        subnet_parts = local_ip.split('.')
        local_subnet = f"{subnet_parts[0]}.{subnet_parts[1]}.{subnet_parts[2]}.0/24"
        network_ranges = [local_subnet]
    except:
        # Fallback
        network_ranges = ["192.168.0.0/24", "192.168.1.0/24", "192.168.178.0/24"]
    
    # Bambu Lab Ports (in Priorität)
    bambu_ports = [990, 8883, 322, 6000]
    found_printers = []
    
    async def check_bambu_host(ip_str: str):
        for port in bambu_ports:
            if await check_port(ip_str, port, timeout=0.3):
                return {
                    "ip": ip_str,
                    "port": port,
                    "type": "bambu",
                    "hostname": get_hostname(ip_str)
                }
        return None
    
    for range_str in network_ranges:
        network = ipaddress.ip_network(range_str, strict=False)
        hosts = [str(ip) for ip in list(network.hosts())[:50]]  # Nur erste 50 IPs
        
        # Scanne parallel
        tasks = [check_bambu_host(ip) for ip in hosts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if result and not isinstance(result, Exception):
                found_printers.append(result)
    
    return {
        "found": len(found_printers),
        "printers": found_printers
    }


@router.get("/detect/klipper")
async def detect_klipper_printers():
    """Schnelle Erkennung von Klipper/Moonraker (Port 7125) im lokalen Netzwerk"""
    
    # Lokales Subnetz ermitteln
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        subnet_parts = local_ip.split('.')
        local_subnet = f"{subnet_parts[0]}.{subnet_parts[1]}.{subnet_parts[2]}.0/24"
        network_ranges = [local_subnet]
    except:
        network_ranges = ["192.168.0.0/24", "192.168.1.0/24", "192.168.178.0/24"]
    
    found_printers = []
    
    async def check_klipper_host(ip_str: str):
        if await check_port(ip_str, 7125, timeout=0.3):
            return {
                "ip": ip_str,
                "port": 7125,
                "type": "klipper",
                "hostname": get_hostname(ip_str)
            }
        return None
    
    for range_str in network_ranges:
        network = ipaddress.ip_network(range_str, strict=False)
        hosts = [str(ip) for ip in list(network.hosts())[:50]]  # Erste 50 IPs
        
        # Scanne parallel
        tasks = [check_klipper_host(ip) for ip in hosts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if result and not isinstance(result, Exception):
                found_printers.append(result)
    
    return {
        "found": len(found_printers),
        "printers": found_printers
    }


# -----------------------------
# CONFIG GENERATION
# -----------------------------
@router.post("/generate/config")
async def generate_config(printers: List[Dict]):
    """
    Generiert Config-Vorschläge basierend auf gefundenen Druckern
    """
    
    config_suggestions = []
    
    for printer in printers:
        ip = printer.get("ip")
        printer_type = printer.get("type")
        hostname = printer.get("hostname", "unknown")
        
        if printer_type == "bambu":
            ip_suffix = ip.split('.')[-1] if ip else "unknown"
            config_suggestions.append({
                "type": "bambu",
                "name": hostname or f"Bambu_{ip_suffix}",
                "config": {
                    "bambu_lan": {
                        "enabled": True,
                        "ip": ip,
                        "port": 6000,
                        "access_code": "ENTER_YOUR_ACCESS_CODE"
                    }
                }
            })
        
        elif printer_type == "klipper":
            ip_suffix = ip.split('.')[-1] if ip else "unknown"
            config_suggestions.append({
                "type": "klipper",
                "name": hostname or f"Klipper_{ip_suffix}",
                "config": {
                    "klipper": {
                        "enabled": True,
                        "moonraker_url": f"http://{ip}:7125",
                        "api_key": "OPTIONAL_API_KEY"
                    }
                }
            })
    
    return {
        "success": True,
        "count": len(config_suggestions),
        "suggestions": config_suggestions
    }


# -----------------------------
# NETWORK INFO
# -----------------------------
@router.get("/network/info")
def get_network_info():
    """Gibt Informationen über das lokale Netzwerk zurück"""
    
    # Eigene IP ermitteln
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "127.0.0.1"
    
    # Hostname
    hostname = socket.gethostname()
    
    # Geschätztes Netzwerk
    ip_parts = local_ip.split('.')
    estimated_network = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
    
    return {
        "local_ip": local_ip,
        "hostname": hostname,
        "estimated_network": estimated_network,
        "default_scan_range": estimated_network
    }


@debug_printer_router.post("/test")
async def test_printer_port(payload: PrinterTestRequest):
    ip = _validate_ipv4(payload.ip)
    port = payload.port
    if not (1 <= port <= 65535):
        raise HTTPException(status_code=400, detail="port must be between 1 and 65535")
    timeout_ms = payload.timeout_ms
    if timeout_ms < 200:
        timeout_ms = 200
    if timeout_ms > 5000:
        timeout_ms = 5000

    timeout_s = timeout_ms / 1000.0
    start = time.perf_counter()
    try:
        with socket.create_connection((ip, port), timeout=timeout_s) as sock:
            sock.settimeout(timeout_s)
        latency_ms = int((time.perf_counter() - start) * 1000)
        log.debug("Port test success ip=%s port=%s latency_ms=%s", ip, port, latency_ms)
        return {
            "ok": True,
            "ip": ip,
            "port": port,
            "reachable": True,
            "latency_ms": latency_ms
        }
    except socket.timeout:
        return {
            "ok": True,
            "ip": ip,
            "port": port,
            "reachable": False,
            "error": "timeout",
            "latency_ms": None
        }
    except ConnectionRefusedError:
        return {
            "ok": True,
            "ip": ip,
            "port": port,
            "reachable": False,
            "error": "refused",
            "latency_ms": None
        }
    except OSError as exc:
        err_label = "unreachable" if isinstance(exc, OSError) else "error"
        return {
            "ok": True,
            "ip": ip,
            "port": port,
            "reachable": False,
            "error": err_label,
            "latency_ms": None
        }
    except Exception as exc:  # pragma: no cover - defensive
        detail = str(exc)[:120]
        log.warning("Port test exception ip=%s port=%s err=%s", ip, port, detail)
        return {
            "ok": False,
            "ip": ip,
            "port": port,
            "reachable": False,
            "error": "exception",
            "detail": detail,
            "latency_ms": None
        }
