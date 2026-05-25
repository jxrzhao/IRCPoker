#!/usr/bin/env python3
"""plot_player_style_distributions.py — distributions of player style metrics.

Reads ``processed/nolimit_holdem/player_features.csv`` (output of
``python -m poker_features``) and plots the marginal distribution of every
style metric across all players. Every player is drawn as a single point,
coloured by their ``net_amount`` (gross chips won minus gross chips bet) so
the same chart reveals both the *shape* of each metric's distribution and
the *outcome* of the players sitting at each point.

Metrics plotted (13 panels, auto-laid-out in a 5x3 grid):

    pre-flop:   VPIP, PFR, 3-bet, fold-to-3-bet, 4-bet, fold-to-4-bet
    post-flop:  AF, Aggression %, C-bet, Donk
    showdown:   WTSD, W$SD
    outcome:    Win Rate

Each panel has two stacked sub-axes:

    Top    A thin grey histogram of the metric across the player population.
           Conveys the marginal density / shape independently of colour.
    Bottom A jittered "strip plot" (1-D scatter): one dot per player, x =
           metric value, y = small random offset, colour = net_amount. The
           jitter only spreads the points vertically so they do not occlude
           each other; the vertical axis carries no quantitative meaning.

A single shared colorbar on the right encodes ``net_amount`` with a diverging
red/blue colormap centred at 0 (red = lost chips, blue = won chips). Because
net_amount has very heavy tails (a handful of players are tens of thousands of
chips up or down while most are near zero), we use a symmetric log
normalisation (``SymLogNorm``):

  * Linear behaviour for |net_amount| <= ``linthresh`` (default = the median of
    |net_amount| over included players, so half of all players land in the
    linear region).
  * Logarithmic behaviour beyond, with the colour scale capped at the
    ``--clip-pct`` percentile of |net_amount| (default 99) so a few extreme
    winners or losers do not bleach out everyone else's colour.

Usage
-----
    # Default: read processed/nolimit_holdem/player_features.csv,
    # write PNG + SVG next to it.
    python scripts/plot_player_style_distributions.py

    # Restrict to players with enough sample size to be meaningful, override paths:
    python scripts/plot_player_style_distributions.py \\
        --min-hands 200 \\
        --output-png /tmp/styles.png \\
        --output-svg /tmp/styles.svg
"""

from __future__ import annotations

import argparse
import csv
import os
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import SymLogNorm
from matplotlib.gridspec import GridSpec


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Metric:
    key:    str   # column name in player_features.csv
    label:  str   # short axis title
    desc:   str   # one-line explanation under the label
    unit:   str   # "%" or "" — controls x-axis ticker formatting only


METRICS: tuple[Metric, ...] = (
    # ---- pre-flop style ------------------------------------------------
    Metric("vpip_pct",         "VPIP",          "voluntary $ in pot, preflop",      "%"),
    Metric("pfr_pct",          "PFR",           "preflop raise rate",               "%"),
    Metric("3bet_pct",         "3-bet",         "raise facing 1 prior raise",       "%"),
    Metric("fold_to_3bet_pct", "Fold-to-3-bet", "opener folds when 3-bet",          "%"),
    Metric("4bet_pct",         "4-bet",         "raise facing 2 prior raises",      "%"),
    Metric("fold_to_4bet_pct", "Fold-to-4-bet", "3-bettor folds when 4-bet",        "%"),
    # ---- post-flop style ----------------------------------------------
    Metric("af_ratio",         "AF",            "(bets+raises) / calls, postflop",  ""),
    Metric("agg_pct",          "Aggression %",  "aggressive / all postflop actions","%"),
    Metric("cbet_pct",         "C-bet",         "preflop aggressor bets the flop",  "%"),
    Metric("donk_pct",         "Donk",          "OOP defender leads into PFR",      "%"),
    # ---- showdown -----------------------------------------------------
    Metric("wtsd_pct",         "WTSD",          "went to showdown | saw flop",      "%"),
    Metric("wsd_pct",          "W$SD",          "won at showdown rate",             "%"),
    # ---- outcome ------------------------------------------------------
    Metric("win_rate",         "Win Rate",      "hands won / hands",                ""),
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _to_float(value: str) -> float | None:
    """Return ``float(value)`` or ``None`` for empty / unparsable cells. We
    treat empty CSV cells as "metric undefined" (e.g. cbet_pct for a player
    that was never preflop raiser), and exclude such players from that panel.
    """
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_rows(path: Path, min_hands: int) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Load the relevant columns from ``player_features.csv``.

    Parameters
    ----------
    path
        CSV path produced by ``poker_features``.
    min_hands
        Drop players with fewer than this many hands. Keeps noisy short
        samples from dominating the chart.

    Returns
    -------
    metric_arrays
        Dict mapping metric key -> 1D float array of length N players, with
        ``np.nan`` for players where the metric is undefined.
    net_amounts
        1D float array of net_amount (same length, same order).
    """
    keys = tuple(m.key for m in METRICS)
    cols: dict[str, list[float]] = {k: [] for k in keys}
    net: list[float] = []

    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                hands = int(row["hands"])
            except (KeyError, ValueError):
                continue
            if hands < min_hands:
                continue
            net_val = _to_float(row.get("net_amount", ""))
            if net_val is None:
                continue
            net.append(net_val)
            for k in keys:
                v = _to_float(row.get(k, ""))
                cols[k].append(np.nan if v is None else v)

    return ({k: np.asarray(v, dtype=float) for k, v in cols.items()},
            np.asarray(net, dtype=float))


# ---------------------------------------------------------------------------
# Colour scale
# ---------------------------------------------------------------------------

def build_net_norm(net: np.ndarray, clip_pct: float) -> SymLogNorm:
    """Construct a symmetric-log colour normalisation centred at 0.

    The colour scale is symmetric so that "won 10k chips" and "lost 10k chips"
    sit at equally saturated ends. We cap at the ``clip_pct``-th percentile of
    ``|net|`` so a few outliers (millionaires / busted whales) don't drown out
    the bulk of the distribution. The linear threshold defaults to the median
    of ``|net|`` over the kept players, which puts roughly half the population
    in the linear region of the scale.
    """
    abs_net = np.abs(net[np.isfinite(net)])
    if abs_net.size == 0:
        return SymLogNorm(linthresh=1.0, vmin=-1.0, vmax=1.0, base=10)
    vmax = max(float(np.percentile(abs_net, clip_pct)), 1.0)
    linthresh = max(float(np.median(abs_net[abs_net > 0])) if (abs_net > 0).any() else 1.0, 1.0)
    linthresh = min(linthresh, vmax / 10.0)  # keep at least one log decade
    return SymLogNorm(linthresh=linthresh, vmin=-vmax, vmax=vmax, base=10)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def _format_percent_axis(ax, unit: str) -> None:
    """Append a ``%`` suffix to the x tick labels when the metric is a percent."""
    if unit == "%":
        ax.xaxis.set_major_formatter(lambda x, _pos: f"{x:g}%")


def _hide_spines(ax, sides=("top", "right", "left")) -> None:
    for s in sides:
        ax.spines[s].set_visible(False)


def _xlimits_for(metric: Metric, v: np.ndarray) -> tuple[float, float]:
    """Pick sensible x-axis limits for one metric.

    - Percent metrics are clamped to ``[0, 100]`` (their definitional range).
    - The win rate is clamped to ``[0, 1]``.
    - Open-ended ratios (e.g. AF) are clipped to roughly the bulk of the
      distribution (1st .. 98th percentile, padded ~5%) so a few extreme
      outliers do not flatten everyone else into a single column.
    """
    if metric.unit == "%":
        return (0.0, 100.0)
    if metric.key == "win_rate":
        return (0.0, 1.0)
    if v.size == 0:
        return (0.0, 1.0)
    lo = float(np.percentile(v, 1))
    hi = float(np.percentile(v, 98))
    if hi <= lo:
        hi = lo + 1.0
    pad = 0.05 * (hi - lo)
    return (max(0.0, lo - pad), hi + pad)


def plot_panel(
    fig,
    outer_cell,
    metric: Metric,
    values: np.ndarray,
    net: np.ndarray,
    cmap,
    norm,
    rng: np.random.Generator,
) -> object:
    """Draw one (histogram + colour-coded strip) panel for a single metric.

    Returns the scatter artist (so the caller can attach a shared colorbar).
    """
    mask = np.isfinite(values)
    v = values[mask]
    n = net[mask]
    xlim = _xlimits_for(metric, v)
    inner = outer_cell.subgridspec(2, 1, height_ratios=(1.0, 3.0), hspace=0.08)
    ax_hist = fig.add_subplot(inner[0])
    ax_strip = fig.add_subplot(inner[1], sharex=ax_hist)

    if v.size:
        ax_hist.hist(v, bins=np.linspace(xlim[0], xlim[1], 61),
                     color="#9ca3af", linewidth=0)
    ax_hist.set_yticks([])
    ax_hist.set_xticks([])
    _hide_spines(ax_hist, ("top", "right", "left", "bottom"))
    ax_hist.set_title(
        f"{metric.label}    (n={v.size:,})\n{metric.desc}",
        loc="left", fontsize=10, pad=6, linespacing=1.15,
    )

    if v.size:
        order = np.argsort(np.abs(n))  # draw extreme nets on top so colour is visible
        y_jitter = rng.uniform(-0.4, 0.4, size=v.size)
        sc = ax_strip.scatter(
            v[order], y_jitter[order],
            c=n[order], cmap=cmap, norm=norm,
            s=7, alpha=0.55, linewidths=0,
        )
    else:
        sc = ax_strip.scatter([], [], c=[], cmap=cmap, norm=norm)

    ax_strip.set_xlim(*xlim)
    ax_strip.set_yticks([])
    ax_strip.set_ylim(-0.7, 0.7)
    _hide_spines(ax_strip, ("top", "right", "left"))
    _format_percent_axis(ax_strip, metric.unit)
    ax_strip.tick_params(axis="x", labelsize=10, length=4)
    ax_strip.grid(axis="x", linestyle=":", color="#d1d5db", linewidth=0.8, zorder=0)

    return sc


def _grid_shape(n_panels: int) -> tuple[int, int]:
    """Pick a (rows, cols) grid for ``n_panels`` panels.

    Heuristic: 3 columns once there are >= 9 panels (keeps the figure from
    becoming absurdly tall), otherwise 2 columns. Single-column for very few
    panels.
    """
    if n_panels <= 2:
        return (n_panels, 1)
    if n_panels <= 8:
        return ((n_panels + 1) // 2, 2)
    cols = 3
    rows = (n_panels + cols - 1) // cols
    return (rows, cols)


def _figure_size(rows: int, cols: int) -> tuple[float, float]:
    """Pick a sensible figure size for the given grid."""
    return (5.5 * cols, 2.9 * rows + 1.5)


def plot_distributions(
    metric_arrays: dict[str, np.ndarray],
    net: np.ndarray,
    output_png: Path,
    output_svg: Path | None,
    clip_pct: float,
    seed: int,
    cmap_name: str = "RdBu",
) -> None:
    """Render the figure to ``output_png`` and optionally ``output_svg``.

    The grid shape adapts to ``len(METRICS)`` so adding or removing metrics
    only requires editing the ``METRICS`` tuple.
    """
    rows, cols = _grid_shape(len(METRICS))
    fig_w, fig_h = _figure_size(rows, cols)
    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = GridSpec(
        rows, cols, figure=fig,
        hspace=0.75, wspace=0.20,
        left=0.05, right=0.90,
        top=1 - 1.0 / fig_h, bottom=1.0 / fig_h,
    )

    cmap = plt.get_cmap(cmap_name)
    norm = build_net_norm(net, clip_pct=clip_pct)
    rng  = np.random.default_rng(seed)

    last_sc = None
    for i, metric in enumerate(METRICS):
        r, c = divmod(i, cols)
        sc = plot_panel(
            fig, gs[r, c], metric,
            metric_arrays[metric.key], net,
            cmap, norm, rng,
        )
        last_sc = sc

    if last_sc is not None:
        cax = fig.add_axes([0.92, 0.10, 0.018, 0.78])
        cbar = fig.colorbar(last_sc, cax=cax, extend="both")
        cbar.set_label("net_amount  (chips won − chips bet)", fontsize=10)
        cbar.ax.tick_params(labelsize=9)

    fig.suptitle(
        "Player style metric distributions, coloured by net chips won",
        x=0.05, y=1 - 0.30 / fig_h, ha="left", fontsize=14, fontweight="bold",
    )
    fig.text(
        0.05, 1 - 0.65 / fig_h,
        f"n = {np.isfinite(net).sum():,} players  ·  "
        f"{len(METRICS)} style metrics  ·  "
        "blue = winning  ·  red = losing  ·  SymLog colour scale",
        ha="left", fontsize=9, color="#4b5563",
    )

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=150)
    if output_svg is not None:
        output_svg.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_svg)
    plt.close(fig)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input", type=Path,
        default=Path("processed/nolimit_holdem/player_features.csv"),
        help="player feature CSV (default: %(default)s)",
    )
    parser.add_argument(
        "--output-png", type=Path,
        default=Path("processed/nolimit_holdem/player_style_distributions.png"),
        help="PNG output path (default: %(default)s)",
    )
    parser.add_argument(
        "--output-svg", type=Path,
        default=Path("processed/nolimit_holdem/player_style_distributions.svg"),
        help="SVG output path; pass an empty string to skip (default: %(default)s)",
    )
    parser.add_argument(
        "--min-hands", type=int, default=100,
        help="drop players with fewer than this many hands (default: %(default)s)",
    )
    parser.add_argument(
        "--clip-pct", type=float, default=99.0,
        help="percentile of |net_amount| to clip the colour scale to (default: %(default)s)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="RNG seed for reproducible jitter (default: %(default)s)",
    )
    parser.add_argument(
        "--cmap", type=str, default="RdBu",
        help="diverging colormap name (default: %(default)s; reversed automatically would invert meaning)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise SystemExit(f"input not found: {args.input}")

    metric_arrays, net = load_rows(args.input, min_hands=args.min_hands)
    if net.size == 0:
        raise SystemExit(
            f"no players satisfy --min-hands {args.min_hands}; "
            f"nothing to plot."
        )

    output_svg = args.output_svg if str(args.output_svg) else None
    plot_distributions(
        metric_arrays=metric_arrays,
        net=net,
        output_png=args.output_png,
        output_svg=output_svg,
        clip_pct=args.clip_pct,
        seed=args.seed,
        cmap_name=args.cmap,
    )

    print(
        f"wrote {args.output_png}"
        + (f" and {output_svg}" if output_svg is not None else "")
        + f"  (n = {net.size:,} players, min_hands = {args.min_hands})"
    )


if __name__ == "__main__":
    main()
