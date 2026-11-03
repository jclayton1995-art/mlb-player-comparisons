import { fmt, LOW_CONFIDENCE, type CompareResponse, type Meta } from '../api';
import { SkillTracks, TrackingTracks } from './Tracks';

/** Range of outcomes: shaded band = middle 60% of what the comps did next; dots = estimate, regression, actual. */
function RangeBar({ low, high, value, model, actual, f }: { low: number; high: number; value: number; model: number | null; actual: number | null; f: string }) {
  const pts = [low, high, value, model, actual].filter((x): x is number => x != null);
  const span = Math.max(...pts) - Math.min(...pts) || 1;
  const lo = Math.min(...pts) - span * 0.25, hi = Math.max(...pts) + span * 0.25;
  const x = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  return (
    <div className="rng">
      <div className="rng-top">
        <span className="rng-est" style={{ left: x(value) }}><b>{fmt(value, f)}</b></span>
      </div>
      <div className="rng-axis">
        <span className="rng-band" style={{ left: x(low), width: `calc(${x(high)} - ${x(low)})` }} />
        {model != null && <span className="rng-dot model" style={{ left: x(model) }} title={`Regression model: ${fmt(model, f)}`} />}
        <span className="rng-dot est" style={{ left: x(value) }} />
        {actual != null && <span className="rng-dot actual" style={{ left: x(actual) }} title={`Actual: ${fmt(actual, f)}`} />}
      </div>
      <div className="rng-bottom">
        <span style={{ left: x(low) }}>{fmt(low, f)}</span>
        <span style={{ left: x(high) }}>{fmt(high, f)}</span>
        {actual != null && <span className="actual" style={{ left: x(actual) }}>actual {fmt(actual, f)}</span>}
      </div>
    </div>
  );
}

export function ProjectionPanel({ meta, data }: { meta: Meta; data: CompareResponse }) {
  const t = data.target, pr = data.projection;
  const wrc = pr.values.wrc_plus, xw = pr.values.xwoba;
  const actual = pr.actual && pr.actual.pa != null ? pr.actual : null;
  const lowConf = pr.best_similarity != null && pr.best_similarity < LOW_CONFIDENCE;
  const track = wrc?.track_adj != null && Math.abs(wrc.track_adj) >= 0.5 ? wrc : null;
  return (
    <aside className="rail">
      <section className="card">
        <header className="card-head">
          <h2>{pr.season} projection</h2>
          <span className="sub">what his {pr.n_comps} closest comps did the next year</span>
        </header>
        {wrc?.value != null && wrc.low != null && wrc.high != null && (
          <div className="rng-block">
            <div className="rng-title">wRC+</div>
            <RangeBar low={wrc.low} high={wrc.high} value={wrc.value} model={pr.model_direct.wrc_plus ?? null} actual={actual?.wrc_plus ?? null} f="{:.0f}" />
          </div>
        )}
        {xw?.value != null && xw.low != null && xw.high != null && (
          <div className="rng-block">
            <div className="rng-title">xwOBA</div>
            <RangeBar low={xw.low} high={xw.high} value={xw.value} model={pr.model_direct.xwoba ?? null} actual={actual?.xwoba ?? null} f="{:.3f}" />
          </div>
        )}
        <div className="legend">
          <span><i className="sw band" /> middle 60% of comps’ next seasons</span>
          <span><i className="sw est" /> estimate</span>
          <span><i className="sw model" /> regression, no comps</span>
          {actual && <span><i className="sw actual" /> actual</span>}
        </div>
        {lowConf && (
          <div className="note warn">
            <b>Few close comps.</b> His best match scores {fmt(pr.best_similarity, '{:.0f}')} against a typical 90 — nobody in the data hits quite like him, so the band deserves extra width.
          </div>
        )}
        {track && (
          <div className="note">
            <b>Track record.</b> His career results run {track.track_gap! > 0 ? '+' : ''}{fmt(track.track_gap, '{:.0f}')} wRC+ {track.track_gap! > 0 ? 'above' : 'below'} what his contact quality implies. About half of that persists, so the comps’ {fmt(track.comps_only, '{:.0f}')} becomes {fmt(track.value, '{:.0f}')}.
          </div>
        )}
      </section>

      <section className="card">
        <header className="card-head">
          <h2>Skill profile</h2>
          <span className="sub">percentile among {t.season} hitters · color = good to bad for that skill</span>
        </header>
        <SkillTracks meta={meta} a={t} />
      </section>

      {t.tracking && Object.keys(meta.tracking).length > 0 && (
        <section className="card">
          <header className="card-head">
            <h2>Bat tracking</h2>
            <span className="sub">Statcast, 2024 on · shown, not used by the model</span>
          </header>
          <TrackingTracks meta={meta} a={t} />
        </section>
      )}
    </aside>
  );
}
