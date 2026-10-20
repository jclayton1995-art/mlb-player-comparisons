import { useEffect, useMemo, useState } from 'react';
import { api, fmt, type ExploreRow, type Meta } from '../api';
import { Avatar } from './Avatar';

type SortKey = 'similarity' | 'wrc_plus' | 'xwoba' | 'proj_wrc' | 'next_wrc' | 'pa' | 'age' | 'season' | 'name' | 'gap' | `m:${string}`;
type Col = { key: SortKey; label: string; hint?: string; num?: boolean; render: (r: ExploreRow) => React.ReactNode };
type Cond = { metric: string; op: '>=' | '<='; pct: number };

const PAGE = 100;
const PA_STEPS = [100, 200, 300, 400, 500];
const PCT_STEPS = [95, 90, 80, 75, 70, 60, 50, 40, 30, 25, 20, 10, 5];

/** Projection minus current wRC+: who the model expects to climb or fall the most. */
function gap(r: ExploreRow) { return r.proj_wrc != null && r.wrc_plus != null ? r.proj_wrc - r.wrc_plus : null; }

/** Savant-style percentile fill (same scale as the share card). */
function pctStyle(p: number | undefined, directional: boolean): React.CSSProperties | undefined {
  if (p == null || !directional) return undefined;
  const t = Math.min(1, Math.abs(p - 50) / 50);
  const [r, g, b] = p < 50 ? [31, 86, 168] : [214, 38, 44];
  const mix = (c: number) => Math.round(255 + (c - 255) * t);
  return { background: `rgb(${mix(r)},${mix(g)},${mix(b)})`, color: t > 0.55 ? '#fff' : undefined };
}

export function Explore({ meta, onPick }: { meta: Meta; onPick: (id: number, season: number) => void }) {
  const [rows, setRows] = useState<ExploreRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [season, setSeason] = useState<number | 'all'>(meta.seasons[meta.seasons.length - 1]);
  const [minPa, setMinPa] = useState(300);
  const [q, setQ] = useState('');
  const [conds, setConds] = useState<Cond[]>([]);
  const [sort, setSort] = useState<SortKey>('wrc_plus');
  const [dir, setDir] = useState<1 | -1>(-1);
  const [shown, setShown] = useState(PAGE);

  useEffect(() => { api.explore().then(setRows).catch((e) => setErr(String(e))); }, []);
  useEffect(() => { setShown(PAGE); }, [season, minPa, q, sort, dir, conds]);

  // Every metric the explorer knows about: model features + display-only tracking (bat speed etc.)
  const metrics = useMemo(() => {
    const out: { key: string; label: string; fmt: string; unit: string; directional: boolean; group: string }[] = [];
    for (const f of meta.features) {
      const m = meta.feature_meta[f];
      out.push({ key: f, label: m.label, fmt: m.fmt, unit: m.unit, directional: m.higher_better != null, group: m.cluster_label });
    }
    for (const [k, m] of Object.entries(meta.tracking)) out.push({ key: k, label: `${m.label} (2024+)`, fmt: m.fmt, unit: m.unit, directional: m.higher_better != null, group: 'Bat tracking' });
    return out;
  }, [meta]);
  const metricOf = (k: string) => metrics.find((m) => m.key === k);

  const condMetrics = conds.map((c) => c.metric).filter((k, i, a) => a.indexOf(k) === i);

  const cols: Col[] = useMemo(() => {
    const base: Col[] = [
      { key: 'name', label: 'Hitter', render: (r) => (
        <div className="who"><Avatar id={r.mlbam_id} name={r.name} size={28} /><div><div className="nm">{r.name}</div><div className="sub">{r.season}{r.team ? ` ${r.team}` : ''}{r.age != null ? ` · age ${r.age}` : ''}</div></div></div>) },
      { key: 'pa', label: 'PA', num: true, render: (r) => r.pa },
      { key: 'wrc_plus', label: 'wRC+', num: true, render: (r) => fmt(r.wrc_plus, '{:.0f}') },
      { key: 'xwoba', label: 'xwOBA', num: true, render: (r) => fmt(r.xwoba, '{:.3f}') },
    ];
    const metricCols: Col[] = condMetrics.map((k) => {
      const m = metricOf(k)!;
      return {
        key: `m:${k}` as SortKey, label: m.label.replace(' (2024+)', ''), hint: 'value · percentile within season', num: true,
        render: (r) => {
          const p = r.pct[k], v = r.val[k];
          return v == null ? <span className="pending">–</span> : (
            <span className="ex-metric" style={pctStyle(p, m.directional)}>{fmt(v, m.fmt)}{m.unit === '%' ? '' : m.unit}<small>{p != null ? ` ${p}` : ''}</small></span>
          );
        },
      };
    });
    const tail: Col[] = [
      { key: 'similarity', label: 'Best comp', hint: 'closest profile, any other player, any season', render: (r) => r.comp_name ? (
        <div className="who"><Avatar id={r.comp_id} name={r.comp_name} size={28} /><div><div className="nm">{r.comp_name}</div><div className="sub">{r.comp_season}{r.comp_next_wrc != null ? ` · next year ${Math.round(r.comp_next_wrc)} wRC+` : ''}</div></div></div>) : '–' },
      { key: 'similarity', label: 'Similarity', hint: '100 = identical, 90 = typical best match', num: true, render: (r) => <span className="ex-sim">{fmt(r.similarity, '{:.1f}')}</span> },
      { key: 'proj_wrc', label: 'Proj. wRC+', hint: 'next season, from his 40 closest comps', num: true, render: (r) => fmt(r.proj_wrc, '{:.0f}') },
      { key: 'gap', label: 'Proj − now', hint: 'projection minus this season', num: true, render: (r) => { const g = gap(r); return g == null ? '–' : <span className={'d ' + (g >= 0 ? 'up' : 'dn')}>{g > 0 ? '+' : ''}{Math.round(g)}</span>; } },
      { key: 'next_wrc', label: 'Actual next', num: true, render: (r) => r.next_wrc != null ? fmt(r.next_wrc, '{:.0f}') : <span className="pending">–</span> },
    ];
    return [...base, ...metricCols, ...tail];
  }, [condMetrics.join(','), metrics]);

  const view = useMemo(() => {
    if (!rows) return [];
    const ql = q.trim().toLowerCase();
    let v = rows.filter((r) =>
      r.pa >= minPa && (season === 'all' || r.season === season)
      && (!ql || r.name.toLowerCase().includes(ql) || (r.comp_name ?? '').toLowerCase().includes(ql))
      && conds.every((c) => { const p = r.pct[c.metric]; return p != null && (c.op === '>=' ? p >= c.pct : p <= c.pct); }));
    const val = (r: ExploreRow): number | string | null =>
      sort === 'gap' ? gap(r) : sort.startsWith('m:') ? (r.pct[sort.slice(2)] ?? null) : (r[sort as keyof ExploreRow] as number | string | null);
    v = [...v].sort((a, b) => {
      const x = val(a), y = val(b);
      if (x == null) return 1; if (y == null) return -1;
      return (x < y ? -1 : x > y ? 1 : 0) * dir;
    });
    return v;
  }, [rows, season, minPa, q, sort, dir, conds]);

  const clickSort = (k: SortKey) => {
    if (k === sort) setDir((d) => (d === 1 ? -1 : 1));
    else { setSort(k); setDir(k === 'name' ? 1 : -1); }
  };
  const addCond = () => setConds((c) => [...c, { metric: c.length ? 'ev50' : 'zone_contact_pct', op: '>=', pct: 70 }]);
  const setCond = (i: number, patch: Partial<Cond>) => setConds((c) => c.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const rmCond = (i: number) => setConds((c) => c.filter((_, j) => j !== i));

  const groups = metrics.reduce<Record<string, typeof metrics>>((acc, m) => { (acc[m.group] ??= []).push(m); return acc; }, {});

  return (
    <section className="explore">
      <div className="explore-head">
        <div>
          <div className="comps-title">Explore</div>
          <div className="comps-note">{rows ? `${view.length.toLocaleString()} of ${rows.length.toLocaleString()} hitter-seasons` : 'loading…'} · click a column to sort, a row to open</div>
        </div>
        <div className="explore-filters">
          <input className="ex-input" placeholder="filter by name" value={q} onChange={(e) => setQ(e.target.value)} />
          <select className="ex-input" value={season} onChange={(e) => setSeason(e.target.value === 'all' ? 'all' : +e.target.value)}>
            <option value="all">all seasons</option>
            {[...meta.seasons].reverse().map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select className="ex-input" value={minPa} onChange={(e) => setMinPa(+e.target.value)}>
            {PA_STEPS.map((p) => <option key={p} value={p}>{p}+ PA</option>)}
          </select>
        </div>
      </div>

      <div className="ex-conds">
        <span className="ex-conds-label">Percentile within season</span>
        {conds.map((c, i) => (
          <div className="ex-cond" key={i}>
            <select className="ex-input" value={c.metric} onChange={(e) => setCond(i, { metric: e.target.value })}>
              {Object.entries(groups).map(([g, ms]) => (
                <optgroup label={g} key={g}>{ms.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}</optgroup>
              ))}
            </select>
            <select className="ex-input" value={c.op} onChange={(e) => setCond(i, { op: e.target.value as Cond['op'] })}>
              <option value=">=">at or above</option>
              <option value="<=">at or below</option>
            </select>
            <select className="ex-input" value={c.pct} onChange={(e) => setCond(i, { pct: +e.target.value })}>
              {PCT_STEPS.map((p) => <option key={p} value={p}>{p}th</option>)}
            </select>
            <button className="btn ex-x" onClick={() => rmCond(i)} title="remove">×</button>
          </div>
        ))}
        <button className="btn" onClick={addCond}>+ add condition</button>
        {conds.length > 0 && <span className="comps-note">all conditions must hold · percentiles are oriented so higher = better where the metric has a direction</span>}
      </div>

      {err && <div className="error">{err}</div>}
      <div className="table-wrap"><table className="comp-table explore-table">
        <thead>
          <tr>
            {cols.map((c, i) => (
              <th key={i} className={(c.num ? 'r ' : '') + (sort === c.key && c.label !== 'Best comp' ? 'sorted' : '')} onClick={() => clickSort(c.key)} title={c.hint}>
                {c.label}{sort === c.key && c.label !== 'Best comp' ? (dir === -1 ? ' ↓' : ' ↑') : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {view.slice(0, shown).map((r) => (
            <tr key={r.row} className="comp-row" onClick={() => onPick(r.mlbam_id, r.season)}>
              {cols.map((c, i) => <td key={i} className={c.num ? 'r cell-v' : ''}>{c.render(r)}</td>)}
            </tr>
          ))}
        </tbody>
      </table></div>
      {view.length > shown && (
        <div className="explore-more"><button className="btn" onClick={() => setShown((s) => s + PAGE * 2)}>Show more ({(view.length - shown).toLocaleString()} left)</button></div>
      )}
    </section>
  );
}
