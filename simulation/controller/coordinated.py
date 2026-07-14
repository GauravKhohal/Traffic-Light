"""Coordinated adaptive control (Phase 4).

Extends the Phase 3 single-intersection controller with inter-signal
coordination over a message bus. Each cycle a signal:

  1. measures its outflow toward each neighbour (vehicles/min entering the
     outgoing edge to that neighbour),
  2. publishes {id, queues, phase, outflow} every `publish_period` seconds,
  3. reads its upstream neighbours' latest outflow to predict `incoming_i`
     per approach, and folds it into the demand term
     `demand_i = q_i + alpha * incoming_i`.

Because a heavy upstream platoon raises `incoming_i` on the corridor
approach, that approach's demand-proportional green grows *before* the queue
forms — the spec's "pre-extend green on the corridor route" green wave,
emergent from the same allocation formula. When coordination is disabled the
controller is behaviourally identical to Phase 3 (predictor returns zero), so
the two modes form a clean A/B for measuring coordination's effect.

Transport-agnostic: works over `InProcessBus` (deterministic metric runs) or
`MqttBus` (real edge deployment) without changes here.
"""
from collections import deque

from simulation.controller.adaptive import AdaptiveIntersectionController
from simulation.coordination.predictor import predict_incoming
from simulation.coordination.transport import build_state_message

PREDICTION_HORIZON_S = 60.0  # predict arrivals over the next minute
OUTFLOW_WINDOW_S = 60         # rolling window for outflow rate (=> veh/min)


class CoordinatedIntersectionController(AdaptiveIntersectionController):
    def __init__(
        self,
        conn,
        tls_id,
        topology,
        bus,
        coordinate=True,
        publish_period=5.0,
        horizon_s=PREDICTION_HORIZON_S,
    ):
        super().__init__(conn, tls_id)  # builds route_lanes / green_phase / state machine
        self.topo = topology
        self.bus = bus
        self.coordinate = coordinate
        self.publish_period = publish_period
        self.horizon_s = horizon_s

        # route index -> upstream signal id feeding it (None if fed by a fringe)
        self.route_upstream = []
        for lanes in self.route_lanes:
            edge = lanes[0].rsplit("_", 1)[0]
            frm = self.topo.edge_from.get(edge)
            self.route_upstream.append(frm if frm in self.topo.signal_neighbours else None)

        # outgoing edges toward signal neighbours, for outflow measurement
        self.out_edge_to = {
            nb: edge
            for nb, edge in self.topo.out_edge_to.items()
            if nb in self.topo.signal_neighbours
        }
        self._out_prev = {edge: set() for edge in self.out_edge_to.values()}
        self._out_window = {edge: deque() for edge in self.out_edge_to.values()}
        self._last_publish = None

    # -- outflow measurement ------------------------------------------------
    def _measure_outflow(self):
        for edge in self.out_edge_to.values():
            current = set(self.conn.edge.getLastStepVehicleIDs(edge))
            entered = len(current - self._out_prev[edge])
            self._out_prev[edge] = current
            window = self._out_window[edge]
            window.append(entered)
            if len(window) > OUTFLOW_WINDOW_S:
                window.popleft()

    def _outflow_rates(self):
        """veh/min toward each signal neighbour (rate-corrected during the
        first minute before the window fills)."""
        rates = {}
        for nb, edge in self.out_edge_to.items():
            window = self._out_window[edge]
            if window:
                rates[nb] = sum(window) * 60.0 / len(window)
            else:
                rates[nb] = 0.0
        return rates

    # -- publishing ---------------------------------------------------------
    def _maybe_publish(self, now):
        if self._last_publish is not None and now - self._last_publish < self.publish_period:
            return
        self._last_publish = now
        try:
            queues = self.read_queues()
        except Exception:
            queues = [0] * self.n
        phase = self.route if self.state == "green" else -1
        msg = build_state_message(self.tls, now, queues, phase, self._outflow_rates())
        self.bus.publish(self.tls, msg)

    # -- coordination hook (called by base _plan_cycle) ---------------------
    def _compute_incoming(self):
        if not self.coordinate:
            return None
        messages = {
            up: self.bus.latest(up) for up in set(self.route_upstream) if up is not None
        }
        return predict_incoming(self.tls, self.route_upstream, messages, self.horizon_s)

    # -- per-step -----------------------------------------------------------
    def step(self, now):
        self._measure_outflow()
        self._maybe_publish(now)
        super().step(now)
