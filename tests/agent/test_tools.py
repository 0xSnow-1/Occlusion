"""SPEC_V2 §9 — booking tools tests (mocked HTTP only, never real cal.com)."""

import io
import json
import logging
import urllib.error

from unittest.mock import patch

from src.agent import tools


class _FakeResp:
    def __init__(self, payload: dict, status: int = 200):
        self._raw = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _resp(payload: dict, status: int = 200):
    return _FakeResp(payload, status)


class TestListEventTypes:
    def test_parses(self, monkeypatch):
        monkeypatch.setenv("CAL_API_KEY", "test-key")
        body = {
            "status": "success",
            "data": [{"id": 1, "slug": "checkup", "title": "Checkup", "length": 30}],
        }
        seen = {}

        def fake_urlopen(req, timeout=10):
            seen["auth"] = req.get_header("Authorization")
            seen["version"] = req.get_header("Cal-api-version")
            seen["agent"] = req.get_header("User-agent")
            return _resp(body)

        with patch.object(tools.urllib.request, "urlopen", fake_urlopen):
            out = tools.list_event_types()
        assert len(out) == 1
        assert out[0].id == 1
        assert out[0].slug == "checkup"
        assert out[0].duration_min == 30
        assert seen["auth"] == "Bearer test-key"
        assert seen["version"] == "2024-06-14"  # event-types pins its own version
        assert "Mozilla" in (seen["agent"] or "")

    def test_api_down_returns_empty(self, monkeypatch):
        monkeypatch.setenv("CAL_API_KEY", "test-key")

        def fake_urlopen(req, timeout=10):
            raise urllib.error.URLError("down")

        with patch.object(tools.urllib.request, "urlopen", fake_urlopen):
            assert tools.list_event_types() == []


class TestGetSlots:
    def test_parses_dict_of_lists(self, monkeypatch):
        monkeypatch.setenv("CAL_API_KEY", "test-key")
        body = {
            "status": "success",
            "data": {"slots": {"2026-09-12": [{"time": "2026-09-12T09:00:00Z"}]}},
        }
        with patch.object(
            tools.urllib.request, "urlopen", lambda req, timeout=10: _resp(body)
        ):
            out = tools.get_slots(456, "2026-09-12T00:00:00Z", "2026-09-19T00:00:00Z", "UTC")
        assert len(out) == 1
        assert out[0].eventTypeId == 456
        assert out[0].start_utc.isoformat().startswith("2026-09-12T09:00:00")

    def test_parses_live_bare_date_map_with_start_key(self, monkeypatch):
        """Exact wire shape seen live 2026-09-12: data is a bare date-map,
        entries carry 'start' (not 'time'), offsets like +08:00."""
        monkeypatch.setenv("CAL_API_KEY", "test-key")
        body = {
            "status": "success",
            "data": {"2026-09-14": [{"start": "2026-09-14T09:00:00.000+08:00"}]},
        }
        with patch.object(
            tools.urllib.request, "urlopen", lambda req, timeout=10: _resp(body)
        ):
            out = tools.get_slots(7034024, "2026-09-12T00:00:00Z", "2026-09-19T00:00:00Z", "Asia/Manila")
        assert len(out) == 1
        assert out[0].start_utc.isoformat().startswith("2026-09-14T09:00:00")

    def test_api_down_returns_empty(self, monkeypatch):
        monkeypatch.setenv("CAL_API_KEY", "test-key")

        def fake_urlopen(req, timeout=10):
            raise urllib.error.URLError("down")

        with patch.object(tools.urllib.request, "urlopen", fake_urlopen):
            assert tools.get_slots(1, "2026-09-12T00:00:00Z", "2026-09-19T00:00:00Z", "UTC") == []


class TestCreateBooking:
    def test_parses_receipt(self, monkeypatch):
        monkeypatch.setenv("CAL_API_KEY", "test-key")
        body = {
            "status": "success",
            "data": {
                "uid": "abc123",
                "title": "Cleaning",
                "startTime": "2026-09-12T09:30:00Z",
            },
        }
        seen = {}

        def fake_urlopen(req, timeout=10):
            seen["payload"] = json.loads(req.data.decode("utf-8"))
            return _resp(body)

        with patch.object(tools.urllib.request, "urlopen", fake_urlopen):
            receipt = tools.create_booking(456, "2026-09-12T09:30:00Z", "Ana", "ana@mail.com")
        assert receipt.ok is True
        assert receipt.uid == "abc123"
        assert receipt.title == "Cleaning"
        assert receipt.start_utc.isoformat().startswith("2026-09-12T09:30:00")
        assert "notes" not in seen["payload"]  # live API 400s on top-level notes
        assert seen["payload"]["attendee"]["timeZone"] == "UTC"  # required live

    def test_api_down_returns_ok_false(self, monkeypatch):
        monkeypatch.setenv("CAL_API_KEY", "test-key")

        def fake_urlopen(req, timeout=10):
            raise urllib.error.URLError("down")

        with patch.object(tools.urllib.request, "urlopen", fake_urlopen):
            receipt = tools.create_booking(456, "2026-09-12T09:30:00Z", "Ana", "ana@mail.com")
        assert receipt.ok is False
        assert receipt.error

    def test_http_401_returns_ok_false(self, monkeypatch):
        monkeypatch.setenv("CAL_API_KEY", "test-key")

        def fake_urlopen(req, timeout=10):
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b"{}"))

        with patch.object(tools.urllib.request, "urlopen", fake_urlopen):
            receipt = tools.create_booking(456, "2026-09-12T09:30:00Z", "Ana", "ana@mail.com")
        assert receipt.ok is False


class TestKeyHygiene:
    def test_key_absent_from_logs(self, monkeypatch, caplog):
        secret = "cal_live_super_secret_xyz"
        monkeypatch.setenv("CAL_API_KEY", secret)

        def fake_urlopen(req, timeout=10):
            raise urllib.error.URLError("down")

        with caplog.at_level(logging.INFO, logger="src.agent.tools"):
            with patch.object(tools.urllib.request, "urlopen", fake_urlopen):
                tools.create_booking(1, "2026-09-12T09:30:00Z", "Ana", "ana@mail.com")
                tools.get_slots(1, "2026-09-12T00:00:00Z", "2026-09-19T00:00:00Z", "UTC")
                tools.list_event_types()
        assert secret not in caplog.text

    def test_missing_key_no_network(self, monkeypatch):
        monkeypatch.delenv("CAL_API_KEY", raising=False)
        with patch.object(
            tools.urllib.request,
            "urlopen",
            lambda req, timeout=10: (_ for _ in ()).throw(AssertionError("no HTTP without key")),
        ):
            assert tools.list_event_types() == []
            assert tools.get_slots(1, "a", "b", "UTC") == []
            receipt = tools.create_booking(1, "2026-09-12T09:30:00Z", "Ana", "ana@mail.com")
            assert receipt.ok is False
