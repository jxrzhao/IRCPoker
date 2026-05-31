import { useState } from 'react';

export default function AboutBar() {
  const [open, setOpen] = useState(false);

  return (
    <div className={`about-bar ${open ? 'open' : ''}`}>
      <button
        className="about-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="about-eyebrow">About this dashboard</span>
        <svg
          className="about-chevron"
          viewBox="0 0 16 16"
          width="13"
          height="13"
          aria-hidden="true"
        >
          <path
            d="M3.5 6 L8 10.5 L12.5 6"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      <div className="about-drawer">
        <div className="about-inner">
          <p className="about-lead">
            PokerProfiler turns raw IRC hold&apos;em hands into a 30-metric
            fingerprint per player
            <span className="sep">|</span>
            spot who wins, who pays, and why.
          </p>
          <ol className="about-steps">
            <li>
              <b>Overview.</b> Scan the population distribution of each metric to
              see how the field plays.
            </li>
            <li>
              <b>Select.</b> Pick a shark from the chip-ledger graph to see who
              feeds them chips.
            </li>
            <li>
              <b>Exploit.</b> Read the radar diff for the largest gaps between the
              shark and their feeders, the exploitable edges.
            </li>
          </ol>
        </div>
      </div>
    </div>
  );
}
