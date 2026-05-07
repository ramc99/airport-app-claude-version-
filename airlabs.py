"""Typed HTTP client for AirLabs.

Errors raise `AirLabsError` so route handlers can render error pages.
Success returns parsed list/dict data — the `{request, response}` envelope
is unwrapped here so the caller works with payloads directly.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

_TIMEOUT_S = 8.0


class AirLabsError(Exception):
    """Raised when AirLabs returns an error or the network call fails."""


def _client() -> httpx.Client:
    return httpx.Client(timeout=_TIMEOUT_S)


def _api_key() -> str:
    key = os.getenv("AIRLABS_API_KEY")
    if not key:
        raise AirLabsError("AIRLABS_API_KEY is not set")
    return key


def _base_url() -> str:
    return os.getenv("AIRLABS_BASE_URL", "https://airlabs.co/api/v9").rstrip("/")


def _call(path: str, params: dict[str, Any]) -> Any:
    clean = {k: v for k, v in params.items() if v is not None and v != ""}
    clean["api_key"] = _api_key()
    try:
        with _client() as c:
            r = c.get(f"{_base_url()}/{path}", params=clean)
    except httpx.RequestError as e:
        raise AirLabsError(f"network error: {e}") from e
    if r.status_code >= 500:
        raise AirLabsError(f"AirLabs server error ({r.status_code})")
    try:
        body = r.json()
    except ValueError as e:
        raise AirLabsError(f"non-JSON response from AirLabs: {r.text[:200]}") from e
    if "error" in body:
        err = body["error"]
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        raise AirLabsError(msg)
    return body.get("response", body)


# ---------- public functions used by Flask routes ----------


def airport(*, iata: str | None = None, icao: str | None = None) -> dict | None:
    """Look up one airport by IATA or ICAO code. Returns the dict or None."""
    if not iata and not icao:
        raise AirLabsError("provide iata or icao code")
    data = _call("airports", {"iata_code": iata, "icao_code": icao})
    if isinstance(data, list):
        return data[0] if data else None
    return data or None


def airline(*, iata: str | None = None, icao: str | None = None) -> dict | None:
    if not iata and not icao:
        raise AirLabsError("provide iata or icao code")
    data = _call("airlines", {"iata_code": iata, "icao_code": icao})
    if isinstance(data, list):
        return data[0] if data else None
    return data or None


def flight(*, flight_iata: str | None = None, flight_icao: str | None = None) -> dict | None:
    """Live status for one flight."""
    if not flight_iata and not flight_icao:
        raise AirLabsError("provide flight code")
    data = _call("flight", {"flight_iata": flight_iata, "flight_icao": flight_icao})
    if isinstance(data, list):
        return data[0] if data else None
    return data or None


def live_flights(
    *,
    dep_iata: str | None = None,
    arr_iata: str | None = None,
    airline_iata: str | None = None,
    flight_iata: str | None = None,
    limit: int = 50,
) -> list[dict]:
    if not any([dep_iata, arr_iata, airline_iata, flight_iata]):
        raise AirLabsError("provide at least one filter")
    data = _call(
        "flights",
        {
            "dep_iata": dep_iata,
            "arr_iata": arr_iata,
            "airline_iata": airline_iata,
            "flight_iata": flight_iata,
        },
    )
    if not isinstance(data, list):
        return []
    return data[:limit]


def schedules(
    *,
    dep_iata: str | None = None,
    arr_iata: str | None = None,
    airline_iata: str | None = None,
    flight_iata: str | None = None,
    limit: int = 50,
) -> list[dict]:
    if not any([dep_iata, arr_iata, airline_iata, flight_iata]):
        raise AirLabsError("provide at least one filter")
    data = _call(
        "schedules",
        {
            "dep_iata": dep_iata,
            "arr_iata": arr_iata,
            "airline_iata": airline_iata,
            "flight_iata": flight_iata,
        },
    )
    if not isinstance(data, list):
        return []
    return data[:limit]


def routes(
    *,
    dep_iata: str | None = None,
    arr_iata: str | None = None,
    airline_iata: str | None = None,
    flight_number: str | None = None,
    limit: int = 50,
) -> list[dict]:
    if not any([dep_iata, arr_iata, airline_iata, flight_number]):
        raise AirLabsError("provide at least one filter")
    data = _call(
        "routes",
        {
            "dep_iata": dep_iata,
            "arr_iata": arr_iata,
            "airline_iata": airline_iata,
            "flight_number": flight_number,
        },
    )
    if not isinstance(data, list):
        return []
    return data[:limit]


def delays(
    *,
    dep_iata: str | None = None,
    arr_iata: str | None = None,
    airline_iata: str | None = None,
    min_delay_min: int = 30,
    type: str = "departures",
    limit: int = 50,
) -> list[dict]:
    if type not in ("departures", "arrivals"):
        raise AirLabsError('type must be "departures" or "arrivals"')
    data = _call(
        "delays",
        {
            "dep_iata": dep_iata,
            "arr_iata": arr_iata,
            "airline_iata": airline_iata,
            "delay": min_delay_min,
            "type": type,
        },
    )
    if not isinstance(data, list):
        return []
    return data[:limit]


def nearby(*, lat: float, lng: float, distance_km: int = 100) -> dict:
    """Returns {airports: [...], flights: [...]}."""
    distance_km = max(1, min(distance_km, 500))
    data = _call("nearby", {"lat": lat, "lng": lng, "distance": distance_km})
    if isinstance(data, dict):
        return {
            "airports": data.get("airports", []),
            "flights": data.get("flights", []),
        }
    return {"airports": [], "flights": []}
