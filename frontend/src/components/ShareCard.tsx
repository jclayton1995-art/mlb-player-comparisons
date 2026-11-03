import { useRef, useState } from 'react';
import { toPng } from 'html-to-image';
import { fmt, headshot as cdnHeadshot, LOW_CONFIDENCE, shortName, type CompareResponse, type Meta } from '../api';

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

const SHORT: Record<string, string> = {
  exit_velocity: 'Exit velo', ev50: 'EV50', max_exit_velocity: 'Max EV', hard_hit_pct: 'Hard-hit', barrel_pct: 'Barrel%',
  brl_pa: 'Barrels/PA', launch_angle: 'Launch angle', anglesweetspotpercent: 'Sweet spot', gb_pct: 'Ground balls', ld_pct: 'Line drives',
  pull_pct: 'Pull', oppo_pct: 'Oppo', pull_air_pct: 'Pulled air', chase_rate: 'Chase', zone_swing_pct: 'Zone swing',
  zone_contact_pct: 'Z-contact', whiff_pct: 'Whiff', swstr_pct: 'SwStr', k_pct: 'K%', bb_pct: 'BB%',
};
const clampP = (p: number) => Math.min(99, Math.max(1, Math.round(p)));

/** The three skills a match is built on: heavily weighted by the model AND close between the two hitters. */
function sharedSkills(meta: Meta, a: { features: Record<string, { pct: number | null }> }, c: { features: Record<string, { pct: number | null }>; z_diff: Record<string, number | null> }, n = 3) {
  const RESULTS = new Set(['k_pct', 'bb_pct']);   // model inputs, but they read as results — keep the "why" to process skills
  const cands = meta.features
    .filter((f) => !RESULTS.has(f) && a.features[f]?.pct != null && c.features[f]?.pct != null && c.z_diff[f] != null)
    .map((f) => ({ f, imp: meta.feature_importance[f] ?? 0, gap: Math.abs(c.z_diff[f]!), pgap: Math.abs(a.features[f].pct! - c.features[f].pct!) }));
  // Genuinely close first (within ~0.4 sd and 15 percentile points), ranked by model weight; then fill by closeness × weight.
  const tight = cands.filter((x) => x.gap <= 0.4 && x.pgap <= 15).sort((x, y) => y.imp - x.imp);
  const rest = cands.filter((x) => !tight.includes(x)).sort((x, y) => y.imp * Math.exp(-y.gap) - x.imp * Math.exp(-x.gap));
  return (tight.length >= 2 ? tight : [...tight, ...rest]).slice(0, tight.length >= 2 ? n : 2)
    .map(({ f }) => ({ f, label: SHORT[f] ?? meta.feature_meta[f].label, pa: clampP(a.features[f].pct!), pb: clampP(c.features[f].pct!) }));
}

/** Similarity meter on a fixed 70–100 scale so cards are comparable to each other; 90 = a typical best match. */
const meterPct = (sim: number) => Math.min(100, Math.max(0, ((sim - 70) / 30) * 100));

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
          <div className="scard" ref={ref}>
            {/* 1 · who */}
            <div className="card-hero">
              <Headshot id={t.mlbam_id} name={t.name} size={76} cls="card-avatar" />
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
                  ? <>Few close comps: best match {fmt(pr.best_similarity, '{:.0f}')} vs. a typical 90, so read the band wide</>
                  : wrc?.track_adj != null && Math.abs(wrc.track_adj) >= 0.5
                    ? <>Band: middle 60% of his {pr.n_comps} comps’ next seasons · {wrc.track_adj > 0 ? '+' : ''}{fmt(wrc.track_adj, '{:.0f}')} for his track record vs. contact quality</>
                    : <>Band: middle 60% of his {pr.n_comps} comps’ next seasons · {fmt(wrc?.value, '{:.0f}')}: their weighted average</>}
              </div>
            </div>

            {/* 3 · who he resembles, and how closely */}
            <div className="card-block comps3">
              <div className="card-h">
                <span>Closest profiles</span>
                <span className="s">numbers are percentile ranks, each in his own season</span>
              </div>
              <div className="cc key">
                <span /><span />
                <div className="meter-key">
                  <span>closeness</span>
                  <span className="tick-lbl" style={{ left: `${meterPct(90)}%` }}>typical best match</span>
                </div>
                <span />
              </div>
              {comps.map((c, i) => (
                <div className="cc" key={c.row}>
                  <span className="cc-rk">{i + 1}</span>
                  <Headshot id={c.mlbam_id} name={c.name} size={46} cls="card-comp-avatar" />
                  <div className="cc-main">
                    <div className="cc-nm">{c.name} <span className="cc-yr">{c.season}{c.team ? ` · ${c.team}` : ''} · age {c.age ?? '–'} · {fmt(c.outcomes.wrc_plus?.value, '{:.0f}')} wRC+</span></div>
                    <div className="meter" aria-label={`similarity ${c.similarity.toFixed(0)}`}>
                      <i className="meter-fill" style={{ width: `${meterPct(c.similarity)}%` }} />
                      <i className="meter-tick" style={{ left: `${meterPct(90)}%` }} />
                      <b>{c.similarity.toFixed(0)}</b>
                    </div>
                  </div>
                  <div className="cc-next">
                    {c.next
                      ? <><b>{fmt(c.next.wrc_plus, '{:.0f}')}</b><span>wRC+ in {c.season + 1}</span><Delta a={c.outcomes.wrc_plus?.value} b={c.next.wrc_plus} season={c.season} /></>
                      : <><b className="pending">–</b><span>{c.season + 1} not yet played</span></>}
                  </div>
                    <table className="why">
                    <thead><tr><th className="who">where they line up</th>{sharedSkills(meta, t, c).map((k) => <th key={k.f}>{k.label}</th>)}</tr></thead>
                    <tbody>
                      <tr className="a"><td className="who">{shortName(t.name)}</td>{sharedSkills(meta, t, c).map((k) => <td key={k.f}>{k.pa}</td>)}</tr>
                      <tr className="b"><td className="who">{shortName(c.name)}</td>{sharedSkills(meta, t, c).map((k) => <td key={k.f}>{k.pb}</td>)}</tr>
                    </tbody>
                  </table>
                </div>
              ))}
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
