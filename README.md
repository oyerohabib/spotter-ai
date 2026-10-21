# Spotter — Weather-Aware Truck Routing

React + Django app that helps a truck driver choose the safest route using weather risk, load weight, and travel time.

## Features

- Enter origin, destination, departure time, and load weight
- Generate up to **3 route alternatives** (Mapbox Directions)
- Sample weather every **10 / 25 / 50 miles** at ETA for each checkpoint (Open-Meteo)
- Classify risk with wind / rain / snow thresholds and load overrides
- Recommend the best route (fewest severe miles → high miles → avg risk → shortest time)
- Map view with routes, risk-colored checkpoints, corridor **heatmap**, and **0–48h** forecast slider

## Stack

| Layer | Tech |
| --- | --- |
| Frontend | Vite, React, TypeScript, Tailwind, shadcn-style UI |
| Backend | Django, Django REST Framework |
| Routing / map | Mapbox Geocoding, Directions, Mapbox GL JS |
| Weather | Open-Meteo (no API key) |
| Hosting | Railway (Django + built SPA via WhiteNoise) |

## Quick start (local)

### 1. API keys

1. Create a free token at [mapbox.com](https://account.mapbox.com/access-tokens/)
2. Copy `.env.example` → `.env` at the repo root:

```bash
cp .env.example .env
```

Fill in the **repo-root** `.env` (Vite is configured to read from there):

```env
MAPBOX_ACCESS_TOKEN=pk....
VITE_MAPBOX_ACCESS_TOKEN=pk....
SECRET_KEY=any-dev-secret
DEBUG=True
```

Use the same public Mapbox token for both values in demos. Restart the Vite dev server after changing env vars.

### 2. Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
python manage.py migrate
python manage.py runserver
```

API health check: `http://127.0.0.1:8000/api/health/`

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` — Vite proxies `/api` to Django.

### 4. Tests

```bash
source .venv/bin/activate
cd backend
python manage.py test routing
```

## API

`POST /api/routes/analyze/`

```json
{
  "origin": "Chicago, IL",
  "destination": "Detroit, MI",
  "departure_at": "2026-06-01T12:00:00Z",
  "load_weight_lb": 35000,
  "sample_interval_miles": 25
}
```

Returns geocoded places, up to three scored routes (geometry, checkpoints, risk summaries), recommendation, and heatmap hourly samples for the slider.

## Risk rules

| Condition | Low | Moderate | High | Severe | No Travel |
| --- | --- | --- | --- | --- | --- |
| Wind (mph) | &lt;25 | 25–34 | 35–44 | 45–54 | ≥55 |
| Rain (in/hr) | &lt;0.10 | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | &gt;1.00 |
| Snow (in/hr) | &lt;0.5 | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | &gt;3.0 |

Load overrides:

- ≥55 mph → **No Travel** (any load)
- 45–54 mph + load &gt; 30,000 lb → **No Travel**
- 35–44 mph + load &gt; 40,000 lb → **Severe**

## Deploy on Railway

1. Push this repo to GitHub and create a Railway project from it
2. Set environment variables:

| Variable | Notes |
| --- | --- |
| `SECRET_KEY` | Strong random string |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | your Railway domain, e.g. `your-app.up.railway.app` |
| `CSRF_TRUSTED_ORIGINS` | `https://your-app.up.railway.app` |
| `MAPBOX_ACCESS_TOKEN` | Mapbox token |
| `VITE_MAPBOX_ACCESS_TOKEN` | Same token (baked into the frontend at build time) |

3. Railway uses `nixpacks.toml` to install Python + Node, build the Vite app, collect static files, and start Gunicorn
4. Confirm `https://<your-app>/api/health/` then open the root URL for the SPA

**Important:** Redeploy after changing `VITE_MAPBOX_ACCESS_TOKEN` so the frontend rebuild picks it up.

## Loom walkthrough checklist (5–10 min)

1. Show trip form defaults (Chicago → Detroit) and load weight
2. Run **Analyze routes** and wait for results
3. Point out recommended route badge and severe/high mile stats
4. Hover checkpoints on the map (ETA + wind/rain/snow + risk)
5. Scrub the **0–48h** forecast slider and show heatmap updates (no refetch)
6. Change sample interval / load weight and re-run to show recommendation shift
7. Briefly open the risk rules section in this README

## Project layout

```
backend/          Django project + routing app (risk, clients, analyze API)
frontend/         Vite React UI (form, map, heatmap slider)
.env.example      Required environment variables
nixpacks.toml     Railway build/start
Procfile          Alternate process definition
```

## Notes

- Open-Meteo is used for weather and requires no key
- Correctness of risk scoring and recommendation ranking is covered by unit tests under `backend/routing/tests/`
- Prioritize clarity over extras — no auth or trip persistence by design
