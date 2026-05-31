import { useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import * as d3 from 'd3';
import { formatMetric } from '../data/metrics.js';
import { COLORS } from '../data/colors.js';

const CW = 280;
const CH = 178;
const M = { top: 10, right: 14, bottom: 26, left: 14 };
const HIST_H = 50; // histogram band height
const STRIP_TOP = M.top + HIST_H + 10; // top of the jittered strip band
const STRIP_BAND = 74; // strip band height (taller = points spread, not a line)
const STRIP_MID = STRIP_TOP + STRIP_BAND / 2;

// One metric panel: marginal histogram over a jittered, net-chip-coloured strip.
// `players`/`st`/`color` are pre-filtered and shared; size is driven by the CSS
// class on the wrapping element so the same cell serves grid, carousel and
// lightbox at different scales.
export default function DistCell({ metric, players, st, color }) {
  const [tip, setTip] = useState(null); // { x, y, player } in viewport coords

  const x = useMemo(
    () => d3.scaleLinear().domain([st.min, st.max]).nice().range([M.left, CW - M.right]),
    [st],
  );

  const values = useMemo(
    () => players.map((p) => p.metrics[metric.key]).filter((v) => v != null && !Number.isNaN(v)),
    [players, metric.key],
  );

  const bins = useMemo(() => d3.bin().domain(x.domain()).thresholds(18)(values), [values, x]);

  const yHist = useMemo(
    () => d3.scaleLinear().domain([0, d3.max(bins, (b) => b.length) || 1]).range([M.top + HIST_H, M.top]),
    [bins],
  );

  // Deterministic jitter per player, drawn least-extreme first so the biggest
  // winners / losers land on top instead of being buried under the pack.
  const dots = useMemo(
    () =>
      players
        .filter((p) => p.metrics[metric.key] != null)
        .map((p, i) => ({
          p,
          cx: x(p.metrics[metric.key]),
          cy: STRIP_MID + (((i * 2654435761) % 1000) / 1000 - 0.5) * STRIP_BAND,
        }))
        .sort((a, b) => Math.abs(a.p.chips_per_hand) - Math.abs(b.p.chips_per_hand)),
    [players, x, metric.key],
  );

  return (
    <div className="dist-cell">
      <div className="dist-cell-head">
        <span className="dist-name">{metric.label}</span>
        <span className="dist-desc">{metric.desc}</span>
      </div>
      <svg viewBox={`0 0 ${CW} ${CH}`} className="dist-svg">
        <g>
          {bins.map((b, i) => (
            <rect
              key={i}
              x={x(b.x0)}
              y={yHist(b.length)}
              width={Math.max(1, x(b.x1) - x(b.x0) - 1)}
              height={M.top + HIST_H - yHist(b.length)}
              fill={COLORS.felt}
              fillOpacity="0.16"
            />
          ))}
        </g>

        <g>
          <line
            x1={x(st.mean)}
            x2={x(st.mean)}
            y1={M.top}
            y2={STRIP_TOP + STRIP_BAND}
            stroke={COLORS.gold}
            strokeDasharray="3 3"
            strokeWidth="1"
            strokeOpacity="0.7"
          />
          <text
            x={x(st.mean)}
            y={M.top - 2}
            textAnchor="middle"
            fontFamily="var(--font-mono)"
            fontSize="7"
            fill={COLORS.gold}
          >
            mean {formatMetric(st.mean, metric.unit)}
          </text>
        </g>

        <g>
          {dots.map(({ p, cx, cy }) => (
            <circle
              key={p.id}
              className="dist-dot"
              cx={cx}
              cy={cy}
              r={2.1}
              fill={color(p.chips_per_hand)}
              fillOpacity={0.6}
              onMouseEnter={(e) => setTip({ x: e.clientX, y: e.clientY, player: p })}
              onMouseMove={(e) => setTip({ x: e.clientX, y: e.clientY, player: p })}
              onMouseLeave={() => setTip(null)}
            />
          ))}
        </g>

        <line
          x1={M.left}
          x2={CW - M.right}
          y1={STRIP_TOP + STRIP_BAND + 4}
          y2={STRIP_TOP + STRIP_BAND + 4}
          stroke={COLORS.inkFaint}
          strokeOpacity="0.4"
          strokeWidth="0.6"
        />
        <g fontFamily="var(--font-mono)" fontSize="8" fill={COLORS.inkFaint}>
          {x.ticks(5).map((t) => (
            <g key={t}>
              <line
                x1={x(t)}
                x2={x(t)}
                y1={STRIP_TOP + STRIP_BAND + 4}
                y2={STRIP_TOP + STRIP_BAND + 7}
                stroke={COLORS.inkFaint}
                strokeOpacity="0.5"
                strokeWidth="0.6"
              />
              <text x={x(t)} y={CH - 6} textAnchor="middle">
                {metric.unit === 'rate' ? t.toFixed(2) : Math.round(t)}
                {metric.unit === 'pct' ? '%' : ''}
              </text>
            </g>
          ))}
        </g>
      </svg>

      <div className="dist-legend">
        <span className="dist-legend-end lose">loses</span>
        <span className="dist-legend-bar" />
        <span className="dist-legend-end win">wins</span>
        <span className="dist-legend-mid">(centre = break-even)</span>
        <span className="dist-legend-cap">net chips / hand</span>
      </div>

      {tip &&
        createPortal(
          <div className="dist-tip" style={{ left: tip.x + 14, top: tip.y + 14 }}>
            <span className="dist-tip-name">{tip.player.name}</span>
            <span className="dist-tip-val">{formatMetric(tip.player.metrics[metric.key], metric.unit)}</span>
            <span className={tip.player.chips_per_hand >= 0 ? 'dist-tip-chips win' : 'dist-tip-chips lose'}>
              {tip.player.chips_per_hand >= 0 ? '+' : ''}
              {Math.round(tip.player.chips_per_hand)} chips/hand
            </span>
          </div>,
          document.body,
        )}
    </div>
  );
}
