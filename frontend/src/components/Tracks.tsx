import { fmt, type Meta, type PlayerSeason, type Stat } from '../api';

/**
 * The one visual language of the app: a 0–100 percentile track per metric.
 * One dot = a player's profile (Savant-style). Two dots joined by a bar = a comparison,
 * where the bar's length is the gap between the two hitters on that skill.
 */

const CLUSTER_ORDER = ['power', 'shape', 'approach', 'swing', 'context'];

export function groupFeatures(meta: Meta) {
  const groups: { key: string; label: string; features: string[]; weight: number }[] = [];
  for (const c of CLUSTER_ORDER) {
    const fs = meta.features.filter((f) => meta.feature_meta[f].cluster === c);
    if (fs.length) groups.push({ key: c, label: meta.clusters[c], features: fs, weight: meta.cluster_importance[c] ?? 0 });
  }
  return groups;
}

const clamp = (p: number) => Math.min(99, Math.max(1, Math.round(p)));

/** Percentile fill, oriented so that higher = better where the metric has a direction. */
export function pctFill(p: number | null | undefined, directional: boolean): React.CSSProperties {
  if (p == null || !directional) return { background: 'var(--dot-neutral)' };
  const t = Math.min(1, Math.abs(p - 50) / 50);
  const [r, g, b] = p < 50 ? [31, 86, 168] : [214, 38, 44];
  const k = 0.3 + 0.7 * t;                                   // never fully white at the median
  const mix = (c: number) => Math.round(255 + (c - 255) * k);
  return { background: `rgb(${mix(r)},${mix(g)},${mix(b)})`, color: k > 0.55 ? '#fff' : 'var(--ink)' };
}

type Fmt = { label: string; fmt: string; unit: string; higher_better: boolean | null };

function unitSuffix(u: string) { return u === '%' || u === '' ? '' : u === 'mph' ? '' : u; }

/** One row: label | track with dot(s) | value(s). */
export function TrackRow({ m, a, b, aLabel, bLabel, colorBy = 'pct' }: {
  m: Fmt; a: Stat | undefined; b?: Stat | undefined; aLabel?: string; bLabel?: string; colorBy?: 'pct' | 'none';
}) {
  const pa = a?.pct != null ? clamp(a.pct) : null;
  const pb = b?.pct != null ? clamp(b.pct) : null;
  const directional = m.higher_better != null;
  const two = b !== undefined;
  return (
    <div className={'trk' + (two ? ' two' : '')}>
      <span className="trk-l" title={m.label}>{m.label}</span>
      <div className="trk-t" aria-label={`${m.label}: ${pa ?? '–'}${two ? ` vs ${pb ?? '–'}` : ''} percentile`}>
        <i className="trk-mid" />
        {two && pa != null && pb != null && (
          <i className="trk-bar" style={{ left: `${Math.min(pa, pb)}%`, width: `${Math.abs(pa - pb)}%` }} />
        )}
        {two && pb != null && (
          <span className="trk-dot b" style={{ left: `${pb}%` }} title={bLabel}>{pb}</span>
        )}
        {pa != null && (
          <span className="trk-dot a" style={{ left: `${pa}%`, ...(colorBy === 'pct' && !two ? pctFill(pa, directional) : {}) }} title={aLabel}>{pa}</span>
        )}
      </div>
      <span className="trk-v a">{fmt(a?.value, m.fmt)}{unitSuffix(m.unit)}</span>
      {two && <span className="trk-v b">{fmt(b?.value, m.fmt)}{unitSuffix(m.unit)}</span>}
    </div>
  );
}

/** All model features, grouped by cluster, for one player or a pair. */
export function SkillTracks({ meta, a, b, showWeights = true }: { meta: Meta; a: PlayerSeason; b?: PlayerSeason; showWeights?: boolean }) {
  const groups = groupFeatures(meta);
  const two = b !== undefined;
  return (
    <div className="tracks">
      <div className={'trk head' + (two ? ' two' : '')}>
        <span className="trk-l" />
        <div className="trk-scale"><span>0</span><span>percentile within season</span><span>100</span></div>
        <span className="trk-v a">{two ? shortLabel(a) : 'value'}</span>
        {two && <span className="trk-v b">{shortLabel(b!)}</span>}
      </div>
      {groups.map((g) => (
        <section className="trk-group" key={g.key}>
          <header>
            <span>{g.label}</span>
            {showWeights && <span className="w">{Math.round(g.weight * 100)}% of the model</span>}
          </header>
          {g.features.map((f) => (
            <TrackRow key={f} m={meta.feature_meta[f]} a={a.features[f]} b={two ? b!.features[f] : undefined}
              aLabel={`${a.name} ${a.season}`} bLabel={two ? `${b!.name} ${b!.season}` : undefined} />
          ))}
        </section>
      ))}
    </div>
  );
}

/** Bat-tracking metrics (2024+), same track. */
export function TrackingTracks({ meta, a, b }: { meta: Meta; a: PlayerSeason; b?: PlayerSeason }) {
  const keys = Object.keys(meta.tracking).filter((k) => a.tracking?.[k] || b?.tracking?.[k]);
  if (!keys.length) return null;
  const two = b !== undefined;
  return (
    <div className="tracks">
      {keys.map((k) => (
        <TrackRow key={k} m={meta.tracking[k]} a={a.tracking?.[k]} b={two ? b!.tracking?.[k] : undefined}
          aLabel={`${a.name} ${a.season}`} bLabel={two ? `${b!.name} ${b!.season}` : undefined} />
      ))}
    </div>
  );
}

function shortLabel(p: PlayerSeason) {
  const parts = p.name.split(' ').filter((x) => !/^(jr\.?|sr\.?|ii|iii|iv)$/i.test(x));
  return `${parts[parts.length - 1]} ’${String(p.season).slice(2)}`;
}
