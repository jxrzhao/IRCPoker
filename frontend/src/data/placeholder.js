// Synthetic stand-in for the real pipeline output
// (processed/nolimit_holdem/player_features.json + a chip-flow edge list).
// Shapes match what the dashboard will consume once the backend writes them,
// so swapping in real data later is a drop-in replacement.
//
// Player: { id, name, hands, net_amount, chips_per_hand, archetype, metrics }
// Edge:   { source, target, chips }  -- `chips` flow from source -> target,
//         i.e. `target` net-won `chips` from `source`. Sharks are the big
//         net-winning targets; their in-neighbours are the feeders.

import { METRICS } from './metrics.js';

// --- deterministic RNG so placeholder views are stable across reloads ---
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const rand = mulberry32(273);

function gauss(mean, sd) {
  // Box-Muller
  const u = Math.max(rand(), 1e-9);
  const v = rand();
  return mean + sd * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function clamp(x, lo, hi) {
  return Math.min(hi, Math.max(lo, x));
}

const HANDLES = [
  'Maverick', 'IronJack', 'RiverRat', 'ColdDeck', 'BluffKing', 'NitNorm',
  'AceHigh', 'TiltMaster', 'DonkLord', 'SilentRaise', 'PocketRox', 'CallStation',
  'GutShot', 'BigSlick', 'ChipLeader', 'FoldEquity', 'TheGrinder', 'RunGood',
  'StoneCold', 'BackdoorBri', 'ShoveItIn', 'LimpLarry', 'TripsTom', 'NutPeddler',
  'BoardLock', 'RangeMerge', 'ThinValue', 'BarrelBob', 'CheckRay', 'OverBet',
  'SnapCall', 'SlowRoll', 'BadBeatBen', 'CoolerCarl', 'WheelHouse', 'BinkBank',
  'FishFinder', 'WhaleHunt', 'EVMachine', 'SoulRead', 'PolarBear', 'MergeMike',
  'FlatCaller', 'SqueezeSue', 'IsoRaiser', 'PotControl', 'BluffCatch', 'ValueTown',
  'DrawHeavy', 'SetMiner', 'AirBaller', 'BetSizer', 'TankTina', 'InstaMuck',
  'RakeBack', 'ColdFour', 'LeadOut', 'ProbeBet', 'FloatKing', 'DelayCbet',
];

// Per-metric population mean / spread, with a directional "shark edge":
// `sharkShift` is added to the mean (in SD units) for winning players, giving
// the radar-diff a coherent, readable exploit story.
const PROFILE = {
  vpip_pct: { mean: 38, sd: 11, lo: 8, hi: 90, sharkShift: -0.7 },
  pfr_pct: { mean: 18, sd: 8, lo: 2, hi: 70, sharkShift: 0.4 },
  '3bet_pct': { mean: 6, sd: 3.5, lo: 0, hi: 25, sharkShift: 0.6 },
  fold_to_3bet_pct: { mean: 58, sd: 14, lo: 10, hi: 95, sharkShift: -0.8 },
  '4bet_pct': { mean: 4, sd: 2.5, lo: 0, hi: 18, sharkShift: 0.5 },
  fold_to_4bet_pct: { mean: 62, sd: 16, lo: 15, hi: 98, sharkShift: -0.4 },

  flop_af: { mean: 2.1, sd: 1.1, lo: 0.1, hi: 8, sharkShift: 0.5 },
  flop_cbet_pct: { mean: 55, sd: 14, lo: 15, hi: 95, sharkShift: 0.3 },
  flop_donk_pct: { mean: 9, sd: 6, lo: 0, hi: 40, sharkShift: -0.5 },
  flop_fold_pct: { mean: 45, sd: 13, lo: 8, hi: 90, sharkShift: -0.3 },
  flop_raise_pct: { mean: 12, sd: 6, lo: 0, hi: 45, sharkShift: 0.4 },

  turn_af: { mean: 1.9, sd: 1.0, lo: 0.1, hi: 8, sharkShift: 0.5 },
  turn_cbet_pct: { mean: 48, sd: 14, lo: 10, hi: 92, sharkShift: 0.3 },
  turn_donk_pct: { mean: 8, sd: 5.5, lo: 0, hi: 38, sharkShift: -0.5 },
  turn_fold_pct: { mean: 47, sd: 13, lo: 10, hi: 90, sharkShift: -0.3 },
  turn_raise_pct: { mean: 11, sd: 6, lo: 0, hi: 42, sharkShift: 0.4 },

  river_af: { mean: 1.7, sd: 1.0, lo: 0.1, hi: 8, sharkShift: 0.4 },
  river_cbet_pct: { mean: 42, sd: 14, lo: 8, hi: 90, sharkShift: 0.3 },
  river_donk_pct: { mean: 7, sd: 5, lo: 0, hi: 35, sharkShift: -0.4 },
  river_fold_pct: { mean: 49, sd: 13, lo: 10, hi: 92, sharkShift: -0.3 },
  river_raise_pct: { mean: 9, sd: 5.5, lo: 0, hi: 40, sharkShift: 0.4 },

  postflop_af: { mean: 1.9, sd: 0.9, lo: 0.2, hi: 7, sharkShift: 0.5 },
  postflop_cbet_pct: { mean: 49, sd: 12, lo: 12, hi: 90, sharkShift: 0.3 },
  postflop_donk_pct: { mean: 8, sd: 5, lo: 0, hi: 36, sharkShift: -0.5 },
  postflop_fold_pct: { mean: 47, sd: 11, lo: 12, hi: 88, sharkShift: -0.3 },
  postflop_raise_pct: { mean: 10, sd: 5, lo: 0, hi: 40, sharkShift: 0.4 },

  wtsd_pct: { mean: 29, sd: 9, lo: 5, hi: 70, sharkShift: -0.4 },
  wsd_pct: { mean: 48, sd: 11, lo: 15, hi: 85, sharkShift: 0.8 },
  win_rate: { mean: 0.16, sd: 0.05, lo: 0.02, hi: 0.45, sharkShift: 0.7 },
  chips_per_hand: { mean: 0, sd: 1, lo: -8, hi: 8, sharkShift: 0 }, // set from net later
};

function makePlayer(id, name, winnerBias) {
  // winnerBias in [-1, 1]: how "shark-like" this player is.
  const hands = Math.round(clamp(gauss(900, 700), 110, 6000));
  const metrics = {};
  for (const m of METRICS) {
    if (m.key === 'chips_per_hand') continue;
    const p = PROFILE[m.key];
    const shift = p.sharkShift * winnerBias * p.sd;
    metrics[m.key] = clamp(gauss(p.mean + shift, p.sd * 0.85), p.lo, p.hi);
  }
  // Net result correlates with winnerBias plus noise.
  const cph = gauss(winnerBias * 2.4, 1.3);
  const net_amount = Math.round(cph * hands);
  metrics.chips_per_hand = +cph.toFixed(2);

  const archetype =
    winnerBias > 0.45 ? 'Shark' : winnerBias < -0.4 ? 'Feeder' : 'Regular';

  return {
    id,
    name,
    hands,
    net_amount,
    chips_per_hand: +cph.toFixed(2),
    archetype,
    metrics,
  };
}

function buildPlayers() {
  const out = [];
  for (let i = 0; i < HANDLES.length; i++) {
    // A few strong winners, a long tail of losers, like a real pool.
    const r = rand();
    let bias;
    if (i < 6) bias = 0.5 + rand() * 0.5; // sharks
    else if (i < 16) bias = (r - 0.5) * 0.6; // regulars
    else bias = -(0.3 + rand() * 0.7); // feeders
    out.push(makePlayer(`p${i}`, HANDLES[i], bias));
  }
  return out.sort((a, b) => b.net_amount - a.net_amount);
}

function buildEdges(players) {
  // For each winner, draw chip-flow IN-edges from several losers.
  const winners = players.filter((p) => p.net_amount > 0);
  const losers = players.filter((p) => p.net_amount <= 0);
  const edges = [];
  for (const w of winners) {
    const nFeeders = 3 + Math.floor(rand() * 4);
    const pool = [...losers].sort(() => rand() - 0.5).slice(0, nFeeders);
    let remaining = w.net_amount;
    pool.forEach((l, idx) => {
      const share = idx === pool.length - 1 ? remaining : Math.round(remaining * (0.25 + rand() * 0.4));
      remaining -= share;
      const chips = Math.max(1, share);
      if (chips > 0) edges.push({ source: l.id, target: w.id, chips });
    });
  }
  return edges;
}

const players = buildPlayers();
const edges = buildEdges(players);

export const PLACEHOLDER = {
  players,
  edges,
  isPlaceholder: true,
};

// Net chips a player received from each in-neighbour (their feeders).
export function feedersOf(playerId, dataset = PLACEHOLDER) {
  return dataset.edges
    .filter((e) => e.target === playerId)
    .map((e) => ({
      player: dataset.players.find((p) => p.id === e.source),
      chips: e.chips,
    }))
    .filter((f) => f.player)
    .sort((a, b) => b.chips - a.chips);
}

// Population-baseline (mean) and per-metric extent for the distribution view.
export function populationStats(dataset = PLACEHOLDER) {
  const stats = {};
  for (const m of METRICS) {
    const vals = dataset.players
      .map((p) => p.metrics[m.key])
      .filter((v) => v != null && !Number.isNaN(v));
    vals.sort((a, b) => a - b);
    const mean = vals.reduce((s, v) => s + v, 0) / vals.length;
    stats[m.key] = {
      min: vals[0],
      max: vals[vals.length - 1],
      mean,
      p50: vals[Math.floor(vals.length / 2)],
    };
  }
  return stats;
}
