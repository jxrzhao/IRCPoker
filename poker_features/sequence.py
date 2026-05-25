"""Reconstruct the global betting sequence from per-player action strings.

The IRC PDB stores each player's actions on each street as their own string,
but several metrics — **3-bet%**, **4-bet%**, **fold-to-3-bet%**,
**fold-to-4-bet%**, **donk-bet%**, plus per-street **fold-to-bet%** and
**raise-vs-bet%** — depend on the *interleaved* order of actions across
players. This module walks the per-player strings in correct table order
and emits per-hand event flags.

Position convention (IRC PDB)
-----------------------------
    position 1   = small blind (or dealer/button in heads-up)
    position 2   = big blind
    position 3.. = UTG, UTG+1, ..., button

Action order
------------
    pre-flop,  heads-up:  [1, 2]                    (SB acts first, BB last)
    pre-flop,  N >= 3:    [3, 4, ..., N, 1, 2]      (UTG ..., button, SB, BB)
    post-flop, heads-up:  [2, 1]                    (BB acts first)
    post-flop, N >= 3:    [1, 2, ..., N]            (SB first, button last)

Public API
----------
    preflop_action_order(num_players)              -> list[int]
    postflop_action_order(num_players)             -> list[int]
    acts_before(a, b, num_players)                 -> bool   (postflop order)
    analyze_preflop(actions_by_pos, n)             -> PreflopAnalysis
    analyze_postflop_street(actions_by_pos,
                            survivors_in, n)       -> StreetAnalysis
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .actions import (
    AGGRESSIVE_ACTIONS,
    CALL_ACTIONS,
    CHECK_ACTIONS,
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

    Used to test whether a defender is *out of position* relative to a
    previous-street aggressor (donk-bet detection).
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

    All flags are booleans. Downstream code sums these across hands to produce
    3-bet% / 4-bet% / fold-to-3-bet% / fold-to-4-bet%.
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
    """Result of walking the pre-flop sequence for a single hand."""

    per_player: dict[int, PerPlayerPreflopEvents] = field(default_factory=dict)
    last_raiser: int | None = None
    survivors:   set[int] = field(default_factory=set)
    raise_count: int = 0


# ---------------------------------------------------------------------------
# Per-player post-flop events (one street)
# ---------------------------------------------------------------------------

@dataclass
class PerPlayerStreetEvents:
    """Hand-level events for one player on one post-flop street.

    Event counts (``bets``, ``raises``, ``calls``, ``checks``, ``folds``) are
    integers — useful for the aggression-factor numerator/denominator.

    Per-hand binary flags (``faced_aggression`` etc.) are True if the event
    happened at least once on this street for this player. They drive the
    per-hand fold-to-bet / raise-vs-bet / c-bet / donk metrics.

    Attributes
    ----------
    saw_street
        Player still in the hand at the start of this street (was dealt into
        the previous street's survivors set).
    bets
        Number of times this player made the FIRST bet of the street on this
        street (i.e., fired into a pot that no one had bet into yet).
    raises
        Number of times this player raised an existing bet/raise.
    calls
        Number of times this player called a bet/raise.
    checks
        Number of times this player checked (which, by definition, can only
        happen when no one has bet yet).
    folds
        Number of times this player folded.
    faced_aggression
        Had at least one action where someone had already bet/raised on this
        street ("facing a bet or raise"). Denominator of fold-to-bet and
        raise-vs-bet.
    folded_to_aggression
        Above, and player folded.
    raised_facing_aggression
        Above, and player raised (3-bet / check-raise / etc. on this street).
    was_first_aggressor
        Player fired the first bet on this street. Used for c-bet and donk
        detection.
    was_last_aggressor
        Player made the LAST bet/raise on this street (i.e., the player who
        "took the lead" going into the next street). Used to identify the
        aggressor whose next-street c-bet we will track.
    """

    saw_street:               bool = False
    bets:                     int  = 0
    raises:                   int  = 0
    calls:                    int  = 0
    checks:                   int  = 0
    folds:                    int  = 0
    faced_aggression:         bool = False
    folded_to_aggression:     bool = False
    raised_facing_aggression: bool = False
    was_first_aggressor:      bool = False
    was_last_aggressor:       bool = False


@dataclass
class StreetAnalysis:
    """Result of walking one post-flop street.

    Attributes
    ----------
    per_player
        Position -> per-player event flags for this street.
    first_aggressor
        Position of the player who fired the first bet on this street, or
        ``None`` if everyone checked.
    last_aggressor
        Position of the player who made the last bet/raise on this street.
        This is the "street aggressor" — the one whose c-bet on the next
        street we will track.
    survivors
        Set of positions still in the hand at the end of this street.
    """

    per_player:      dict[int, PerPlayerStreetEvents] = field(default_factory=dict)
    first_aggressor: int | None = None
    last_aggressor:  int | None = None
    survivors:       set[int] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Pre-flop sequence walker
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
    """
    order = preflop_action_order(num_players)
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

    while True:
        progressed = False
        for p in order:
            if p in folded or cursors[p] >= len(voluntary[p]):
                continue
            action = voluntary[p][cursors[p]]
            cursors[p] += 1
            progressed = True

            prior_raises = raise_count

            if prior_raises == 1:
                per_player[p].opp_3bet = True
            elif prior_raises == 2:
                per_player[p].opp_4bet = True

            if open_raiser == p and prior_raises >= 2:
                per_player[p].faced_3bet_as_opener = True
            if three_better == p and prior_raises >= 3:
                per_player[p].faced_4bet_as_3better = True

            if action in AGGRESSIVE_ACTIONS:
                if prior_raises == 0:
                    open_raiser = p
                    per_player[p].was_open_raiser = True
                elif prior_raises == 1:
                    three_better = p
                    per_player[p].made_3bet = True
                elif prior_raises == 2:
                    per_player[p].made_4bet = True
                raise_count += 1
                last_raiser = p
            elif action in FOLD_ACTIONS:
                folded.add(p)
                if open_raiser == p and prior_raises >= 2:
                    per_player[p].folded_to_3bet = True
                if three_better == p and prior_raises >= 3:
                    per_player[p].folded_to_4bet = True

        if not progressed:
            break

    survivors = {p for p in order if p not in folded}
    return PreflopAnalysis(
        per_player=per_player,
        last_raiser=last_raiser,
        survivors=survivors,
        raise_count=raise_count,
    )


# ---------------------------------------------------------------------------
# Post-flop sequence walker (one street)
# ---------------------------------------------------------------------------

def analyze_postflop_street(
    actions_by_position: Mapping[int, str],
    survivors_in: set[int],
    num_players: int,
) -> StreetAnalysis:
    """Walk the interleaved action sequence for one post-flop street.

    Parameters
    ----------
    actions_by_position
        Mapping from player position to their action string for THIS street
        (e.g. the value at "stage": "f" for the flop). Players missing from
        the mapping are treated as having no actions on this street.
    survivors_in
        Set of player positions still in the hand at the START of this street
        (i.e. who saw this street). Players not in this set are skipped.
    num_players
        The hand's player count, used to determine action order.

    Returns
    -------
    StreetAnalysis
        Per-player events, first / last aggressor positions, and the set of
        survivors at the END of this street (input to the next street).
    """
    order = [p for p in postflop_action_order(num_players) if p in survivors_in]
    cursors: dict[int, int] = {p: 0 for p in order}
    folded: set[int] = set()

    per_player: dict[int, PerPlayerStreetEvents] = {
        p: PerPlayerStreetEvents(saw_street=True) for p in order
    }

    aggressor_count = 0
    first_aggressor: int | None = None
    last_aggressor:  int | None = None

    while True:
        progressed = False
        for p in order:
            actions = actions_by_position.get(p, "")
            if p in folded or cursors[p] >= len(actions):
                continue
            action = actions[cursors[p]]
            cursors[p] += 1
            progressed = True

            facing_aggression = aggressor_count > 0

            if action in AGGRESSIVE_ACTIONS:
                if facing_aggression:
                    per_player[p].raises += 1
                    per_player[p].faced_aggression = True
                    per_player[p].raised_facing_aggression = True
                else:
                    per_player[p].bets += 1
                    if first_aggressor is None:
                        first_aggressor = p
                        per_player[p].was_first_aggressor = True
                aggressor_count += 1
                last_aggressor = p
            elif action in CALL_ACTIONS:
                per_player[p].calls += 1
                per_player[p].faced_aggression = True
            elif action in CHECK_ACTIONS:
                per_player[p].checks += 1
                # A check is by definition NOT facing aggression (you cannot
                # check if someone has already bet) — leave faced_aggression alone.
            elif action in FOLD_ACTIONS:
                per_player[p].folds += 1
                folded.add(p)
                if facing_aggression:
                    per_player[p].faced_aggression = True
                    per_player[p].folded_to_aggression = True

        if not progressed:
            break

    if last_aggressor is not None:
        per_player[last_aggressor].was_last_aggressor = True

    survivors_out = {p for p in order if p not in folded}
    return StreetAnalysis(
        per_player=per_player,
        first_aggressor=first_aggressor,
        last_aggressor=last_aggressor,
        survivors=survivors_out,
    )
