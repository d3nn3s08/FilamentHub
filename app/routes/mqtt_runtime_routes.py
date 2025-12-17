from __future__ import annotations

from typing import Any, Dict, Optional
from sqlmodel import select

from app.database import get_session
from app.models.printer import Printer

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
# status setzen#
from app.services import mqtt_runtime

from datetime import datetime

router = APIRouter()


class MQTTErrorResponse(BaseModel):
    connected: bool = False
    error: str


class MQTTConnectRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    broker: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("broker", "host", "ip"),
        description="MQTT broker host/IP (Bambu printers typically use TLS on port 8883).",
    )
    port: int = Field(default=8883, ge=1, le=65535)
    client_id: str = Field(
        default="filamenthub_debug",
        validation_alias=AliasChoices("client_id", "clientId"),
        min_length=1,
    )
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = Field(default="311", description="MQTT protocol version: 5 | 311 | 31")
    tls: bool = Field(default=True, description="Must be true (PrinterMQTTClient enforces TLS).")
    # Printer mode
    use_printer_config: bool = Field(default=False, description="If true, use printer config from DB (printer_id required)")
    printer_id: Optional[str] = Field(default=None, description="Printer UUID (when use_printer_config is true)")


class MQTTConnectResponse(BaseModel):
    connected: bool
    client_id: str
    broker: str
    port: int


class MQTTStatusResponse(BaseModel):
    connected: bool
    client_id: Optional[str] = None
    broker: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    connected_since: Optional[str] = None
    cloud_serial: Optional[str] = None
    last_seen: Optional[str] = None
    subscriptions_count: Optional[int] = None
    topics_count: Optional[int] = None
    message_count: Optional[int] = None
    last_message_time: Optional[str] = None
    qos: Optional[int] = None
    uptime: Optional[str] = None


class MQTTTopicsResponse(BaseModel):
    connected: bool
    items: list[str]
    count: int


class MQTTMessageItem(BaseModel):
    topic: str
    payload: str
    timestamp: str


class MQTTMessagesResponse(BaseModel):
    connected: bool
    messages: list[MQTTMessageItem]
    count: int


@router.post(
    "/connect",
    response_model=MQTTConnectResponse,
    responses={400: {"model": MQTTErrorResponse}, 500: {"model": MQTTErrorResponse}},
)
def connect(req: MQTTConnectRequest):
    """Connect via mqtt_runtime.

    On success: HTTP 200 and a deterministic connected=true response.
    On failure: HTTP 4xx/5xx with a clear JSON error.
    """
    payload = req.model_dump() if hasattr(req, "model_dump") else req.dict()

    # Initialize variables for static analysis / safe returns
    printer = None
    broker = None
    port = None
    protocol = None
    client_id = None
    runtime_payload = None

    # Printer mode: use DB as Source of Truth
    if payload.get("use_printer_config"):
        pid = payload.get("printer_id")
        if not pid:
            return JSONResponse(status_code=400, content={"connected": False, "error": "printer_id required when use_printer_config is true"})

        # Load printer from DB
        try:
            with next(get_session()) as session:
                printer = session.exec(select(Printer).where(Printer.id == pid)).first()
        except Exception as exc:
            return JSONResponse(status_code=500, content={"connected": False, "error": f"db error: {str(exc)}"})

        if not printer:
            return JSONResponse(status_code=400, content={"connected": False, "error": "Printer not found"})
        if not getattr(printer, "active", True):
            return JSONResponse(status_code=400, content={"connected": False, "error": "Printer not active"})
        if getattr(printer, "printer_type", "") != "bambu":
            return JSONResponse(status_code=400, content={"connected": False, "error": "Unsupported printer type"})
        if not getattr(printer, "ip_address", None):
            return JSONResponse(status_code=400, content={"connected": False, "error": "Printer has no ip_address"})
        if not getattr(printer, "api_key", None):
            return JSONResponse(status_code=400, content={"connected": False, "error": "Printer has no api_key"})

        # Build runtime payload exclusively from DB
        broker = printer.ip_address
        port = int(getattr(printer, "port", 6000) or 6000)
        protocol = str(getattr(printer, "mqtt_version", "5") or "5")
        username = "bblp"
        password = printer.api_key
        tls = True
        client_id = f"filamenthub_{printer.name}_{str(printer.id)[:6]}"

        runtime_payload = {
            "host": broker,
            "port": port,
            "client_id": client_id,
            "username": username,
            "password": password,
            "protocol": protocol,
            "tls": tls,
            "cloud_serial": getattr(printer, "cloud_serial", None),
            "printer_id": printer.id,
            "printer_name": printer.name,
            "printer_model": printer.model,
        }

        # cloud_serial must be present for Bambu printers
        if not runtime_payload.get("cloud_serial"):
            return JSONResponse(status_code=400, content={"connected": False, "error": "printer has no cloud_serial"})

        result = mqtt_runtime.connect(runtime_payload)

        # Handle runtime result immediately while `printer` is in scope
        if not isinstance(result, dict):
            return JSONResponse(status_code=500, content={"connected": False, "error": "invalid runtime response"})
        if not result.get("success"):
            error = str(result.get("error") or "connect failed")
            status_code = 400 if ("missing" in error or "must be" in error) else 500
            return JSONResponse(status_code=status_code, content={"connected": False, "error": error})

        # Successful printer-mode response (connection established at transport
        # level). IMPORTANT: application-level `connected` remains False
        # until a device/<cloud_serial>/report arrives and updates runtime state.
        return {
            "connected": False,
            "mode": "printer",
            "client_id": result.get("client_id"),
            "printer_id": printer.id,
            "printer_name": printer.name,
            "broker": broker,
            "port": port,
            "protocol": protocol,
        }
    else:
        # Manual mode: normalize external API names to the runtime service keys.
        runtime_payload = {
            "host": payload.get("broker"),
            "port": payload.get("port"),
            "client_id": payload.get("client_id"),
            "username": payload.get("username"),
            "password": payload.get("password"),
            "protocol": payload.get("protocol"),
            "tls": payload.get("tls"),
        }

        result = mqtt_runtime.connect(runtime_payload)

        if not isinstance(result, dict):
            return JSONResponse(status_code=500, content={"connected": False, "error": "invalid runtime response"})
        if not result.get("success"):
            error = str(result.get("error") or "connect failed")
            status_code = 400 if ("missing" in error or "must be" in error) else 500
            return JSONResponse(status_code=status_code, content={"connected": False, "error": error})

        # fallback: manual mode response. Do NOT claim application-level
        # connected here — UI must use /status which reflects reports.
        return {
            "connected": False,
            "client_id": str(runtime_payload.get("client_id") or ""),
            "broker": str(runtime_payload.get("host") or ""),
            "port": int(runtime_payload.get("port") or 8883),
        }


@router.post(
    "/disconnect",
    responses={500: {"model": MQTTErrorResponse}},
)
def disconnect() -> Any:
    """Disconnect via mqtt_runtime."""
    try:
        result = mqtt_runtime.disconnect()
        if isinstance(result, dict):
            return result
        return {"success": True, "connected": False}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"connected": False, "error": str(exc)})


@router.get(
    "/status",
    response_model=MQTTStatusResponse,
    response_model_exclude_none=True,
    responses={500: {"model": MQTTErrorResponse}},
)
def status():
    """Get status via mqtt_runtime."""
    try:
        # Return the runtime state 1:1 — mqtt_runtime.status() returns a dict
        # with the keys required by the UI. Do not apply heuristics here.
        result = mqtt_runtime.status()
        if not isinstance(result, dict):
            return {"connected": False}
        return result

    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"connected": False, "error": str(exc)}
        )


@router.get(
    "/topics",
    response_model_exclude_none=True,
    responses={500: {"model": MQTTErrorResponse}},
)
def topics():
    """Get subscribed MQTT topics (not message stats)."""
    try:
        result = mqtt_runtime.topics()
        if not isinstance(result, dict):
            return {"connected": False, "items": [], "count": 0}

        connected = bool(result.get("connected"))
        items = result.get("items") or []
        count = int(result.get("count") or 0)

        return {"connected": connected, "items": items, "count": count}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"connected": False, "error": str(exc)})


@router.get(
    "/messages",
    response_model_exclude_none=True,
    responses={500: {"model": MQTTErrorResponse}},
)
def messages(limit: int = 50):
    """Get last N live messages (newest first)."""
    try:
        result = mqtt_runtime.status()
        connected = bool(result.get("connected")) if isinstance(result, dict) else False
        
        msgs = mqtt_runtime.get_messages(limit=min(limit, 100))
        
        return {
            "connected": connected,
            "messages": msgs,
            "count": len(msgs),
        }
    except Exception as exc:
        return JSONResponse(status_code=500, content={"connected": False, "error": str(exc)})
