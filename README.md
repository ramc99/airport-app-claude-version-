# Airport App with Chatbot

A Flask-based airport information application with an integrated AI chatbot for answering user queries about flights, airports, airlines, schedules, delays, and routes.

## Features

- **Flight Information**: Search and view flight details by flight number
- **Airport Information**: Get details about airports worldwide
- **Airline Information**: View airline details and statistics
- **Flight Schedules**: Browse scheduled flights
- **Delay Information**: Track flight delays
- **Route Information**: Find routes between airports
- **Nearby Airports**: Discover airports near a location
- **AI Chatbot**: Natural language interface powered by a cloud LLM (OpenRouter)

## Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- An API key from [AirLabs](https://airlabs.co/)
- An API key from [OpenRouter](https://openrouter.ai/) (or any OpenAI-compatible provider) for the chatbot

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/ramc99/airport-app.git
cd airport-app
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -e .
```

### 4. Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

```
AIRLABS_API_KEY=your_airlabs_key
AIRLABS_BASE_URL=https://airlabs.co/api/v9
FLASK_SECRET_KEY=change-me-in-prod

# Cloud LLM — defaults to a free OpenRouter model
CLOUD_LLM_API_KEY=your_openrouter_key
CLOUD_LLM_URL=https://openrouter.ai/api/v1/chat/completions
CLOUD_MODEL=meta-llama/llama-3-8b-instruct:free
```

`CLOUD_LLM_URL` and `CLOUD_MODEL` are optional — the defaults work with any free OpenRouter account. You can substitute any OpenAI-compatible provider by setting those two vars.

## Running the Application

```bash
python app.py
```

The app starts on `http://127.0.0.1:5000`.

## Using the Chatbot

The chatbot widget is available on every page (bottom-right corner). Ask anything in plain English:

**Flight status:** "What's the status of BA178?" · "Where is flight DL456?"  
**Airport info:** "Tell me about JFK" · "What's the code for Heathrow?"  
**Delays:** "Show me delays at JFK" · "Are there delays at ORD?"  
**Schedules:** "Flights from LHR to JFK" · "Flights leaving CDG tomorrow"  
**Routes:** "Which airlines fly LHR to JFK?" · "How do I get from Paris to New York?"

## Project Structure

```
airport-app/
├── app.py              # Flask routes + chatbot API endpoint
├── airlabs.py          # Typed HTTP client for AirLabs API
├── pyproject.toml      # Dependencies and project config
├── tests/
│   ├── conftest.py     # pytest fixtures
│   ├── test_airlabs.py # Unit tests for airlabs.py
│   └── test_routes.py  # Flask route tests
├── static/
│   └── style.css
├── templates/
│   ├── base.html       # Base template with chatbot UI
│   ├── index.html
│   ├── flight.html
│   ├── airport.html
│   ├── airline.html
│   ├── schedules.html
│   ├── delays.html
│   ├── routes.html
│   ├── nearby.html
│   └── error.html
└── .env.example
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

All tests mock external HTTP calls — no API keys required.

## API Reference

### `GET /healthz`

Returns `{"status": "ok", "ts": "<ISO-8601 UTC timestamp>"}`.

### `GET /search?q=<query>`

Universal search — routes to the right page based on the query format:

| Input | Result |
|---|---|
| 3 letters (e.g. `LHR`) | Airport page |
| 4 letters (e.g. `EGLL`) | Airport page (ICAO) |
| 2 letters (e.g. `BA`) | Airline page |
| Contains digits (e.g. `BA178`) | Flight page |

### `POST /api/chat`

**Content-Type:** `application/json`

```json
{ "message": "What's the status of BA178?" }
```

```json
{ "response": "Flight BA178 is currently en route from LHR to JFK." }
```

## Troubleshooting

**App won't start** — check Python ≥ 3.11 and that all deps installed: `pip install -e .`

**No flight/airport data** — verify `AIRLABS_API_KEY` in `.env`; free-tier accounts have rate limits.

**Chatbot returns "API key not configured"** — set `CLOUD_LLM_API_KEY` in `.env`.

**Chatbot returns auth error** — confirm the key is valid at [openrouter.ai/keys](https://openrouter.ai/keys).

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Commit your changes: `git commit -m 'Add new feature'`
4. Push and open a pull request

## License

MIT License — see the LICENSE file for details.

## Acknowledgments

- [AirLabs](https://airlabs.co/) for the flight data API
- [OpenRouter](https://openrouter.ai/) for LLM API access
- Flask framework community
