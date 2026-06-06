#!/usr/bin/env python3
"""Convert player_features.csv into the JSON shape the dashboard consumes.

Reads the feature CSV produced by ``python -m poker_features`` and emits
``frontend/public/data/players.json`` as a flat list of player objects in the
frontend data contract:

    { id, name, hands, net_amount, chips_per_hand, metrics: { ...28 } }

Only the columns the views actually read are kept, so the payload stays small.
Min-hands filtering is deliberately left to the client (the slider is live), so
this script ships every player at or above ``--floor`` hands.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

# All 30 fingerprint metrics, in metrics.js order. win_rate and chips_per_hand
# live in `metrics` (the showdown tab renders them) and chips_per_hand is also
# mirrored to the top level for the colour scale.
METRIC_KEYS = [
    "vpip_pct", "pfr_pct", "3bet_pct", "fold_to_3bet_pct", "4bet_pct", "fold_to_4bet_pct",
    "flop_af", "flop_cbet_pct", "flop_donk_pct", "flop_fold_pct", "flop_raise_pct",
    "turn_af", "turn_cbet_pct", "turn_donk_pct", "turn_fold_pct", "turn_raise_pct",
    "river_af", "river_cbet_pct", "river_donk_pct", "river_fold_pct", "river_raise_pct",
    "postflop_af", "postflop_cbet_pct", "postflop_donk_pct", "postflop_fold_pct", "postflop_raise_pct",
    "wtsd_pct", "wsd_pct", "win_rate", "chips_per_hand",
]


def _num(value: str) -> float | None:
    """Parse a CSV cell to float, or None for empty / unparsable (undefined)."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def build_rows(csv_path: Path, floor: int) -> list[dict]:
    rows: list[dict] = []
    with csv_path.open("r", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            try:
                hands = int(row["hands"])
            except (KeyError, ValueError):
                continue
            if hands < floor:
                continue
            metrics = {k: _num(row.get(k, "")) for k in METRIC_KEYS}
            rows.append({
                "id": f"p{i}",
                "name": row["player"],
                "hands": hands,
                "net_amount": int(_num(row.get("net_amount", "")) or 0),
                "chips_per_hand": _num(row.get("chips_per_hand", "")),
                "metrics": metrics,
            })
    rows.sort(key=lambda r: r["net_amount"], reverse=True)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path,
        default=Path("processed/nolimit_holdem/player_features.csv"),
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("frontend/public/data/players.json"),
    )
    parser.add_argument(
        "--floor", type=int, default=50,
        help="drop players below this many hands (default: %(default)s)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise SystemExit(f"input not found: {args.input}")
    rows = build_rows(args.input, args.floor)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(rows, f, separators=(",", ":"))
    print(f"wrote {args.output} ({len(rows):,} players, floor={args.floor})")


if __name__ == "__main__":
    main()
