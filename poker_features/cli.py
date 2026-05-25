"""Command-line entry point for the :mod:`poker_features` package.

Usage::

    python -m poker_features [options]

The options mirror what the old ``scripts/build_player_features.py`` script
supported plus a few new conveniences. Defaults assume the cleaned dataset
lives under ``processed/nolimit_holdem/`` relative to the current directory.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .features import CSV_FIELDS
from .io import write_csv, write_json
from .pipeline import build_features


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        prog="python -m poker_features",
    )
    parser.add_argument(
        "--input", type=Path,
        default=Path("processed/nolimit_holdem/holdem_hands.jsonl"),
        help="cleaned holdem hands JSONL (default: %(default)s)",
    )
    parser.add_argument(
        "--output-csv", type=Path,
        default=Path("processed/nolimit_holdem/player_features.csv"),
        help="output CSV path (default: %(default)s)",
    )
    parser.add_argument(
        "--output-json", type=Path,
        default=Path("processed/nolimit_holdem/player_features.json"),
        help="output JSON path (default: %(default)s)",
    )
    parser.add_argument(
        "--max-hands", type=int, default=None,
        help="stop after N hands (for smoke testing on a small subset)",
    )
    parser.add_argument(
        "--min-hands", type=int, default=1,
        help="omit players with fewer than this many hands (default: %(default)s)",
    )
    parser.add_argument(
        "--no-progress", action="store_true",
        help="disable the streaming progress bar "
             "(auto-disabled when stderr is not a TTY)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if not args.input.exists():
        raise SystemExit(f"input not found: {args.input}")
    for out in (args.output_csv, args.output_json):
        out.parent.mkdir(parents=True, exist_ok=True)

    rows = build_features(
        args.input,
        max_hands=args.max_hands,
        min_hands=args.min_hands,
        show_progress=not args.no_progress,
    )
    write_csv(args.output_csv, CSV_FIELDS, rows)
    write_json(args.output_json, rows)

    print(json.dumps({
        "input":       str(args.input),
        "output_csv":  str(args.output_csv),
        "output_json": str(args.output_json),
        "players":     len(rows),
        "max_hands":   args.max_hands,
        "min_hands":   args.min_hands,
    }, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
