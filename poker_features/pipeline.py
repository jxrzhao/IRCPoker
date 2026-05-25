"""High-level streaming orchestration: hand JSONL -> per-player feature rows.

The pipeline is intentionally thin: it owns the per-player accumulator dict,
streams one hand at a time via :func:`poker_features.io.iter_hands`, dispatches
each hand to :func:`poker_features.features.update_from_hand`, and finalises
all accumulators into output rows once the stream completes.

Memory is ``O(players)`` — typically a few megabytes for the full IRC dataset
(~50 k distinct nicknames) — regardless of the total number of hands.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .features import (
    CSV_FIELDS,
    finalize_player,
    new_accumulator_dict,
    update_from_hand,
)
from .io import iter_hands
from .progress import Progress


def build_features(
    input_path: Path,
    *,
    max_hands: int | None = None,
    min_hands: int = 1,
    show_progress: bool = True,
) -> list[dict[str, Any]]:
    """Stream hands from ``input_path`` and return one feature row per player.

    Parameters
    ----------
    input_path
        Path to a cleaned hand JSONL file (the output of
        ``scripts/clean_nolimit_holdem.py``).
    max_hands
        Optional cap on the number of hands consumed. Useful for smoke tests.
    min_hands
        Drop players with fewer than this many hands from the output. Setting
        this to e.g. 50 or 100 before clustering keeps very low-volume players
        from polluting the style space with noisy estimates.
    show_progress
        Show a stderr progress bar while streaming. Automatically suppressed
        when stderr is not a TTY.

    Returns
    -------
    list of dict
        One row per surviving player, sorted by descending hand count then by
        nickname. Each row is the dict returned by :func:`finalize_player`.
    """
    accs = new_accumulator_dict()
    total = 0
    total_bytes = input_path.stat().st_size if input_path.exists() else 0
    progress = Progress(
        total_bytes=total_bytes,
        max_hands=max_hands,
        enabled=show_progress,
    )

    for hand in iter_hands(input_path, max_hands, progress=progress):
        total += 1
        update_from_hand(accs, hand)

    rows = [
        finalize_player(name, acc)
        for name, acc in accs.items()
        if acc.hands >= min_hands
    ]
    rows.sort(key=lambda r: (-r["hands"], r["player"]))
    print(
        f"[poker_features] processed {total:,} hands -> "
        f"{len(rows):,} players (>= {min_hands} hands)",
        file=sys.stderr,
    )
    return rows


__all__ = ["build_features", "CSV_FIELDS"]
