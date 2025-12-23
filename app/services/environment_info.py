import logging
import os
import platform
import socket
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from fastapi import Request

logger = logging.getLogger(__name__)

_CONFIG_CACHE: Optional[Dict[str, Any]] = None
_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"
_DEFAULT_PORT = 8085
_DEFAULT_HOST = "0.0.0.0"
_CGROUP_PATH = Path("/proc/1/cgroup")


def _load_server_config() -> Dict[str, Any]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    if not _CONFIG_PATH.exists():
        _CONFIG_CACHE = {}
        return {}
    try:
        with _CONFIG_PATH.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if isinstance(raw, dict):
            _CONFIG_CACHE = raw
            return raw
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to read server config file: %s", exc)
    _CONFIG_CACHE = {}
    return {}


def _parse_port(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_host(
    request: Optional[Request], server_block: Dict[str, Any]
) -> Tuple[str, str]:
    if request is not None:
        host = request.url.hostname
        if host:
            return host, "request.url.hostname"
    env_host = os.getenv("HOST")
    if env_host:
        return env_host, "env.HOST"
    config_host = server_block.get("host")
    if isinstance(config_host, str) and config_host:
        return config_host, "config.yaml"
    return _DEFAULT_HOST, "fallback"


def _resolve_port(
    request: Optional[Request], server_block: Dict[str, Any]
) -> Tuple[int, str]:
    if request is not None and request.url.port:
        return request.url.port, "request.url.port"
    env_port = _parse_port(os.getenv("PORT"))
    if env_port is not None:
        return env_port, "env.PORT"
    config_port = _parse_port(server_block.get("port"))
    if config_port is not None:
        return config_port, "config.yaml"
    return _DEFAULT_PORT, "fallback"


def _read_cgroup() -> Optional[str]:
    try:
        return _CGROUP_PATH.read_text()
    except Exception:
        return None


def _detect_containerization() -> Tuple[bool, Optional[str], List[str]]:
    hints: List[str] = []
    containerized = False
    runtime: Optional[str] = None

    if Path("/.dockerenv").exists():
        containerized = True
        runtime = runtime or "docker"
        hints.append("found /.dockerenv")

    cgroup_text = _read_cgroup()
    if cgroup_text:
        lower = cgroup_text.lower()
        if "kubepods" in lower:
            containerized = True
            runtime = runtime or "kubernetes"
            hints.append("cgroup contains kubepods")
        elif "docker" in lower or "moby" in lower:
            containerized = True
            runtime = runtime or "docker"
            hints.append("cgroup contains docker/moby")
        elif "podman" in lower:
            containerized = True
            runtime = runtime or "podman"
            hints.append("cgroup contains podman")
        elif "lxc" in lower:
            containerized = True
            runtime = runtime or "lxc"
            hints.append("cgroup contains lxc")

    for env_var in (
        "KUBERNETES_SERVICE_HOST",
        "CONTAINER",
        "CONTAINERIZED",
        "DOTNET_RUNNING_IN_CONTAINER",
        "CI_CONTAINER",
    ):
        if os.getenv(env_var):
            containerized = True
            runtime = runtime or env_var.lower()
            hints.append(f"env {env_var} is set")
            break

    return containerized, runtime, hints


def build_environment_snapshot(request: Optional[Request] = None) -> Dict[str, Any]:
    config = _load_server_config()
    server_block = config.get("server", {}) if isinstance(config, dict) else {}
    host, host_source = _resolve_host(request, server_block)
    port, port_source = _resolve_port(request, server_block)
    containerized, container_runtime, container_hints = _detect_containerization()

    return {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_details": platform.platform(),
        "architecture": platform.machine(),
        "hostname": socket.gethostname(),
        "python_version": sys.version,
        "python_executable": sys.executable,
        "server": {
            "host": host,
            "host_source": host_source,
            "port": port,
            "port_source": port_source,
        },
        "containerized": containerized,
        "container_runtime": container_runtime,
        "container_hints": container_hints,
    }
