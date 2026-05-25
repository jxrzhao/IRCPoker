#!/usr/bin/env python3
"""
Extract heads-up holdem hands and player profiles from cleaned JSONL data.

The input is expected to be the output of clean_nolimit_holdem.py. The script
streams one hand at a time, writes every two-player hand to JSONL, and builds a
CSV/JSON summary of players who appeared in those heads-up hands.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def default_output_paths(input_path: Path, output_dir: Path) -> tuple[Path, Path, Path]:
    stem = input_path.stem
    return (
        output_dir / f"{stem}.heads_up.jsonl",
        output_dir / f"{stem}.heads_up_players.csv",
        output_dir / f"{stem}.heads_up_players.json",
    )


def new_profile() -> dict[str, int]:
    return {
        "heads_up_hands": 0,
        "known_pocket_cards_hands": 0,
        "wins": 0,
        "win_amount": 0,
        "total_bet": 0,
        "net_amount": 0,
    }


def update_profiles(hand: dict[str, Any], profiles: dict[str, dict[str, int]]) -> None:
    players = hand.get("players", {})
    if not isinstance(players, dict):
        return

    both_pocket_cards_known = all(
        isinstance(player_data, dict)
        and isinstance(player_data.get("pocket_cards"), list)
        and len(player_data["pocket_cards"]) == 2
        for player_data in players.values()
    )

    for player, player_data in players.items():
        if not isinstance(player_data, dict):
            continue

        total_win = player_data.get("total_win", 0)
        total_bet = player_data.get("total_bet", 0)
        if not isinstance(total_win, int):
            total_win = 0
        if not isinstance(total_bet, int):
            total_bet = 0

        profile = profiles[player]
        profile["heads_up_hands"] += 1
        profile["known_pocket_cards_hands"] += int(both_pocket_cards_known)
        profile["wins"] += int(total_win > 0)
        profile["win_amount"] += total_win
        profile["total_bet"] += total_bet
        profile["net_amount"] += total_win - total_bet


def profile_rows(profiles: dict[str, dict[str, int]]) -> list[dict[str, str | int | float]]:
    rows: list[dict[str, str | int | float]] = []
    for player, profile in profiles.items():
        hands = profile["heads_up_hands"]
        wins = profile["wins"]
        win_rate = wins / hands if hands else 0
        rows.append(
            {
                "player": player,
                "heads_up_hands": hands,
                "known_pocket_cards_hands": profile["known_pocket_cards_hands"],
                "wins": wins,
                "win_rate": round(win_rate, 6),
                "win_amount": profile["win_amount"],
                "total_bet": profile["total_bet"],
                "net_amount": profile["net_amount"],
            }
        )
    return sorted(rows, key=lambda row: (-int(row["heads_up_hands"]), str(row["player"])))


def write_profiles_csv(path: Path, rows: list[dict[str, str | int | float]]) -> None:
    fieldnames = [
        "player",
        "heads_up_hands",
        "known_pocket_cards_hands",
        "wins",
        "win_rate",
        "win_amount",
        "total_bet",
        "net_amount",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_profiles_json(path: Path, rows: list[dict[str, str | int | float]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, sort_keys=True)
        f.write("\n")


def extract_heads_up(input_path: Path, hands_path: Path, csv_path: Path, json_path: Path) -> dict[str, int | str]:
    stats: Counter = Counter()
    profiles: dict[str, dict[str, int]] = defaultdict(new_profile)

    with input_path.open("r", encoding="utf-8", errors="replace") as in_f, hands_path.open(
        "w", encoding="utf-8"
    ) as out_f:
        for line in in_f:
            if not line.strip():
                continue
            stats["input_lines"] += 1

            try:
                hand = json.loads(line)
            except json.JSONDecodeError:
                stats["invalid_json_lines"] += 1
                continue

            if hand.get("num_players") != 2:
                continue

            players = hand.get("players")
            if not isinstance(players, dict) or len(players) != 2:
                stats["invalid_heads_up_player_maps"] += 1
                continue

            out_f.write(line)
            stats["heads_up_hands"] += 1
            update_profiles(hand, profiles)

    rows = profile_rows(profiles)
    write_profiles_csv(csv_path, rows)
    write_profiles_json(json_path, rows)

    return {
        "input": str(input_path),
        "heads_up_hands_jsonl": str(hands_path),
        "player_profiles_csv": str(csv_path),
        "player_profiles_json": str(json_path),
        "input_lines": stats["input_lines"],
        "heads_up_hands": stats["heads_up_hands"],
        "players": len(rows),
        "invalid_json_lines": stats["invalid_json_lines"],
        "invalid_heads_up_player_maps": stats["invalid_heads_up_player_maps"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("processed/nolimit_holdem/holdem_hands.jsonl"),
        help="cleaned holdem JSONL input",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("processed/nolimit_holdem"),
        help="directory for extracted hands and player profiles",
    )
    parser.add_argument("--hands-output", type=Path, default=None, help="heads-up hands JSONL output")
    parser.add_argument("--profiles-csv", type=Path, default=None, help="player profile CSV output")
    parser.add_argument("--profiles-json", type=Path, default=None, help="player profile JSON output")
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input file does not exist: {args.input}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    default_hands, default_csv, default_json = default_output_paths(args.input, args.output_dir)
    hands_path = args.hands_output or default_hands
    csv_path = args.profiles_csv or default_csv
    json_path = args.profiles_json or default_json

    for path in (hands_path, csv_path, json_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    summary = extract_heads_up(args.input, hands_path, csv_path, json_path)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
