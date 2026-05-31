// Live-data helpers: load the pipeline output and derive per-metric population
// stats for the distribution view. Shape contract lives in placeholder.js.

import { METRICS } from './metrics.js';

// Fetch the generated player feature table (scripts/build_frontend_data.py).
export async function loadPlayers() {
  const res = await fetch(`${import.meta.env.BASE_URL}data/players.json`);
  if (!res.ok) throw new Error(`players.json ${res.status}`);
  return res.json();
}

// Fetch the shark-feeder chip ledger (scripts/build_chip_ledger.py).
export async function loadLedger() {
  const res = await fetch(`${import.meta.env.BASE_URL}data/ledger.json`);
  if (!res.ok) throw new Error(`ledger.json ${res.status}`);
  return res.json();
}

// Per-metric population summary. `min`/`max`/`mean` drive the distribution
// histograms; `lo`/`hi` are the 2nd/98th percentiles, a robust extent the radar
// normalises against so a single outlier (e.g. an extreme aggression factor)
// cannot flatten an axis.
export function populationStats(players) {
  const stats = {};
  for (const m of METRICS) {
    const vals = [];
    for (const p of players) {
      const v = m.key === 'chips_per_hand' ? p.chips_per_hand : p.metrics?.[m.key];
      if (v == null || Number.isNaN(v)) continue;
      vals.push(v);
    }
    if (!vals.length) {
      stats[m.key] = { min: 0, max: 1, mean: 0, lo: 0, hi: 1 };
      continue;
    }
    vals.sort((a, b) => a - b);
    const sum = vals.reduce((s, v) => s + v, 0);
    const q = (t) => vals[Math.min(vals.length - 1, Math.floor(t * vals.length))];
    stats[m.key] = {
      min: vals[0],
      max: vals[vals.length - 1],
      mean: sum / vals.length,
      lo: q(0.02),
      hi: q(0.98),
    };
  }
  return stats;
}
