import { useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { KEY_METRICS, METRICS, formatMetric } from '../data/metrics.js';
import { COLORS } from '../data/colors.js';

const SIZE = 360;
const CX = SIZE / 2;
const CY = SIZE / 2 + 6;
const R = 128;
const AXIS_KEYS = KEY_METRICS.map((m) => m.key);
const ALL_KEYS = METRICS.map((m) => m.key);

// Normalise a raw value into [0,1] against the population's robust 2nd..98th
// percentile extent (st.lo/st.hi) so one outlier can't flatten an axis.
function norm(value, st) {
  if (value == null || !st || st.hi === st.lo) return 0;
  return Math.max(0, Math.min(1, (value - st.lo) / (st.hi - st.lo)));
}

// Element-wise mean fingerprint across the chosen feeders.
function meanVector(feeders, keys) {
  const acc = {};
  for (const k of keys) {
    let s = 0;
    let c = 0;
    for (const f of feeders) {
      const v = f.player.metrics[k];
      if (v != null && !Number.isNaN(v)) {
        s += v;
        c += 1;
      }
    }
    acc[k] = c ? s / c : null;
  }
  return acc;
}

function polygon(values, stats) {
  return AXIS_KEYS
    .map((k, i) => {
      const ang = (i / AXIS_KEYS.length) * 2 * Math.PI - Math.PI / 2;
      const rr = norm(values[k], stats[k]) * R;
      return `${CX + rr * Math.cos(ang)},${CY + rr * Math.sin(ang)}`;
    })
    .join(' ');
}

export default function RadarDiff({
  shark = null,
  feeders = [],
  stats = {},
  feederCount = 8,
  onFeederCount,
}) {
  const [tip, setTip] = useState(null); // { x, y, metric } in viewport coords
  const [hoverKey, setHoverKey] = useState(null); // axis highlighted from a hypothesis row
  const maxFeeders = Math.max(1, feeders.length);
  const count = Math.min(feederCount, maxFeeders);
  const shownFeeders = useMemo(() => feeders.slice(0, count), [feeders, count]);

  const feederMean = useMemo(() => meanVector(shownFeeders, ALL_KEYS), [shownFeeders]);

  // Exploit hypotheses: largest normalised shark-feeder gaps across ALL metrics
  // (not just the radar axes), so an edge on any street can surface.
  const hypotheses = useMemo(() => {
    if (!shark || !shownFeeders.length) return [];
    return METRICS.map((m) => {
      const sN = norm(shark.metrics[m.key], stats[m.key]);
      const fN = norm(feederMean[m.key], stats[m.key]);
      return {
        key: m.key,
        label: m.label,
        diff: sN - fN,
        sharkVal: shark.metrics[m.key],
        feederVal: feederMean[m.key],
        unit: m.unit,
      };
    })
      .sort((a, b) => Math.abs(b.diff) - Math.abs(a.diff))
      .slice(0, 4);
  }, [shark, shownFeeders, feederMean, stats]);

  if (!shark) {
    return (
      <section className="panel fill radar">
        <div className="panel-head">
          <h2>Shark vs Feeder Radar</h2>
          <span className="panel-sub">fingerprint diff</span>
        </div>
        <div className="empty-hint">
          A selected shark&apos;s fingerprint vs. the mean of the players who feed
          them chips.
        </div>
      </section>
    );
  }

  return (
    <section className="panel fill radar">
      <div className="panel-head">
        <h2>Shark vs Feeder Radar</h2>
        <span className="panel-sub">key-metric fingerprint diff</span>
      </div>

      <div className="feeder-filter">
        <div className="feeder-filter-head">
          <span className="feeder-filter-label">Feeders averaged</span>
          <span className="feeder-filter-val">
            {count}
            <span className="feeder-filter-max"> / {maxFeeders}</span>
          </span>
        </div>
        <input
          type="range"
          min="1"
          max={maxFeeders}
          step="1"
          value={count}
          onChange={(e) => onFeederCount?.(Number(e.target.value))}
        />
        <div className="feeder-filter-hint">drag to average more or fewer of the shark&apos;s top feeders</div>
      </div>

      <div className="radar-legend">
        <span className="sel-chip">
          <span className="swatch gold" /> <b>{shark.name}</b> (shark)
        </span>
        <span className="sel-chip">
          <span className="swatch red dashed" /> mean of {count} feeders
        </span>
      </div>

      <div className="radar-body">
        <svg viewBox={`0 0 ${SIZE} ${SIZE + 18}`} className="radar-svg">
          {[0.25, 0.5, 0.75, 1].map((t) => (
            <circle key={t} cx={CX} cy={CY} r={R * t} fill="none" stroke={COLORS.panelEdge} strokeWidth="1" />
          ))}
          {KEY_METRICS.map((m, i) => {
            const ang = (i / KEY_METRICS.length) * 2 * Math.PI - Math.PI / 2;
            const x = CX + R * Math.cos(ang);
            const y = CY + R * Math.sin(ang);
            const lx = CX + (R + 22) * Math.cos(ang);
            const ly = CY + (R + 22) * Math.sin(ang);
            return (
              <g key={m.key}>
                <line x1={CX} y1={CY} x2={x} y2={y} stroke={COLORS.panelEdge} />
                <text
                  x={lx}
                  y={ly}
                  textAnchor={Math.abs(lx - CX) < 6 ? 'middle' : lx > CX ? 'start' : 'end'}
                  dominantBaseline="middle"
                  fontSize="9.5"
                  fontFamily="var(--font-mono)"
                  fill={COLORS.inkSoft}
                >
                  {m.label}
                </text>
              </g>
            );
          })}

          <polygon
            points={polygon(feederMean, stats)}
            fill={COLORS.red}
            fillOpacity="0.1"
            stroke={COLORS.red}
            strokeWidth="2"
            strokeDasharray="5 4"
          />
          <polygon
            points={polygon(shark.metrics, stats)}
            fill={COLORS.gold}
            fillOpacity="0.18"
            stroke={COLORS.gold}
            strokeWidth="2.5"
          />
          {KEY_METRICS.map((m, i) => {
            const ang = (i / KEY_METRICS.length) * 2 * Math.PI - Math.PI / 2;
            const ca = Math.cos(ang);
            const sa = Math.sin(ang);
            const sr = norm(shark.metrics[m.key], stats[m.key]) * R;
            const fr = norm(feederMean[m.key], stats[m.key]) * R;
            const sx = CX + sr * ca;
            const sy = CY + sr * sa;
            const fx = CX + fr * ca;
            const fy = CY + fr * sa;
            const active = tip?.metric.key === m.key || hoverKey === m.key;
            const show = (e) => setTip({ x: e.clientX, y: e.clientY, metric: m });
            const hit = (cx, cy, key) => (
              <circle
                key={key}
                cx={cx}
                cy={cy}
                r="11"
                fill="transparent"
                style={{ cursor: 'pointer' }}
                onMouseEnter={show}
                onMouseMove={show}
                onMouseLeave={() => setTip(null)}
              />
            );
            return (
              <g key={m.key}>
                {active && (
                  <>
                    <circle cx={sx} cy={sy} r="7" fill={COLORS.gold} fillOpacity="0.22" className="radar-pulse" />
                    <circle cx={fx} cy={fy} r="7" fill={COLORS.red} fillOpacity="0.22" className="radar-pulse" />
                  </>
                )}
                <circle
                  cx={sx}
                  cy={sy}
                  r={active ? 4.6 : 2.6}
                  fill={COLORS.gold}
                  stroke="#fff"
                  strokeWidth={active ? 1.4 : 0.8}
                  className="radar-vertex"
                />
                <circle
                  cx={fx}
                  cy={fy}
                  r={active ? 4.2 : 2.4}
                  fill={COLORS.red}
                  stroke="#fff"
                  strokeWidth={active ? 1.4 : 0.8}
                  className="radar-vertex"
                />
                {hit(sx, sy, `hs-${m.key}`)}
                {hit(fx, fy, `hf-${m.key}`)}
              </g>
            );
          })}
        </svg>

        <div className="hypotheses">
          <div className="hyp-title">Exploit hypotheses</div>
          <div className="hyp-sub">largest fingerprint gaps (any street)</div>
          {hypotheses.map((h) => {
            const dir = h.diff > 0 ? 'more' : 'less';
            const onRadar = AXIS_KEYS.includes(h.key);
            return (
              <div
                className={`hyp-row ${hoverKey === h.key ? 'active' : ''}`}
                key={h.key}
                onMouseEnter={() => onRadar && setHoverKey(h.key)}
                onMouseLeave={() => setHoverKey(null)}
                style={{ cursor: onRadar ? 'pointer' : 'default' }}
              >
                <div className="hyp-bar-wrap">
                  <div
                    className="hyp-bar"
                    style={{
                      width: `${Math.min(100, Math.abs(h.diff) * 100)}%`,
                      background: h.diff > 0 ? COLORS.gold : COLORS.red,
                    }}
                  />
                </div>
                <div className="hyp-text">
                  <b>{h.label}</b>
                  {onRadar && <span className="hyp-onradar" title="shown on the radar">{'◈'}</span>}
                  : shark plays{' '}
                  <span style={{ color: h.diff > 0 ? COLORS.gold : COLORS.red }}>{dir}</span>{' '}
                  ({formatMetric(h.sharkVal, h.unit)} vs {formatMetric(h.feederVal, h.unit)})
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {tip &&
        createPortal(
          <div className="dist-tip" style={{ left: tip.x + 14, top: tip.y + 14 }}>
            <span className="dist-tip-name">{tip.metric.label}</span>
            <span className="dist-tip-val">
              shark {formatMetric(shark.metrics[tip.metric.key], tip.metric.unit)}
            </span>
            <span className="dist-tip-val">
              feeders {formatMetric(feederMean[tip.metric.key], tip.metric.unit)}
            </span>
          </div>,
          document.body,
        )}
    </section>
  );
}
