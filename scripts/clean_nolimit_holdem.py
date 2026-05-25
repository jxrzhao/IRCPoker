#!/usr/bin/env python3
"""
Clean IRC Poker hold'em archives into line-delimited JSON.

This script follows the hdb/hroster/pdb record layout documented in
PokerHandsDataset/src/extract.py, but uses only the Python standard library so
it can run without installing PokerHandsDataset's optional dependencies.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import tarfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


STAGES = ("preflop", "flop", "turn", "river", "showdown")
CARD_RE = re.compile(r"^(?:[2-9TJQKA]|10)[schd]$")
ACTION_RE = re.compile(r"^[BfkbcrAQK-]+$")
POT_RE = re.compile(r"^[0-9]+/[0-9]+$")


@dataclass
class HdbRecord:
    timestamp: int
    dealer: int
    hand_num: int
    num_players: int
    flop: str
    turn: str
    river: str
    showdown: str
    board: list[str]

    @property
    def pots(self) -> list[dict]:
        pots = []
        for stage in STAGES[1:]:
            players, size = getattr(self, stage).split("/")
            pots.append({"stage": stage[0], "num_players": int(players), "size": int(size)})
        return pots


@dataclass
class PdbRecord:
    player: str
    timestamp: int
    num_players: int
    position: int
    preflop: str
    flop: str
    turn: str
    river: str
    bankroll: int
    total_bet: int
    total_win: int
    pocket_cards: list[str]

    @property
    def bets(self) -> list[dict]:
        return [
            {
                "stage": stage[0],
                "actions": list(getattr(self, stage)),
                "raw_actions": getattr(self, stage),
            }
            for stage in STAGES[:-1]
        ]


def normalize_card(card: str) -> str:
    return "T" + card[-1] if card.startswith("10") else card


def parse_int(value: str) -> int:
    return int(value.strip())


def parse_hdb_line(line: str) -> HdbRecord:
    parts = line.split()
    if len(parts) < 8:
        raise ValueError("hdb line has fewer than 8 fields")
    pots = parts[4:8]
    if not all(POT_RE.match(pot) for pot in pots):
        raise ValueError("hdb line has invalid pot fields")
    cards = [normalize_card(card) for card in parts[8:]]
    if not all(CARD_RE.match(card) for card in cards):
        raise ValueError("hdb line has invalid board cards")
    return HdbRecord(
        timestamp=parse_int(parts[0]),
        dealer=parse_int(parts[1]),
        hand_num=parse_int(parts[2]),
        num_players=parse_int(parts[3]),
        flop=pots[0],
        turn=pots[1],
        river=pots[2],
        showdown=pots[3],
        board=cards,
    )


def parse_hroster_line(line: str) -> tuple[int, int, list[str]]:
    parts = line.split()
    if len(parts) < 2:
        raise ValueError("hroster line has fewer than 2 fields")
    timestamp = parse_int(parts[0])
    num_players = parse_int(parts[1])
    players = parts[2:]
    if len(players) != num_players:
        raise ValueError("hroster player count mismatch")
    return timestamp, num_players, players


def parse_pdb_line(line: str) -> PdbRecord:
    parts = line.split()
    if len(parts) < 11:
        raise ValueError("pdb line has fewer than 11 fields")
    actions = parts[4:8]
    if not all(ACTION_RE.match(action) for action in actions):
        raise ValueError("pdb line has invalid actions")
    cards = [normalize_card(card) for card in parts[11:]]
    if not all(CARD_RE.match(card) for card in cards):
        raise ValueError("pdb line has invalid pocket cards")
    return PdbRecord(
        player=parts[0],
        timestamp=parse_int(parts[1]),
        num_players=parse_int(parts[2]),
        position=parse_int(parts[3]),
        preflop=actions[0],
        flop=actions[1],
        turn=actions[2],
        river=actions[3],
        bankroll=parse_int(parts[8]),
        total_bet=parse_int(parts[9]),
        total_win=parse_int(parts[10]),
        pocket_cards=cards,
    )


def safe_extract_archive(archive: Path, extract_dir: Path) -> int:
    extract_dir = extract_dir.resolve()
    extracted = 0
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            target = (extract_dir / member.name).resolve()
            if not str(target).startswith(str(extract_dir) + "/"):
                raise ValueError(f"unsafe archive path: {member.name}")
        tar.extractall(extract_dir)
        extracted = len(tar.getmembers())
    return extracted


def read_hroster(path: Path, stats: Counter) -> dict[int, list[str]]:
    roster: dict[int, list[str]] = {}
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                timestamp, _num_players, players = parse_hroster_line(line)
                roster[timestamp] = players
            except Exception:
                stats["invalid_hroster_lines"] += 1
    return roster


def read_pdb_files(pdb_dir: Path, stats: Counter) -> dict[str, dict[int, PdbRecord]]:
    records: dict[str, dict[int, PdbRecord]] = {}
    for path in sorted(pdb_dir.glob("pdb.*")):
        player_from_file = path.name.removeprefix("pdb.")
        player_records: dict[int, PdbRecord] = {}
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    rec = parse_pdb_line(line)
                    player_records[rec.timestamp] = rec
                except Exception:
                    stats["invalid_pdb_lines"] += 1
        records[player_from_file] = player_records
    return records


def iter_month_dirs(extract_dir: Path, archives: Iterable[Path]) -> Iterable[tuple[str, str, Path]]:
    for archive in sorted(archives):
        stem = archive.name.removesuffix(".tgz")
        game, month = stem.split(".", 1)
        month_dir = extract_dir / game / month
        if month_dir.exists():
            yield game, month, month_dir


def build_hand(game: str, month: str, hdb: HdbRecord, players: list[str], pdb: dict[str, dict[int, PdbRecord]]) -> dict:
    player_records = {}
    for player in players:
        rec = pdb.get(player, {}).get(hdb.timestamp)
        if rec is None:
            raise KeyError(player)
        player_records[player] = {
            "position": rec.position,
            "bankroll": rec.bankroll,
            "total_bet": rec.total_bet,
            "total_win": rec.total_win,
            "pocket_cards": rec.pocket_cards,
            "bets": rec.bets,
        }
    return {
        "_id": f"{game}_{month}_{hdb.timestamp}",
        "game": game,
        "month": month,
        "timestamp": hdb.timestamp,
        "dealer": hdb.dealer,
        "hand_num": hdb.hand_num,
        "num_players": hdb.num_players,
        "board": hdb.board,
        "pots": hdb.pots,
        "players": player_records,
    }


def clean_month(game: str, month: str, month_dir: Path, out_f, stats: Counter) -> dict:
    month_stats: Counter = Counter()
    hdb_path = month_dir / "hdb"
    hroster_path = month_dir / "hroster"
    pdb_dir = month_dir / "pdb"
    if not hdb_path.exists() or not hroster_path.exists() or not pdb_dir.exists():
        stats["missing_required_files"] += 1
        return {"month": month, "hands": 0, "error": "missing hdb, hroster, or pdb"}

    roster = read_hroster(hroster_path, month_stats)
    pdb = read_pdb_files(pdb_dir, month_stats)
    month_stats["pdb_files"] = len(pdb)
    month_stats["roster_rows"] = len(roster)

    with hdb_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            month_stats["hdb_rows"] += 1
            try:
                hdb = parse_hdb_line(line)
            except Exception:
                month_stats["invalid_hdb_lines"] += 1
                continue
            players = roster.get(hdb.timestamp)
            if players is None or len(players) != hdb.num_players:
                month_stats["missing_roster_rows"] += 1
                continue
            try:
                hand = build_hand(game, month, hdb, players, pdb)
            except KeyError:
                month_stats["missing_pdb_records"] += 1
                continue
            json.dump(hand, out_f, separators=(",", ":"))
            out_f.write("\n")
            month_stats["hands"] += 1
            month_stats["player_entries"] += len(hand["players"])
            if len(hdb.board) == 5:
                month_stats["complete_boards"] += 1
            if hdb.pots[-1]["num_players"] > 0:
                month_stats["showdowns"] += 1

    stats.update(month_stats)
    row = dict(month_stats)
    row["month"] = month
    return row


def write_csv_summary(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "month",
        "hands",
        "hdb_rows",
        "roster_rows",
        "pdb_files",
        "player_entries",
        "complete_boards",
        "showdowns",
        "invalid_hdb_lines",
        "invalid_hroster_lines",
        "invalid_pdb_lines",
        "missing_roster_rows",
        "missing_pdb_records",
        "error",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, 0) for key in fieldnames})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("IRCdata"))
    parser.add_argument("--output-dir", type=Path, default=Path("processed/nolimit_holdem"))
    parser.add_argument("--archive-glob", default="nolimit.*.tgz")
    parser.add_argument(
        "--games",
        default=None,
        help="comma-separated archive prefixes, e.g. holdem1,holdem2,holdem3,holdempot",
    )
    parser.add_argument("--skip-extract", action="store_true", help="parse existing extracted files only")
    args = parser.parse_args()

    if args.games:
        games = [game.strip() for game in args.games.split(",") if game.strip()]
        archives = sorted(archive for game in games for archive in args.data_dir.glob(f"{game}.*.tgz"))
    else:
        archives = sorted(args.data_dir.glob(args.archive_glob))
    if not archives:
        pattern = args.games or args.archive_glob
        raise SystemExit(f"No archives matched {pattern} in {args.data_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if not args.skip_extract:
        for archive in archives:
            safe_extract_archive(archive, args.data_dir)

    stats = Counter({"archives": len(archives)})
    monthly_rows: list[dict] = []
    output_stem = "holdem_hands" if args.games else args.archive_glob.replace("*", "all").replace(".tgz", "")
    hands_path = args.output_dir / f"{output_stem}.jsonl"
    with hands_path.open("w", encoding="utf-8") as out_f:
        for game, month, month_dir in iter_month_dirs(args.data_dir, archives):
            monthly_rows.append(clean_month(game, month, month_dir, out_f, stats))

    summary = {
        "input_dir": str(args.data_dir),
        "output_dir": str(args.output_dir),
        "archives": [archive.name for archive in archives],
        "hands_jsonl": str(hands_path),
        "monthly_csv": str(args.output_dir / "summary_by_month.csv"),
        "totals": dict(stats),
        "months": monthly_rows,
    }

    write_csv_summary(args.output_dir / "summary_by_month.csv", monthly_rows)
    with (args.output_dir / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    print(json.dumps(summary["totals"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
