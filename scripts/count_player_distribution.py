#!/usr/bin/env python3
"""
Count the distribution of table sizes in cleaned poker hand JSONL files.

Memory use does not grow with total file size: the file is read sequentially in
small OS-buffered chunks, one line at a time. Nothing ever calls read() or
readlines() on the whole file.

Peak RAM is roughly O(size of the largest single line) plus a small Counter
(table sizes are bounded integers). Requires standard JSONL: one complete JSON
object per line (no pretty-printed multi-line records).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def count_file(path: Path, counts: Counter, stats: Counter) -> None:
    # Iterating the text file yields lines from an internal buffer; the file is
    # not loaded into memory as a whole.
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                hand = json.loads(line)
            except json.JSONDecodeError:
                stats["invalid_json_lines"] += 1
                continue

            num_players = hand.get("num_players")
            if not isinstance(num_players, int):
                stats["missing_num_players"] += 1
                continue

            counts[num_players] += 1
            stats["hands"] += 1


def print_table(counts: Counter, total: int) -> None:
    print("num_players,hands,percent")
    for num_players in sorted(counts):
        percent = counts[num_players] / total * 100 if total else 0
        print(f"{num_players},{counts[num_players]},{percent:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "jsonl",
        type=Path,
        nargs="?",
        default=Path("processed/nolimit_holdem/holdem_hands.jsonl"),
        help="Path to a single JSONL file of hands",
    )
    args = parser.parse_args()

    path = args.jsonl.resolve()
    if not path.is_file():
        raise SystemExit(f"Not a file: {path}")

    counts: Counter = Counter()
    stats: Counter = Counter()
    count_file(path, counts, stats)

    print_table(counts, stats["hands"])
    print()
    print(f"file,{path}")
    print(f"hands,{stats['hands']}")
    print(f"invalid_json_lines,{stats['invalid_json_lines']}")
    print(f"missing_num_players,{stats['missing_num_players']}")


if __name__ == "__main__":
    main()
