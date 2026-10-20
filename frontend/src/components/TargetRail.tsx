import { fmt, type CompareResponse, type Meta } from '../api';
import { Avatar } from './Avatar';
import { Profile } from './Profile';

type Props = {
  meta: Meta;
  data: CompareResponse;
  seasons: number[];
  onSeason: (s: number) => void;
};

function Range({ low, high, value, actual, model, fmtStr }: { low: number; high: number; value: number; actual: number | null; model: number | null; fmtStr: string }) {
  const pts = [low, high, value, actual, model].filter((x): x is number => x != null);
  const span = Math.max(...pts) - Math.min(...pts) || 1;
  const lo = Math.min(...pts) - span * 0.15, hi = Math.max(...pts) + span * 0.15;
  const x = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  return (
    <>
      <div className="range">
        <span className="band" style={{ left: x(low), width: `calc(${x(high)} - ${x(low)})` }} />
        {model != null && <span className="pt" style={{ left: x(model), background: '#fff', boxShadow: '0 0 0 1px var(--accent)' }} title={`Regression model: ${fmt(model, fmtStr)}`} />}
        <span className="pt" style={{ left: x(value) }} title={`Comp projection: ${fmt(value, fmtStr)}`} />
        {actual != null && <span className="pt actual" style={{ left: x(actual) }} title={`Actual: ${fmt(actual, fmtStr)}`} />}
      </div>
      <div className="range-axis"><span>{fmt(lo, fmtStr)}</span><span>{fmt(hi, fmtStr)}</span></div>
    </>
  );
}

function pctLabel(p: number) { const n = Math.min(99, Math.max(1, Math.round(p))); const s = n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd' : n % 10 === 3 && n !== 13 ? 'rd' : 'th'; return `${n}${s}`; }

export function TargetRail({ meta, data, seasons, onSeason }: Props) {
  const t = data.target;
  const pr = data.projection;
  const wrc = pr.values.wrc_plus, xw = pr.values.xwoba;
  const hasActual = pr.actual && pr.actual.pa != null;

  const headline: { key: string; label: string; fmt: string }[] = [
    { key: 'xwoba', label: 'xwOBA', fmt: '{:.3f}' },
    { key: 'wrc_plus', label: 'wRC+', fmt: '{:.0f}' },
    { key: 'ops', label: 'OPS', fmt: '{:.3f}' },
  ];

  return (
    <aside className="rail">
      <section className="panel panel-pad">
        <div className="hero">
          <Avatar id={t.mlbam_id} name={t.name} size={88} className="hero-avatar" />
          <div>
            <h1 className="hero-name">{t.name}</h1>
            <div className="hero-meta">
              <span><b>{t.season}</b> season</span>
              {t.team && <span>{t.team}</span>}
              {t.bats && <span>bats <b>{t.bats}</b></span>}
              <span><b>{t.pa ?? '–'}</b> PA</span>
              {t.age != null && <span>age <b>{t.age}</b></span>}
            </div>
          </div>
        </div>
        <div className="seasons" role="tablist" aria-label="Season">
          {seasons.map((s) => (
            <button key={s} role="tab" aria-selected={s === t.season} className={'season-chip' + (s === t.season ? ' on' : '')} onClick={() => onSeason(s)}>
              {s}
            </button>
          ))}
        </div>
        <div className="headline">
          {headline.map((h) => {
            const o = t.outcomes[h.key];
            return (
              <div className="hl" key={h.key}>
                <div className="v">{fmt(o?.value, h.fmt)}</div>
                <div className="l">{h.label}</div>
                <div className="p">{o?.pct != null ? `${pctLabel(o.pct)} pct` : ''}</div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="panel panel-pad">
        <div className="panel-head">
          <span className="panel-title">{pr.season} projection from comps</span>
          <span className="panel-note">{pr.n_comps} nearest, kernel-weighted</span>
        </div>
        <div className="proj-grid">
          <div className="proj">
            <div className="l">wRC+</div>
            <div className="v">{fmt(wrc?.value, '{:.0f}')}</div>
            <div className="r">{wrc?.low != null ? `${fmt(wrc.low, '{:.0f}')} – ${fmt(wrc.high, '{:.0f}')} likely range` : ''}</div>
            {wrc?.value != null && wrc.low != null && wrc.high != null && (
              <Range low={wrc.low} high={wrc.high} value={wrc.value} actual={hasActual ? pr.actual!.wrc_plus : null} model={pr.model_direct.wrc_plus ?? null} fmtStr="{:.0f}" />
            )}
          </div>
          <div className="proj">
            <div className="l">xwOBA</div>
            <div className="v">{fmt(xw?.value, '{:.3f}')}</div>
            <div className="r">{xw?.low != null ? `${fmt(xw.low, '{:.3f}')} – ${fmt(xw.high, '{:.3f}')} likely range` : ''}</div>
            {xw?.value != null && xw.low != null && xw.high != null && (
              <Range low={xw.low} high={xw.high} value={xw.value} actual={hasActual ? pr.actual!.xwoba : null} model={pr.model_direct.xwoba ?? null} fmtStr="{:.3f}" />
            )}
          </div>
        </div>
        {hasActual ? (
          <div className="proj-line">
            <span>What actually happened in {pr.season}</span>
            <span>
              <b>{fmt(pr.actual!.wrc_plus, '{:.0f}')} wRC+</b>, <b>{fmt(pr.actual!.xwoba, '{:.3f}')} xwOBA</b> in {pr.actual!.pa} PA
            </span>
          </div>
        ) : (
          <div className="proj-line"><span>{pr.season} not yet on record</span><span>projection stands</span></div>
        )}
        <div className="proj-line">
          <span>Regression model, no comps</span>
          <span><b>{fmt(pr.model_direct.wrc_plus, '{:.0f}')}</b> wRC+, <b>{fmt(pr.model_direct.xwoba, '{:.3f}')}</b> xwOBA</span>
        </div>
        <div className="proj-foot">
          Band is the 20th–80th percentile of what the comps did the following year. Hollow dot is the regression model; black dot is the actual result.
        </div>
      </section>

      {t.tracking && Object.keys(meta.tracking).length > 0 && (
        <section className="panel panel-pad">
          <div className="panel-head">
            <span className="panel-title">Bat tracking</span>
            <span className="panel-note">Statcast, 2024 on · percentile vs {t.season}</span>
          </div>
          <div className="track-grid">
            {Object.entries(meta.tracking).map(([k, m]) => {
              const s = t.tracking?.[k];
              if (!s) return null;
              const pct = s.pct == null ? null : Math.min(99, Math.max(1, Math.round(s.pct)));
              return (
                <div className="track" key={k}>
                  <div className="v">{fmt(s.value, m.fmt)}<span className="u">{m.unit === '%' ? '%' : m.unit ? ` ${m.unit}` : ''}</span></div>
                  <div className="l">{m.label}</div>
                  <div className="bar"><span className="mid" /><span className="fill" style={{ width: `${pct ?? 0}%`, opacity: 0.35 + 0.65 * ((pct ?? 50) / 100) }} /></div>
                  <div className="p">{pct == null ? '' : `${pct}th pct`}</div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      <section className="panel panel-pad">
        <div className="panel-head">
          <span className="panel-title">Underlying profile</span>
          <span className="panel-note">percentile vs {t.season} hitters</span>
        </div>
        <Profile meta={meta} p={t} />
      </section>
    </aside>
  );
}
