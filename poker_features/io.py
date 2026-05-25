"""Streaming I/O helpers: JSONL hand reader + CSV / JSON feature writers.

These helpers know about file formats but nothing about poker. They sit
between :mod:`poker_features.features` (in-memory aggregation) and
:mod:`poker_features.cli` (command-line dispatch).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, Iterator

from .progress import Progress


def iter_hands(
    path: Path,
    max_hands: int | None,
    progress: Progress | None = None,
) -> Iterator[dict]:
    """Yield decoded hand dicts from a JSONL file.

    Stops after ``max_hands`` if provided. Invalid JSON lines are counted on
    stderr and skipped, mirroring the tolerant behaviour of the other scripts
    in this project.

    The file is opened in **binary** mode so byte offsets can be tracked
    cheaply for the progress bar — ``json.loads`` accepts UTF-8 bytes
    directly.
    """
    bad = 0
    yielded = 0
    bytes_read = 0
    with path.open("rb") as f:
        for raw in f:
            bytes_read += len(raw)
            if not raw.strip():
                continue
            try:
                hand = json.loads(raw)
            except json.JSONDecodeError:
                bad += 1
                continue
            yield hand
            yielded += 1
            if progress is not None:
                progress.update(yielded, bytes_read)
            if max_hands is not None and yielded >= max_hands:
                break
    if progress is not None:
        progress.close()
    if bad:
        print(f"[poker_features] skipped {bad} malformed JSON lines", file=sys.stderr)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    """Write feature rows as CSV. ``None`` values become empty cells.

    ``fieldnames`` may contain identifiers that start with a digit (e.g.
    ``"3bet_pct"``); ``csv.DictWriter`` handles these fine.
    """
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if row.get(k) is None else row[k]) for k in fieldnames})


def write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write feature rows as a single pretty-printed JSON array."""
    with path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, sort_keys=True)
        f.write("\n")
