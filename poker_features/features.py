"""Per-player feature accumulator, hand-level update, and finalisation.

Public entry points used by the pipeline:

* :func:`update_from_hand`
    Given the per-name accumulator dictionary and a single hand dict,
    reconstruct the cross-player betting sequence ONCE for each street and
    fan out per-player updates.

* :func:`finalize_player`
    Convert one populated :class:`PlayerAccumulator` into the flat dict that
    is written to CSV / JSON.

:data:`CSV_FIELDS` lists the output columns in canonical order.

Metric catalogue
----------------
Pre-flop (unchanged from v2)::

    vpip_pct             100 * vpip_hands / hands
    pfr_pct              100 * pfr_hands  / hands
    3bet_pct             100 * made_3bet  / opp_3bet
    fold_to_3bet_pct     100 * folded_to_3bet / faced_3bet_as_opener
    4bet_pct             100 * made_4bet  / opp_4bet
    fold_to_4bet_pct     100 * folded_to_4bet / faced_4bet_as_3better

Post-flop, computed independently for ``flop``, ``turn`` and ``river``
(prefixes ``flop_``, ``turn_``, ``river_``) **and** as an aggregate over
all three streets (prefix ``postflop_``)::

    *_af                 (bets + raises) / calls            on this street
    *_cbet_pct           100 * cbet_made / cbet_opps        on this street
    *_donk_pct           100 * donk_made / donk_opps        on this street
    *_fold_pct           100 * hands folded-when-facing-bet / hands facing bet
    *_raise_pct          100 * hands raised-when-facing-bet / hands facing bet

C-bet chain across streets:

    flop_cbet_opp  := preflop aggressor + saw flop
    turn_cbet_opp  := flop aggressor    + saw turn
    river_cbet_opp := turn aggressor    + saw river

Donk chain (OOP defender leading into the previous street's aggressor):

    flop_donk_opp  := not-PFR              + OOP rel. to PFR              + saw flop
    turn_donk_opp  := not-flop-aggressor   + OOP rel. to flop aggressor   + saw turn
    river_donk_opp := not-turn-aggressor   + OOP rel. to turn aggressor   + saw river

A donk opportunity only exists when the previous street had aggression (i.e.
an aggressor exists). If everyone checked the flop, no one has a turn-donk
opportunity that hand.

Showdown & outcome (unchanged)::

    wtsd_pct             100 * showdown_hands / flop.saw_hands
    wsd_pct              100 * showdown_wins  / showdown_hands
    win_rate             wins / hands
    chips_per_hand       net_amount / hands
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .actions import (
    is_preflop_raiser,
    is_voluntary_preflop,
    stage_actions,
)
from .sequence import (
    PerPlayerPreflopEvents,
    PerPlayerStreetEvents,
    acts_before,
    analyze_postflop_street,
    analyze_preflop,
)


# ---------------------------------------------------------------------------
# Per-street counter block
# ---------------------------------------------------------------------------

@dataclass
class StreetCounters:
    """Accumulated event tallies for a single post-flop street.

    ``saw_hands`` is the universal denominator for "would have been able to
    do something on this street." Event counters (``bets`` ... ``folds``)
    drive aggression factor. Per-hand binary tallies (``faced_aggression_*``,
    ``cbet_*``, ``donk_*``) drive the percentage metrics.
    """

    # Event counters (each per-hand event)
    bets:   int = 0  # first chips into the pot on this street
    raises: int = 0  # raised an existing bet/raise
    calls:  int = 0
    checks: int = 0
    folds:  int = 0

    # Hand counters
    saw_hands:                       int = 0  # saw the street at all (was a survivor coming in)
    faced_aggression_hands:          int = 0  # had >=1 action while facing a bet/raise
    folded_to_aggression_hands:      int = 0  # of the above, folded
    raised_facing_aggression_hands:  int = 0  # of the above, raised

    # C-bet chain (denominator depends on previous-street aggressor)
    cbet_opp_hands:  int = 0
    cbet_made_hands: int = 0

    # Donk (denominator: OOP defender saw street + previous-street aggressor exists)
    donk_opp_hands:  int = 0
    donk_made_hands: int = 0


# ---------------------------------------------------------------------------
# Player accumulator
# ---------------------------------------------------------------------------

@dataclass
class PlayerAccumulator:
    """Raw running counters for one player across the streaming pass.

    Normalisation into rates / ratios happens once at the end in
    :func:`finalize_player`; the accumulator itself stays in integer space so
    it is cheap to update per hand and exactly reproducible.
    """

    # Volume
    hands:         int = 0
    first_seen_ts: int | None = None
    last_seen_ts:  int | None = None
    months: set[str] = field(default_factory=set)
    games:  set[str] = field(default_factory=set)

    # Pre-flop basic (single-string driven)
    vpip_hands: int = 0
    pfr_hands:  int = 0

    # Pre-flop sequence-driven
    opp_3bet_hands:                 int = 0
    made_3bet_hands:                int = 0
    opener_facing_3bet_hands:       int = 0
    folded_to_3bet_hands:           int = 0
    opp_4bet_hands:                 int = 0
    made_4bet_hands:                int = 0
    three_bettor_facing_4bet_hands: int = 0
    folded_to_4bet_hands:           int = 0

    # Post-flop, per street
    flop:  StreetCounters = field(default_factory=StreetCounters)
    turn:  StreetCounters = field(default_factory=StreetCounters)
    river: StreetCounters = field(default_factory=StreetCounters)

    # Showdown
    showdown_hands: int = 0
    showdown_wins:  int = 0

    # Outcome
    wins:       int = 0
    win_amount: int = 0
    total_bet:  int = 0
    net_amount: int = 0


# ---------------------------------------------------------------------------
# Per-street helper
# ---------------------------------------------------------------------------

def _update_street(
    counters: StreetCounters,
    events: PerPlayerStreetEvents | None,
    *,
    is_prev_street_aggressor: bool,
    prev_street_aggressor_position: int | None,
    my_position: int,
    num_players: int,
) -> None:
    """Fold one hand's per-street events into the player's running counters.

    ``is_prev_street_aggressor`` is True iff this player was the player whose
    c-bet on THIS street we are tracking (the pre-flop aggressor for the
    flop, the flop aggressor for the turn, etc.).

    ``prev_street_aggressor_position`` is that same aggressor's position; it
    is needed independently because the donk denominator requires this
    player to be OOP relative to that aggressor.
    """
    if events is None or not events.saw_street:
        return

    counters.saw_hands += 1
    counters.bets   += events.bets
    counters.raises += events.raises
    counters.calls  += events.calls
    counters.checks += events.checks
    counters.folds  += events.folds

    if events.faced_aggression:
        counters.faced_aggression_hands += 1
        if events.folded_to_aggression:
            counters.folded_to_aggression_hands += 1
        if events.raised_facing_aggression:
            counters.raised_facing_aggression_hands += 1

    if is_prev_street_aggressor:
        counters.cbet_opp_hands += 1
        if events.was_first_aggressor:
            counters.cbet_made_hands += 1

    if (
        prev_street_aggressor_position is not None
        and my_position != prev_street_aggressor_position
        and acts_before(my_position, prev_street_aggressor_position, num_players)
    ):
        counters.donk_opp_hands += 1
        if events.was_first_aggressor:
            counters.donk_made_hands += 1


# ---------------------------------------------------------------------------
# Per-hand update for a single player
# ---------------------------------------------------------------------------

def update_player(
    acc: PlayerAccumulator,
    player_data: dict,
    hand_meta: dict,
    *,
    preflop_events: PerPlayerPreflopEvents,
    flop_events:    PerPlayerStreetEvents | None,
    turn_events:    PerPlayerStreetEvents | None,
    river_events:   PerPlayerStreetEvents | None,
    preflop_aggressor: int | None,
    flop_aggressor:    int | None,
    turn_aggressor:    int | None,
    num_players: int,
) -> None:
    """Update ``acc`` with the events of one hand for one player.

    Cross-player flags (per-street events and street aggressors) must be
    pre-computed at the hand level by :func:`update_from_hand`.
    """
    acc.hands += 1
    pos = player_data["position"]

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
    # The PDB only records pocket cards when shown -> two known cards is a
    # tight proxy for "went to showdown".
    pocket = player_data.get("pocket_cards") or []
    went_to_showdown = isinstance(pocket, list) and len(pocket) == 2
    if went_to_showdown:
        acc.showdown_hands += 1
        if win > 0:
            acc.showdown_wins += 1

    # ---- pre-flop, single-string driven --------------------------------
    bets    = player_data.get("bets") or []
    preflop = stage_actions(bets, "p")
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

    # ---- post-flop, per street ------------------------------------------
    _update_street(
        acc.flop, flop_events,
        is_prev_street_aggressor=(preflop_aggressor is not None and pos == preflop_aggressor),
        prev_street_aggressor_position=preflop_aggressor,
        my_position=pos,
        num_players=num_players,
    )
    _update_street(
        acc.turn, turn_events,
        is_prev_street_aggressor=(flop_aggressor is not None and pos == flop_aggressor),
        prev_street_aggressor_position=flop_aggressor,
        my_position=pos,
        num_players=num_players,
    )
    _update_street(
        acc.river, river_events,
        is_prev_street_aggressor=(turn_aggressor is not None and pos == turn_aggressor),
        prev_street_aggressor_position=turn_aggressor,
        my_position=pos,
        num_players=num_players,
    )


# ---------------------------------------------------------------------------
# Hand-level orchestration
# ---------------------------------------------------------------------------

def update_from_hand(
    accs: dict[str, PlayerAccumulator],
    hand: dict,
) -> None:
    """Update each involved player's accumulator with the events of one hand.

    Reconstructs the global betting sequence for each of the four streets,
    then fans out a per-player update with the relevant cross-player flags.
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

    by_position:    dict[int, tuple[str, dict]] = {}
    preflop_by_pos: dict[int, str] = {}
    flop_by_pos:    dict[int, str] = {}
    turn_by_pos:    dict[int, str] = {}
    river_by_pos:   dict[int, str] = {}

    for name, data in players.items():
        if not isinstance(data, dict):
            continue
        pos = data.get("position")
        if not isinstance(pos, int):
            continue
        by_position[pos] = (name, data)
        bets = data.get("bets") or []
        preflop_by_pos[pos] = stage_actions(bets, "p")
        flop_by_pos[pos]    = stage_actions(bets, "f")
        turn_by_pos[pos]    = stage_actions(bets, "t")
        river_by_pos[pos]   = stage_actions(bets, "r")

    pre  = analyze_preflop(preflop_by_pos, num_players)
    flop  = analyze_postflop_street(flop_by_pos,  pre.survivors,  num_players)
    turn  = analyze_postflop_street(turn_by_pos,  flop.survivors, num_players)
    river = analyze_postflop_street(river_by_pos, turn.survivors, num_players)

    for pos, (name, data) in by_position.items():
        update_player(
            accs[name], data, meta,
            preflop_events=pre.per_player.get(pos) or PerPlayerPreflopEvents(),
            flop_events=flop.per_player.get(pos),
            turn_events=turn.per_player.get(pos),
            river_events=river.per_player.get(pos),
            preflop_aggressor=pre.last_raiser,
            flop_aggressor=flop.last_aggressor,
            turn_aggressor=turn.last_aggressor,
            num_players=num_players,
        )


# ---------------------------------------------------------------------------
# Finalisation
# ---------------------------------------------------------------------------

def _pct(num: int, denom: int, digits: int = 2) -> float | None:
    """Return ``100 * num / denom`` rounded to ``digits`` decimals.

    Returns ``None`` (not ``0.0``) when ``denom`` is zero so "no
    observations" never collapses into "observed 0 %".
    """
    return None if denom == 0 else round(100.0 * num / denom, digits)


def _ratio(num: int, denom: int, digits: int = 4) -> float | None:
    """Return ``num / denom`` rounded to ``digits`` decimals, ``None`` when
    ``denom`` is zero."""
    return None if denom == 0 else round(num / denom, digits)


def _street_metrics(s: StreetCounters, prefix: str) -> dict[str, float | None]:
    """Derive the five per-street metrics for one street block."""
    bets_raises = s.bets + s.raises
    return {
        f"{prefix}_af":         _ratio(bets_raises, s.calls),
        f"{prefix}_cbet_pct":   _pct(s.cbet_made_hands,             s.cbet_opp_hands),
        f"{prefix}_donk_pct":   _pct(s.donk_made_hands,             s.donk_opp_hands),
        f"{prefix}_fold_pct":   _pct(s.folded_to_aggression_hands,  s.faced_aggression_hands),
        f"{prefix}_raise_pct":  _pct(s.raised_facing_aggression_hands, s.faced_aggression_hands),
    }


def finalize_player(name: str, acc: PlayerAccumulator) -> dict[str, Any]:
    """Convert a populated :class:`PlayerAccumulator` into a flat row dict.

    Percentages live in ``[0, 100]`` (or ``None``). The aggression factor
    ``*_af`` is an unbounded ratio. ``None`` is emitted whenever a metric's
    denominator is zero, so the same value round-trips through both JSON
    (``null``) and CSV (empty cell).
    """
    f, t, r = acc.flop, acc.turn, acc.river

    # ---- overall postflop aggregates ----------------------------------------
    total_bets   = f.bets   + t.bets   + r.bets
    total_raises = f.raises + t.raises + r.raises
    total_calls  = f.calls  + t.calls  + r.calls

    total_cbet_opp  = f.cbet_opp_hands  + t.cbet_opp_hands  + r.cbet_opp_hands
    total_cbet_made = f.cbet_made_hands + t.cbet_made_hands + r.cbet_made_hands
    total_donk_opp  = f.donk_opp_hands  + t.donk_opp_hands  + r.donk_opp_hands
    total_donk_made = f.donk_made_hands + t.donk_made_hands + r.donk_made_hands

    total_faced  = f.faced_aggression_hands         + t.faced_aggression_hands         + r.faced_aggression_hands
    total_folded = f.folded_to_aggression_hands     + t.folded_to_aggression_hands     + r.folded_to_aggression_hands
    total_raised = f.raised_facing_aggression_hands + t.raised_facing_aggression_hands + r.raised_facing_aggression_hands

    row: dict[str, Any] = {
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
        "3bet_pct":          _pct(acc.made_3bet_hands,      acc.opp_3bet_hands),
        "fold_to_3bet_pct":  _pct(acc.folded_to_3bet_hands, acc.opener_facing_3bet_hands),
        "4bet_pct":          _pct(acc.made_4bet_hands,      acc.opp_4bet_hands),
        "fold_to_4bet_pct":  _pct(acc.folded_to_4bet_hands, acc.three_bettor_facing_4bet_hands),
    }

    # per-street post-flop
    row.update(_street_metrics(f, "flop"))
    row.update(_street_metrics(t, "turn"))
    row.update(_street_metrics(r, "river"))

    # overall post-flop
    row.update({
        "postflop_af":        _ratio(total_bets + total_raises, total_calls),
        "postflop_cbet_pct":  _pct(total_cbet_made, total_cbet_opp),
        "postflop_donk_pct":  _pct(total_donk_made, total_donk_opp),
        "postflop_fold_pct":  _pct(total_folded,    total_faced),
        "postflop_raise_pct": _pct(total_raised,    total_faced),
    })

    row.update({
        # showdown
        "wtsd_pct":       _pct(acc.showdown_hands, f.saw_hands),
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
    })
    return row


CSV_FIELDS: list[str] = [
    "player", "hands", "months_active", "first_seen_ts", "last_seen_ts", "games",

    "vpip_pct", "pfr_pct",
    "3bet_pct", "fold_to_3bet_pct", "4bet_pct", "fold_to_4bet_pct",

    "flop_af",  "flop_cbet_pct",  "flop_donk_pct",  "flop_fold_pct",  "flop_raise_pct",
    "turn_af",  "turn_cbet_pct",  "turn_donk_pct",  "turn_fold_pct",  "turn_raise_pct",
    "river_af", "river_cbet_pct", "river_donk_pct", "river_fold_pct", "river_raise_pct",

    "postflop_af", "postflop_cbet_pct", "postflop_donk_pct",
    "postflop_fold_pct", "postflop_raise_pct",

    "wtsd_pct", "wsd_pct", "showdown_hands", "known_pocket_cards_hands",
    "wins", "win_rate", "win_amount", "total_bet", "net_amount", "chips_per_hand",
]


def new_accumulator_dict() -> dict[str, PlayerAccumulator]:
    """Convenience factory: a ``defaultdict`` returning fresh accumulators."""
    return defaultdict(PlayerAccumulator)
