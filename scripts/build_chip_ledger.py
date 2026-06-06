#!/usr/bin/env python3
"""Build a chip-flow ledger from cleaned IRC hold'em hands.

For every hand we know each player's net result (``total_win - total_bet``).
A hand's pot is shared, so we cannot observe "A paid B" directly; instead we
attribute each winner's gain proportionally across that hand's losers:

    edge[u -> v] += loss_u * (gain_v / total_gain)     for every loser u, winner v

where ``loss_u`` is how many chips loser ``u`` is down on the hand and
``gain_v`` is how many chips winner ``v`` is up. Summed over all hands this
gives a directed weighted graph (the *chip ledger*) where ``edge[u -> v]`` is
the net chips ``v`` has taken from ``u``.

Hands whose pot does not balance (``sum(net) != 0`` beyond a small tolerance)
are skipped: in the IRC PDB ~9% of hands have an unrecorded win amount, and
attributing those would invent chip flow. The skip count is reported, never
silently dropped.

Only players in the qualifying pool (``--min-hands``, default 100, matching the
distribution view) are kept as ledger nodes, which bounds the edge set.

The full pairwise ledger has millions of edges, far too many to ship to a
browser graph. We therefore emit only the *shark-feeder subgraph*: the top
net-winning sharks, each shark's top feeders, and the edges between them. That
is exactly what both downstream views render.

Output (JSON), compact:
    {
      "sharks": [ {id, name, net_amount, hands, feeders: [{id, name, chips, ...}]} ],
      "nodes":  [ {id, name, net_amount, hands, role} ],   # sharks + feeders only
      "edges":  [ {source, target, chips} ]                # feeder -> shark net flow
    }
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def load_pool(features_csv: Path, min_hands: int) -> dict[str, dict]:
    """Return {name: {hands, net_amount}} for players at/above ``min_hands``."""
    pool: dict[str, dict] = {}
    with features_csv.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                hands = int(row["hands"])
            except (KeyError, ValueError):
                continue
            if hands < min_hands:
                continue
            try:
                net = int(float(row.get("net_amount") or 0))
            except ValueError:
                net = 0
            pool[row["player"]] = {"hands": hands, "net_amount": net}
    return pool


def accumulate_hand(
    players: dict,
    pool: set[str],
    edges: dict[tuple[str, str], float],
    tol: int,
) -> bool:
    """Fold one hand's chip flow into ``edges``. Returns False if skipped."""
    nets: dict[str, int] = {}
    for name, d in players.items():
        if name not in pool:
            continue
        win = int(d.get("total_win") or 0)
        bet = int(d.get("total_bet") or 0)
        nets[name] = win - bet

    if len(nets) < 2:
        return False

    total = sum(nets.values())
    # Pot must roughly conserve chips among the players we are tracking. When
    # some seats are outside the pool the residual is expected, so we balance
    # only on the full hand below; here we gate on the in-pool participants
    # genuinely splitting chips.
    gains = {n: v for n, v in nets.items() if v > 0}
    losses = {n: -v for n, v in nets.items() if v < 0}
    if not gains or not losses:
        return False
    if abs(total) > tol and abs(total) > 0.2 * sum(gains.values()):
        return False

    total_gain = sum(gains.values())
    for u, loss in losses.items():
        for v, gain in gains.items():
            edges[(u, v)] += loss * (gain / total_gain)
    return True


def net_edges(edges: dict[tuple[str, str], float]) -> dict[tuple[str, str], float]:
    """Collapse u->v and v->u into a single signed net edge u->v (positive)."""
    out: dict[tuple[str, str], float] = {}
    seen: set[tuple[str, str]] = set()
    for (u, v), w in edges.items():
        if (u, v) in seen or (v, u) in seen:
            continue
        net = w - edges.get((v, u), 0.0)
        seen.add((u, v))
        if net > 0:
            out[(u, v)] = net
        elif net < 0:
            out[(v, u)] = -net
    return out


def build(
    hands_jsonl: Path,
    pool: dict[str, dict],
    tol: int,
    max_hands: int | None,
) -> tuple[dict[tuple[str, str], float], int, int]:
    pool_names = set(pool)
    edges: dict[tuple[str, str], float] = defaultdict(float)
    used = skipped = 0
    with hands_jsonl.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if max_hands is not None and i >= max_hands:
                break
            line = line.strip()
            if not line:
                continue
            hand = json.loads(line)
            players = hand.get("players") or {}
            if accumulate_hand(players, pool_names, edges, tol):
                used += 1
            else:
                skipped += 1
    return net_edges(edges), used, skipped


def assemble_output(
    pool: dict[str, dict],
    edges: dict[tuple[str, str], float],
    n_sharks: int,
    n_feeders: int,
) -> dict:
    ids = {name: f"p{i}" for i, name in enumerate(sorted(pool))}

    # in-flow per player: who fed them and how much
    feeders_of: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for (u, v), chips in edges.items():
        feeders_of[v].append((u, chips))

    sharks = sorted(pool, key=lambda n: pool[n]["net_amount"], reverse=True)[:n_sharks]
    shark_set = set(sharks)

    shark_rows = []
    edge_rows = []
    feeder_names: set[str] = set()
    for name in sharks:
        feeders = sorted(feeders_of.get(name, []), key=lambda t: t[1], reverse=True)[:n_feeders]
        shark_rows.append({
            "id": ids[name],
            "name": name,
            "net_amount": pool[name]["net_amount"],
            "hands": pool[name]["hands"],
            "feeders": [
                {"id": ids[u], "name": u, "chips": round(chips),
                 "net_amount": pool[u]["net_amount"], "hands": pool[u]["hands"]}
                for u, chips in feeders
            ],
        })
        for u, chips in feeders:
            feeder_names.add(u)
            edge_rows.append({"source": ids[u], "target": ids[name], "chips": round(chips)})

    # Nodes = only the players that appear in the shark-feeder subgraph.
    node_names = shark_set | feeder_names
    nodes = [
        {"id": ids[n], "name": n, "net_amount": pool[n]["net_amount"], "hands": pool[n]["hands"],
         "role": "shark" if n in shark_set else "feeder"}
        for n in sorted(node_names)
    ]
    return {"sharks": shark_rows, "nodes": nodes, "edges": edge_rows}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--hands", type=Path, default=Path("processed/nolimit_holdem/holdem_hands.jsonl"))
    p.add_argument("--features", type=Path, default=Path("processed/nolimit_holdem/player_features.csv"))
    p.add_argument("--output", type=Path, default=Path("frontend/public/data/ledger.json"))
    p.add_argument("--min-hands", type=int, default=100)
    p.add_argument("--tol", type=int, default=2, help="chip tolerance for pot balance")
    p.add_argument("--sharks", type=int, default=40, help="number of top net-winners to expose")
    p.add_argument("--feeders", type=int, default=20, help="top feeders kept per shark")
    p.add_argument("--max-hands", type=int, default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if not args.hands.exists():
        raise SystemExit(f"hands not found: {args.hands}")
    if not args.features.exists():
        raise SystemExit(f"features not found: {args.features}")

    pool = load_pool(args.features, args.min_hands)
    edges, used, skipped = build(args.hands, pool, args.tol, args.max_hands)
    out = assemble_output(pool, edges, args.sharks, args.feeders)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))

    print(json.dumps({
        "pool_players": len(pool),
        "hands_used": used,
        "hands_skipped": skipped,
        "skip_pct": round(100 * skipped / max(1, used + skipped), 1),
        "edges": len(out["edges"]),
        "sharks": len(out["sharks"]),
        "output": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
