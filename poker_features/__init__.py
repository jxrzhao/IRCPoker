"""Per-player feature extraction for the cleaned IRC Hold'em dataset.

The package is organised so each layer has a single responsibility:

    actions.py     action-code constants and primitives
    sequence.py    pre-flop sequence reconstruction (interleave per-player
                   action strings into the global table-order timeline)
    features.py    PlayerAccumulator + hand-level update + finalisation
    progress.py    in-place stderr progress bar
    io.py          streaming JSONL reader + CSV/JSON writers
    pipeline.py    high-level orchestration (build_features)
    cli.py         argparse entry point (python -m poker_features)

Typical programmatic use::

    from pathlib import Path
    from poker_features import build_features, CSV_FIELDS, write_csv

    rows = build_features(Path("processed/nolimit_holdem/holdem_hands.jsonl"),
                          max_hands=100_000, min_hands=50)
    write_csv(Path("features.csv"), CSV_FIELDS, rows)
"""

from __future__ import annotations

from .features import (
    CSV_FIELDS,
    PlayerAccumulator,
    finalize_player,
    new_accumulator_dict,
    update_from_hand,
    update_player,
)
from .io import iter_hands, write_csv, write_json
from .pipeline import build_features
from .progress import Progress
from .sequence import (
    PerPlayerPreflopEvents,
    PreflopAnalysis,
    acts_before,
    analyze_preflop,
    postflop_action_order,
    preflop_action_order,
)

__all__ = [
    "CSV_FIELDS",
    "PerPlayerPreflopEvents",
    "PlayerAccumulator",
    "PreflopAnalysis",
    "Progress",
    "acts_before",
    "analyze_preflop",
    "build_features",
    "finalize_player",
    "iter_hands",
    "new_accumulator_dict",
    "postflop_action_order",
    "preflop_action_order",
    "update_from_hand",
    "update_player",
    "write_csv",
    "write_json",
]
