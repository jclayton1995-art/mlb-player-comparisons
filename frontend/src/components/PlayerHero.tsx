import { fmt, type CompareResponse } from '../api';
import { Avatar } from './Avatar';

type Props = { data: CompareResponse; seasons: number[]; onSeason: (s: number) => void; onShare: () => void };

const ord = (n: number) => { const s = n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd' : n % 10 === 3 && n !== 13 ? 'rd' : 'th'; return `${n}${s}`; };
const pctText = (p: number | null | undefined) => (p == null ? '' : `${ord(Math.min(99, Math.max(1, Math.round(p))))} percentile`);

/** Full-width band: who he is, which season, his headline numbers, and next year's projection in one line. */
export function PlayerHero({ data, seasons, onSeason, onShare }: Props) {
  const t = data.target, pr = data.projection;
  const wrc = pr.values.wrc_plus;
  const actual = pr.actual && pr.actual.pa != null ? pr.actual : null;
  return (
    <header className="hero-band">
      <div className="hero-inner">
        <Avatar id={t.mlbam_id} name={t.name} size={112} className="hero-photo" />
        <div className="hero-main">
          <h1 className="hero-name">{t.name}</h1>
          <div className="hero-meta">
            <span>{t.team ?? '—'}</span>
            {t.bats && <span>{t.bats === 'S' ? 'switch' : t.bats === 'L' ? 'left-handed' : 'right-handed'}</span>}
            {t.age != null && <span>age {t.age}</span>}
            <span>{t.pa} PA in {t.season}</span>
          </div>
          <nav className="seasons" aria-label="Season">
            {seasons.map((s) => (
              <button key={s} className={'season' + (s === t.season ? ' on' : '')} aria-current={s === t.season || undefined} onClick={() => onSeason(s)}>{s}</button>
            ))}
          </nav>
        </div>
        <div className="hero-stats">
          <div className="stat">
            <span className="v">{fmt(t.outcomes.wrc_plus?.value, '{:.0f}')}</span>
            <span className="l">wRC+</span>
            <span className="p">{pctText(t.outcomes.wrc_plus?.pct)}</span>
          </div>
          <div className="stat">
            <span className="v">{fmt(t.outcomes.xwoba?.value, '{:.3f}')}</span>
            <span className="l">xwOBA</span>
            <span className="p">{pctText(t.outcomes.xwoba?.pct)}</span>
          </div>
          <div className="stat proj">
            <span className="v">{fmt(wrc?.value, '{:.0f}')}</span>
            <span className="l">{pr.season} projected wRC+</span>
            <span className="p">{wrc?.low != null ? `likely ${fmt(wrc.low, '{:.0f}')}–${fmt(wrc.high, '{:.0f}')}` : ''}{actual ? ` · actual ${fmt(actual.wrc_plus, '{:.0f}')}` : ''}</span>
          </div>
          <button className="btn share" onClick={onShare}>Share card</button>
        </div>
      </div>
    </header>
  );
}
