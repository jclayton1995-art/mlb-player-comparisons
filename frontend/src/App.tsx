import { useCallback, useEffect, useState } from 'react';
import { api, type CompareResponse, type Meta } from './api';
import { Search } from './components/Search';
import { TargetRail } from './components/TargetRail';
import { CompList } from './components/CompList';
import { ModelPanel } from './components/ModelPanel';
import { ShareCard } from './components/ShareCard';
import { Explore } from './components/Explore';

type Sel = { id: number; season: number } | null;

function readHash(): Sel {
  const m = location.hash.match(/#\/(\d+)\/(\d{4})/);
  return m ? { id: +m[1], season: +m[2] } : null;
}
const isExplore = () => location.hash.startsWith('#/explore');

const STARTERS: { name: string; id: number; season: number }[] = [
  { name: 'Aaron Judge 2024', id: 592450, season: 2024 },
  { name: 'Bobby Witt Jr. 2024', id: 677951, season: 2024 },
  { name: 'Luis Arraez 2023', id: 650333, season: 2023 },
  { name: 'Elly De La Cruz 2024', id: 682829, season: 2024 },
];

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [sel, setSel] = useState<Sel>(readHash);
  const [data, setData] = useState<CompareResponse | null>(null);
  const [seasons, setSeasons] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [showModel, setShowModel] = useState(false);
  const [showShare, setShowShare] = useState(false);
  const [explore, setExplore] = useState(isExplore);

  useEffect(() => {
    api.meta().then(setMeta).catch((e) => setErr(String(e)));
    const onHash = () => { setSel(readHash()); setExplore(isExplore()); };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const pick = useCallback((id: number, season: number) => {
    location.hash = `#/${id}/${season}`;
  }, []);

  useEffect(() => {
    if (!sel) { setData(null); return; }
    let live = true;
    setLoading(true);
    setErr(null);
    Promise.all([api.compare(sel.id, sel.season), api.player(sel.id)])
      .then(([c, p]) => {
        if (!live) return;
        setData(c);
        setSeasons(p.seasons.map((s) => s.season));
        document.title = `${c.target.name} ${c.target.season} — Comps`;
      })
      .catch((e) => live && setErr(String(e)))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [sel]);

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-name">Comps</span>
          <span className="brand-sub">hitter comparisons on underlying skills</span>
        </div>
        <Search onPick={pick} />
        <div className="topbar-right">
          <button className={'btn' + (explore ? ' on' : '')} onClick={() => { location.hash = '#/explore'; }}>Explore</button>
          {meta && (
            <button className={'btn model-btn' + (showModel ? ' on' : '')} onClick={() => setShowModel(true)}>
              How comps are chosen
            </button>
          )}
        </div>
      </header>

      {err && <div className="error" style={{ margin: '16px 24px' }}>{err}</div>}

      {explore && meta && <main className="main-wide"><Explore meta={meta} onPick={pick} /></main>}

      {!explore && !sel && meta && (
        <div className="empty">
          <h2>Pick a hitter to find his comps</h2>
          <div>
            {meta.n_rows.toLocaleString()} hitter-seasons, {meta.seasons[0]}–{meta.seasons[meta.seasons.length - 1]}. Search above, start with one of these, or <a href="#/explore">explore the whole league</a>.
          </div>
          <div className="quick">
            {STARTERS.map((s) => (
              <button key={s.id + s.season} className="btn" onClick={() => pick(s.id, s.season)}>{s.name}</button>
            ))}
          </div>
        </div>
      )}

      {!explore && sel && meta && (
        <main className="main" style={{ opacity: loading ? 0.6 : 1, transition: 'opacity .15s' }}>
          {data ? (
            <>
              <TargetRail meta={meta} data={data} seasons={seasons} onSeason={(s) => pick(sel.id, s)} />
              <CompList meta={meta} data={data} onPick={pick} onShare={() => setShowShare(true)} />
            </>
          ) : (
            <>
              <div className="skeleton" style={{ height: 520 }} />
              <div className="skeleton" style={{ height: 520 }} />
            </>
          )}
        </main>
      )}

      {showModel && meta && <ModelPanel meta={meta} onClose={() => setShowModel(false)} />}
      {showShare && meta && data && <ShareCard meta={meta} data={data} onClose={() => setShowShare(false)} />}
    </div>
  );
}
