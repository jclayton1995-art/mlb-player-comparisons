import { useEffect, useMemo, useState } from 'react';
import { api, fmt, type ExploreRow, type Meta } from '../api';
import { Avatar } from './Avatar';

type List = { title: string; sub: string; rows: ExploreRow[]; render: (r: ExploreRow) => React.ReactNode };

/** The front page: the model's view of the league right now, so there is something to react to before you search. */
export function Home({ meta, onPick }: { meta: Meta; onPick: (id: number, season: number) => void }) {
  const [rows, setRows] = useState<ExploreRow[] | null>(null);
  useEffect(() => { api.explore().then(setRows).catch(() => setRows([])); }, []);
  const latest = meta.seasons[meta.seasons.length - 1];

  const lists = useMemo<List[]>(() => {
    if (!rows) return [];
    const cur = rows.filter((r) => r.season === latest && r.pa >= 300);
    const full = cur.filter((r) => r.pa >= 400);   // climb/fall lists: whole seasons only, so they read as calls, not small-sample noise
    const gap = (r: ExploreRow) => (r.proj_wrc != null && r.wrc_plus != null ? r.proj_wrc - r.wrc_plus : null);
    const num = (v: number | null | undefined) => <b>{fmt(v, '{:.0f}')}</b>;
    return [
      { title: `Highest ${latest + 1} projections`, sub: 'projected wRC+ · from each hitter’s 40 closest comps',
        rows: [...cur].sort((a, b) => (b.proj_wrc ?? -1) - (a.proj_wrc ?? -1)).slice(0, 8), render: (r) => num(r.proj_wrc) },
      { title: 'Expected to climb', sub: 'projection minus this season, wRC+',
        rows: [...full].filter((r) => gap(r) != null).sort((a, b) => gap(b)! - gap(a)!).slice(0, 8), render: (r) => <b className="up">+{Math.round(gap(r)!)}</b> },
      { title: 'Expected to fall', sub: 'projection minus this season, wRC+',
        rows: [...full].filter((r) => gap(r) != null).sort((a, b) => gap(a)! - gap(b)!).slice(0, 8), render: (r) => <b className="dn">{Math.round(gap(r)!)}</b> },
      { title: 'Closest matches in the data', sub: 'this season’s hitters with a near-twin somewhere since 2015',
        rows: [...cur].sort((a, b) => (b.similarity ?? -1) - (a.similarity ?? -1)).slice(0, 8),
        render: (r) => <span className="twin"><b>{fmt(r.similarity, '{:.0f}')}</b><span>{r.comp_name} ’{String(r.comp_season).slice(2)}</span></span> },
    ];
  }, [rows, latest]);

  return (
    <main className="home">
      <section className="home-hero">
        <h1>Who does he hit like?</h1>
        <p>
          Every hitter-season since {meta.seasons[0]}, matched on the skills underneath the numbers — contact quality, batted-ball shape, approach — never on the results. Search a hitter, or start with the model’s view of {latest}.
        </p>
        <div className="home-links">
          <a className="btn primary" href="#/explore">Explore the whole league</a>
          <button className="btn" onClick={() => document.querySelector<HTMLInputElement>('.search-input')?.focus()}>Search a hitter</button>
        </div>
      </section>
      <section className="home-grid">
        {lists.map((l) => (
          <div className="card list" key={l.title}>
            <header className="card-head"><h2>{l.title}</h2><span className="sub">{l.sub}</span></header>
            <ol>
              {l.rows.map((r) => (
                <li key={r.row}>
                  <button onClick={() => onPick(r.mlbam_id, r.season)}>
                    <Avatar id={r.mlbam_id} name={r.name} size={32} />
                    <span className="nm">{r.name}<span className="sub">{r.team ?? ''}{r.age != null ? ` · ${r.age}` : ''} · {fmt(r.wrc_plus, '{:.0f}')} wRC+</span></span>
                    <span className="val">{l.render(r)}</span>
                  </button>
                </li>
              ))}
            </ol>
          </div>
        ))}
        {!rows && <div className="skeleton" style={{ height: 320 }} />}
      </section>
    </main>
  );
}
