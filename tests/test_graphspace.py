"""Integration-level checks for the GraphSpace façade."""
from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path

import pytest

from tests.conftest import DummyEmbeddingService, DummyLLMService


def _install_google_stubs() -> None:
    """Install minimal Google client stubs so imports succeed during tests."""
    if "google" not in sys.modules:
        sys.modules["google"] = types.ModuleType("google")

    credentials_module = types.ModuleType("google.oauth2.credentials")

    class Credentials:
        def __init__(self) -> None:  # pragma: no cover - simple stub
            self.token = "token"
            self.refresh_token = "refresh"
            self.token_uri = "token_uri"
            self.client_id = "client"
            self.client_secret = "secret"
            self.scopes: list[str] = []
            self.expiry = None
            self.valid = True
            self.expired = False

        @classmethod
        def from_authorized_user_info(cls, info, scopes):  # pragma: no cover
            creds = cls()
            creds.scopes = scopes or []
            return creds

        def refresh(self, request) -> None:  # pragma: no cover
            self.expired = False
            self.valid = True

    credentials_module.Credentials = Credentials
    sys.modules["google.oauth2.credentials"] = credentials_module
    sys.modules.setdefault("google.oauth2", types.ModuleType("google.oauth2"))

    flow_module = types.ModuleType("google_auth_oauthlib.flow")

    class InstalledAppFlow:
        @classmethod
        def from_client_secrets_file(cls, *args, **kwargs):  # pragma: no cover
            return cls()

        def run_local_server(self, port: int = 0):  # pragma: no cover
            return Credentials()

    flow_module.InstalledAppFlow = InstalledAppFlow
    sys.modules["google_auth_oauthlib.flow"] = flow_module

    requests_module = types.ModuleType("google.auth.transport.requests")

    class Request:  # pragma: no cover - unused stub
        pass

    requests_module.Request = Request
    sys.modules["google.auth.transport.requests"] = requests_module

    discovery_module = types.ModuleType("googleapiclient.discovery")

    class _Files:
        def list(self, **kwargs):  # pragma: no cover
            return types.SimpleNamespace(execute=lambda: {"files": [], "nextPageToken": None})

        def get(self, **kwargs):  # pragma: no cover
            return types.SimpleNamespace(execute=lambda: {"mimeType": "application/pdf", "name": "file"})

        def get_media(self, **kwargs):  # pragma: no cover
            return types.SimpleNamespace()

        def export_media(self, **kwargs):  # pragma: no cover
            return types.SimpleNamespace()

    class _Service:
        def files(self):  # pragma: no cover
            return _Files()

    def build(*args, **kwargs):  # pragma: no cover
        return _Service()

    discovery_module.build = build
    discovery_module.Resource = object
    sys.modules["googleapiclient.discovery"] = discovery_module

    http_module = types.ModuleType("googleapiclient.http")

    class MediaIoBaseDownload:
        def __init__(self, fh, request) -> None:  # pragma: no cover
            self._done = False

        def next_chunk(self):  # pragma: no cover
            if self._done:
                return (types.SimpleNamespace(progress=1.0), True)
            self._done = True
            return (types.SimpleNamespace(progress=1.0), True)

    http_module.MediaIoBaseDownload = MediaIoBaseDownload
    sys.modules["googleapiclient.http"] = http_module


def _install_calendar_stubs() -> None:
    """Provide lightweight calendar provider stubs."""
    models_module = types.ModuleType("graph_space_v2.integrations.calendar.models")

    class CalendarEvent:  # pragma: no cover - simple data stub
        pass

    class Calendar:  # pragma: no cover
        pass

    models_module.CalendarEvent = CalendarEvent
    models_module.Calendar = Calendar
    sys.modules.setdefault("graph_space_v2.integrations.calendar.models", models_module)

    service_module = types.ModuleType("graph_space_v2.integrations.calendar.calendar_service")

    class CalendarService:  # pragma: no cover
        pass

    service_module.CalendarService = CalendarService
    sys.modules.setdefault("graph_space_v2.integrations.calendar.calendar_service", service_module)

    task_sync_module = types.ModuleType("graph_space_v2.integrations.calendar.task_sync")

    class TaskCalendarSync:  # pragma: no cover
        pass

    task_sync_module.TaskCalendarSync = TaskCalendarSync
    sys.modules.setdefault("graph_space_v2.integrations.calendar.task_sync", task_sync_module)

    providers_module = types.ModuleType("graph_space_v2.integrations.calendar.providers")

    class GoogleCalendarProvider:  # pragma: no cover
        pass

    class ICalProvider:  # pragma: no cover
        pass

    providers_module.GoogleCalendarProvider = GoogleCalendarProvider
    providers_module.ICalProvider = ICalProvider
    sys.modules.setdefault("graph_space_v2.integrations.calendar.providers", providers_module)


def _install_requests_stub() -> None:
    """Provide a minimal requests module."""
    if "requests" in sys.modules:
        return

    requests_module = types.ModuleType("requests")

    class _Response:  # pragma: no cover
        def __init__(self, status_code: int = 200, content: bytes | None = None):
            self.status_code = status_code
            self.content = content or b""

        def json(self):  # pragma: no cover
            return {}

    def get(*args, **kwargs):  # pragma: no cover
        return _Response()

    def post(*args, **kwargs):  # pragma: no cover
        return _Response()

    requests_module.get = get
    requests_module.post = post
    requests_module.Response = _Response
    sys.modules["requests"] = requests_module


_install_google_stubs()
_install_calendar_stubs()
_install_requests_stub()


def _load_graphspace_module():
    """Import graphspace after stubbing external dependencies."""
    module = importlib.import_module("graph_space_v2.graphspace")
    return module, importlib.import_module("graph_space_v2")


class DummyDocumentProcessor:
    """Minimal document processor stub for GraphSpace wiring tests."""

    def __init__(self, llm_service, embedding_service, knowledge_graph):  # pragma: no cover - behaviour not under test
        self.llm_service = llm_service
        self.embedding_service = embedding_service
        self.knowledge_graph = knowledge_graph


@pytest.fixture()
def graphspace_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.json"
    config = {
        "embedding": {"model": "dummy", "dimension": 3},
        "llm": {"model": "dummy", "fallback_model": "dummy"},
    }
    config_path.write_text(json.dumps(config))
    return config_path


@pytest.fixture()
def user_data(tmp_path: Path) -> Path:
    data_path = tmp_path / "user_data.json"
    data = {"notes": [], "tasks": [], "contacts": [], "documents": []}
    data_path.write_text(json.dumps(data))
    return data_path


@pytest.fixture()
def patched_graphspace(monkeypatch: pytest.MonkeyPatch, graphspace_config: Path, user_data: Path):
    """Instantiate GraphSpace with lightweight service stubs."""
    graphspace_module, _ = _load_graphspace_module()
    monkeypatch.setattr(graphspace_module, "EmbeddingService", DummyEmbeddingService)
    monkeypatch.setattr(graphspace_module, "LLMService", DummyLLMService)
    monkeypatch.setattr(graphspace_module, "DocumentProcessor", DummyDocumentProcessor)

    instance = graphspace_module.GraphSpace(
        data_path=str(user_data),
        config_path=str(graphspace_config),
        use_api=False,
    )
    return instance


def test_graphspace_adds_and_serializes_tasks(patched_graphspace) -> None:
    """GraphSpace should expose TaskService through high-level helpers."""
    task_id = patched_graphspace.add_task({"description": "Plan release"})
    tasks = patched_graphspace.get_tasks()

    assert tasks[0]["id"] == task_id
    assert tasks[0]["title"].startswith("Title for")


def test_graphspace_lazy_google_drive_service(patched_graphspace) -> None:
    """Google Drive service should remain None when integration disabled."""
    assert patched_graphspace.google_drive_service is None
