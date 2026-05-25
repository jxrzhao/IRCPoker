"""Reconstruct the global betting sequence from per-player action strings.

The IRC PDB stores each player's actions on each street as their own string,
but several metrics — **3-bet%**, **4-bet%**, **fold-to-3-bet%**,
**fold-to-4-bet%**, **donk-bet%** — depend on the *interleaved* order of
actions across players. This module walks the per-player strings in correct
table order and emits per-hand event flags.

Position convention (IRC PDB)
-----------------------------
    position 1   = small blind (or dealer/button in heads-up)
    position 2   = big blind
    position 3.. = UTG, UTG+1, ..., button

Action order
------------
    pre-flop, heads-up:  [1, 2]                     (SB acts first, BB last)
    pre-flop, N >= 3:    [3, 4, ..., N, 1, 2]       (UTG ..., button, SB, BB)
    post-flop, heads-up: [2, 1]                     (BB acts first)
    post-flop, N >= 3:   [1, 2, ..., N]             (SB first, button last)

Public API
----------
    preflop_action_order(num_players)   -> list[int]
    postflop_action_order(num_players)  -> list[int]
    acts_before(a, b, num_players)      -> bool   (postflop order)
    analyze_preflop(actions_by_pos, n)  -> PreflopAnalysis
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .actions import (
    AGGRESSIVE_ACTIONS,
    FOLD_ACTIONS,
    strip_leading_blinds,
)


# ---------------------------------------------------------------------------
# Table order helpers
# ---------------------------------------------------------------------------

def preflop_action_order(num_players: int) -> list[int]:
    """Return the position numbers in the order they will act pre-flop."""
    if num_players <= 1:
        return list(range(1, num_players + 1))
    if num_players == 2:
        return [1, 2]
    return list(range(3, num_players + 1)) + [1, 2]


def postflop_action_order(num_players: int) -> list[int]:
    """Return the position numbers in the order they will act post-flop."""
    if num_players <= 1:
        return list(range(1, num_players + 1))
    if num_players == 2:
        return [2, 1]
    return list(range(1, num_players + 1))


def acts_before(a: int, b: int, num_players: int) -> bool:
    """True iff position ``a`` acts before position ``b`` post-flop.

    Used to test whether a defender is *out of position* relative to the
    pre-flop aggressor (donk-bet detection).
    """
    order = postflop_action_order(num_players)
    try:
        return order.index(a) < order.index(b)
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Per-player pre-flop events
# ---------------------------------------------------------------------------

@dataclass
class PerPlayerPreflopEvents:
    """Hand-level pre-flop event flags for one player.

    All flags are booleans (each event either happened in this hand or not).
    Downstream code sums these across hands to produce 3-bet% / 4-bet% etc.

    Attributes
    ----------
    was_open_raiser
        Player made the **1st** voluntary raise of the street (RFI).
    made_3bet
        Player made the **2nd** voluntary raise (= a 3-bet).
    made_4bet
        Player made the **3rd** voluntary raise (= a 4-bet).
    opp_3bet
        Player had at least one action where exactly one prior raise had
        occurred (someone else had opened). This is the denominator of 3-bet%.
    opp_4bet
        Player had at least one action where exactly two prior raises had
        occurred. This is the denominator of 4-bet%.
    faced_3bet_as_opener
        Player was the open raiser and at a later point in the sequence saw
        another player 3-bet. Denominator of fold-to-3-bet%.
    folded_to_3bet
        Above, and player's response to the 3-bet was a fold.
    faced_4bet_as_3better
        Player was the 3-bettor and at a later point saw a 4-bet.
        Denominator of fold-to-4-bet%.
    folded_to_4bet
        Above, and player's response to the 4-bet was a fold.
    """

    was_open_raiser:        bool = False
    made_3bet:              bool = False
    made_4bet:              bool = False
    opp_3bet:               bool = False
    opp_4bet:               bool = False
    faced_3bet_as_opener:   bool = False
    folded_to_3bet:         bool = False
    faced_4bet_as_3better:  bool = False
    folded_to_4bet:         bool = False


@dataclass
class PreflopAnalysis:
    """Result of walking the pre-flop sequence for a single hand.

    Attributes
    ----------
    per_player
        Position -> per-player event flags.
    last_raiser
        Position of the last pre-flop raiser (the *pre-flop aggressor*) or
        ``None`` if the hand never had a raise. Used as the reference point
        for donk-bet detection on the flop.
    survivors
        Set of positions still in the hand at the end of pre-flop (never
        folded). These are the players eligible to see the flop.
    raise_count
        Total number of voluntary raises (open + 3-bet + 4-bet + ...) made
        during pre-flop. Exposed mostly for tests / sanity checks.
    """

    per_player: dict[int, PerPlayerPreflopEvents] = field(default_factory=dict)
    last_raiser: int | None = None
    survivors:   set[int] = field(default_factory=set)
    raise_count: int = 0


# ---------------------------------------------------------------------------
# The sequence walker
# ---------------------------------------------------------------------------

def analyze_preflop(
    actions_by_position: Mapping[int, str],
    num_players: int,
) -> PreflopAnalysis:
    """Walk the interleaved pre-flop action sequence.

    Each player's per-street action string lists their voluntary actions in
    order. By going round-robin in :func:`preflop_action_order` and consuming
    one character per still-active player per round, we recover the *global*
    sequence of actions for the street. We then label each raise with its
    "level" (1 = open, 2 = 3-bet, 3 = 4-bet, ...) by maintaining a running
    raise counter, and tag each player's actions with the corresponding
    opportunity / response flags.

    Parameters
    ----------
    actions_by_position
        Mapping from player position to their **raw** pre-flop action string
        (with the blind ``B`` still attached for SB/BB). Players missing from
        the mapping are treated as having no actions.
    num_players
        The hand's player count, used to determine action order.

    Returns
    -------
    PreflopAnalysis
        Hand-level summary plus per-position event flags.
    """
    order = preflop_action_order(num_players)

    # Strip leading B from SB/BB so we walk voluntary actions only.
    voluntary: dict[int, str] = {
        p: strip_leading_blinds(actions_by_position.get(p, ""))
        for p in order
    }
    cursors: dict[int, int] = {p: 0 for p in order}

    per_player: dict[int, PerPlayerPreflopEvents] = {p: PerPlayerPreflopEvents() for p in order}
    folded: set[int] = set()

    raise_count = 0
    open_raiser:    int | None = None
    three_better:   int | None = None
    last_raiser:    int | None = None

    # Round-robin through the table. A round ends when we make a full pass
    # without consuming any action. The loop is guaranteed to terminate
    # because each consumed action strictly decreases total remaining actions.
    while True:
        progressed = False
        for p in order:
            if p in folded or cursors[p] >= len(voluntary[p]):
                continue
            action = voluntary[p][cursors[p]]
            cursors[p] += 1
            progressed = True

            prior_raises = raise_count

            # --- opportunity-to-N-bet flags (based on what we are facing) ---
            if prior_raises == 1:
                per_player[p].opp_3bet = True
            elif prior_raises == 2:
                per_player[p].opp_4bet = True

            # --- "faced the next raise" flags (for the previous aggressor) ---
            # The open raiser saw a 3-bet iff prior_raises >= 2 by the time
            # they next act. The 3-bettor saw a 4-bet iff prior_raises >= 3.
            if open_raiser == p and prior_raises >= 2:
                per_player[p].faced_3bet_as_opener = True
            if three_better == p and prior_raises >= 3:
                per_player[p].faced_4bet_as_3better = True

            # --- process this action ---
            if action in AGGRESSIVE_ACTIONS:
                if prior_raises == 0:
                    open_raiser = p
                    per_player[p].was_open_raiser = True
                elif prior_raises == 1:
                    three_better = p
                    per_player[p].made_3bet = True
                elif prior_raises == 2:
                    per_player[p].made_4bet = True
                # 5-bet+ exists but isn't tracked separately.
                raise_count += 1
                last_raiser = p
            elif action in FOLD_ACTIONS:
                folded.add(p)
                # The fold-to-N-bet flag is set iff this fold is the response
                # to the immediately following raise level (i.e. the player
                # acted because they faced that raise, not earlier).
                if open_raiser == p and prior_raises >= 2:
                    per_player[p].folded_to_3bet = True
                if three_better == p and prior_raises >= 3:
                    per_player[p].folded_to_4bet = True
            # else: check or call — no state change beyond cursor advance.

        if not progressed:
            break

    survivors = {p for p in order if p not in folded}
    return PreflopAnalysis(
        per_player=per_player,
        last_raiser=last_raiser,
        survivors=survivors,
        raise_count=raise_count,
    )
