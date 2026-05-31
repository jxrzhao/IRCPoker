import { useMemo, useState } from 'react';
import { COLORS, netChipColor } from '../data/colors.js';

const W = 380;
const H = 320;
const CX = W / 2;
const CY = H / 2;
const SEAT_RX = 130;
const SEAT_RY = 102;
const TABLE_RX = 172;
const TABLE_RY = 140;
const SHARK_R = 26;

const PARCHMENT = '#f3ead4';
const BRASS = '#c8a45a';

function netLabel(net) {
  const sign = net >= 0 ? '+' : '-';
  const a = Math.abs(net);
  if (a >= 1e6) return `${sign}${(a / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `${sign}${(a / 1e3).toFixed(0)}k`;
  return `${sign}${a}`;
}

// Poker-chip glyph: disc + edge spots + inner ring, so a node reads as a chip.
function Chip({ x, y, r, fill, ring }) {
  const spots = 8;
  return (
    <g>
      {ring && <circle cx={x} cy={y} r={r + 4} fill="none" stroke={BRASS} strokeWidth="2" />}
      <circle cx={x} cy={y} r={r} fill={fill} stroke="#fffdf7" strokeWidth="1.5" />
      {Array.from({ length: spots }).map((_, i) => {
        const a = (i / spots) * 2 * Math.PI;
        return (
          <rect
            key={i}
            x={x + (r - 1.5) * Math.cos(a) - r * 0.16}
            y={y + (r - 1.5) * Math.sin(a) - r * 0.06}
            width={r * 0.32}
            height={r * 0.12}
            rx={r * 0.05}
            fill="#fffdf7"
            fillOpacity="0.85"
            transform={`rotate(${(a * 180) / Math.PI} ${x + (r - 1.5) * Math.cos(a)} ${y + (r - 1.5) * Math.sin(a)})`}
          />
        );
      })}
      <circle cx={x} cy={y} r={r * 0.56} fill="none" stroke="#fffdf7" strokeOpacity="0.55" strokeWidth="1" />
    </g>
  );
}

// Tapered chip-flow ribbon from a seat into the pot, ending in an arrowhead.
function flowPath(seat) {
  const dx = CX - seat.x;
  const dy = CY - seat.y;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  const px = -uy;
  const py = ux;
  const w0 = seat.w; // half-width at seat
  const stem = 1.6;
  const headLen = 12;
  const headHalf = 6.5;
  const s = { x: seat.x + ux * (seat.r + 1), y: seat.y + uy * (seat.r + 1) };
  const tip = { x: CX - ux * (SHARK_R + 3), y: CY - uy * (SHARK_R + 3) };
  const hb = { x: tip.x - ux * headLen, y: tip.y - uy * headLen };
  const P = (pt, n) => `${pt.x + px * n},${pt.y + py * n}`;
  return [
    `M${P(s, w0)}`,
    `L${P(hb, stem)}`,
    `L${P(hb, headHalf)}`,
    `L${tip.x},${tip.y}`,
    `L${P(hb, -headHalf)}`,
    `L${P(hb, -stem)}`,
    `L${P(s, -w0)}`,
    'Z',
  ].join(' ');
}

// Shark-vs-feeders as a poker table flanked by a clickable shark list (left) and
// a live feeder-detail list (right). Chip size / ribbon width are log-scaled then
// clamped so one dominant feeder doesn't dwarf the rest. The min-hands filter is
// applied upstream in App, so `sharks`/`feeders` already respect it.
export default function ChipLedgerGraph({
  sharks = [],
  shark = null,
  feeders = [],
  selectedSharkId = null,
  onSelectShark,
  feederCount = 8,
}) {
  const [hoverName, setHoverName] = useState(null);

  const shown = useMemo(() => feeders.slice(0, feederCount), [feeders, feederCount]);

  const color = useMemo(
    () => netChipColor(shown.map((f) => f.net_amount).concat(shark ? [shark.net_amount] : [])),
    [shown, shark],
  );

  const chipScale = useMemo(() => {
    const vals = shown.map((f) => Math.max(1, f.chips));
    const lo = Math.log(Math.min(...vals, 1) || 1);
    const hi = Math.log(Math.max(...vals, 2));
    return (chips) => (hi === lo ? 0.5 : (Math.log(Math.max(1, chips)) - lo) / (hi - lo));
  }, [shown]);

  const seats = useMemo(
    () =>
      shown.map((f, i) => {
        const ang = (i / shown.length) * 2 * Math.PI - Math.PI / 2;
        const t = chipScale(f.chips);
        return {
          f,
          x: CX + SEAT_RX * Math.cos(ang),
          y: CY + SEAT_RY * Math.sin(ang),
          // wide radius range so "more chips fed" is unmistakable at a glance
          r: 7 + t * 18,
          w: 2 + t * 9,
        };
      }),
    [shown, chipScale],
  );

  if (!shark) {
    return (
      <section className="panel fill ledger">
        <div className="panel-head">
          <h2>Chip-Ledger Graph</h2>
          <span className="panel-sub">net chip flow · pick a shark</span>
        </div>
        <div className="ledger-empty">
          <p className="empty-hint">
            Directed net chip-flow between players. Pick a shark to drive the
            other views.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel fill ledger">
      <div className="panel-head">
        <h2>Chip-Ledger Graph</h2>
        <span className="panel-sub">net chip flow · feeders → shark</span>
      </div>

      <div className="ledger-layout">
        <aside className="ledger-rail">
          <div className="rail-title">
            <span>Sharks · top winners</span>
            <span className="rail-count">{sharks.length}</span>
          </div>
          <ul className="rail-list">
            {sharks.map((s, i) => (
              <li key={s.id}>
                <button
                  className={`rail-row shark ${s.id === selectedSharkId ? 'active' : ''}`}
                  onClick={() => onSelectShark?.(s.id)}
                >
                  <span className="rail-rank">{i + 1}</span>
                  <span className="rail-name">{s.name}</span>
                  <span className="rail-net win">{netLabel(s.net_amount)}</span>
                  <span className="rail-go" aria-hidden="true">›</span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <div className="ledger-stage">
          <div className="ledger-caption">
            <span className="cap-spade">&#9824;</span>
            <span className="cap-name">{shark.name}</span>
            <span className="cap-net">{netLabel(shark.net_amount)} chips won</span>
          </div>

          <svg viewBox={`0 0 ${W} ${H}`} className="ledger-svg">
            <defs>
              <radialGradient id="felt" cx="50%" cy="40%" r="68%">
                <stop offset="0" stopColor="#5b8a6c" />
                <stop offset="0.7" stopColor="#46735a" />
                <stop offset="1" stopColor="#395f49" />
              </radialGradient>
              <linearGradient id="brass" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stopColor="#ecd79a" />
                <stop offset="0.5" stopColor="#c8a45a" />
                <stop offset="1" stopColor="#9c7a32" />
              </linearGradient>
            </defs>

            <ellipse cx={CX} cy={CY} rx={TABLE_RX} ry={TABLE_RY} fill="url(#brass)" />
            <ellipse cx={CX} cy={CY} rx={TABLE_RX - 6} ry={TABLE_RY - 6} fill="url(#felt)" />
            {/* soft top sheen for depth */}
            <ellipse cx={CX} cy={CY - TABLE_RY * 0.34} rx={TABLE_RX * 0.66} ry={TABLE_RY * 0.4} fill="#ffffff" fillOpacity="0.06" />
            <ellipse cx={CX} cy={CY} rx={TABLE_RX - 14} ry={TABLE_RY - 14} fill="none" stroke="#ffffff" strokeOpacity="0.12" strokeWidth="1" />

            {/* flow ribbons (behind chips) */}
            {seats.map(({ f }, idx) => (
              <path
                key={`flow-${f.name}`}
                d={flowPath(seats[idx])}
                fill={color(f.net_amount)}
                fillOpacity={hoverName && hoverName !== f.name ? 0.25 : 0.78}
              />
            ))}

            {/* feeder chips */}
            {seats.map(({ f, x, y, r }) => (
              <g
                key={f.name}
                opacity={hoverName && hoverName !== f.name ? 0.45 : 1}
                style={{ cursor: 'pointer' }}
                onMouseEnter={() => setHoverName(f.name)}
                onMouseLeave={() => setHoverName(null)}
              >
                <Chip x={x} y={y} r={r} fill={color(f.net_amount)} ring={hoverName === f.name} />
                <text
                  x={x}
                  y={y + r + 11}
                  textAnchor="middle"
                  fontFamily="var(--font-mono)"
                  fontSize="9"
                  fill={PARCHMENT}
                  style={{ pointerEvents: 'none' }}
                >
                  {f.name}
                </text>
              </g>
            ))}

            {/* shark pot */}
            <Chip x={CX} y={CY} r={SHARK_R} fill="url(#brass)" />
            <text
              x={CX}
              y={CY + 1}
              textAnchor="middle"
              dominantBaseline="central"
              fontFamily="'Cormorant Garamond', Georgia, serif"
              fontSize="22"
              fill="#3a2f12"
              style={{ pointerEvents: 'none' }}
            >
              &#9824;
            </text>
          </svg>

          <div className="ledger-foot">
            <span className="lf-item">
              <svg width="56" height="30" aria-hidden="true">
                <circle cx="9" cy="20" r="5" fill="none" stroke={COLORS.gold} strokeWidth="1.5" />
                <circle cx="38" cy="15" r="13" fill="none" stroke={COLORS.gold} strokeWidth="1.5" />
              </svg>
              <span className="lf-text">
                <b>chip size</b> = chips this feeder lost to the shark
                <span className="lf-sub">few &nbsp;→&nbsp; many</span>
              </span>
            </span>
            <span className="lf-item">
              <span className="lf-rampwrap">
                <span className="lf-rampcap lose">net loser</span>
                <span className="lf-ramp" />
                <span className="lf-rampcap win">net winner</span>
              </span>
              <span className="lf-text">
                <b>chip colour</b> = feeder&apos;s overall result
              </span>
            </span>
          </div>
        </div>

        <aside className="ledger-rail">
          <div className="rail-title">
            <span>Top feeders · into {shark.name}</span>
            <span className="rail-count">{shown.length}</span>
          </div>
          <ul className="rail-list">
            {shown.map((f, i) => (
              <li key={f.name}>
                <div
                  className={`rail-row feeder ${hoverName === f.name ? 'active' : ''}`}
                  onMouseEnter={() => setHoverName(f.name)}
                  onMouseLeave={() => setHoverName(null)}
                >
                  <span className="rail-rank">{i + 1}</span>
                  <span className="rail-swatch" style={{ background: color(f.net_amount) }} />
                  <span className="rail-name">{f.name}</span>
                  <span className="rail-fed">{netLabel(f.chips)}</span>
                </div>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </section>
  );
}
