import ipaddress
import socket
from typing import Optional

import psutil
from fastapi import APIRouter

router = APIRouter(
    prefix="/api/debug",
    tags=["Debug"]
)


def _private_ipv4_from_psutil() -> Optional[str]:
    try:
        for addrs in psutil.net_if_addrs().values():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    ip = addr.address
                    if _is_private_ipv4(ip):
                        return ip
    except Exception:
        return None
    return None


def _is_private_ipv4(ip: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.version == 4 and ip_obj.is_private
    except ValueError:
        return False


def _suggest_range(ip: str) -> Optional[str]:
    if not _is_private_ipv4(ip):
        return None
    try:
        parts = ip.split('.')
        parts[-1] = '0'
        return '.'.join(parts) + '/24'
    except Exception:
        return None


def _detect_local_ip() -> Optional[str]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        if _is_private_ipv4(ip):
            return ip
    except Exception:
        pass
    return _private_ipv4_from_psutil()


@router.get("/network")
async def get_network_info():
    hostname = None
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = None

    local_ip = _detect_local_ip()
    suggested = _suggest_range(local_ip) if local_ip else None
    return {
        "ok": True,
        "hostname": hostname,
        "local_ip": local_ip,
        "suggested_range": suggested,
    }
