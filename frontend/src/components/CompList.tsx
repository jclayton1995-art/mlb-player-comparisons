import { Fragment, useState } from 'react';
import { fmt, shortName, type Comp, type CompareResponse, type Meta, type PlayerSeason } from '../api';
import { DualProfile, groupFeatures } from './Profile';
import { Avatar } from './Avatar';

/** 17 ticks, one per underlying metric, grouped by cluster. Up (blue) = comp is higher
 *  than the target on that metric, down (gold) = lower. Height = size of the gap in
 *  season-relative standard deviations, capped at 2. */
function Fingerprint({ meta, c }: { meta: Meta; c: Comp }) {
  const groups = groupFeatures(meta);
  return (
    <div className="fp" aria-label="profile difference vs target">
      {groups.map((g) => (
        <div className="fp-group" key={g.key}>
          {g.features.map((f) => {
            const d = c.z_diff[f] ?? 0;
            const h = Math.min(Math.abs(d), 2) / 2 * 50; // % of tick height
            const fm = meta.feature_meta[f];
            return (
              <span className="fp-tick" key={f} title={`${fm.label}: ${d >= 0 ? '+' : ''}${d.toFixed(2)} sd vs target`}>
                <i className={d >= 0 ? 'up' : 'dn'} style={{ height: `${h}%` }} />
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function Delta({ now, next, digits }: { now: number | null; next: number | null; digits: number }) {
  if (now == null || next == null) return null;
  const d = next - now;
  const s = d.toFixed(digits);
  return <span className={'d ' + (d >= 0 ? 'up' : 'dn')}>{d >= 0 ? '+' : ''}{digits === 3 ? s.replace(/^(-?)0\./, '$1.') : s}</span>;
}

function OutcomeTable({ meta, a, b }: { meta: Meta; a: PlayerSeason; b: PlayerSeason }) {
  const rows = ['xwoba', 'wrc_plus', 'avg', 'obp', 'slg', 'iso', 'babip', 'hr', 'war'].filter((k) => meta.outcomes[k]);
  return (
    <table className="outcome-table">
      <thead>
        <tr>
          <th>Results</th>
          <th className="tg">{a.season}</th>
          <th>{b.season}</th>
          <th>{b.season + 1}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((k) => {
          const f = meta.outcomes[k].fmt;
          return (
            <tr key={k} className={k === 'xwoba' || k === 'wrc_plus' ? 'hi' : ''}>
              <td>{meta.outcomes[k].label}</td>
              <td className="tg">{fmt(a.outcomes[k]?.value, f)}</td>
              <td>{fmt(b.outcomes[k]?.value, f)}</td>
              <td>{b.next ? fmt(b.next[k], f) : <span className="pending">–</span>}</td>
            </tr>
          );
        })}
        <tr>
          <td>PA</td>
          <td className="tg">{a.pa}</td>
          <td>{b.pa}</td>
          <td>{b.next?.pa ?? <span className="pending">–</span>}</td>
        </tr>
      </tbody>
    </table>
  );
}

export function CompList({ meta, data, onPick, onShare }: { meta: Meta; data: CompareResponse; onPick: (id: number, s: number) => void; onShare: () => void }) {
  const [open, setOpen] = useState<number | null>(null);
  const t = data.target;
  return (
    <section>
      <div className="comps-head">
        <span className="comps-title">Closest profiles to {shortName(t.name)} {t.season}</span>
        <span className="comps-note">any season 2015 on, excluding himself</span>
        <div className="comps-legend">
          <span className="lg"><i className="up" /> comp higher</span>
          <span className="lg"><i className="dn" /> comp lower</span>
          <button className="btn" style={{ height: 28 }} onClick={onShare}>Share card</button>
        </div>
      </div>
      <div className="table-wrap"><table className="comp-table">
        <thead>
          <tr>
            <th className="rank"></th>
            <th>Similarity</th>
            <th>Player season</th>
            <th>Profile vs target</th>
            <th className="r">xwOBA</th>
            <th className="r">wRC+</th>
            <th className="r">Next year</th>
          </tr>
        </thead>
        <tbody>
          {data.comps.map((c, i) => {
            const isOpen = open === c.row;
            return (
              <Fragment key={c.row}>
                <tr className={'comp-row' + (isOpen ? ' open' : '')} onClick={() => setOpen(isOpen ? null : c.row)} aria-expanded={isOpen}>
                  <td className="rank">{i + 1}</td>
                  <td>
                    <div className="sim">{c.similarity.toFixed(0)}</div>
                    <div className="sim-bar"><i style={{ width: `${c.similarity}%` }} /></div>
                  </td>
                  <td>
                    <div className="who">
                      <Avatar id={c.mlbam_id} name={c.name} size={36} />
                      <div>
                        <div className="nm">{c.name}</div>
                        <div className="sub">{c.season}{c.team ? ` ${c.team}` : ''} · {c.pa} PA{c.age != null ? ` · age ${c.age}` : ''}{c.bats ? ` · ${c.bats}HB` : ''}</div>
                      </div>
                    </div>
                  </td>
                  <td><Fingerprint meta={meta} c={c} /></td>
                  <td className="r cell-v">{fmt(c.outcomes.xwoba?.value, '{:.3f}')}</td>
                  <td className="r cell-v">{fmt(c.outcomes.wrc_plus?.value, '{:.0f}')}</td>
                  <td className="r cell-v next-cell">
                    {c.next ? (
                      <>
                        {fmt(c.next.wrc_plus, '{:.0f}')} wRC+
                        <Delta now={c.outcomes.wrc_plus?.value ?? null} next={c.next.wrc_plus} digits={0} />
                      </>
                    ) : (
                      <span className="pending">{c.season + 1} not on record</span>
                    )}
                  </td>
                </tr>
                {isOpen && (
                  <tr className="expand">
                    <td colSpan={7}>
                      <div className="expand-body">
                        <div>
                          <div className="expand-title">
                            <span>Side by side</span>
                            <button className="btn" style={{ height: 26 }} onClick={() => onPick(c.mlbam_id, c.season)}>
                              Open {shortName(c.name)} {c.season}
                            </button>
                          </div>
                          <DualProfile meta={meta} a={t} b={c} />
                        </div>
                        <div>
                          {t.tracking && c.tracking && (
                            <>
                              <div className="expand-title"><span>Bat tracking</span><span className="sub">2024 on</span></div>
                              <table className="outcome-table" style={{ marginBottom: 16 }}>
                                <thead><tr><th>Swing</th><th className="tg">{t.season}</th><th>{c.season}</th></tr></thead>
                                <tbody>
                                  {Object.entries(meta.tracking).map(([k, m]) => (
                                    <tr key={k}>
                                      <td>{m.label}</td>
                                      <td className="tg">{fmt(t.tracking?.[k]?.value, m.fmt)}</td>
                                      <td>{fmt(c.tracking?.[k]?.value, m.fmt)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </>
                          )}
                          <div className="expand-title">
                            <span>What happened next</span>
                            <span className="sub">{shortName(c.name)} {c.season} → {c.season + 1}</span>
                          </div>
                          <OutcomeTable meta={meta} a={t} b={c} />
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table></div>
    </section>
  );
}
