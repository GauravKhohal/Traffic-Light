"""In-memory store of live intersection state + a rolling wait-time history
for the dashboard (Phase 6).

This is the single place the rest of the backend reads/writes signal state,
so swapping it for the production stores the spec calls for — Redis for the
hot per-intersection state, PostgreSQL/TimescaleDB for the historical series —
means reimplementing just this class, not the API. Kept in-memory here so the
dashboard runs with no external services.
"""
import threading
import time
from collections import deque

# nominal approach labels, in each signal's phase order (see feeds for mapping)
APPROACH_LABELS = ["N", "E", "S", "W"]


def grid_position(signal_id: str):
    """(x, y) on the 3x3 grid from an id like 'B1' (column A/B/C, row 0-2)."""
    col = {"A": 0, "B": 1, "C": 2}.get(signal_id[0], 0)
    row = int(signal_id[1]) if signal_id[1:].isdigit() else 0
    return col, row


class StateStore:
    def __init__(self, history_seconds=900):
        self._lock = threading.Lock()
        self._signals = {}                      # id -> latest state dict
        self._overrides = {}                    # id -> forced approach label
        self._history = deque(maxlen=history_seconds)  # {t, avg_wait, total_queue}
        # "fixed" = plain round-robin, fixed 30s each, no reaction to demand
        # (what every uncontrolled intersection does today); "ai" = the
        # demand-proportional adaptive controller. Only DemoFeed reads this -
        # it's for showing a client the before/after live, not for the SUMO
        # research runs, which pick their controller by which script is run.
        self._mode = "fixed"
        self._served_since_mode_change = 0

    # -- signal state -------------------------------------------------------
    def update_signal(self, state: dict):
        """Upsert one signal's latest state. `state` must include 'id'."""
        sid = state["id"]
        with self._lock:
            state = dict(state)
            state["x"], state["y"] = grid_position(sid)
            state["override"] = self._overrides.get(sid)
            state["updated"] = time.time()
            self._signals[sid] = state

    def record_metrics(self, avg_wait: float, total_queue: float, t=None):
        with self._lock:
            self._history.append(
                {
                    "t": t if t is not None else time.time(),
                    "avg_wait": round(float(avg_wait), 2),
                    "total_queue": round(float(total_queue), 1),
                }
            )

    # -- overrides ----------------------------------------------------------
    def set_override(self, signal_id: str, approach):
        """Force a signal to an approach (label) or clear it (approach=None).
        Returns False if the signal is unknown."""
        with self._lock:
            if signal_id not in self._signals:
                return False
            if approach is None:
                self._overrides.pop(signal_id, None)
            else:
                self._overrides[signal_id] = approach
            if signal_id in self._signals:
                self._signals[signal_id]["override"] = self._overrides.get(signal_id)
            return True

    def get_override(self, signal_id: str):
        with self._lock:
            return self._overrides.get(signal_id)

    # -- control mode (demo feed only) ---------------------------------------
    def get_mode(self):
        with self._lock:
            return self._mode

    def set_mode(self, mode: str):
        if mode not in ("fixed", "ai"):
            return False
        with self._lock:
            self._mode = mode
            self._served_since_mode_change = 0  # fair throughput comparison per mode
        return True

    def record_served(self, n: int = 1):
        with self._lock:
            self._served_since_mode_change += n

    # -- snapshots ----------------------------------------------------------
    def snapshot(self):
        with self._lock:
            return {
                "signals": sorted(
                    (dict(s) for s in self._signals.values()), key=lambda s: s["id"]
                ),
                "history": list(self._history),
                "mode": self._mode,
                "served_since_mode_change": self._served_since_mode_change,
            }

    def signals(self):
        with self._lock:
            return sorted((dict(s) for s in self._signals.values()), key=lambda s: s["id"])

    def history(self):
        with self._lock:
            return list(self._history)
