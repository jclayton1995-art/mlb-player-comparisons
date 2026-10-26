import { useRef, useState } from 'react';
import { toPng } from 'html-to-image';
import { fmt, headshot as cdnHeadshot, LOW_CONFIDENCE, shortName, type CompareResponse, type Meta } from '../api';

const SHORT: Record<string, string> = {
  exit_velocity: 'Exit velo', ev50: 'EV50', max_exit_velocity: 'Max EV', hard_hit_pct: 'Hard-hit%', barrel_pct: 'Barrel%',
  brl_pa: 'Barrels / PA', launch_angle: 'Launch angle', anglesweetspotpercent: 'Sweet-spot%', gb_pct: 'Ground-ball%', ld_pct: 'Line-drive%',
  pull_pct: 'Pull%', oppo_pct: 'Oppo%', pull_air_pct: 'Pulled air%', chase_rate: 'Chase%', zone_swing_pct: 'Zone swing%',
  zone_contact_pct: 'Z-Contact%', o_contact_pct: 'Chase contact%', bat_speed: 'Bat speed', whiff_pct: 'Whiff%', swstr_pct: 'SwStr%', k_pct: 'K%', bb_pct: 'BB%',
};

/** Jack's pick: five process skills, contact → approach → swing → power → shape. K% and BB% stay model inputs
 *  (dropping them costs ~0.4 wRC+ RMSE) but read as results, so they're not shown. Bat speed is display-only (2024+). */
const CARD_METRICS = ['zone_contact_pct', 'chase_rate', 'bat_speed', 'ev50', 'pull_air_pct'];

function keyMetrics(meta: Meta): string[] {
  return CARD_METRICS.filter((f) => meta.features.includes(f) || meta.tracking[f]);
}

/** Same-origin proxy first (exportable to PNG); MLB's CDN as a display fallback; initials last. */
function Headshot({ id, name, size, cls }: { id: number; name: string; size: number; cls: string }) {
  const [stage, setStage] = useState(0);
  const src = stage === 0 ? `/api/headshot/${id}?w=${size > 80 ? 480 : 240}` : cdnHeadshot(id, size > 80 ? 480 : 240);
  return (
    <div className={cls} style={{ width: size, height: size, fontSize: size * 0.34 }}>
      {stage < 2
        ? <img src={src} alt="" crossOrigin={stage === 0 ? 'anonymous' : undefined} onError={() => setStage((s) => s + 1)} />
        : <span>{name.split(' ').map((p) => p[0]).slice(0, 2).join('')}</span>}
    </div>
  );
}

/** Savant-style cell fill. The server's percentile is already oriented so higher = better
 *  (lower-is-better metrics are flipped there). 0 = deep blue, 50 = white, 100 = bright red. */
function cellStyle(pct: number | null | undefined, higherBetter: boolean | null): React.CSSProperties | undefined {
  if (pct == null || higherBetter == null) return undefined;
  const p = pct;
  const t = Math.min(1, Math.abs(p - 50) / 50);             // 0 at the median, 1 at the extremes
  const [r, g, b] = p < 50 ? [31, 86, 168] : [214, 38, 44];   // blue · red
  const mix = (c: number) => Math.round(255 + (c - 255) * t);
  return { background: `rgb(${mix(r)},${mix(g)},${mix(b)})`, color: t > 0.55 ? '#fff' : undefined };
}

function Delta({ a, b, season }: { a: number | null | undefined; b: number | null | undefined; season: number }) {
  if (a == null || b == null) return null;
  const d = Math.round(b - a);
  return <span className={'delta ' + (d > 0 ? 'up' : d < 0 ? 'dn' : '')}>({d > 0 ? '+' : ''}{d} vs ’{String(season).slice(2)})</span>;
}

/** A fixed 1080×1350 (4:5) social card, laid out at half size and exported at 2×. */
export function ShareCard({ data, meta, onClose }: { data: CompareResponse; meta: Meta; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [busy, setBusy] = useState(false);
  const t = data.target;
  const pr = data.projection;
  const wrc = pr.values.wrc_plus, xw = pr.values.xwoba;
  const comps = data.comps.slice(0, 3);
  const actual = pr.actual && pr.actual.pa != null ? pr.actual.wrc_plus : null;
  const lowConf = pr.best_similarity != null && pr.best_similarity < LOW_CONFIDENCE;
  const keys = keyMetrics(meta);
  const file = `${t.name.replace(/[^A-Za-z0-9]+/g, '_')}_${t.season}_comps.png`;

  // Range bar geometry: pad the axis a little beyond low/high (and the actual, if shown)
  const pts = [wrc?.low, wrc?.high, wrc?.value, actual].filter((x): x is number => x != null);
  const span = Math.max(...pts) - Math.min(...pts) || 1;
  const axLo = Math.min(...pts) - span * 0.22, axHi = Math.max(...pts) + span * 0.22;
  const x = (v: number) => `${((v - axLo) / (axHi - axLo)) * 100}%`;

  const download = async () => {
    if (!ref.current) return;
    setBusy(true);
    try {
      const url = await toPng(ref.current, { pixelRatio: 2, cacheBust: true, backgroundColor: '#ffffff' });
      const a = document.createElement('a'); a.href = url; a.download = file; a.click();
    } finally { setBusy(false); }
  };

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <div className="share-modal" role="dialog" aria-label="Share card">
        <div className="share-tools">
          <span className="panel-title">Share card</span>
          <span className="panel-note">1080 × 1350</span>
          <span style={{ flex: 1 }} />
          <button className="btn" onClick={onClose}>Close</button>
          <button className="btn primary" onClick={download} disabled={busy}>{busy ? 'Rendering…' : 'Download PNG'}</button>
        </div>

        <div className="share-stage">
          <div className="card" ref={ref}>
            {/* 1 · who */}
            <div className="card-hero">
              <Headshot id={t.mlbam_id} name={t.name} size={88} cls="card-avatar" />
              <div className="card-hero-text">
                <div className="card-name">{t.name}</div>
                <div className="card-meta">{t.season}{t.team ? ` · ${t.team}` : ''} · {t.pa} PA{t.age != null ? ` · age ${t.age}` : ''}</div>
                <div className="card-stats">
                  <div><span className="v">{fmt(t.outcomes.wrc_plus?.value, '{:.0f}')}</span><span className="l">wRC+</span></div>
                  <div><span className="v">{fmt(t.outcomes.xwoba?.value, '{:.3f}')}</span><span className="l">xwOBA</span></div>
                </div>
              </div>
            </div>

            {/* 2 · what's next */}
            <div className="card-proj">
              <div className="card-h">
                <span>{pr.season} wRC+ projection</span>
                <span className="s">{fmt(xw?.value, '{:.3f}')} xwOBA</span>
              </div>
              <div className="card-range">
                <div className="marks top">
                  {wrc?.value != null && <span className="mid" style={{ left: x(wrc.value) }}><b>{fmt(wrc.value, '{:.0f}')}</b> wRC+</span>}
                </div>
                <div className="axis">
                  {wrc?.low != null && wrc?.high != null && (
                    <span className="band" style={{ left: x(wrc.low), width: `calc(${x(wrc.high)} - ${x(wrc.low)})` }} />
                  )}
                  {wrc?.value != null && <span className="est" style={{ left: x(wrc.value) }} />}
                  {actual != null && <span className="act" style={{ left: x(actual) }} />}
                </div>
                <div className="marks bottom">
                  {wrc?.low != null && <span className="lo" style={{ left: x(wrc.low) }}>{fmt(wrc.low, '{:.0f}')}</span>}
                  {wrc?.high != null && <span className="hi" style={{ left: x(wrc.high) }}>{fmt(wrc.high, '{:.0f}')}</span>}
                  {actual != null && <span className="actual" style={{ left: x(actual) }}><b>{fmt(actual, '{:.0f}')}</b> actual {pr.season}</span>}
                </div>
              </div>
              <div className="card-cap">
                {lowConf
                  ? <>Few close comps (best match {fmt(pr.best_similarity, '{:.0f}')}, typical 90) — nobody in the data hits quite like him; read the band wide</>
                  : wrc?.track_adj != null && Math.abs(wrc.track_adj) >= 0.5
                    ? <>Band: middle 60% of what his {pr.n_comps} closest comps did next · adjusted {wrc.track_adj > 0 ? '+' : ''}{fmt(wrc.track_adj, '{:.0f}')} for a career of {wrc.track_adj > 0 ? 'out-hitting' : 'under-hitting'} his contact quality</>
                    : <>Band: the middle 60% of what his {pr.n_comps} closest comps did the next season · {fmt(wrc?.value, '{:.0f}')}: their weighted average</>}
              </div>
            </div>

            {/* 3 · who he resembles */}
            <div className="card-block">
              <div className="card-h">
                <span>Closest profiles</span>
                <span className="s">similarity: 100 = identical skill profile, 90 = a typical best match</span>
              </div>
              <div className="card-comp head">
                <span /><span /><span />
                <span className="c">Similarity</span>
                <span className="c">wRC+ the next season</span>
              </div>
              {comps.map((c, i) => (
                <div className="card-comp" key={c.row}>
                  <span className="rk">{i + 1}</span>
                  <Headshot id={c.mlbam_id} name={c.name} size={34} cls="card-comp-avatar" />
                  <span className="who">
                    <span className="nm">{c.name}</span>
                    <span className="sub">{c.season}{c.age != null ? ` · age ${c.age}` : ''}{c.team ? ` · ${c.team}` : ''}</span>
                  </span>
                  <span className="sim">{c.similarity.toFixed(0)}</span>
                  <span className="num">
                    {c.next
                      ? <>{fmt(c.next.wrc_plus, '{:.0f}')} <Delta a={c.outcomes.wrc_plus?.value} b={c.next.wrc_plus} season={c.season} /></>
                      : <span className="pending">{c.season + 1} pending</span>}
                  </span>
                </div>
              ))}
            </div>

            {/* 4 · why, in numbers */}
            <div className="card-block">
              <div className="card-h"><span>The skills behind the match</span><span className="s">percentile that season: <i className="sw lo" /> poor → <i className="sw hi" /> elite</span></div>
              <table className="card-table">
                <thead>
                  <tr>
                    <th></th>
                    <th className="me">{shortName(t.name)} <span className="yr">’{String(t.season).slice(2)}</span></th>
                    {comps.map((c) => <th key={c.row}>{shortName(c.name)} <span className="yr">’{String(c.season).slice(2)}</span></th>)}
                  </tr>
                </thead>
                <tbody>
                  {keys.map((f) => {
                    const m = meta.feature_meta[f] ?? meta.tracking[f];
                    const isTrack = !meta.feature_meta[f];
                    const stat = (p: typeof t) => (isTrack ? p.tracking?.[f] : p.features[f]);
                    const unit = m.unit === '%' || m.unit === 'mph' ? '' : m.unit;
                    return (
                      <tr key={f}>
                        <td className="lab">{SHORT[f] ?? m.label}{m.unit === 'mph' ? ' (mph)' : ''}{isTrack ? <span className="yr"> 2024+</span> : null}</td>
                        <td className="me" style={cellStyle(stat(t)?.pct, m.higher_better)}>{fmt(stat(t)?.value, m.fmt)}{unit}</td>
                        {comps.map((c) => <td key={c.row} style={cellStyle(stat(c)?.pct, m.higher_better)}>{fmt(stat(c)?.value, m.fmt)}{unit}</td>)}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="card-foot">
              <b>Comps</b> · matched on skills, not on results · Statcast + FanGraphs {meta.seasons[0]}–{meta.seasons[meta.seasons.length - 1]}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
