"""Unit tests for airlabs.py — all HTTP calls are mocked."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

import airlabs
from airlabs import AirLabsError


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _mock_response(payload: dict, status: int = 200) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.json.return_value = payload
    r.text = str(payload)
    return r


def _patch_call(response_payload: dict, status: int = 200):
    """Patch httpx.Client.get to return a fake response."""
    return patch(
        "httpx.Client.get",
        return_value=_mock_response(response_payload, status),
    )


# ---------------------------------------------------------------------------
# _call internals
# ---------------------------------------------------------------------------

class TestCallInternals:
    def test_raises_when_api_key_missing(self, monkeypatch):
        monkeypatch.delenv("AIRLABS_API_KEY", raising=False)
        with pytest.raises(AirLabsError, match="AIRLABS_API_KEY"):
            airlabs._call("airports", {})

    def test_raises_on_network_error(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        with patch("httpx.Client.get", side_effect=httpx.RequestError("timeout")):
            with pytest.raises(AirLabsError, match="network error"):
                airlabs._call("airports", {})

    def test_raises_on_server_500(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        with _patch_call({}, status=500):
            with pytest.raises(AirLabsError, match="server error"):
                airlabs._call("airports", {})

    def test_raises_on_non_json(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        r = MagicMock(spec=httpx.Response)
        r.status_code = 200
        r.json.side_effect = ValueError("no JSON")
        r.text = "not json"
        with patch("httpx.Client.get", return_value=r):
            with pytest.raises(AirLabsError, match="non-JSON"):
                airlabs._call("airports", {})

    def test_raises_on_error_key_dict(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        with _patch_call({"error": {"message": "invalid key"}}):
            with pytest.raises(AirLabsError, match="invalid key"):
                airlabs._call("airports", {})

    def test_raises_on_error_key_string(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        with _patch_call({"error": "bad request"}):
            with pytest.raises(AirLabsError, match="bad request"):
                airlabs._call("airports", {})

    def test_unwraps_response_key(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        with _patch_call({"response": [{"iata_code": "LHR"}]}):
            result = airlabs._call("airports", {})
        assert result == [{"iata_code": "LHR"}]

    def test_returns_raw_when_no_response_key(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        with _patch_call({"airports": [], "flights": []}):
            result = airlabs._call("nearby", {})
        assert "airports" in result

    def test_none_and_empty_params_excluded(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        captured = {}
        original_get = httpx.Client.get

        def fake_get(self, url, params=None, **kwargs):
            captured["params"] = params
            return _mock_response({"response": []})

        with patch("httpx.Client.get", fake_get):
            airlabs._call("airports", {"iata_code": None, "icao_code": "", "foo": "bar"})

        assert "iata_code" not in captured["params"]
        assert "icao_code" not in captured["params"]
        assert captured["params"]["foo"] == "bar"

    def test_uses_custom_base_url(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        monkeypatch.setenv("AIRLABS_BASE_URL", "https://custom.example.com/v1/")
        captured = {}

        def fake_get(self, url, **kwargs):
            captured["url"] = url
            return _mock_response({"response": []})

        with patch("httpx.Client.get", fake_get):
            airlabs._call("airports", {})

        assert captured["url"].startswith("https://custom.example.com/v1/airports")


# ---------------------------------------------------------------------------
# airport()
# ---------------------------------------------------------------------------

class TestAirport:
    def test_returns_first_of_list(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        payload = [{"iata_code": "LHR", "name": "Heathrow"}]
        with _patch_call({"response": payload}):
            result = airlabs.airport(iata="LHR")
        assert result["iata_code"] == "LHR"

    def test_returns_none_for_empty_list(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        with _patch_call({"response": []}):
            result = airlabs.airport(iata="XXX")
        assert result is None

    def test_raises_without_code(self):
        with pytest.raises(AirLabsError):
            airlabs.airport()

    def test_accepts_icao(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        with _patch_call({"response": [{"icao_code": "EGLL"}]}):
            result = airlabs.airport(icao="EGLL")
        assert result["icao_code"] == "EGLL"


# ---------------------------------------------------------------------------
# airline()
# ---------------------------------------------------------------------------

class TestAirline:
    def test_returns_first_of_list(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        with _patch_call({"response": [{"iata_code": "BA"}]}):
            result = airlabs.airline(iata="BA")
        assert result["iata_code"] == "BA"

    def test_returns_none_empty(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        with _patch_call({"response": []}):
            assert airlabs.airline(iata="ZZ") is None

    def test_raises_without_code(self):
        with pytest.raises(AirLabsError):
            airlabs.airline()


# ---------------------------------------------------------------------------
# flight()
# ---------------------------------------------------------------------------

class TestFlight:
    def test_returns_flight_dict(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        with _patch_call({"response": [{"flight_iata": "BA178"}]}):
            result = airlabs.flight(flight_iata="BA178")
        assert result["flight_iata"] == "BA178"

    def test_returns_none_empty(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        with _patch_call({"response": []}):
            assert airlabs.flight(flight_iata="ZZ999") is None

    def test_raises_without_code(self):
        with pytest.raises(AirLabsError):
            airlabs.flight()


# ---------------------------------------------------------------------------
# live_flights()
# ---------------------------------------------------------------------------

class TestLiveFlights:
    def test_returns_list(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        flights = [{"flight_iata": f"BA{i}"} for i in range(5)]
        with _patch_call({"response": flights}):
            result = airlabs.live_flights(airline_iata="BA", limit=3)
        assert len(result) == 3

    def test_raises_without_filter(self):
        with pytest.raises(AirLabsError):
            airlabs.live_flights()

    def test_returns_empty_on_non_list(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        with _patch_call({"response": {}}):
            result = airlabs.live_flights(dep_iata="LHR")
        assert result == []


# ---------------------------------------------------------------------------
# schedules()
# ---------------------------------------------------------------------------

class TestSchedules:
    def test_returns_list(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        rows = [{"flight_iata": "BA100"}]
        with _patch_call({"response": rows}):
            result = airlabs.schedules(dep_iata="LHR")
        assert result == rows

    def test_raises_without_filter(self):
        with pytest.raises(AirLabsError):
            airlabs.schedules()

    def test_limit_applied(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        rows = [{"i": i} for i in range(20)]
        with _patch_call({"response": rows}):
            result = airlabs.schedules(dep_iata="LHR", limit=5)
        assert len(result) == 5


# ---------------------------------------------------------------------------
# routes()
# ---------------------------------------------------------------------------

class TestRoutes:
    def test_returns_list(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        with _patch_call({"response": [{"dep_iata": "LHR"}]}):
            result = airlabs.routes(dep_iata="LHR")
        assert result[0]["dep_iata"] == "LHR"

    def test_raises_without_filter(self):
        with pytest.raises(AirLabsError):
            airlabs.routes()


# ---------------------------------------------------------------------------
# delays()
# ---------------------------------------------------------------------------

class TestDelays:
    def test_returns_list(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        with _patch_call({"response": [{"delay": 45}]}):
            result = airlabs.delays(dep_iata="LHR", min_delay_min=30)
        assert result[0]["delay"] == 45

    def test_invalid_type_raises(self):
        with pytest.raises(AirLabsError, match="type must be"):
            airlabs.delays(dep_iata="LHR", type="bad")

    def test_arrivals_type_accepted(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        with _patch_call({"response": []}):
            result = airlabs.delays(arr_iata="JFK", type="arrivals")
        assert result == []


# ---------------------------------------------------------------------------
# nearby()
# ---------------------------------------------------------------------------

class TestNearby:
    def test_returns_airports_and_flights(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        payload = {"airports": [{"iata": "LHR"}], "flights": [{"flight": "BA1"}]}
        with _patch_call(payload):
            result = airlabs.nearby(lat=51.5, lng=-0.1)
        assert "airports" in result
        assert "flights" in result

    def test_clamps_distance_min(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        captured = {}

        def fake_get(self, url, params=None, **kwargs):
            captured["params"] = params
            return _mock_response({"airports": [], "flights": []})

        with patch("httpx.Client.get", fake_get):
            airlabs.nearby(lat=0, lng=0, distance_km=0)
        assert captured["params"]["distance"] == 1

    def test_clamps_distance_max(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        captured = {}

        def fake_get(self, url, params=None, **kwargs):
            captured["params"] = params
            return _mock_response({"airports": [], "flights": []})

        with patch("httpx.Client.get", fake_get):
            airlabs.nearby(lat=0, lng=0, distance_km=9999)
        assert captured["params"]["distance"] == 500

    def test_returns_empty_on_non_dict(self, monkeypatch):
        monkeypatch.setenv("AIRLABS_API_KEY", "key")
        with _patch_call({"response": []}):
            result = airlabs.nearby(lat=0, lng=0)
        assert result == {"airports": [], "flights": []}
