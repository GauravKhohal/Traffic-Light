# Phase 6 — Dashboard, Backend & Deployment

A live web dashboard for the 3×3 signal grid: a schematic map coloured by
congestion, per-signal cards showing current phase + countdown and per-approach
queue lengths, a historical network-wait chart, and a manual override button
per approach on every signal. A FastAPI backend aggregates live state and
streams it to the React front-end over a WebSocket.

```
┌────────────┐   MQTT    ┌─────────────┐   WebSocket   ┌──────────────┐
│ SUMO sim / │  signals/ │  FastAPI    │  /ws, /api    │  React +     │
│ edge nodes │ ─{id}/state─▶ backend    │ ─────────────▶│  Recharts UI │
│ (Phase 4)  │           │ StateStore  │  overrides ◀──│  (Vite)      │
└────────────┘           └─────────────┘               └──────────────┘
        (or the backend's built-in synthetic demo feed)
```

## Quick start (Docker, one command)

```
cd dashboard
docker compose up --build
# open http://localhost:8000
```

This runs the backend with the **demo feed** (synthetic but plausible signal
dynamics for all 9 intersections) plus a Mosquitto broker — no simulation
required. The dashboard is live immediately, overrides work, and the wait
chart fills in.

### Live from the actual simulation

```
DASHBOARD_FEED=mqtt docker compose up --build
# from the repo root, feed real signal state into the broker:
python simulation/scripts/run_coordinated.py --transport mqtt
```

The coordinated controllers publish `signals/{id}/state` (Phase 4); the
backend's `MqttFeed` subscribes and the dashboard shows the real run.

## Run without Docker (development)

Backend (serves API + WebSocket; also serves the built UI if `frontend/dist`
exists):

```
.venv\Scripts\pip install -r dashboard\backend\requirements.txt
.venv\Scripts\python -m uvicorn app:app --app-dir dashboard\backend --port 8000
```

Front-end dev server with hot reload (proxies /api and /ws to :8000):

```
cd dashboard\frontend
npm install
npm run dev        # http://localhost:5173
```

Production build (the backend then serves it at /):

```
cd dashboard\frontend && npm run build
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/state` | latest state of all signals + wait history |
| GET | `/api/signals` | signals + approach labels |
| GET | `/api/history` | network wait / total-queue time series |
| POST | `/api/signals/{id}/override` | body `{"approach":"N"}` to force, `{"approach":null}` to release |
| WS | `/ws` | pushes the full snapshot ~2×/second |

Manual overrides are the spec's per-signal override control: the backend holds
the forced approach and the (demo) controller switches to it, releasing on
`Auto`. Against the live simulation this is where an override command would be
published back to the edge controller.

## Tests

```
.venv\Scripts\python -m pytest dashboard\backend\test_app.py -q
```

Covers the state store, demo feed (all 9 signals, override takes effect), the
REST endpoints (including 400/404 paths), and the WebSocket stream.

## Production stores (swap-ins)

Live state is kept in-memory in `backend/state_store.py` so the demo needs no
external services. The spec's production stores slot in behind that one class
without touching the API or UI: **Redis** for the hot per-intersection state
(`update_signal`/`snapshot`) and **PostgreSQL + TimescaleDB** for the
historical series (`record_metrics`/`history`).

## Edge deployment (per-intersection node)

Each intersection is designed to run standalone on edge hardware (Raspberry Pi
/ Jetson), which is what the earlier phases build toward:

- **Detection** ([../detection](../detection)) — YOLOv8 counts vehicles per
  approach from the camera and estimates queue length.
- **Control** ([../simulation/controller](../simulation/controller)) — the
  rule-based adaptive controller runs locally; it publishes state and reads
  neighbours over MQTT for the green wave (Phase 4).
- **Resilience** — if detection fails the controller falls back to fixed
  timing (Phase 3, verified); if the network drops it keeps running on local
  detection alone. The dashboard/coordinator are advisory — local safety
  timing (yellow/all-red, min/max green) always wins.

A single edge node therefore runs `detection` + one `CoordinatedIntersection\
Controller` against its local camera and signal hardware, pointed at a broker
reachable by its neighbours. The same MQTT messages this dashboard visualises
are what the nodes exchange in the field.
