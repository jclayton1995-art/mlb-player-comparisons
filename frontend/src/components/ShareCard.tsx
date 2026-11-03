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
/** Tag for the similarity score (median best match is 90; 95+ is rare). */
const matchTag = (raw: number): { word: string; tone: 'gold' | 'ink' | 'mute' } => {
  const sim = Math.round(raw);                       // tag the score as displayed, so a 89.6 shown as 90 reads "strong"
  if (sim >= 95) return { word: 'near-twin', tone: 'gold' };
  if (sim >= 90) return { word: 'strong match', tone: 'gold' };
  if (sim >= 80) return { word: 'solid match', tone: 'ink' };
  return { word: 'loose match', tone: 'mute' };
};

/** The three skills a match is built on: heavily weighted by the model AND close between the two hitters. */
function sharedSkills(meta: Meta, a: { features: Record<string, { pct: number | null }> }, c: { features: Record<string, { pct: number | null }>; z_diff: Record<string, number | null> }, n = 3) {
  const RESULTS = new Set(['k_pct', 'bb_pct']);   // model inputs, but they read as results — keep the "why" to process skills
  const cands = meta.features
    .filter((f) => !RESULTS.has(f) && a.features[f]?.pct != null && c.features[f]?.pct != null && c.z_diff[f] != null)
    .map((f) => ({ f, imp: meta.feature_importance[f] ?? 0, gap: Math.abs(c.z_diff[f]!), pgap: Math.abs(a.features[f].pct! - c.features[f].pct!) }));
  // Genuinely close first (within ~0.4 sd and 15 percentile points), ranked by model weight; then fill by closeness × weight.
  const tight = cands.filter((x) => x.gap <= 0.4 && x.pgap <= 12).sort((x, y) => y.imp - x.imp);
  const rest = cands.filter((x) => !tight.includes(x)).sort((x, y) => y.imp * Math.exp(-y.gap) - x.imp * Math.exp(-x.gap));
  return (tight.length >= 2 ? tight : [...tight, ...rest]).slice(0, tight.length >= 2 ? n : 2)
    .map(({ f }) => ({ f, label: SHORT[f] ?? meta.feature_meta[f].label, pa: clampP(a.features[f].pct!), pb: clampP(c.features[f].pct!) }));
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
  const wrc = pr.values.wrc_plus;
  // Which comp the card is about: defaults to the closest; any of the top five can be chosen.
  const [pick, setPick] = useState(0);
  const chosen = data.comps[pick] ?? data.comps[0];
  const comps = chosen ? [chosen, ...data.comps.filter((c) => c.row !== chosen.row).slice(0, 2)] : [];
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

        <div className="share-pick">
          <span className="share-pick-l">Comp to</span>
          {data.comps.slice(0, 5).map((c, i) => (
            <button key={c.row} className={'share-pick-btn' + (i === pick ? ' on' : '')} onClick={() => setPick(i)}>
              {shortName(c.name)} ’{String(c.season).slice(2)} <b>{c.similarity.toFixed(0)}</b>
            </button>
          ))}
        </div>
        <div className="share-stage">
          <div className="scard v6" ref={ref}>
            {comps[0] && (() => { const c = comps[0]; const sk = sharedSkills(meta, t, c, 4); return (
              <>
                {/* headline block: the story in one sentence */}
                <div className="v6-top">
                  <div className="v6-kicker">Comps · {t.season}</div>
                  <div className="v6-faces">
                    <Headshot id={t.mlbam_id} name={t.name} size={88} cls="v6-face me" />
                    <Headshot id={c.mlbam_id} name={c.name} size={88} cls="v6-face them" />
                  </div>
                  <h1 className="v6-h1">{t.name} <span className="v6-hits">comps to</span> {c.season} {c.name}</h1>
                  <div className="v6-deck">
                    <span className="v6-score">Similarity <b>{c.similarity.toFixed(0)}</b><small>/100</small><span className={'v6-badge ' + matchTag(c.similarity).tone}>{matchTag(c.similarity).word}</span></span>
                    {comps.length > 1 && (
                      <span className="v6-runners">
                        <span className="v6-runners-l">next closest</span>
                        {comps.slice(1).map((d) => (
                          <span className="v6-runner" key={d.row}>
                            <Headshot id={d.mlbam_id} name={d.name} size={26} cls="v6-runner-face" />
                            <span>{shortName(d.name)} ’{String(d.season).slice(2)}</span><b>{d.similarity.toFixed(0)}</b>
                          </span>
                        ))}
                      </span>
                    )}
                  </div>
                </div>

                {/* evidence: the skills they share, as tracks */}
                <div className="v6-ev">
                  <div className="v6-ev-head">
                    <span>Where their swings line up</span>
                    <span className="v6-legend"><i className="me" /> {shortName(t.name)} ’{String(t.season).slice(2)} <i className="them" /> {shortName(c.name)} ’{String(c.season).slice(2)} · percentile that season</span>
                  </div>
                  {sk.map((k) => (
                    <div className={'v6-trk' + (Math.abs(k.pa - k.pb) < 8 ? ' tight' : '')} key={k.f}>
                      <span className="l">{k.label}</span>
                      <div className="t">
                        <i className="mid" />
                        <i className="bar" style={{ left: `${Math.min(k.pa, k.pb)}%`, width: `${Math.abs(k.pa - k.pb)}%` }} />
                        <span className="dot them" style={{ left: `${k.pb}%` }}>{k.pb}</span>
                        <span className="dot me" style={{ left: `${k.pa}%` }}>{k.pa}</span>
                      </div>
                    </div>
                  ))}
                </div>

                {/* consequence: what the comp did next */}
                <div className="v6-next">
                  <span className="v6-kicker">What {shortName(c.name)} did next</span>
                  {c.next
                    ? <div className="v6-next-line"><b>{fmt(c.next.wrc_plus, '{:.0f}')}</b> wRC+ in {c.next_season}<span className="from">from {fmt(c.outcomes.wrc_plus?.value, '{:.0f}')} in {c.season}</span><Delta a={c.outcomes.wrc_plus?.value} b={c.next.wrc_plus} season={c.season} /></div>
                    : <div className="v6-next-line"><span className="from">{c.next_season} hasn’t happened yet</span></div>}
                </div>
              </>
            ); })()}

            {/* payoff: the projection, on paper */}
            <div className="v6-proj">
              <div className="v6-proj-l">
                <span className="v6-kicker dark">{pr.season} projection</span>
                <span className="v6-proj-n"><b>{fmt(wrc?.value, '{:.0f}')}</b> wRC+</span>
                <span className="v6-proj-sub">{fmt(t.outcomes.wrc_plus?.value, '{:.0f}')} wRC+ in {t.season}</span>
              </div>
              <div className="v6-proj-r">
                <div className="card-range v6-range">
                  <div className="axis">
                    {wrc?.low != null && wrc?.high != null && <span className="band" style={{ left: x(wrc.low), width: `calc(${x(wrc.high)} - ${x(wrc.low)})` }} />}
                    {wrc?.value != null && <span className="est" style={{ left: x(wrc.value) }} />}
                    {actual != null && <span className="act" style={{ left: x(actual) }} />}
                  </div>
                  <div className="marks bottom">
                    {wrc?.low != null && <span className="lo" style={{ left: x(wrc.low) }}>{fmt(wrc.low, '{:.0f}')}</span>}
                    {wrc?.high != null && <span className="hi" style={{ left: x(wrc.high) }}>{fmt(wrc.high, '{:.0f}')}</span>}
                    {actual != null && <span className="actual" style={{ left: x(actual) }}><b>{fmt(actual, '{:.0f}')}</b> actual</span>}
                  </div>
                </div>
                <div className="v6-cap">
                  {lowConf
                    ? <>Fewer close matches than most hitters — the range matters more than the point</>
                    : <>Likely range: the middle 60% of what his {pr.n_comps} closest comps did the next season</>}
                </div>
              </div>
            </div>

            <div className="v6-foot"><b>Comps</b> · matched on skills, not results · Statcast + FanGraphs {meta.seasons[0]}–{meta.seasons[meta.seasons.length - 1]}</div>
          </div>
        </div>
      </div>
    </>
  );
}
