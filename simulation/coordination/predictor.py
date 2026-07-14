"""Incoming-traffic prediction from neighbours' published outflow (Phase 4).

The spec's demand term is `demand_i = q_i + alpha * incoming_i`, where
`incoming_i` is the number of vehicles predicted to arrive on approach i
from upstream signals within the planning horizon.

Each neighbour publishes its outflow toward each adjacent junction in
vehicles/minute (measured on the outgoing edge to that junction). For our
approach i fed by upstream signal U, the relevant rate is U's outflow toward
*us*; over a horizon of H seconds that predicts `rate * H/60` arrivals.

Travel time (edge length / free-flow speed, ~13s on this grid) is far
shorter than a signal cycle (90-180s), so a neighbour's current outflow is a
valid predictor of near-future arrivals on our approach; the pure count is
what the allocation formula needs. Travel time matters for *timing* a green
wave (serving the corridor route as the platoon lands), handled by the
controller's route ordering, not here.

Pure and SUMO-free so it can be unit-tested directly.
"""


def predict_incoming(signal_id, route_upstream, messages, horizon_s):
    """Predicted arrivals per route over the next `horizon_s` seconds.

    - signal_id: id of the signal doing the prediction (to look up neighbours'
      outflow *toward us*).
    - route_upstream: list, one entry per route, giving the upstream signal id
      feeding that route, or None if it is fed from a network fringe.
    - messages: {neighbour_id: latest state message dict or None}.
    Returns a list of non-negative floats, one per route.
    """
    horizon_min = horizon_s / 60.0
    incoming = []
    for upstream in route_upstream:
        rate = 0.0
        if upstream is not None:
            msg = messages.get(upstream)
            if msg:
                rate = float(msg.get("outflow", {}).get(signal_id, 0.0))
        incoming.append(max(0.0, rate) * horizon_min)
    return incoming
