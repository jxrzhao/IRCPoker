import * as d3 from 'd3';

export const COLORS = {
  felt: '#1e5e40',
  feltDeep: '#133f2b',
  red: '#b0322b',
  gold: '#b8860b',
  ink: '#1c1c1c',
  inkSoft: '#5c5346',
  inkFaint: '#9a8f7c',
  panel: '#fbf8f0',
  panelEdge: '#e2d8c2',
};

// Net-chip diverging ramp ("oat <-> sage"): terracotta clay (big loss) -> warm
// oat (break-even) -> sage green (big win). Softest/lowest-contrast so it melts
// into the parchment ground. The legend bars read the matching CSS variable
// --chip-ramp (theme.css); keep the two in sync if this changes.
const CHIP_STOPS = ['#c0795b', '#d9a98a', '#e7ddc6', '#9aaf86', '#6f9068'];
const chipMid = CHIP_STOPS[2];
const CHIP_RAMP = d3.interpolateRgbBasis(CHIP_STOPS);

// Diverging colour for net chip flow on a SYMMETRIC-LOG footing, mirroring the
// offline matplotlib distribution view (winner = green, loser = red). A plain
// linear scale collapses 99% of players to one colour because a few extreme
// winners stretch the domain, so we clip the magnitude at the 99th percentile
// of |value| and compress the rest with a symlog transform whose linear region
// is the median |value|. `values` is the active pool's signed chip figures.
export function netChipColor(values) {
  const abs = values
    .filter((v) => v != null && Number.isFinite(v))
    .map(Math.abs);
  const sorted = abs.slice().sort((a, b) => a - b);
  const pct = (p) => sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))] || 1;
  const clip = Math.max(pct(0.99), 1);
  const positive = sorted.filter((v) => v > 0);
  let lin = positive.length ? positive[Math.floor(positive.length / 2)] : 1;
  lin = Math.min(Math.max(lin, 1), clip / 10); // keep at least one log decade

  const sym = (x) => {
    const a = Math.abs(x);
    return Math.sign(x) * (a <= lin ? a / lin : 1 + Math.log10(a / lin));
  };
  const norm = sym(clip) || 1;

  return (value) => {
    if (value == null || Number.isNaN(value)) return chipMid;
    const c = Math.max(-clip, Math.min(clip, value));
    return CHIP_RAMP((sym(c) / norm + 1) / 2);
  };
}
