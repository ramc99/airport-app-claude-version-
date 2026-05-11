"""Flask route tests — airlabs and requests.post are mocked throughout."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests as req_lib

import airlabs
from airlabs import AirLabsError


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

AIRPORT = {"iata_code": "LHR", "name": "Heathrow", "city": "London", "country_code": "GB"}
AIRLINE = {"iata_code": "BA", "name": "British Airways"}
FLIGHT = {"flight_iata": "BA178", "status": "en-route"}


def _mock_llm_response(content: str, status: int = 200) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    r.raise_for_status = MagicMock()
    return r


# ---------------------------------------------------------------------------
# static pages
# ---------------------------------------------------------------------------

class TestStaticPages:
    def test_home(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_healthz(self, client):
        r = client.get("/healthz")
        assert r.status_code == 200
        body = r.get_json()
        assert body["status"] == "ok"
        assert "ts" in body


# ---------------------------------------------------------------------------
# /search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_empty_redirects_home(self, client):
        r = client.get("/search?q=")
        assert r.status_code == 302
        assert "/" in r.headers["Location"]

    def test_three_letters_redirects_airport(self, client):
        r = client.get("/search?q=LHR")
        assert r.status_code == 302
        assert "airport" in r.headers["Location"]

    def test_two_letters_redirects_airline(self, client):
        r = client.get("/search?q=BA")
        assert r.status_code == 302
        assert "airline" in r.headers["Location"]

    def test_flight_number_redirects_flight(self, client):
        r = client.get("/search?q=BA178")
        assert r.status_code == 302
        assert "flight" in r.headers["Location"]

    def test_four_letters_icao_redirects_airport(self, client):
        r = client.get("/search?q=EGLL")
        assert r.status_code == 302
        assert "airport" in r.headers["Location"]

    def test_unrecognised_query_returns_400(self, client):
        r = client.get("/search?q=TOOLONG")
        assert r.status_code == 400

    def test_case_insensitive(self, client):
        r = client.get("/search?q=lhr")
        assert r.status_code == 302
        assert "airport" in r.headers["Location"]


# ---------------------------------------------------------------------------
# /flight
# ---------------------------------------------------------------------------

class TestFlightView:
    def test_no_code_renders_empty(self, client):
        r = client.get("/flight")
        assert r.status_code == 200

    def test_iata_flight_found(self, client):
        with patch.object(airlabs, "flight", return_value=FLIGHT):
            r = client.get("/flight?code=BA178")
        assert r.status_code == 200

    def test_icao_flight_dispatched(self, client):
        with patch.object(airlabs, "flight", return_value=FLIGHT) as m:
            client.get("/flight?code=BAW178")
        m.assert_called_once_with(flight_icao="BAW178")

    def test_flight_not_found_still_200(self, client):
        with patch.object(airlabs, "flight", return_value=None):
            r = client.get("/flight?code=XX999")
        assert r.status_code == 200

    def test_airlabs_error_returns_502(self, client):
        with patch.object(airlabs, "flight", side_effect=AirLabsError("bad")):
            r = client.get("/flight?code=BA178")
        assert r.status_code == 502


# ---------------------------------------------------------------------------
# /airport/<code>
# ---------------------------------------------------------------------------

class TestAirportView:
    def _stub_all(self):
        return patch.multiple(
            airlabs,
            airport=MagicMock(return_value=AIRPORT),
            schedules=MagicMock(return_value=[]),
            delays=MagicMock(return_value=[]),
        )

    def test_iata_airport_found(self, client):
        with self._stub_all():
            r = client.get("/airport/LHR")
        assert r.status_code == 200

    def test_icao_dispatches_correctly(self, client):
        with patch.object(airlabs, "airport", return_value=AIRPORT) as m, \
             patch.object(airlabs, "schedules", return_value=[]), \
             patch.object(airlabs, "delays", return_value=[]):
            client.get("/airport/EGLL")
        m.assert_called_once_with(icao="EGLL")

    def test_not_found_returns_404(self, client):
        with patch.object(airlabs, "airport", return_value=None):
            r = client.get("/airport/XYZ")
        assert r.status_code == 404

    def test_no_iata_skips_schedules(self, client):
        airport_no_iata = {"icao_code": "XXXX"}
        with patch.object(airlabs, "airport", return_value=airport_no_iata), \
             patch.object(airlabs, "schedules") as sched_mock, \
             patch.object(airlabs, "delays") as del_mock:
            r = client.get("/airport/XXXX")
        sched_mock.assert_not_called()
        del_mock.assert_not_called()
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# /airline/<code>
# ---------------------------------------------------------------------------

class TestAirlineView:
    def test_iata_airline_found(self, client):
        with patch.object(airlabs, "airline", return_value=AIRLINE), \
             patch.object(airlabs, "live_flights", return_value=[]):
            r = client.get("/airline/BA")
        assert r.status_code == 200

    def test_icao_dispatches_correctly(self, client):
        with patch.object(airlabs, "airline", return_value=AIRLINE) as m, \
             patch.object(airlabs, "live_flights", return_value=[]):
            client.get("/airline/BAW")
        m.assert_called_once_with(icao="BAW")

    def test_not_found_returns_404(self, client):
        with patch.object(airlabs, "airline", return_value=None):
            r = client.get("/airline/ZZ")
        assert r.status_code == 404

    def test_no_iata_skips_live_flights(self, client):
        with patch.object(airlabs, "airline", return_value={"icao_code": "XXX"}), \
             patch.object(airlabs, "live_flights") as lf:
            r = client.get("/airline/XXX")
        lf.assert_not_called()
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# /schedules
# ---------------------------------------------------------------------------

class TestSchedulesView:
    def test_no_params_no_search(self, client):
        with patch.object(airlabs, "schedules") as m:
            r = client.get("/schedules")
        m.assert_not_called()
        assert r.status_code == 200

    def test_with_dep_triggers_search(self, client):
        with patch.object(airlabs, "schedules", return_value=[]) as m:
            r = client.get("/schedules?dep=LHR")
        m.assert_called_once()
        assert r.status_code == 200

    def test_with_all_params(self, client):
        with patch.object(airlabs, "schedules", return_value=[]) as m:
            client.get("/schedules?dep=LHR&arr=JFK&airline=BA")
        call_kwargs = m.call_args.kwargs
        assert call_kwargs["dep_iata"] == "LHR"
        assert call_kwargs["arr_iata"] == "JFK"
        assert call_kwargs["airline_iata"] == "BA"


# ---------------------------------------------------------------------------
# /routes
# ---------------------------------------------------------------------------

class TestRoutesView:
    def test_no_params_no_search(self, client):
        with patch.object(airlabs, "routes") as m:
            r = client.get("/routes")
        m.assert_not_called()
        assert r.status_code == 200

    def test_with_dep_triggers_search(self, client):
        with patch.object(airlabs, "routes", return_value=[]):
            r = client.get("/routes?dep=LHR")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# /delays
# ---------------------------------------------------------------------------

class TestDelaysView:
    def test_no_params_no_search(self, client):
        with patch.object(airlabs, "delays") as m:
            r = client.get("/delays")
        m.assert_not_called()
        assert r.status_code == 200

    def test_with_dep_triggers_search(self, client):
        with patch.object(airlabs, "delays", return_value=[]):
            r = client.get("/delays?dep=LHR")
        assert r.status_code == 200

    def test_invalid_min_defaults_to_30(self, client):
        with patch.object(airlabs, "delays", return_value=[]) as m:
            client.get("/delays?dep=LHR&min=notanumber")
        assert m.call_args.kwargs["min_delay_min"] == 30

    def test_valid_min_passed_through(self, client):
        with patch.object(airlabs, "delays", return_value=[]) as m:
            client.get("/delays?dep=LHR&min=60")
        assert m.call_args.kwargs["min_delay_min"] == 60

    def test_invalid_type_defaults_to_departures(self, client):
        with patch.object(airlabs, "delays", return_value=[]) as m:
            client.get("/delays?dep=LHR&type=badvalue")
        assert m.call_args.kwargs["type"] == "departures"

    def test_arrivals_type_accepted(self, client):
        with patch.object(airlabs, "delays", return_value=[]) as m:
            client.get("/delays?arr=JFK&type=arrivals")
        assert m.call_args.kwargs["type"] == "arrivals"


# ---------------------------------------------------------------------------
# /nearby
# ---------------------------------------------------------------------------

class TestNearbyView:
    def test_no_params_renders(self, client):
        r = client.get("/nearby")
        assert r.status_code == 200

    def test_with_coords(self, client):
        with patch.object(airlabs, "nearby", return_value={"airports": [], "flights": []}):
            r = client.get("/nearby?lat=51.5&lng=-0.1")
        assert r.status_code == 200

    def test_invalid_coords_return_400(self, client):
        r = client.get("/nearby?lat=abc&lng=xyz")
        assert r.status_code == 400

    def test_custom_distance(self, client):
        with patch.object(airlabs, "nearby", return_value={"airports": [], "flights": []}) as m:
            client.get("/nearby?lat=51.5&lng=-0.1&distance=200")
        assert m.call_args.kwargs["distance_km"] == 200


# ---------------------------------------------------------------------------
# /api/chat
# ---------------------------------------------------------------------------

class TestChatApi:
    def test_empty_message_returns_prompt(self, client):
        r = client.post("/api/chat", json={"message": ""})
        assert r.status_code == 200
        assert "ask" in r.get_json()["response"].lower()

    def test_no_api_key_returns_config_error(self, client, monkeypatch):
        import app as app_module
        monkeypatch.setattr(app_module, "CLOUD_LLM_API_KEY", None)
        r = client.post("/api/chat", json={"message": "hello"})
        assert r.status_code == 200
        assert "not configured" in r.get_json()["response"].lower()

    def test_successful_llm_response(self, client, monkeypatch):
        import app as app_module
        monkeypatch.setattr(app_module, "CLOUD_LLM_API_KEY", "test-key")
        mock_resp = _mock_llm_response("There are many flights from Heathrow.")
        with patch("requests.post", return_value=mock_resp):
            r = client.post("/api/chat", json={"message": "flights from LHR"})
        assert r.status_code == 200
        assert "Heathrow" in r.get_json()["response"]

    def test_empty_llm_content_returns_fallback(self, client, monkeypatch):
        import app as app_module
        monkeypatch.setattr(app_module, "CLOUD_LLM_API_KEY", "test-key")
        mock_resp = _mock_llm_response("")
        with patch("requests.post", return_value=mock_resp):
            r = client.post("/api/chat", json={"message": "hello"})
        assert "empty" in r.get_json()["response"].lower()

    def test_timeout_returns_friendly_message(self, client, monkeypatch):
        import app as app_module
        monkeypatch.setattr(app_module, "CLOUD_LLM_API_KEY", "test-key")
        with patch("requests.post", side_effect=req_lib.exceptions.Timeout):
            r = client.post("/api/chat", json={"message": "hello"})
        assert "too long" in r.get_json()["response"].lower()

    def test_connection_error_returns_friendly_message(self, client, monkeypatch):
        import app as app_module
        monkeypatch.setattr(app_module, "CLOUD_LLM_API_KEY", "test-key")
        with patch("requests.post", side_effect=req_lib.exceptions.ConnectionError):
            r = client.post("/api/chat", json={"message": "hello"})
        assert "connect" in r.get_json()["response"].lower()

    def test_401_auth_error_message(self, client, monkeypatch):
        import app as app_module
        monkeypatch.setattr(app_module, "CLOUD_LLM_API_KEY", "bad-key")
        http_err = req_lib.exceptions.HTTPError("401 Unauthorized")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = http_err
        with patch("requests.post", return_value=mock_resp):
            r = client.post("/api/chat", json={"message": "hello"})
        assert "authentication" in r.get_json()["response"].lower()

    def test_429_rate_limit_message(self, client, monkeypatch):
        import app as app_module
        monkeypatch.setattr(app_module, "CLOUD_LLM_API_KEY", "test-key")
        http_err = req_lib.exceptions.HTTPError("429 Too Many Requests")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = http_err
        with patch("requests.post", return_value=mock_resp):
            r = client.post("/api/chat", json={"message": "hello"})
        assert "rate limit" in r.get_json()["response"].lower()

    def test_non_json_content_type_gracefully_handled(self, client, monkeypatch):
        """get_json(silent=True) returns None for any content type; handler falls back to empty message."""
        import app as app_module
        monkeypatch.setattr(app_module, "CLOUD_LLM_API_KEY", "test-key")
        r = client.post("/api/chat", data="not json", content_type="text/plain")
        assert r.status_code == 200
        assert "ask" in r.get_json()["response"].lower()
