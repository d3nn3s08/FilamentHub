import os
import time
from fastapi import APIRouter

try:
  import psutil  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
  psutil = None

router = APIRouter(prefix="/api/debug", tags=["Debug Performance"])

# capture app start for uptime
app_start_ts = time.time()


def get_disk_path():
  cwd = os.getcwd()
  drive, _ = os.path.splitdrive(cwd)
  if drive:
    return drive + os.sep
  return "/"


@router.get("/performance")
async def debug_performance():
  data = {
    "ok": True,
    "backend_uptime_s": int(time.time() - app_start_ts),
    "cpu_percent": None,
    "ram_used_mb": None,
    "ram_total_mb": None,
    "disk_used_gb": None,
    "disk_total_gb": None,
    "note": None,
  }

  if psutil is None:
    data["note"] = "psutil not installed"
    return data

  try:
    data["cpu_percent"] = round(psutil.cpu_percent(interval=None), 1)
  except Exception:
    data["note"] = "cpu read failed"

  try:
    vm = psutil.virtual_memory()
    data["ram_used_mb"] = int(vm.used / 1024 / 1024)
    data["ram_total_mb"] = int(vm.total / 1024 / 1024)
  except Exception:
    data["note"] = (data["note"] or "ram read failed")

  try:
    disk_path = get_disk_path()
    disk = psutil.disk_usage(disk_path)
    data["disk_used_gb"] = round(disk.used / 1024 / 1024 / 1024, 2)
    data["disk_total_gb"] = round(disk.total / 1024 / 1024 / 1024, 2)
  except Exception:
    data["note"] = (data["note"] or "disk read failed")

  return data
