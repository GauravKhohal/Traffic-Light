"""FastAPI backend for the traffic-signal dashboard (Phase 6).

Aggregates live per-intersection state from a feed (synthetic demo, or the
Phase 4 MQTT stream) into an in-memory StateStore, and exposes it to the
React dashboard over REST + a WebSocket, plus a manual per-signal override.

Run:
    DASHBOARD_FEED=demo uvicorn app:app --app-dir dashboard/backend --port 8000
    # live from the simulation instead:
    #   terminal A: python simulation/scripts/run_coordinated.py --transport mqtt
    #   terminal B: DASHBOARD_FEED=mqtt MQTT_HOST=localhost uvicorn app:app ...
"""
import asyncio
import contextlib
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from feeds import DemoFeed, MqttFeed
from state_store import APPROACH_LABELS, StateStore

HERE = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIST = os.path.join(HERE, "..", "frontend", "dist")

store = StateStore()
feed = None


def _make_feed():
    kind = os.environ.get("DASHBOARD_FEED", "demo").lower()
    if kind == "mqtt":
        host = os.environ.get("MQTT_HOST", "localhost")
        port = int(os.environ.get("MQTT_PORT", "1883"))
        return MqttFeed(store, host=host, port=port)
    return DemoFeed(store)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    global feed
    feed = _make_feed()
    task = asyncio.create_task(feed.run())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        if hasattr(feed, "stop"):
            feed.stop()


app = FastAPI(title="Traffic Signal Dashboard", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class OverrideRequest(BaseModel):
    approach: str | None = None  # an APPROACH_LABEL to force, or null to clear


class ModeRequest(BaseModel):
    mode: str  # "fixed" (plain round-robin) or "ai" (adaptive)


class RunningRequest(BaseModel):
    running: bool  # False freezes the demo feed mid-tick; True resumes it


@app.get("/api/state")
def get_state():
    return store.snapshot()


@app.post("/api/mode")
def set_mode(req: ModeRequest):
    if not store.set_mode(req.mode):
        return JSONResponse(
            status_code=400, content={"error": 'mode must be "fixed" or "ai"'}
        )
    return {"mode": req.mode}


@app.post("/api/demo")
def set_running(req: RunningRequest):
    store.set_running(req.running)
    return {"running": req.running}


@app.get("/api/signals")
def get_signals():
    return {"signals": store.signals(), "approaches": APPROACH_LABELS}


@app.get("/api/history")
def get_history():
    return {"history": store.history()}


@app.post("/api/signals/{signal_id}/override")
def set_override(signal_id: str, req: OverrideRequest):
    if req.approach is not None and req.approach not in APPROACH_LABELS:
        return JSONResponse(
            status_code=400,
            content={"error": f"approach must be one of {APPROACH_LABELS} or null"},
        )
    ok = store.set_override(signal_id, req.approach)
    if not ok:
        return JSONResponse(status_code=404, content={"error": f"unknown signal {signal_id}"})
    return {"id": signal_id, "override": req.approach}


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(store.snapshot())
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass


# Serve the built React app at / (registered last so /api and /ws win).
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
