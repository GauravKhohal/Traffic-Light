"""Static grid topology for inter-signal coordination (Phase 4).

Read once from the SUMO net (no TraCI). For each signalized junction it
records, per connecting edge, which neighbour junction is on the other end
and the free-flow travel time along it — enough for a signal to know which
upstream neighbour feeds each of its approaches and which outgoing edge
carries its outflow toward each neighbour.
"""
import os
from dataclasses import dataclass, field


@dataclass
class SignalTopology:
    signal_id: str
    # incoming edge id -> (upstream junction id, free-flow travel time seconds)
    edge_from: dict = field(default_factory=dict)
    edge_travel_time: dict = field(default_factory=dict)
    # neighbour junction id -> outgoing edge id carrying our outflow to it
    out_edge_to: dict = field(default_factory=dict)
    # neighbour junctions that are themselves signals (coordination peers)
    signal_neighbours: set = field(default_factory=set)


def build_topology(net_path: str):
    """Return {signal_id: SignalTopology} for every traffic-light junction."""
    import sumolib

    net = sumolib.net.readNet(net_path)
    signal_ids = {t.getID() for t in net.getTrafficLights()}

    topo = {}
    for sid in signal_ids:
        node = net.getNode(sid)
        st = SignalTopology(signal_id=sid)
        for e in node.getIncoming():
            frm = e.getFromNode().getID()
            st.edge_from[e.getID()] = frm
            st.edge_travel_time[e.getID()] = e.getLength() / e.getSpeed()
            if frm in signal_ids:
                st.signal_neighbours.add(frm)
        for e in node.getOutgoing():
            st.out_edge_to[e.getToNode().getID()] = e.getID()
        topo[sid] = st
    return topo


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    net = os.path.join(here, "..", "network", "grid3x3.net.xml")
    topo = build_topology(net)
    for sid in sorted(topo):
        st = topo[sid]
        peers = sorted(st.signal_neighbours)
        print(f"{sid}: signal-neighbours {peers}")
        for edge, frm in sorted(st.edge_from.items()):
            tt = st.edge_travel_time[edge]
            print(f"    in  {edge:10s} <- {frm:6s} tt={tt:5.1f}s")
        for nb, edge in sorted(st.out_edge_to.items()):
            print(f"    out {edge:10s} -> {nb}")
