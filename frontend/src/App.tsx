import { useCallback, useEffect, useState } from 'react';
import { api, type CompareResponse, type Meta } from './api';
import { Search } from './components/Search';
import { PlayerHero } from './components/PlayerHero';
import { ProjectionPanel } from './components/ProjectionPanel';
import { Home } from './components/Home';
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
          <a className="brand-name" href="#/">Comps</a>
          <span className="brand-sub">hitter comps on underlying skills</span>
        </div>
        <Search onPick={pick} />
        <div className="topbar-right">
          <a className={'nav' + (explore ? ' on' : '')} href="#/explore">Explore</a>
          {meta && <button className={'nav' + (showModel ? ' on' : '')} onClick={() => setShowModel(true)}>How it works</button>}
        </div>
      </header>

      {err && <div className="error" style={{ margin: '16px 24px' }}>{err}</div>}

      {explore && meta && <main className="main-wide"><Explore meta={meta} onPick={pick} /></main>}

      {!explore && !sel && meta && <Home meta={meta} onPick={pick} />}

      {!explore && sel && meta && (
        data ? (
          <>
            <PlayerHero data={data} seasons={seasons} onSeason={(s) => pick(sel.id, s)} onShare={() => setShowShare(true)} />
            <main className="main" style={{ opacity: loading ? 0.6 : 1, transition: 'opacity .15s' }}>
              <ProjectionPanel meta={meta} data={data} />
              <CompList meta={meta} data={data} onPick={pick} />
            </main>
          </>
        ) : (
          <main className="main"><div className="skeleton" style={{ height: 520 }} /><div className="skeleton" style={{ height: 520 }} /></main>
        )
      )}

      {showModel && meta && <ModelPanel meta={meta} onClose={() => setShowModel(false)} />}
      {showShare && meta && data && <ShareCard meta={meta} data={data} onClose={() => setShowShare(false)} />}
    </div>
  );
}
