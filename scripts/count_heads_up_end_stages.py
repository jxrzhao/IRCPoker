#!/usr/bin/env python3
"""
Count where heads-up holdem hands end.

By default this reads processed/nolimit_holdem/holdem_hands.heads_up.jsonl.
The script streams the JSONL input, so it can handle large extracted files.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


END_STAGES = ("preflop", "flop", "turn", "river", "showdown")


def showdown_players(hand: dict[str, Any]) -> int:
    pots = hand.get("pots", [])
    if not isinstance(pots, list):
        return 0
    for pot in pots:
        if isinstance(pot, dict) and pot.get("stage") == "s":
            num_players = pot.get("num_players", 0)
            return num_players if isinstance(num_players, int) else 0
    return 0


def end_stage(hand: dict[str, Any]) -> str:
    if showdown_players(hand) > 1:
        return "showdown"

    board = hand.get("board", [])
    if not isinstance(board, list):
        return "unknown"

    board_cards = len(board)
    if board_cards == 0:
        return "preflop"
    if board_cards == 3:
        return "flop"
    if board_cards == 4:
        return "turn"
    if board_cards == 5:
        return "river"
    return "unknown"


def count_end_stages(input_path: Path) -> tuple[Counter, Counter]:
    counts: Counter = Counter()
    stats: Counter = Counter()

    with input_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            stats["input_lines"] += 1

            try:
                hand = json.loads(line)
            except json.JSONDecodeError:
                stats["invalid_json_lines"] += 1
                continue

            stage = end_stage(hand)
            counts[stage] += 1
            stats["valid_hands"] += 1

    return counts, stats


def summary_rows(counts: Counter, total: int) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    for stage in END_STAGES + ("unknown",):
        hands = counts[stage]
        if hands == 0 and stage == "unknown":
            continue
        percent = hands / total * 100 if total else 0
        rows.append({"end_stage": stage, "hands": hands, "percent": f"{percent:.4f}"})
    return rows


def print_summary(rows: list[dict[str, str | int]], stats: Counter) -> None:
    print("end_stage,hands,percent")
    for row in rows:
        print(f"{row['end_stage']},{row['hands']},{row['percent']}")
    print()
    print(f"input_lines,{stats['input_lines']}")
    print(f"valid_hands,{stats['valid_hands']}")
    print(f"invalid_json_lines,{stats['invalid_json_lines']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("processed/nolimit_holdem/holdem_hands.heads_up.jsonl"),
        help="heads-up hands JSONL input",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="optional path to write the summary as JSON",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input file does not exist: {args.input}")

    counts, stats = count_end_stages(args.input)
    rows = summary_rows(counts, stats["valid_hands"])
    print_summary(rows, stats)

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "input": str(args.input),
            "summary": rows,
            "input_lines": stats["input_lines"],
            "valid_hands": stats["valid_hands"],
            "invalid_json_lines": stats["invalid_json_lines"],
        }
        with args.output_json.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")


if __name__ == "__main__":
    main()
