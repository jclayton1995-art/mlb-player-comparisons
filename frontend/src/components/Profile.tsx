import { fmt, shortName, type Meta, type PlayerSeason } from '../api';

const CLUSTER_ORDER = ['power', 'shape', 'approach', 'swing', 'context'];

export function groupFeatures(meta: Meta) {
  const groups: { key: string; label: string; features: string[]; weight: number }[] = [];
  for (const c of CLUSTER_ORDER) {
    const fs = meta.features.filter((f) => meta.feature_meta[f].cluster === c);
    if (fs.length) groups.push({ key: c, label: meta.clusters[c], features: fs, weight: meta.cluster_importance[c] ?? 0 });
  }
  return groups;
}

/** One player's underlying profile: within-season percentile bars, grouped by skill cluster. */
export function Profile({ meta, p }: { meta: Meta; p: PlayerSeason }) {
  const groups = groupFeatures(meta);
  return (
    <div>
      {groups.map((g) => (
        <div className="cluster" key={g.key}>
          <div className="cluster-head">
            <span className="t">{g.label}</span>
            <span className="w">{Math.round(g.weight * 100)}% of model weight</span>
          </div>
          {g.features.map((f) => {
            const s = p.features[f];
            const fm = meta.feature_meta[f];
            const pct = s?.pct ?? null;
            return (
              <div className="bar-row" key={f} title={`${fm.label}: ${fmt(s?.value, fm.fmt)}${fm.unit} — ${pct == null ? '' : Math.round(pct) + 'th percentile this season'}`}>
                <span className="lab">{fm.label}</span>
                <div className="bar">
                  <span className="mid" />
                  <span className="fill" style={{ width: `${pct ?? 0}%`, opacity: 0.35 + 0.65 * ((pct ?? 50) / 100) }} />
                </div>
                <span className="val">{fmt(s?.value, fm.fmt)}</span>
                <span className="pct">{pct == null ? '–' : Math.min(99, Math.max(1, Math.round(pct)))}</span>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

/** Target vs comp, same scale: two thin bars per metric. */
export function DualProfile({ meta, a, b }: { meta: Meta; a: PlayerSeason; b: PlayerSeason }) {
  const groups = groupFeatures(meta);
  return (
    <div>
      <div className="dual-head">
        <span />
        <span className="muted">percentile within season</span>
        <span className="a">{shortName(a.name)} {a.season}</span>
        <span className="b">{shortName(b.name)} {b.season}</span>
      </div>
      {groups.map((g) => (
        <div className="cluster" key={g.key}>
          <div className="cluster-head"><span className="t">{g.label}</span></div>
          {g.features.map((f) => {
            const fm = meta.feature_meta[f];
            const sa = a.features[f], sb = b.features[f];
            return (
              <div className="bar-row dual" key={f}>
                <span className="lab">{fm.label}</span>
                <div className="bar dual">
                  <span className="mid" />
                  <span className="fill" style={{ width: `${sa?.pct ?? 0}%` }} />
                  <span className="fill comp" style={{ width: `${sb?.pct ?? 0}%` }} />
                </div>
                <span className="val" style={{ color: 'var(--accent-ink)' }}>{fmt(sa?.value, fm.fmt)}</span>
                <span className="val">{fmt(sb?.value, fm.fmt)}</span>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
