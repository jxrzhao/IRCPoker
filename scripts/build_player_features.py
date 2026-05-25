#!/usr/bin/env python3
"""Backward-compatible CLI shim for the ``poker_features`` package.

The implementation lived here in v1; it now lives in the ``poker_features``
package at the repository root. This file remains so existing invocations
keep working:

    python scripts/build_player_features.py [options]

The preferred form is now:

    python -m poker_features [options]

Both go through the same entry point — see ``poker_features.cli.main``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make ``poker_features`` importable when this wrapper is invoked directly
# (e.g. ``python scripts/build_player_features.py``) regardless of the
# current working directory.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from poker_features.cli import main  # noqa: E402  (path mutated above)


if __name__ == "__main__":
    main()
