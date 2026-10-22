# Spotter — Weather-Aware Truck Routing

React + Django app that helps a truck driver choose the safest route using weather risk, load weight, and travel time.

## Features

- Enter origin, destination, departure time, and load weight
- Generate up to **3 route options** (Mapbox Directions, with exclude/via fill-in when needed)
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
2. Copy env templates:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

Fill in the **repo-root** `.env` for Django:

```env
MAPBOX_ACCESS_TOKEN=pk....
SECRET_KEY=any-dev-secret
DEBUG=True
```

Fill in **`frontend/.env`** for Vite (Mapbox GL JS):

```env
VITE_MAPBOX_ACCESS_TOKEN=pk....
```

Use the same public Mapbox token for both values in demos. Restart the Vite dev server after changing `frontend/.env`.

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

## Deploy on Render (recommended if Railway is unavailable)

Create a **Web Service** from this GitHub repo. Leave **Root Directory** empty. Do **not** use Render’s default Python commands.

| Field | Value |
| --- | --- |
| Language | Python 3 |
| Branch | `main` |
| Root Directory | *(leave blank)* |
| Build Command | `bash bin/render-build.sh` |
| Start Command | `cd backend && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT` |

Environment variables (add before first deploy):

| Variable | Value |
| --- | --- |
| `SECRET_KEY` | strong random string |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `.onrender.com` (or your exact hostname, e.g. `spotter-ai.onrender.com`) |
| `CSRF_TRUSTED_ORIGINS` | `https://spotter-ai.onrender.com` (your real URL) |
| `MAPBOX_ACCESS_TOKEN` | Mapbox token |
| `VITE_MAPBOX_ACCESS_TOKEN` | same token — **required at build time** for the map |

After deploy:

1. Open `https://<your-service>.onrender.com/api/health/` — should return `{"status":"ok"}`
2. Open the root URL, select places, analyze

**Notes**

- Free Render instances sleep when idle; the first request after sleep can take ~30–60s
- Changing `VITE_MAPBOX_ACCESS_TOKEN` requires a **redeploy** (rebuild) so Vite can bake it in
- `RENDER_EXTERNAL_HOSTNAME` / `RENDER_EXTERNAL_URL` are set by Render automatically and are honored in Django settings

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
backend/                Django project + routing app (risk, clients, analyze API)
frontend/               Vite React UI (form, map, heatmap slider)
frontend/.env.example   Vite env template (VITE_MAPBOX_ACCESS_TOKEN)
.env.example            Django / server env template
nixpacks.toml           Railway build/start
bin/render-build.sh     Render build (Python + Node)
Procfile                Alternate process definition
```

## Notes

- Open-Meteo is used for weather and requires no key
- Correctness of risk scoring and recommendation ranking is covered by unit tests under `backend/routing/tests/`
- Prioritize clarity over extras — no auth or trip persistence by design
