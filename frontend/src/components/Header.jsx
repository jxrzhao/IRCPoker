function LogoEmblem() {
  return (
    <svg
      className="logo-emblem"
      viewBox="0 0 96 112"
      role="img"
      aria-label="PokerProfiler emblem"
    >
      <defs>
        <linearGradient id="cardFace" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fdfaf1" />
          <stop offset="1" stopColor="#efe7d4" />
        </linearGradient>
      </defs>
      {/* card face + engraved double keyline */}
      <rect x="1.5" y="1.5" width="93" height="109" rx="13"
        fill="url(#cardFace)" stroke="#2a2118" strokeWidth="1.6" />
      <rect x="6.5" y="6.5" width="83" height="99" rx="9"
        fill="none" stroke="#a87f2b" strokeWidth="1" strokeOpacity="0.5" />
      {/* faint engraved quadrant cross */}
      <g stroke="#a87f2b" strokeOpacity="0.16" strokeWidth="0.8">
        <line x1="48" y1="12" x2="48" y2="100" />
        <line x1="12" y1="56" x2="84" y2="56" />
      </g>
      {/* four suits, 2x2 */}
      <g fontFamily="'Cormorant Garamond', Georgia, serif" fontSize="33"
        textAnchor="middle" dominantBaseline="central">
        <text x="32" y="40" fill="#241f17">&#9824;</text>
        <text x="64" y="40" fill="#9c2b22">&#9829;</text>
        <text x="32" y="74" fill="#9c2b22">&#9830;</text>
        <text x="64" y="74" fill="#241f17">&#9827;</text>
      </g>
    </svg>
  );
}

export default function Header({ minHands, onMinHands }) {
  return (
    <header className="app-header">
      <div className="brand">
        <LogoEmblem />
        <div>
          <h1>
            Poker<em>Profiler</em>
          </h1>
          <div className="tagline">Playstyle Profiling &amp; Exploit Discovery</div>
        </div>
      </div>

      <div className="header-controls">
        <div className="control filter-control">
          <label htmlFor="minhands" className="control-label">
            <span>min-hands filter</span>
            <span className="control-val">
              {minHands.toLocaleString()}
              <span className="control-unit">hands</span>
            </span>
          </label>
          <input
            id="minhands"
            type="range"
            min="100"
            max="13000"
            step="50"
            value={minHands}
            onChange={(e) => onMinHands(Number(e.target.value))}
          />
          <span className="control-hint">filters every view below</span>
        </div>
      </div>
    </header>
  );
}
