# PokerProfiler

Visual analytics for playstyle profiling and exploit discovery from the
[IRC Poker Database](http://poker.cs.ualberta.ca/irc_poker_database.html).

The backend cleans the raw IRC hold'em archives and builds a 30-metric
behavioural fingerprint per player. The frontend is an interactive linked-view
dashboard with three panels: a population distribution view, a chip-ledger
graph, and a shark-vs-feeder radar diff.

Raw archives, cleaned JSONL, and generated CSV/JSON are all git-ignored, so you
regenerate them locally with the steps below.

## Requirements

- Python 3 (standard library only for the pipeline; `matplotlib` + `numpy` only
  if you want the offline validation plots)
- Node.js 18+ for the frontend

## 1. Get the data

Download the IRC Poker Database archives and place the hold'em `.tgz` files under
`IRCdata/` at the repo root:

```text
IRCdata/
  holdem1.*.tgz  holdem2.*.tgz  holdem3.*.tgz  holdempot.*.tgz
```

## 2. Run the backend pipeline

From the repo root:

```bash
# Clean the raw archives -> processed/nolimit_holdem/holdem_hands.jsonl
python scripts/clean_nolimit_holdem.py --games holdem1,holdem2,holdem3,holdempot

# Build the 30-metric fingerprint -> player_features.csv / .json
python -m poker_features

# Convert features into the frontend payload -> frontend/public/data/players.json
python scripts/build_frontend_data.py

# Build the chip-flow ledger -> frontend/public/data/ledger.json
python scripts/build_chip_ledger.py
```

After this, `frontend/public/data/` contains `players.json` and `ledger.json`,
the two files the dashboard reads.

## 3. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open the printed URL (default http://localhost:5173).

## Project layout

```text
poker_features/   feature pipeline (clean hands -> 30-metric fingerprint)
scripts/          clean_nolimit_holdem.py, build_frontend_data.py, build_chip_ledger.py
frontend/         Vite + React + D3 dashboard
```
