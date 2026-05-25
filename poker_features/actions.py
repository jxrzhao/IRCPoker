"""Action code vocabulary for the IRC poker PDB format.

The PDB file stores each player's actions on each street as a string of single
character codes. Their meaning is documented in
``scripts/clean_nolimit_holdem.py`` (``ACTION_RE = "[BfkbcrAQK-]+"``):

    B  blind bet (forced — small or big)
    f  fold
    k  check
    b  bet      (first chips of the street that are not a forced blind)
    c  call
    r  raise
    A  all-in   (treated here as an aggressive action)
    Q  quit / sit-out (involuntary fold)
    K  kicked from the table (involuntary fold)
    -  no action (the hand ended on an earlier street)

The frozensets exposed here let downstream code classify any code in O(1).
"""

from __future__ import annotations

AGGRESSIVE_ACTIONS: frozenset[str] = frozenset("brA")  # bets, raises, all-ins
CALL_ACTIONS:       frozenset[str] = frozenset("c")
CHECK_ACTIONS:      frozenset[str] = frozenset("k")
FOLD_ACTIONS:       frozenset[str] = frozenset("fQK")
BLIND_ACTIONS:      frozenset[str] = frozenset("B")

# A player voluntarily puts money in the pot pre-flop iff at least one of their
# pre-flop actions is a call/bet/raise/all-in. Blinds, checks, folds, quits and
# kicks are explicitly excluded.
VOLUNTARY_PREFLOP_ACTIONS: frozenset[str] = AGGRESSIVE_ACTIONS | CALL_ACTIONS

POSTFLOP_STAGES: tuple[str, ...] = ("f", "t", "r")  # flop, turn, river


def stage_actions(bets: list[dict], stage_code: str) -> str:
    """Return the raw action string for ``stage_code`` (``"p"``, ``"f"``, ``"t"``,
    or ``"r"``).

    Empty string is returned if the stage entry is missing from ``bets`` or
    its ``raw_actions`` field is the literal ``"-"`` (which the cleaner uses
    to denote "the hand ended on an earlier street").
    """
    for entry in bets:
        if entry.get("stage") == stage_code:
            raw = entry.get("raw_actions", "")
            return "" if raw == "-" else raw
    return ""


def strip_leading_blinds(actions: str) -> str:
    """Return ``actions`` with any leading ``B`` characters removed.

    Blinds are forced and not part of voluntary betting; in IRC PDB they only
    appear at the start of the pre-flop string for SB and BB. Stripping them
    leaves a pure voluntary action sequence that the sequence reconstructor
    can interleave with confidence.
    """
    i = 0
    while i < len(actions) and actions[i] in BLIND_ACTIONS:
        i += 1
    return actions[i:]


def is_voluntary_preflop(preflop: str) -> bool:
    """True iff the player called/bet/raised/went all-in at least once pre-flop.

    Blinds (``B``), checks (``k``), folds (``f``), quits (``Q``) and kicks
    (``K``) are explicitly excluded — they are either forced or non-voluntary
    exits.
    """
    return any(c in VOLUNTARY_PREFLOP_ACTIONS for c in preflop)


def is_preflop_raiser(preflop: str) -> bool:
    """True iff any of the player's pre-flop actions is aggressive (``b``,
    ``r``, ``A``). Used for the PFR% indicator.
    """
    return any(c in AGGRESSIVE_ACTIONS for c in preflop)


def first_nonblind_is_bet(actions: str) -> bool:
    """Did the player fire the first non-blind chips of this street?

    Walks the action string skipping forced blinds (which only appear pre-flop
    anyway) and returns True iff the first remaining action is bet / raise /
    all-in.

        ``"b..."``  -> True   (bet first)
        ``"br"``    -> True
        ``"kb"``    -> False  (checked, then bet later)
        ``"c..."``  -> False  (faced a bet)
        ``""``      -> False
    """
    for c in actions:
        if c in BLIND_ACTIONS:
            continue
        return c in AGGRESSIVE_ACTIONS
    return False
