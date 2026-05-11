"""airport-app — Flask routes for live airport / flight queries."""
from __future__ import annotations

import os
import json
import re
import requests
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for, jsonify

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

import airlabs  # noqa: E402  (import after dotenv so module reads env at call time)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only")

# Cloud LLM API Configuration
CLOUD_LLM_API_KEY = os.getenv("CLOUD_LLM_API_KEY")
CLOUD_LLM_URL = os.getenv("CLOUD_LLM_URL", "https://openrouter.ai/api/v1/chat/completions")
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "meta-llama/llama-3-8b-instruct:free")


def _err(message: str, status: int = 400):
    return render_template("error.html", message=message), status


@app.errorhandler(airlabs.AirLabsError)
def _handle_airlabs(e: airlabs.AirLabsError):
    return _err(f"AirLabs: {e}", status=502)


# ---------- pages ----------


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/healthz")
def healthz():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


@app.route("/search")
def search():
    """Universal search bar: figure out what they typed and route to the right page."""
    q = (request.args.get("q") or "").strip().upper()
    if not q:
        return redirect(url_for("home"))

    # Heuristic: airline/flight codes have digits, airports don't.
    has_digits = any(c.isdigit() for c in q)
    if has_digits:
        return redirect(url_for("flight_view", code=q))
    if len(q) == 3:
        return redirect(url_for("airport_view", code=q))
    if len(q) == 2:
        return redirect(url_for("airline_view", code=q))
    # 4 letters could be ICAO airport
    if len(q) == 4:
        return redirect(url_for("airport_view", code=q))
    return _err(f"Couldn't interpret '{q}'. Try an IATA airport code (3 letters), airline code (2 letters), or flight number (e.g. BA178).")


# ---------- flight ----------


@app.route("/flight")
def flight_view():
    code = (request.args.get("code") or "").strip().upper()
    if not code:
        return render_template("flight.html", flight=None, code=None)
    is_icao = len(code) >= 4 and not any(c.isdigit() for c in code[:3])
    if is_icao:
        f = airlabs.flight(flight_icao=code)
    else:
        f = airlabs.flight(flight_iata=code)
    return render_template("flight.html", flight=f, code=code)


# ---------- airport ----------


@app.route("/airport/<code>")
def airport_view(code: str):
    code = code.strip().upper()
    if len(code) == 4:
        info = airlabs.airport(icao=code)
    else:
        info = airlabs.airport(iata=code)
    if not info:
        return _err(f"No airport found for code '{code}'", status=404)

    iata = info.get("iata_code") or (code if len(code) == 3 else None)
    deps = airlabs.schedules(dep_iata=iata, limit=15) if iata else []
    arrs = airlabs.schedules(arr_iata=iata, limit=15) if iata else []
    delayed = airlabs.delays(dep_iata=iata, min_delay_min=30, limit=10) if iata else []

    return render_template(
        "airport.html",
        airport=info,
        iata=iata,
        departures=deps,
        arrivals=arrs,
        delays=delayed,
    )


# ---------- airline ----------


@app.route("/airline/<code>")
def airline_view(code: str):
    code = code.strip().upper()
    if len(code) == 3:
        info = airlabs.airline(icao=code)
    else:
        info = airlabs.airline(iata=code)
    if not info:
        return _err(f"No airline found for code '{code}'", status=404)
    iata = info.get("iata_code") or (code if len(code) == 2 else None)
    flights = airlabs.live_flights(airline_iata=iata, limit=20) if iata else []
    return render_template("airline.html", airline=info, iata=iata, flights=flights)


# ---------- schedules ----------


@app.route("/schedules")
def schedules_view():
    dep = (request.args.get("dep") or "").strip().upper() or None
    arr = (request.args.get("arr") or "").strip().upper() or None
    airline_code = (request.args.get("airline") or "").strip().upper() or None
    rows: list[dict] = []
    if dep or arr or airline_code:
        rows = airlabs.schedules(
            dep_iata=dep,
            arr_iata=arr,
            airline_iata=airline_code,
            limit=50,
        )
    return render_template(
        "schedules.html",
        rows=rows,
        dep=dep or "",
        arr=arr or "",
        airline=airline_code or "",
        searched=any([dep, arr, airline_code]),
    )


# ---------- routes ----------


@app.route("/routes")
def routes_view():
    dep = (request.args.get("dep") or "").strip().upper() or None
    arr = (request.args.get("arr") or "").strip().upper() or None
    airline_code = (request.args.get("airline") or "").strip().upper() or None
    rows: list[dict] = []
    if dep or arr or airline_code:
        rows = airlabs.routes(
            dep_iata=dep,
            arr_iata=arr,
            airline_iata=airline_code,
            limit=50,
        )
    return render_template(
        "routes.html",
        rows=rows,
        dep=dep or "",
        arr=arr or "",
        airline=airline_code or "",
        searched=any([dep, arr, airline_code]),
    )


# ---------- delays ----------


@app.route("/delays")
def delays_view():
    dep = (request.args.get("dep") or "").strip().upper() or None
    arr = (request.args.get("arr") or "").strip().upper() or None
    delay_min = request.args.get("min", "30")
    try:
        delay_min_int = int(delay_min)
    except ValueError:
        delay_min_int = 30
    type_ = request.args.get("type", "departures")
    if type_ not in ("departures", "arrivals"):
        type_ = "departures"

    rows: list[dict] = []
    if dep or arr:
        rows = airlabs.delays(
            dep_iata=dep,
            arr_iata=arr,
            min_delay_min=delay_min_int,
            type=type_,
            limit=50,
        )
    return render_template(
        "delays.html",
        rows=rows,
        dep=dep or "",
        arr=arr or "",
        min_delay=delay_min_int,
        type=type_,
        searched=bool(dep or arr),
    )


# ---------- nearby ----------


@app.route("/nearby")
def nearby_view():
    lat = request.args.get("lat")
    lng = request.args.get("lng")
    dist = request.args.get("distance", "100")
    result = None
    if lat and lng:
        try:
            result = airlabs.nearby(
                lat=float(lat),
                lng=float(lng),
                distance_km=int(dist) if dist.isdigit() else 100,
            )
        except (ValueError, TypeError):
            return _err("Invalid coordinates")
    return render_template(
        "nearby.html",
        result=result,
        lat=lat or "",
        lng=lng or "",
        distance=dist,
    )


# ---------- chatbot API ----------

_NOISE_WORDS = {
    'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HER', 'WAS',
    'ONE', 'OUR', 'OUT', 'DAY', 'GET', 'HAS', 'HIM', 'HIS', 'HOW', 'ITS', 'MAY',
    'NEW', 'NOW', 'OLD', 'SEE', 'TWO', 'WAY', 'WHO', 'BOY', 'DID', 'GOT', 'LET',
    'PUT', 'SAY', 'TOO', 'USE', 'FLY', 'ANY', 'BIG', 'FAR', 'OFF', 'OWN', 'SET',
    'TRY', 'WHY', 'ASK', 'RUN', 'AGO', 'VIA', 'ETA', 'ETD',
}


def _fetch_realtime_context(message: str) -> str:
    """Extract entities from the message, call AirLabs, and return context string."""
    try:
        msg_up = message.upper()
        msg_lo = message.lower()

        flight_codes = re.findall(r'\b([A-Z]{2}\d{1,4}[A-Z]?)\b', msg_up)
        airport_codes = [c for c in re.findall(r'\b([A-Z]{3})\b', msg_up) if c not in _NOISE_WORDS]

        is_delay    = any(w in msg_lo for w in ('delay', 'delayed', 'late'))
        is_schedule = any(w in msg_lo for w in ('flight', 'schedule', 'fly', 'depart', 'arrive', 'from', 'to', 'when'))
        is_route    = any(w in msg_lo for w in ('route', 'routes', 'airlines fly'))
        is_airport  = any(w in msg_lo for w in ('airport', 'terminal'))
        is_live     = any(w in msg_lo for w in ('status', 'where is', 'live', 'current', 'tracking', 'right now'))

        parts: list[str] = []

        if flight_codes:
            f = airlabs.flight(flight_iata=flight_codes[0])
            if f:
                parts.append(f"Live flight {flight_codes[0]}: {json.dumps(f)}")

        if is_delay and airport_codes:
            rows = airlabs.delays(dep_iata=airport_codes[0], limit=5)
            if rows:
                parts.append(f"Current delays at {airport_codes[0]}: {json.dumps(rows)}")

        if is_schedule and len(airport_codes) >= 2:
            rows = airlabs.schedules(dep_iata=airport_codes[0], arr_iata=airport_codes[1], limit=10)
            if rows:
                parts.append(f"Schedules {airport_codes[0]} to {airport_codes[1]}: {json.dumps(rows)}")
        elif is_schedule and len(airport_codes) == 1:
            rows = airlabs.schedules(dep_iata=airport_codes[0], limit=10)
            if rows:
                parts.append(f"Departures from {airport_codes[0]}: {json.dumps(rows)}")

        if is_route and len(airport_codes) >= 2:
            rows = airlabs.routes(dep_iata=airport_codes[0], arr_iata=airport_codes[1], limit=10)
            if rows:
                parts.append(f"Routes {airport_codes[0]} to {airport_codes[1]}: {json.dumps(rows)}")

        if is_airport and airport_codes and not parts:
            info = airlabs.airport(iata=airport_codes[0])
            if info:
                parts.append(f"Airport {airport_codes[0]}: {json.dumps(info)}")

        return "\n".join(parts)
    except Exception:
        return ""


_SYSTEM_PROMPT = """You are a helpful airport assistant. Answer questions about flights, airports, airlines, schedules, delays, and routes.

Rules:
- Reply in plain text only. No markdown, no tables, no bullet points, no bold, no headers.
- Be concise and direct.
- If real-time data is provided, use it to give accurate answers. Otherwise use general aviation knowledge.
- If you need a specific code or date from the user, ask in one short sentence.
"""


@app.route("/api/chat", methods=["POST"])
def chat_api():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return {"response": "Please ask a question about flights, airports, airlines, schedules, delays, or routes."}

    if not CLOUD_LLM_API_KEY:
        return {"response": "Cloud LLM API key is not configured. Please set CLOUD_LLM_API_KEY in your .env file."}

    realtime = _fetch_realtime_context(message)
    user_content = f"{message}\n\n[Real-time AirLabs data]\n{realtime}" if realtime else message

    try:
        response = requests.post(
            CLOUD_LLM_URL,
            headers={
                "Authorization": f"Bearer {CLOUD_LLM_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:5000",
                "X-Title": "Airport App Chatbot"
            },
            json={
                "model": CLOUD_MODEL,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()

        llm_response = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not llm_response:
            llm_response = "I received an empty response from the AI service. Please try rephrasing your question."

        return {"response": llm_response}

    except requests.exceptions.Timeout:
        return {"response": "The AI service took too long to respond. Please try again."}
    except requests.exceptions.ConnectionError:
        return {"response": "Unable to connect to the AI service. Please check your internet connection and API configuration."}
    except requests.exceptions.HTTPError as e:
        error_msg = str(e)
        if "401" in error_msg or "403" in error_msg:
            return {"response": "Authentication failed. Please check your API key configuration."}
        elif "429" in error_msg:
            return {"response": "Rate limit exceeded. Please wait a moment and try again."}
        else:
            return {"response": f"API error occurred: {error_msg}. Please check your configuration."}
    except Exception as e:
        app.logger.error(f"Cloud LLM error: {e}")
        return {"response": f"Sorry, I encountered an error processing your request. Details: {str(e)}"}


if __name__ == "__main__":
    app.run(debug=False, port=5000, threaded=True)
