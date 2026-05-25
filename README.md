# IRC Poker Player Features

This repository cleans manually downloaded IRC Poker no-limit hold'em archives
and builds per-player feature tables from the cleaned hands.

Raw IRC data is not committed to this repository. Each user should download the
archives locally and place them under `IRCdata/`.

## Expected Layout

From the repository root:

```text
ECS273/
  IRCdata/
    nolimit.*.tgz
  poker_features/
  scripts/
```

`IRCdata/`, archive files, JSONL files, CSV files, and JSON outputs are ignored
by git so local data and generated artifacts stay out of commits.

## 1. Download IRC Data

Download the IRC Poker data manually, then copy the no-limit hold'em archives
into `IRCdata/`.

```bash
mkdir -p IRCdata
```

The cleaner looks for files matching `nolimit.*.tgz` by default. If you only
want specific archive prefixes, such as `holdem1`, `holdem2`, `holdem3`, or
`holdempot`, use the `--games` option shown below.

## 2. Clean No-Limit Hold'em Hands

Run the cleaner from the repository root:

```bash
python scripts/clean_nolimit_holdem.py
```

Default inputs and outputs:

- Input archives: `IRCdata/nolimit.*.tgz`
- Cleaned hands: `processed/nolimit_holdem/nolimit.all.jsonl`
- Monthly summary CSV: `processed/nolimit_holdem/summary_by_month.csv`
- Summary JSON: `processed/nolimit_holdem/summary.json`

To clean only selected hold'em game archives and write the standard
`holdem_hands.jsonl` file expected by the player feature builder:

```bash
python scripts/clean_nolimit_holdem.py \
  --games holdem1,holdem2,holdem3,holdempot
```

This writes:

```text
processed/nolimit_holdem/holdem_hands.jsonl
```

If the archives have already been extracted under `IRCdata/`, skip extraction
and parse the existing extracted files:

```bash
python scripts/clean_nolimit_holdem.py --skip-extract
```

## 3. Build Player Features

The preferred feature builder is the `poker_features` package:

```bash
python -m poker_features
```

Default inputs and outputs:

- Input hands: `processed/nolimit_holdem/holdem_hands.jsonl`
- Feature CSV: `processed/nolimit_holdem/player_features.csv`
- Feature JSON: `processed/nolimit_holdem/player_features.json`

Use `--min-hands` to drop low-volume players before downstream analysis:

```bash
python -m poker_features --min-hands 50
```

Use `--max-hands` for a quick smoke test:

```bash
python -m poker_features --max-hands 10000 --min-hands 5
```

Use explicit paths when the cleaned file is not the default:

```bash
python -m poker_features \
  --input processed/nolimit_holdem/nolimit.all.jsonl \
  --output-csv processed/nolimit_holdem/player_features.csv \
  --output-json processed/nolimit_holdem/player_features.json
```

The old script entry point is still available as a compatibility wrapper:

```bash
python scripts/build_player_features.py
```

## End-to-End Example

For the common hold'em workflow:

```bash
mkdir -p IRCdata
# Manually download/copy IRC no-limit hold'em .tgz archives into IRCdata/.

python scripts/clean_nolimit_holdem.py \
  --games holdem1,holdem2,holdem3,holdempot

python -m poker_features --min-hands 50
```

After this completes, use
`processed/nolimit_holdem/player_features.csv` for analysis, clustering, or
visualization.