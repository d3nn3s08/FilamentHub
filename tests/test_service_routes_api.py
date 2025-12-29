from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app
from app.routes import service_routes


def test_install_dependencies_returns_success_when_run_command_mocked():
    """Verifies POST /api/services/dependencies/install returns CommandResult JSON
    with success True when internal run_command is mocked.
    """
    mock_result = service_routes.CommandResult(
        success=True, message="Mocked install", output="ok", exit_code=0
    )

    with patch('app.routes.service_routes.run_command', return_value=mock_result):
        client = TestClient(app)
        resp = client.post('/api/services/dependencies/install')

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    # Required fields for global message/toast system
    assert 'success' in data
    assert 'message' in data
    assert data['success'] is True
    assert data['message'] == 'Mocked install'


def test_install_dependencies_handles_run_command_exception_gracefully():
    """Wenn `run_command` eine Exception wirft, sollte der Endpoint
    ein stabiles Fehler-JSON liefern (oder mindestens einen HTTP-Fehler
    mit JSON-Detail). Fokus: Schema und verständliche Fehlermeldung.
    """
    with patch('app.routes.service_routes.run_command', side_effect=RuntimeError('Test failure')):
        client = TestClient(app)
        try:
            resp = client.post('/api/services/dependencies/install')
        except RuntimeError as exc:
            # Laufzeit-Fehler wird direkt weitergeworfen - akzeptiere und prüfe Inhalt
            assert 'Test failure' in str(exc)
            return

    # Falls kein Exception-Throw, akzeptiere entweder ein 200 mit CommandResult-artigem Fehlerpayload
    # oder ein Fehlerstatus mit JSON-Detail. Wichtig: keine echten Kommandos.
    assert resp.headers.get('content-type', '').startswith('application/json')
    if resp.status_code == 200:
        data = resp.json()
        assert isinstance(data, dict)
        assert 'success' in data
        assert data['success'] is False
        assert 'message' in data
        assert 'Test failure' in str(data['message'])
    else:
        data = resp.json()
        assert 'detail' in data or 'message' in data
        # Ensure the error mentions the mocked failure somewhere
        assert 'Test failure' in str(data.get('detail', '')) or 'Test failure' in str(data.get('message', ''))


def test_install_dependencies_propagates_command_error_result():
    """Wenn `run_command` ein Fehler-Result zurückgibt, soll das
    unverändert durchgereicht werden (success False, message bleibt).
    """
    mock_result = service_routes.CommandResult(
        success=False, message="Fehlertext", output="err", exit_code=1
    )

    with patch('app.routes.service_routes.run_command', return_value=mock_result):
        client = TestClient(app)
        resp = client.post('/api/services/dependencies/install')

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert data.get('success') is False
    assert data.get('message') == 'Fehlertext'


# -----------------------------
# Tests for docker compose up (uses run_command)
# -----------------------------
def test_docker_compose_up_success():
    """run_command returns success → endpoint returns same success True/message"""
    mock_result = service_routes.CommandResult(success=True, message="OK", output="v", exit_code=0)

    with patch('app.routes.service_routes.run_command', return_value=mock_result):
        client = TestClient(app)
        resp = client.post('/api/services/docker/compose/up')

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert data.get('success') is True
    assert 'message' in data


def test_docker_compose_up_command_error_propagated():
    """run_command returns success=False → endpoint returns success False and passes message through"""
    mock_result = service_routes.CommandResult(success=False, message="Fehler", output="err", exit_code=1)

    with patch('app.routes.service_routes.run_command', return_value=mock_result):
        client = TestClient(app)
        resp = client.post('/api/services/docker/compose/up')

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert data.get('success') is False
    assert data.get('message') == 'Fehler'


def test_docker_compose_up_handles_run_command_exception():
    """Wenn run_command eine Exception wirft, Endpoint gibt stabilen Fehler zurück oder Exception propagiert (beide akzeptiert)"""
    with patch('app.routes.service_routes.run_command', side_effect=RuntimeError('boom')):
        client = TestClient(app)
        try:
            resp = client.post('/api/services/docker/compose/up')
        except RuntimeError as exc:
            assert 'boom' in str(exc)
            return

    # Falls kein Exception-Throw, prüfe JSON-Antwort
    assert resp.headers.get('content-type', '').startswith('application/json')
    data = resp.json()
    assert isinstance(data, dict)
    # Preferierte Form: success False + message enthält Fehler
    assert data.get('success') is False
    assert 'boom' in str(data.get('message', ''))
