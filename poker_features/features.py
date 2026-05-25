"""Per-player feature accumulator + hand-level update + finalisation.

Two public entry points are intended for use by the pipeline:

* :func:`update_from_hand`
    Given a per-name accumulator dictionary and a single hand dict, compute
    cross-player events for the hand once (via
    :mod:`poker_features.sequence`) and then update each involved player's
    accumulator with both their own action stats and the cross-player flags.

* :func:`finalize_player`
    Convert one filled :class:`PlayerAccumulator` into a flat dictionary of
    derived features (the row that ends up in CSV / JSON).

:data:`CSV_FIELDS` lists the output columns in their canonical order.

Metric definitions
------------------
See the docstring of the top-level package and ``CSV_FIELDS`` below for the
full list. The key additions over the v1 release are five **sequence-aware**
metrics:

    3bet_pct             100 * made_3bet / opp_3bet
    fold_to_3bet_pct     100 * folded_to_3bet / faced_3bet_as_opener
    4bet_pct             100 * made_4bet / opp_4bet
    fold_to_4bet_pct     100 * folded_to_4bet / faced_4bet_as_3better
    donk_pct             100 * (OOP defender bet flop first) / (OOP defender saw flop)

OOP-defender donk: a player who *called* the pre-flop aggressor's raise, was
out-of-position post-flop, saw the flop, and fired the first bet (a "donk
bet") rather than checking to the pre-flop raiser.

The c-bet definition was tightened to require being the **last** pre-flop
raiser (i.e. the pre-flop aggressor), not just any pre-flop raiser. In single-
raised pots this is identical to the previous definition; in 3-bet+ pots it
correctly attributes c-bets to the last aggressor.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .actions import (
    AGGRESSIVE_ACTIONS,
    CALL_ACTIONS,
    CHECK_ACTIONS,
    POSTFLOP_STAGES,
    first_nonblind_is_bet,
    is_preflop_raiser,
    is_voluntary_preflop,
    stage_actions,
)
from .sequence import (
    PerPlayerPreflopEvents,
    acts_before,
    analyze_preflop,
)


# ---------------------------------------------------------------------------
# Accumulator
# ---------------------------------------------------------------------------

@dataclass
class PlayerAccumulator:
    """Running counters used to derive a single player's features in a
    streaming pass. All fields are raw integer event tallies; normalisation
    happens in :func:`finalize_player`.
    """

    # Volume
    hands: int = 0
    first_seen_ts: int | None = None
    last_seen_ts:  int | None = None
    months: set[str] = field(default_factory=set)
    games:  set[str] = field(default_factory=set)

    # Pre-flop basic (single-string driven)
    vpip_hands: int = 0
    pfr_hands: int = 0

    # Pre-flop sequence-driven
    opp_3bet_hands:                   int = 0
    made_3bet_hands:                  int = 0
    opener_facing_3bet_hands:         int = 0  # denominator of fold_to_3bet
    folded_to_3bet_hands:             int = 0
    opp_4bet_hands:                   int = 0
    made_4bet_hands:                  int = 0
    three_bettor_facing_4bet_hands:   int = 0  # denominator of fold_to_4bet
    folded_to_4bet_hands:             int = 0

    # Post-flop style (event-level over flop / turn / river)
    postflop_bets_raises: int = 0
    postflop_calls: int = 0
    postflop_checks: int = 0

    # Continuation bet (last pre-flop raiser fires the flop)
    cbet_opps: int = 0
    cbet_made: int = 0

    # Donk bet (OOP defender leads into the pre-flop aggressor)
    donk_opps: int = 0
    donk_made: int = 0

    # Post-flop saw-flop count (denominator for WTSD)
    saw_flop_hands: int = 0

    # Showdown
    showdown_hands: int = 0
    showdown_wins:  int = 0

    # Outcome
    wins: int = 0
    win_amount: int = 0
    total_bet: int = 0
    net_amount: int = 0


# ---------------------------------------------------------------------------
# Per-hand event tallying for a single player
# ---------------------------------------------------------------------------

def _count_postflop_events(bets: list[dict], acc: PlayerAccumulator) -> None:
    """Tally per-action bets/raises/calls/checks across flop, turn and river."""
    for stage in POSTFLOP_STAGES:
        for c in stage_actions(bets, stage):
            if c in AGGRESSIVE_ACTIONS:
                acc.postflop_bets_raises += 1
            elif c in CALL_ACTIONS:
                acc.postflop_calls += 1
            elif c in CHECK_ACTIONS:
                acc.postflop_checks += 1


def update_player(
    acc: PlayerAccumulator,
    player_data: dict,
    hand_meta: dict,
    *,
    preflop_events: PerPlayerPreflopEvents,
    is_last_preflop_raiser: bool,
    is_oop_defender: bool,
) -> None:
    """Update ``acc`` with the events of one hand for one player.

    The cross-player flags (``preflop_events``, ``is_last_preflop_raiser``,
    ``is_oop_defender``) must be pre-computed at the hand level by
    :func:`update_from_hand` — they cannot be derived from this player's
    action string alone.
    """
    acc.hands += 1

    ts = hand_meta.get("timestamp")
    if isinstance(ts, int):
        acc.first_seen_ts = ts if acc.first_seen_ts is None else min(acc.first_seen_ts, ts)
        acc.last_seen_ts  = ts if acc.last_seen_ts  is None else max(acc.last_seen_ts,  ts)
    month = hand_meta.get("month")
    if isinstance(month, str):
        acc.months.add(month)
    game = hand_meta.get("game")
    if isinstance(game, str):
        acc.games.add(game)

    # ---- outcome --------------------------------------------------------
    win = int(player_data.get("total_win") or 0)
    bet = int(player_data.get("total_bet") or 0)
    acc.win_amount += win
    acc.total_bet  += bet
    acc.net_amount += (win - bet)
    if win > 0:
        acc.wins += 1

    # ---- showdown -------------------------------------------------------
    # The PDB only records pocket cards when shown, so two known pocket cards
    # is a tight proxy for "went to showdown".
    pocket = player_data.get("pocket_cards") or []
    went_to_showdown = isinstance(pocket, list) and len(pocket) == 2
    if went_to_showdown:
        acc.showdown_hands += 1
        if win > 0:
            acc.showdown_wins += 1

    # ---- pre-flop, single-string driven --------------------------------
    bets    = player_data.get("bets") or []
    preflop = stage_actions(bets, "p")
    flop    = stage_actions(bets, "f")

    if is_voluntary_preflop(preflop):
        acc.vpip_hands += 1
    if is_preflop_raiser(preflop):
        acc.pfr_hands += 1

    # ---- pre-flop, sequence-driven --------------------------------------
    e = preflop_events
    if e.opp_3bet:
        acc.opp_3bet_hands += 1
    if e.made_3bet:
        acc.made_3bet_hands += 1
    if e.faced_3bet_as_opener:
        acc.opener_facing_3bet_hands += 1
        if e.folded_to_3bet:
            acc.folded_to_3bet_hands += 1
    if e.opp_4bet:
        acc.opp_4bet_hands += 1
    if e.made_4bet:
        acc.made_4bet_hands += 1
    if e.faced_4bet_as_3better:
        acc.three_bettor_facing_4bet_hands += 1
        if e.folded_to_4bet:
            acc.folded_to_4bet_hands += 1

    # ---- post-flop ------------------------------------------------------
    if flop:
        acc.saw_flop_hands += 1
        first_was_bet = first_nonblind_is_bet(flop)
        if is_last_preflop_raiser:
            acc.cbet_opps += 1
            if first_was_bet:
                acc.cbet_made += 1
        if is_oop_defender:
            acc.donk_opps += 1
            if first_was_bet:
                acc.donk_made += 1

    _count_postflop_events(bets, acc)


# ---------------------------------------------------------------------------
# Hand-level orchestration
# ---------------------------------------------------------------------------

def update_from_hand(
    accs: dict[str, PlayerAccumulator],
    hand: dict,
) -> None:
    """Update each involved player's accumulator with the events of one hand.

    This is the only function the streaming pipeline needs to call. It:

      1. Indexes the hand's players by table position.
      2. Reconstructs the pre-flop betting sequence once.
      3. Derives ``is_last_preflop_raiser`` and ``is_oop_defender`` flags
         for each player from the sequence result.
      4. Delegates to :func:`update_player` for each player.
    """
    players = hand.get("players") or {}
    if not isinstance(players, dict):
        return
    num_players = int(hand.get("num_players", len(players)) or 0)

    meta = {
        "timestamp": hand.get("timestamp"),
        "month":     hand.get("month"),
        "game":      hand.get("game"),
    }

    # Index players by position, gather pre-flop action strings.
    by_position:     dict[int, tuple[str, dict]] = {}
    preflop_by_pos:  dict[int, str] = {}
    for name, data in players.items():
        if not isinstance(data, dict):
            continue
        pos = data.get("position")
        if not isinstance(pos, int):
            continue
        by_position[pos] = (name, data)
        preflop_by_pos[pos] = stage_actions(data.get("bets") or [], "p")

    analysis = analyze_preflop(preflop_by_pos, num_players)
    aggressor = analysis.last_raiser

    for pos, (name, data) in by_position.items():
        events = analysis.per_player.get(pos) or PerPlayerPreflopEvents()
        is_aggressor = (aggressor is not None) and (pos == aggressor)
        is_oop_defender = (
            aggressor is not None
            and pos != aggressor
            and pos in analysis.survivors
            and acts_before(pos, aggressor, num_players)
        )
        update_player(
            accs[name], data, meta,
            preflop_events=events,
            is_last_preflop_raiser=is_aggressor,
            is_oop_defender=is_oop_defender,
        )


# ---------------------------------------------------------------------------
# Finalisation
# ---------------------------------------------------------------------------

def _pct(num: int, denom: int, digits: int = 2) -> float | None:
    """Return ``100 * num / denom`` rounded to ``digits`` decimals, or ``None``
    if ``denom`` is zero. ``None`` (not ``0.0``) is used so that "no
    observations" is never confused with "observed 0 %" downstream.
    """
    return None if denom == 0 else round(100.0 * num / denom, digits)


def _ratio(num: int, denom: int, digits: int = 4) -> float | None:
    """Return ``num / denom`` rounded to ``digits`` decimals, or ``None`` if
    ``denom`` is zero."""
    return None if denom == 0 else round(num / denom, digits)


def finalize_player(name: str, acc: PlayerAccumulator) -> dict[str, Any]:
    """Convert a populated :class:`PlayerAccumulator` into a flat row dict.

    Percentages live in ``[0, 100]`` (or ``None``). Ratios are unbounded
    (e.g. ``af_ratio``) and reported as ``None`` when their denominator is
    zero. We use ``None`` rather than ``NaN`` so the same value round-trips
    cleanly through both JSON (``null``) and CSV (empty cell).
    """
    return {
        "player":         name,
        "hands":          acc.hands,
        "months_active":  len(acc.months),
        "first_seen_ts":  acc.first_seen_ts,
        "last_seen_ts":   acc.last_seen_ts,
        "games":          "|".join(sorted(acc.games)),

        # pre-flop basic
        "vpip_pct":          _pct(acc.vpip_hands, acc.hands),
        "pfr_pct":           _pct(acc.pfr_hands,  acc.hands),
        # pre-flop sequence
        "3bet_pct":          _pct(acc.made_3bet_hands,        acc.opp_3bet_hands),
        "fold_to_3bet_pct":  _pct(acc.folded_to_3bet_hands,   acc.opener_facing_3bet_hands),
        "4bet_pct":          _pct(acc.made_4bet_hands,        acc.opp_4bet_hands),
        "fold_to_4bet_pct":  _pct(acc.folded_to_4bet_hands,   acc.three_bettor_facing_4bet_hands),

        # post-flop style
        "af_ratio":  _ratio(acc.postflop_bets_raises, acc.postflop_calls),
        "agg_pct":   _pct(
            acc.postflop_bets_raises,
            acc.postflop_bets_raises + acc.postflop_calls + acc.postflop_checks,
        ),
        "cbet_pct":  _pct(acc.cbet_made, acc.cbet_opps),
        "donk_pct":  _pct(acc.donk_made, acc.donk_opps),

        # showdown
        "wtsd_pct":       _pct(acc.showdown_hands, acc.saw_flop_hands),
        "wsd_pct":        _pct(acc.showdown_wins,  acc.showdown_hands),
        "showdown_hands": acc.showdown_hands,
        "known_pocket_cards_hands": acc.showdown_hands,

        # outcome
        "wins":           acc.wins,
        "win_rate":       _ratio(acc.wins, acc.hands, digits=6),
        "win_amount":     acc.win_amount,
        "total_bet":      acc.total_bet,
        "net_amount":     acc.net_amount,
        "chips_per_hand": _ratio(acc.net_amount, acc.hands),
    }


CSV_FIELDS: list[str] = [
    "player", "hands", "months_active", "first_seen_ts", "last_seen_ts", "games",
    "vpip_pct", "pfr_pct",
    "3bet_pct", "fold_to_3bet_pct", "4bet_pct", "fold_to_4bet_pct",
    "af_ratio", "agg_pct", "cbet_pct", "donk_pct",
    "wtsd_pct", "wsd_pct", "showdown_hands", "known_pocket_cards_hands",
    "wins", "win_rate", "win_amount", "total_bet", "net_amount", "chips_per_hand",
]


def new_accumulator_dict() -> dict[str, PlayerAccumulator]:
    """Convenience factory: a ``defaultdict`` returning fresh accumulators."""
    return defaultdict(PlayerAccumulator)
