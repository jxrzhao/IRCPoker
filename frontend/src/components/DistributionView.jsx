import { useEffect, useMemo, useState } from 'react';
import { GROUPS, metricsForGroup } from '../data/metrics.js';
import { netChipColor } from '../data/colors.js';
import DistCell from './DistCell.jsx';

const ROTATE_MS = 2200;
const CLOSE_MS = 200; // keep in sync with the lb-out animation

export default function DistributionView({ players = [], stats = {}, minHands }) {
  const [group, setGroup] = useState('preflop');
  const [active, setActive] = useState(0);
  const [prevGroup, setPrevGroup] = useState(group);
  const [paused, setPaused] = useState(false);
  const [zoomed, setZoomed] = useState(null); // metric object shown in lightbox
  const [closing, setClosing] = useState(false);

  const metrics = useMemo(() => metricsForGroup(group), [group]);
  const color = useMemo(() => netChipColor(players.map((p) => p.chips_per_hand)), [players]);
  const hasData = players.length > 0;

  // Reset the carousel to the first card when the group tab changes. This is the
  // documented "adjust state during render" pattern (no effect needed).
  if (group !== prevGroup) {
    setPrevGroup(group);
    setActive(0);
  }

  // Auto-advance, paused on hover or while the lightbox is open.
  useEffect(() => {
    if (!hasData || paused || zoomed || metrics.length < 2) return undefined;
    const id = setInterval(() => setActive((i) => (i + 1) % metrics.length), ROTATE_MS);
    return () => clearInterval(id);
  }, [hasData, paused, zoomed, metrics.length]);

  // Animate the lightbox out before unmounting.
  function closeZoom() {
    setClosing(true);
    setTimeout(() => {
      setZoomed(null);
      setClosing(false);
    }, CLOSE_MS);
  }

  // Close the lightbox on Escape.
  useEffect(() => {
    if (!zoomed) return undefined;
    const onKey = (e) => e.key === 'Escape' && closeZoom();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [zoomed]);

  return (
    <section className="panel dist">
      <div className="panel-head">
        <h2>Population Distribution</h2>
        <span className="panel-sub">
          {hasData ? (
            <>
              <strong className="dist-count">{players.length.toLocaleString()}</strong> players
              {minHands != null && (
                <span className="dist-filtertag">≥ {minHands.toLocaleString()} hands</span>
              )}
              {' · dot = player, shaded by net chips/hand'}
            </>
          ) : (
            'per-metric population distribution · dot = player'
          )}
        </span>
      </div>

      <div className="radar-tabs">
        {GROUPS.map((g) => (
          <button
            key={g.key}
            className={group === g.key ? 'active' : ''}
            onClick={() => setGroup(g.key)}
          >
            {g.label}
          </button>
        ))}
        <span className="dist-legendrow">
          <span className="dist-meankey">
            <span className="meanline" /> population mean
          </span>
          <span className="dist-chipkey">
            <span className="dist-chipkey-cap">net chips / hand</span>
            <span className="dist-chipkey-end lose">big loss</span>
            <span className="dist-chipkey-bar" />
            <span className="dist-chipkey-end win">big win</span>
          </span>
        </span>
      </div>

      {hasData ? (
        <div
          className="dist-carousel"
          onMouseEnter={() => setPaused(true)}
          onMouseLeave={() => setPaused(false)}
        >
          <button
            className="carousel-arrow prev"
            aria-label="previous metric"
            onClick={() => setActive((i) => (i - 1 + metrics.length) % metrics.length)}
          >
            ‹
          </button>

          <div className="carousel-stage">
            {metrics.map((m, i) => {
              const n = metrics.length;
              let off = i - active;
              if (off > n / 2) off -= n;
              if (off < -n / 2) off += n;
              const abs = Math.abs(off);
              const center = off === 0;
              // Hovering the carousel pauses rotation AND lifts the centre card
              // so it reads as clickable.
              const scale = center ? (paused ? 1.05 : 1) : 0.66;
              return (
                <div
                  key={m.key}
                  className={`coverflow-slide ${center ? 'active' : ''} ${center && paused ? 'lifted' : ''}`}
                  style={{
                    transform: `translate(-50%, -50%) translateX(${off * 70}%) scale(${scale})`,
                    opacity: abs > 2 ? 0 : center ? 1 : abs === 1 ? 0.55 : 0.25,
                    zIndex: 10 - abs,
                    pointerEvents: abs > 1 ? 'none' : 'auto',
                  }}
                  onClick={() => (center ? setZoomed(m) : setActive(i))}
                >
                  <DistCell metric={m} players={players} st={stats[m.key]} color={color} />
                </div>
              );
            })}
          </div>

          <button
            className="carousel-arrow next"
            aria-label="next metric"
            onClick={() => setActive((i) => (i + 1) % metrics.length)}
          >
            ›
          </button>

          <div className="carousel-dots">
            {metrics.map((m, i) => (
              <button
                key={m.key}
                className={i === active ? 'on' : ''}
                aria-label={`show ${m.label}`}
                onClick={() => setActive(i)}
              />
            ))}
          </div>
        </div>
      ) : (
        <div className="empty-hint">
          Per-metric population histograms. One dot per player, shaded by net
          chips per hand.
        </div>
      )}

      {zoomed && (
        <div
          className={`dist-lightbox ${closing ? 'closing' : ''}`}
          onClick={closeZoom}
        >
          <div className="dist-lightbox-card" onClick={(e) => e.stopPropagation()}>
            <DistCell metric={zoomed} players={players} st={stats[zoomed.key]} color={color} />
          </div>
        </div>
      )}
    </section>
  );
}
