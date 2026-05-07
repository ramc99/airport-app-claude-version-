# airport-app

A Flask web app for live airport, flight, schedule, and delay queries
backed by the AirLabs API.

## Stack

- Python 3.11+, Flask 3.x (sync; this is a normal CRUD-style frontend over
  a REST API — sync simplicity wins per engineering standards)
- httpx client for AirLabs
- Server-rendered Jinja2 templates
- Tailwind via CDN, low-saturation calm aesthetic

## Layout

```
airport-app/
├── app.py              # Flask routes + bootstrap
├── airlabs.py          # AirLabs HTTP client (typed wrappers)
├── templates/
│   ├── base.html       # Shared layout, nav, global search
│   ├── index.html      # Home / dashboard
│   ├── flight.html     # Flight status detail
│   ├── airport.html    # Airport detail (info + departures + arrivals + delays)
│   ├── airline.html    # Airline detail
│   ├── schedules.html  # Schedules search
│   ├── routes.html     # Route lookup
│   ├── delays.html     # Delays at an airport
│   ├── nearby.html     # Nearby airports / flights
│   ├── search.html     # Global search results
│   └── error.html      # Error display
├── static/
│   └── style.css       # Small overrides on top of Tailwind
├── pyproject.toml
├── .env.example
└── AGENTS.md           # this file
```

## Routes

| URL                        | Purpose                                   |
|----------------------------|-------------------------------------------|
| `GET /`                    | Home with quick links and global search   |
| `GET /search?q=...`        | Resolve query → redirect to detail page   |
| `GET /flight?code=BA178`   | Flight status                             |
| `GET /airport/<code>`      | Airport detail (deps, arrs, delays)       |
| `GET /airline/<code>`      | Airline detail                            |
| `GET /schedules`           | Schedules search form + results           |
| `GET /routes`              | Routes between two airports               |
| `GET /delays`              | Currently delayed flights at an airport   |
| `GET /nearby`              | Airports / flights near coordinates       |
| `GET /healthz`             | Health check                              |

## Configuration

`.env` (mode 600, never committed):

```
AIRLABS_API_KEY=...
AIRLABS_BASE_URL=https://airlabs.co/api/v9
FLASK_SECRET_KEY=...
```

## Running

```bash
source /home/ramchand/Dev2prod/weather-app/.venv/bin/activate
cd /home/ramchand/Dev2prod/airport-app
flask --app app run --debug
```
