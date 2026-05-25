#!/usr/bin/env python3
"""
Sample N hands from a cleaned holdem JSONL file.

Uses reservoir sampling, which gives a uniform sample while reading the input
once and keeping only N records in memory.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def parse_window(window: str) -> tuple[int, int | None]:
    if ":" not in window:
        raise argparse.ArgumentTypeError("window must look like START:END, START:, or :END")

    start_text, end_text = window.split(":", 1)
    if not start_text and not end_text:
        raise argparse.ArgumentTypeError("window must include a start or end line")

    try:
        start = int(start_text) if start_text else 1
        end = int(end_text) if end_text else None
    except ValueError as exc:
        raise argparse.ArgumentTypeError("window bounds must be integers") from exc

    if start < 1:
        raise argparse.ArgumentTypeError("window start must be at least 1")
    if end is not None and end < start:
        raise argparse.ArgumentTypeError("window end must be greater than or equal to start")

    return start, end


def sample_jsonl(
    input_path: Path,
    sample_size: int,
    seed: int | None,
    start_line: int,
    end_line: int | None,
) -> tuple[list[str], int, int, int]:
    rng = random.Random(seed)
    reservoir: list[str] = []
    valid_rows = 0
    invalid_rows = 0
    lines_seen = 0

    with input_path.open("r", encoding="utf-8", errors="replace") as f:
        for line_num, line in enumerate(f, start=1):
            if line_num < start_line:
                continue
            if end_line is not None and line_num > end_line:
                break

            lines_seen += 1
            if not line.strip():
                continue

            try:
                json.loads(line)
            except json.JSONDecodeError:
                invalid_rows += 1
                continue

            valid_rows += 1
            if len(reservoir) < sample_size:
                reservoir.append(line)
                continue

            replace_at = rng.randrange(valid_rows)
            if replace_at < sample_size:
                reservoir[replace_at] = line

    return reservoir, valid_rows, invalid_rows, lines_seen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "n",
        type=int,
        help="number of hands to sample",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("processed/nolimit_holdem/holdem_hands.jsonl"),
        help="input cleaned holdem JSONL file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="output JSONL file; defaults to processed/nolimit_holdem/holdem_hands.sample_N.jsonl",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="random seed for reproducible samples",
    )
    parser.add_argument(
        "--window",
        type=parse_window,
        default=None,
        metavar="START:END",
        help="1-based inclusive line window, e.g. 100000:200000, 100000:, or :200000",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help="1-based input line where the sampling window starts, inclusive; ignored when --window is used",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=None,
        help="1-based input line where the sampling window ends, inclusive; ignored when --window is used",
    )
    args = parser.parse_args()

    start_line, end_line = args.window if args.window is not None else (args.start, args.end)

    if args.n < 1:
        raise SystemExit("n must be at least 1")
    if start_line < 1:
        raise SystemExit("--start must be at least 1")
    if end_line is not None and end_line < start_line:
        raise SystemExit("--end must be greater than or equal to --start")
    if not args.input.exists():
        raise SystemExit(f"Input file does not exist: {args.input}")

    if args.output is None:
        window = f".lines_{start_line}_{end_line}" if end_line is not None or start_line != 1 else ""
        output_path = args.input.with_name(f"{args.input.stem}.sample_{args.n}{window}.jsonl")
    else:
        output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sample, valid_rows, invalid_rows, lines_seen = sample_jsonl(
        args.input,
        args.n,
        args.seed,
        start_line,
        end_line,
    )
    with output_path.open("w", encoding="utf-8") as f:
        f.writelines(sample)

    summary = {
        "end_line": end_line,
        "input": str(args.input),
        "input_lines_in_window": lines_seen,
        "output": str(output_path),
        "requested_sample_size": args.n,
        "written_sample_size": len(sample),
        "start_line": start_line,
        "valid_rows_seen": valid_rows,
        "invalid_json_lines": invalid_rows,
        "seed": args.seed,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
