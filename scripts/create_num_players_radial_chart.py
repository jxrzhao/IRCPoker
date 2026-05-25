#!/usr/bin/env python3
"""
Create a radial chart of hand counts by num_players.

The script streams a cleaned poker hand JSONL file, counts hands by
``num_players``, and writes a standalone SVG chart. The chart includes count
and percent labels plus the total number of hands in the center.
"""

from __future__ import annotations

import argparse
import html
import json
import math
from collections import Counter
from pathlib import Path
from typing import NamedTuple


COLORS = [
    "#2563eb",
    "#16a34a",
    "#dc2626",
    "#9333ea",
    "#ea580c",
    "#0891b2",
    "#4f46e5",
    "#65a30d",
    "#be123c",
    "#7c3aed",
    "#0d9488",
    "#ca8a04",
]


class Row(NamedTuple):
    num_players: int
    hands: int
    percent: float
    color: str


def count_file(path: Path) -> tuple[Counter[int], Counter[str]]:
    counts: Counter[int] = Counter()
    stats: Counter[str] = Counter()

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                hand = json.loads(line)
            except json.JSONDecodeError:
                stats["invalid_json_lines"] += 1
                continue

            num_players = hand.get("num_players")
            if not isinstance(num_players, int):
                stats["missing_num_players"] += 1
                continue

            counts[num_players] += 1
            stats["hands"] += 1

    return counts, stats


def rows_from_counts(counts: Counter[int], total: int) -> list[Row]:
    return [
        Row(
            num_players=num_players,
            hands=counts[num_players],
            percent=(counts[num_players] / total * 100) if total else 0,
            color=COLORS[index % len(COLORS)],
        )
        for index, num_players in enumerate(sorted(counts))
    ]


def polar_to_cartesian(cx: float, cy: float, radius: float, angle: float) -> tuple[float, float]:
    return cx + radius * math.cos(angle), cy + radius * math.sin(angle)


def donut_segment_path(
    cx: float,
    cy: float,
    outer_radius: float,
    inner_radius: float,
    start_angle: float,
    end_angle: float,
) -> str:
    large_arc = 1 if end_angle - start_angle > math.pi else 0
    ox1, oy1 = polar_to_cartesian(cx, cy, outer_radius, start_angle)
    ox2, oy2 = polar_to_cartesian(cx, cy, outer_radius, end_angle)
    ix1, iy1 = polar_to_cartesian(cx, cy, inner_radius, end_angle)
    ix2, iy2 = polar_to_cartesian(cx, cy, inner_radius, start_angle)

    return (
        f"M {ox1:.3f} {oy1:.3f} "
        f"A {outer_radius} {outer_radius} 0 {large_arc} 1 {ox2:.3f} {oy2:.3f} "
        f"L {ix1:.3f} {iy1:.3f} "
        f"A {inner_radius} {inner_radius} 0 {large_arc} 0 {ix2:.3f} {iy2:.3f} Z"
    )


def format_int(value: int) -> str:
    return f"{value:,}"


def chart_svg(rows: list[Row], total: int, source: Path) -> str:
    width = 1080
    height = 760
    cx = 360
    cy = 390
    outer_radius = 250
    inner_radius = 132
    start_angle = -math.pi / 2
    label_radius = 302

    segments: list[str] = []
    labels: list[str] = []
    angle = start_angle
    for row in rows:
        sweep = (row.hands / total * math.tau) if total else 0
        end_angle = angle + sweep
        segments.append(
            f'<path d="{donut_segment_path(cx, cy, outer_radius, inner_radius, angle, end_angle)}" '
            f'fill="{row.color}" stroke="#ffffff" stroke-width="3">'
            f"<title>{row.num_players} players: {format_int(row.hands)} hands ({row.percent:.2f}%)</title>"
            "</path>"
        )

        if row.percent >= 1.5:
            mid = angle + sweep / 2
            lx, ly = polar_to_cartesian(cx, cy, label_radius, mid)
            anchor = "start" if lx >= cx else "end"
            labels.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
                'class="slice-label">'
                f"{row.num_players}p {row.percent:.1f}%"
                "</text>"
            )
        angle = end_angle

    legend_rows: list[str] = []
    legend_x = 690
    legend_y = 190
    for index, row in enumerate(rows):
        y = legend_y + index * 46
        legend_rows.append(
            f'<rect x="{legend_x}" y="{y - 16}" width="18" height="18" rx="3" fill="{row.color}" />'
            f'<text x="{legend_x + 34}" y="{y}" class="legend-label">'
            f"{row.num_players} players"
            "</text>"
            f'<text x="{legend_x + 190}" y="{y}" class="legend-value">'
            f"{format_int(row.hands)} ({row.percent:.2f}%)"
            "</text>"
        )

    source_label = html.escape(str(source))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">Hand composition by number of players</title>
  <desc id="desc">Radial chart showing the distribution of poker hands by num_players, including percentages and total hands.</desc>
  <style>
    text {{
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      fill: #111827;
    }}
    .title {{
      font-size: 34px;
      font-weight: 750;
    }}
    .subtitle {{
      font-size: 16px;
      fill: #4b5563;
    }}
    .center-total {{
      font-size: 38px;
      font-weight: 800;
    }}
    .center-caption {{
      font-size: 15px;
      fill: #6b7280;
      text-transform: uppercase;
      letter-spacing: 1.2px;
    }}
    .slice-label {{
      font-size: 15px;
      font-weight: 700;
      fill: #374151;
    }}
    .legend-title {{
      font-size: 18px;
      font-weight: 750;
    }}
    .legend-label {{
      font-size: 16px;
      font-weight: 650;
    }}
    .legend-value {{
      font-size: 15px;
      fill: #4b5563;
    }}
    .source {{
      font-size: 12px;
      fill: #6b7280;
    }}
  </style>
  <rect width="100%" height="100%" fill="#f8fafc" />
  <text x="52" y="68" class="title">Hand Composition by Number of Players</text>
  <text x="52" y="98" class="subtitle">Distribution of cleaned poker hands grouped by num_players</text>
  <g>
    {''.join(segments)}
  </g>
  <circle cx="{cx}" cy="{cy}" r="{inner_radius - 8}" fill="#f8fafc" />
  <text x="{cx}" y="{cy - 8}" text-anchor="middle" class="center-total">{format_int(total)}</text>
  <text x="{cx}" y="{cy + 24}" text-anchor="middle" class="center-caption">Total Hands</text>
  <g>
    {''.join(labels)}
  </g>
  <text x="{legend_x}" y="140" class="legend-title">num_players</text>
  <g>
    {''.join(legend_rows)}
  </g>
  <text x="52" y="720" class="source">Source: {source_label}</text>
</svg>
"""


def write_csv(rows: list[Row], output_path: Path) -> None:
    csv_path = output_path.with_suffix(".csv")
    with csv_path.open("w", encoding="utf-8") as f:
        f.write("num_players,hands,percent\n")
        for row in rows:
            f.write(f"{row.num_players},{row.hands},{row.percent:.4f}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "jsonl",
        type=Path,
        nargs="?",
        default=Path("processed/nolimit_holdem/holdem_hands.jsonl"),
        help="Path to a cleaned hand JSONL file",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("processed/nolimit_holdem/num_players_radial_chart.svg"),
        help="SVG chart output path",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Also write a CSV next to the chart",
    )
    args = parser.parse_args()

    input_path = args.jsonl.resolve()
    output_path = args.output.resolve()
    if not input_path.is_file():
        raise SystemExit(f"Not a file: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    counts, stats = count_file(input_path)
    rows = rows_from_counts(counts, stats["hands"])
    output_path.write_text(chart_svg(rows, stats["hands"], input_path), encoding="utf-8")

    if args.csv:
        write_csv(rows, output_path)

    print(f"chart,{output_path}")
    print(f"hands,{stats['hands']}")
    print(f"invalid_json_lines,{stats['invalid_json_lines']}")
    print(f"missing_num_players,{stats['missing_num_players']}")


if __name__ == "__main__":
    main()
