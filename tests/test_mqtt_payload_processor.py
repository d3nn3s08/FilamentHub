import json

from types import SimpleNamespace

import pytest

from app.services import mqtt_payload_processor as processor


class FakeMapper:
    def __init__(self, model_name):
        self.model_name = model_name

    def map(self, data):
        class MapperResult:
            def __init__(self, model_name):
                self.model_name = model_name

            def to_dict(self):
                return {"model": self.model_name, "payload": data}

        return MapperResult(self.model_name)


class FakePrinterAutoDetector:
    MODEL = "FAKE"

    @staticmethod
    def detect_model_from_payload(payload):
        return payload.get("meta", {}).get("model") or FakePrinterAutoDetector.MODEL

    @staticmethod
    def detect_model_from_serial(serial):
        return serial and "AUTO" or None

    @staticmethod
    def detect_capabilities(payload):
        return {"capability": payload.get("meta", {}).get("capability", "basic")}


def _patch_base(monkeypatch):
    monkeypatch.setattr(processor, "UniversalMapper", FakeMapper)
    monkeypatch.setattr(processor, "PrinterAutoDetector", FakePrinterAutoDetector)
    monkeypatch.setattr(processor, "parse_ams", lambda payload: payload.get("ams", []))
    monkeypatch.setattr(processor, "parse_job", lambda payload: payload.get("job", {}))


def test_process_report_payload(monkeypatch):
    _patch_base(monkeypatch)
    topic = "device/SERIAL123/report"
    payload = json.dumps(
        {
            "meta": {"model": "BAMBU", "capability": "advanced"},
            "ams": [{"slot": 1}],
            "job": {"status": "completed"},
        }
    )

    result = processor.process_mqtt_payload(topic, payload)

    assert result["serial"] == "SERIAL123"
    assert result["raw"]["job"]["status"] == "completed"
    assert result["ams"][0]["slot"] == 1
    assert result["mapped_dict"]["model"] == "BAMBU"
    assert result["capabilities"]["capability"] == "advanced"


def test_process_non_report_topic_avoids_ams_job(monkeypatch):
    _patch_base(monkeypatch)
    topic = "device/SERIAL123/status"
    payload = json.dumps({"meta": {"model": "X1C"}})

    result = processor.process_mqtt_payload(topic, payload)

    assert result["serial"] == "SERIAL123"
    assert result["ams"] == []
    assert result["job"] == {}
    assert result["mapped_dict"]["model"] == "X1C"


def test_process_invalid_json_returns_defaults(monkeypatch):
    _patch_base(monkeypatch)
    topic = "device/UNKNOWN/report"
    result = processor.process_mqtt_payload(topic, "not-json")

    assert result["raw"] is None
    assert result["ams"] == []
    assert result["job"] == {}
    assert result["mapped"] is None
    assert result["mapped_dict"] is None


def test_process_map_failure_returns_none(monkeypatch):
    _patch_base(monkeypatch)
    monkeypatch.setattr(processor, "UniversalMapper", lambda model: SimpleNamespace(map=lambda data: (_ for _ in ()).throw(ValueError("boom"))))
    topic = "device/NOPE/report"
    payload = json.dumps({})

    result = processor.process_mqtt_payload(topic, payload)

    assert result["mapped"] is None
    assert result["mapped_dict"] is None
