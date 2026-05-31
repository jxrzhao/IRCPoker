import { useDeferredValue, useEffect, useMemo, useState } from 'react';
import Header from './components/Header.jsx';
import AboutBar from './components/AboutBar.jsx';
import ChipLedgerGraph from './components/ChipLedgerGraph.jsx';
import RadarDiff from './components/RadarDiff.jsx';
import DistributionView from './components/DistributionView.jsx';
import { loadLedger, loadPlayers, populationStats } from './data/dataset.js';

// DistributionView and RadarDiff are wired to live pipeline output (players.json
// + ledger.json). ChipLedgerGraph stays blank until its force-graph is built.
export default function App() {
  const [minHands, setMinHands] = useState(100);
  const [allPlayers, setAllPlayers] = useState([]);
  const [ledger, setLedger] = useState(null);
  const [selectedSharkId, setSelectedSharkId] = useState(null);
  const [feederCount, setFeederCount] = useState(8);

  useEffect(() => {
    let alive = true;
    loadPlayers()
      .then((rows) => alive && setAllPlayers(rows))
      .catch((err) => console.error('load players.json failed', err));
    loadLedger()
      .then((data) => {
        if (!alive) return;
        setLedger(data);
        // Default the radar/ledger to the top shark as soon as data lands.
        if (data?.sharks?.length) setSelectedSharkId(data.sharks[0].id);
      })
      .catch((err) => console.error('load ledger.json failed', err));
    return () => {
      alive = false;
    };
  }, []);

  // The slider value updates instantly (Header reads `minHands`), but the heavy
  // per-player filter + stat recompute + thousands of SVG dots are driven by a
  // deferred copy so dragging stays smooth: React keeps the old chart on screen
  // and recomputes once the drag settles instead of on every tick.
  const deferredMinHands = useDeferredValue(minHands);
  const players = useMemo(
    () => allPlayers.filter((p) => p.hands >= deferredMinHands),
    [allPlayers, deferredMinHands],
  );
  const stats = useMemo(() => populationStats(players), [players]);

  const playersByName = useMemo(() => {
    const map = new Map();
    for (const p of allPlayers) map.set(p.name, p);
    return map;
  }, [allPlayers]);

  // The min-hands filter applies to every view: sharks and feeders below the
  // threshold drop out, and the radar normalises against the same filtered pool.
  const sharks = useMemo(
    () => (ledger?.sharks || []).filter((s) => s.hands >= deferredMinHands),
    [ledger, deferredMinHands],
  );
  // Keep the selected shark if it still qualifies, else fall back to the top one.
  const activeShark =
    sharks.find((s) => s.id === selectedSharkId) || sharks[0] || null;
  const sharkPlayer = activeShark ? playersByName.get(activeShark.name) || null : null;
  const feeders = useMemo(() => {
    if (!activeShark) return [];
    return activeShark.feeders
      .filter((f) => f.hands >= deferredMinHands)
      .map((f) => ({ ...f, player: playersByName.get(f.name) }))
      .filter((f) => f.player);
  }, [activeShark, playersByName, deferredMinHands]);

  return (
    <div className="app">
      <Header minHands={minHands} onMinHands={setMinHands} />
      <AboutBar />

      <main className="app-body">
        <div className="row-solo">
          <DistributionView players={players} stats={stats} minHands={deferredMinHands} />
        </div>

        <div className="row-duo">
          <ChipLedgerGraph
            sharks={sharks}
            shark={activeShark}
            feeders={feeders}
            selectedSharkId={activeShark?.id || null}
            onSelectShark={setSelectedSharkId}
            feederCount={feederCount}
          />
          <RadarDiff
            shark={sharkPlayer}
            feeders={feeders}
            stats={stats}
            feederCount={feederCount}
            onFeederCount={setFeederCount}
          />
        </div>

        <footer className="app-footer">ECS 273 · Team 16</footer>
      </main>
    </div>
  );
}
