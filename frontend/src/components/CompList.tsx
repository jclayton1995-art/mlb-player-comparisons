import { Fragment, useState } from 'react';
import { fmt, shortName, type CompareResponse, type Meta, type PlayerSeason } from '../api';
import { Avatar } from './Avatar';
import { SkillTracks, TrackingTracks } from './Tracks';

function Delta({ now, next, digits }: { now: number | null; next: number | null; digits: number }) {
  if (now == null || next == null) return null;
  const d = next - now;
  const s = d.toFixed(digits);
  return <span className={'delta ' + (d >= 0 ? 'up' : 'dn')}>{d >= 0 ? '+' : ''}{digits === 3 ? s.replace(/^(-?)0\./, '$1.') : s}</span>;
}

function Outcomes({ meta, a, b }: { meta: Meta; a: PlayerSeason; b: PlayerSeason }) {
  const rows = ['wrc_plus', 'xwoba', 'avg', 'obp', 'slg', 'iso', 'babip', 'hr', 'war'].filter((k) => meta.outcomes[k]);
  return (
    <table className="tbl">
      <thead>
        <tr>
          <th>Results</th>
          <th className="r me">{shortName(a.name)} ’{String(a.season).slice(2)}</th>
          <th className="r">{shortName(b.name)} ’{String(b.season).slice(2)}</th>
          <th className="r">{shortName(b.name)} ’{String(b.next_season).slice(2)}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((k) => {
          const f = meta.outcomes[k].fmt;
          return (
            <tr key={k} className={k === 'wrc_plus' || k === 'xwoba' ? 'hi' : ''}>
              <td>{meta.outcomes[k].label}</td>
              <td className="r me">{fmt(a.outcomes[k]?.value, f)}</td>
              <td className="r">{fmt(b.outcomes[k]?.value, f)}</td>
              <td className="r">{b.next ? fmt(b.next[k], f) : <span className="faint">–</span>}</td>
            </tr>
          );
        })}
        <tr><td>PA</td><td className="r me">{a.pa}</td><td className="r">{b.pa}</td><td className="r">{b.next?.pa ?? <span className="faint">–</span>}</td></tr>
      </tbody>
    </table>
  );
}

export function CompList({ meta, data, onPick }: { meta: Meta; data: CompareResponse; onPick: (id: number, s: number) => void }) {
  const [open, setOpen] = useState<number | null>(null);
  const t = data.target;
  return (
    <section className="comps">
      <header className="section-head">
        <h2>Closest profiles</h2>
        <span className="sub">to {shortName(t.name)} {t.season}, from every hitter-season since {meta.seasons[0]} · similarity: 100 = identical skills, 90 = a typical best match</span>
      </header>
      <div className="comp-list">
        {data.comps.map((c, i) => {
          const isOpen = open === c.row;
          return (
            <Fragment key={c.row}>
              <button className={'comp' + (isOpen ? ' open' : '')} onClick={() => setOpen(isOpen ? null : c.row)} aria-expanded={isOpen}>
                <span className="rk">{i + 1}</span>
                <Avatar id={c.mlbam_id} name={c.name} size={40} />
                <span className="who">
                  <span className="nm">{c.name}</span>
                  <span className="sub">{c.season}{c.team ? ` ${c.team}` : ''} · age {c.age ?? '–'} · {c.pa} PA</span>
                </span>
                <span className="sim"><b>{c.similarity.toFixed(0)}</b><span>similarity</span></span>
                <span className="then"><b>{fmt(c.outcomes.wrc_plus?.value, '{:.0f}')}</b><span>wRC+ that year</span></span>
                <span className="next">
                  {c.next
                    ? <><b>{fmt(c.next.wrc_plus, '{:.0f}')}</b><span>next year <Delta now={c.outcomes.wrc_plus?.value ?? null} next={c.next.wrc_plus} digits={0} /></span></>
                    : <><b className="faint">–</b><span>{c.next_season} not yet played</span></>}
                </span>
                <span className="chev" aria-hidden="true">{isOpen ? '−' : '+'}</span>
              </button>
              {isOpen && (
                <div className="compare">
                  <div className="compare-main">
                    <header className="section-head small">
                      <h3>{shortName(t.name)} {t.season} vs. {shortName(c.name)} {c.season}</h3>
                      <span className="sub">length of the bar = how far apart they are on that skill</span>
                      <button className="btn" onClick={() => onPick(c.mlbam_id, c.season)}>Open {shortName(c.name)} {c.season}</button>
                    </header>
                    <div className="legend">
                      <span><i className="sw dot-a" /> {shortName(t.name)} ’{String(t.season).slice(2)}</span>
                      <span><i className="sw dot-b" /> {shortName(c.name)} ’{String(c.season).slice(2)}</span>
                    </div>
                    <SkillTracks meta={meta} a={t} b={c} showWeights />
                  </div>
                  <div className="compare-side">
                    <h3>What happened next</h3>
                    <Outcomes meta={meta} a={t} b={c} />
                    {t.tracking && c.tracking && (
                      <>
                        <h3>Bat tracking</h3>
                        <TrackingTracks meta={meta} a={t} b={c} />
                      </>
                    )}
                  </div>
                </div>
              )}
            </Fragment>
          );
        })}
      </div>
    </section>
  );
}
