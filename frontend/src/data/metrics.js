// 30-dimensional behavioural fingerprint metadata.
// Mirrors poker_features/features.py CSV_FIELDS (Table 1 in the proposal).
// `group` drives the Distribution View tabs and the Radar Diff axis subsets.

export const GROUPS = [
  { key: 'preflop', label: 'Pre-flop' },
  { key: 'flop', label: 'Flop' },
  { key: 'turn', label: 'Turn' },
  { key: 'river', label: 'River' },
  { key: 'postflop', label: 'Post-flop (agg.)' },
  { key: 'showdown', label: 'Showdown & Outcome' },
];

// unit: 'pct' = 0..100, 'af' = unbounded aggression-factor ratio,
//       'rate' = 0..1, 'chips' = signed chips/hand.
export const METRICS = [
  // ---- Pre-flop (6) ----
  { key: 'vpip_pct', label: 'VPIP', group: 'preflop', unit: 'pct', desc: 'Voluntarily put chips in pot' },
  { key: 'pfr_pct', label: 'PFR', group: 'preflop', unit: 'pct', desc: 'Pre-flop raise %' },
  { key: '3bet_pct', label: '3-Bet', group: 'preflop', unit: 'pct', desc: '3-bet when given the chance' },
  { key: 'fold_to_3bet_pct', label: 'Fold to 3-Bet', group: 'preflop', unit: 'pct', desc: 'Opener folds facing a 3-bet' },
  { key: '4bet_pct', label: '4-Bet', group: 'preflop', unit: 'pct', desc: '4-bet when given the chance' },
  { key: 'fold_to_4bet_pct', label: 'Fold to 4-Bet', group: 'preflop', unit: 'pct', desc: '3-bettor folds facing a 4-bet' },

  // ---- Flop (5) ----
  { key: 'flop_af', label: 'Flop AF', group: 'flop', unit: 'af', desc: 'Aggression factor on the flop' },
  { key: 'flop_cbet_pct', label: 'Flop C-Bet', group: 'flop', unit: 'pct', desc: 'Continuation-bet the flop' },
  { key: 'flop_donk_pct', label: 'Flop Donk', group: 'flop', unit: 'pct', desc: 'Donk-lead into the aggressor' },
  { key: 'flop_fold_pct', label: 'Flop Fold', group: 'flop', unit: 'pct', desc: 'Fold when facing a flop bet' },
  { key: 'flop_raise_pct', label: 'Flop Raise', group: 'flop', unit: 'pct', desc: 'Raise when facing a flop bet' },

  // ---- Turn (5) ----
  { key: 'turn_af', label: 'Turn AF', group: 'turn', unit: 'af', desc: 'Aggression factor on the turn' },
  { key: 'turn_cbet_pct', label: 'Turn C-Bet', group: 'turn', unit: 'pct', desc: 'Continuation-bet the turn' },
  { key: 'turn_donk_pct', label: 'Turn Donk', group: 'turn', unit: 'pct', desc: 'Donk-lead into the aggressor' },
  { key: 'turn_fold_pct', label: 'Turn Fold', group: 'turn', unit: 'pct', desc: 'Fold when facing a turn bet' },
  { key: 'turn_raise_pct', label: 'Turn Raise', group: 'turn', unit: 'pct', desc: 'Raise when facing a turn bet' },

  // ---- River (5) ----
  { key: 'river_af', label: 'River AF', group: 'river', unit: 'af', desc: 'Aggression factor on the river' },
  { key: 'river_cbet_pct', label: 'River C-Bet', group: 'river', unit: 'pct', desc: 'Continuation-bet the river' },
  { key: 'river_donk_pct', label: 'River Donk', group: 'river', unit: 'pct', desc: 'Donk-lead into the aggressor' },
  { key: 'river_fold_pct', label: 'River Fold', group: 'river', unit: 'pct', desc: 'Fold when facing a river bet' },
  { key: 'river_raise_pct', label: 'River Raise', group: 'river', unit: 'pct', desc: 'Raise when facing a river bet' },

  // ---- Post-flop aggregate (5) ----
  { key: 'postflop_af', label: 'Post-flop AF', group: 'postflop', unit: 'af', desc: 'Aggression factor, all post-flop streets' },
  { key: 'postflop_cbet_pct', label: 'Post-flop C-Bet', group: 'postflop', unit: 'pct', desc: 'C-bet aggregated over streets' },
  { key: 'postflop_donk_pct', label: 'Post-flop Donk', group: 'postflop', unit: 'pct', desc: 'Donk aggregated over streets' },
  { key: 'postflop_fold_pct', label: 'Post-flop Fold', group: 'postflop', unit: 'pct', desc: 'Fold-to-bet aggregated over streets' },
  { key: 'postflop_raise_pct', label: 'Post-flop Raise', group: 'postflop', unit: 'pct', desc: 'Raise-vs-bet aggregated over streets' },

  // ---- Showdown & Outcome (4) ----
  { key: 'wtsd_pct', label: 'WTSD', group: 'showdown', unit: 'pct', desc: 'Went to showdown (saw flop)' },
  { key: 'wsd_pct', label: 'W$SD', group: 'showdown', unit: 'pct', desc: 'Won money at showdown' },
  { key: 'win_rate', label: 'Win Rate', group: 'showdown', unit: 'rate', desc: 'Hands won / hands played' },
  { key: 'chips_per_hand', label: 'Chips / Hand', group: 'showdown', unit: 'chips', desc: 'Net chips per hand' },
];

export const METRICS_BY_KEY = Object.fromEntries(METRICS.map((m) => [m.key, m]));

// Curated key axes for the shark-vs-feeder radar: a readable subset of the 30
// (proposal §4.5 "a selected subset of the metrics chosen for readability").
// Covers the canonical playstyle dimensions: preflop looseness/aggression,
// preflop defence, postflop aggression/continuation, and showdown behaviour.
export const KEY_METRIC_KEYS = [
  'vpip_pct',
  'pfr_pct',
  '3bet_pct',
  'fold_to_3bet_pct',
  'postflop_af',
  'postflop_cbet_pct',
  'wtsd_pct',
  'wsd_pct',
];
export const KEY_METRICS = KEY_METRIC_KEYS.map((k) => METRICS_BY_KEY[k]);

export function metricsForGroup(groupKey) {
  return METRICS.filter((m) => m.group === groupKey);
}

// Display helper. Returns a short formatted string for a raw metric value.
export function formatMetric(value, unit) {
  if (value == null || Number.isNaN(value)) return '·';
  switch (unit) {
    case 'pct':
      return `${value.toFixed(1)}%`;
    case 'af':
      return value.toFixed(2);
    case 'rate':
      return value.toFixed(3);
    case 'chips':
      return `${value > 0 ? '+' : ''}${Math.round(value)}`;
    default:
      return String(value);
  }
}
