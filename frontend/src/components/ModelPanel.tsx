import { type Meta } from '../api';

const METHOD_LABEL: Record<string, string> = {
  comps_direct_k40: 'This app: 40 nearest comps',
  model_direct: 'Regression model (no comps)',
  marcel_k300: 'Marcel-style regression to the mean',
  marcel_k600: 'Marcel-style, heavier regression',
  legacy_direct_k40: 'Old app: hand-weighted z-scores',
  naive: 'Assume same as this year',
};

export function ModelPanel({ meta, onClose }: { meta: Meta; onClose: () => void }) {
  const imps = Object.entries(meta.feature_importance).sort((a, b) => b[1] - a[1]);
  const max = imps[0]?.[1] ?? 1;
  const bt = meta.backtest;
  const rows = (o: string) => (bt ? bt.summary.filter((r) => r.outcome === o && !r.method.includes('k600')) : []);
  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <div className="drawer" role="dialog" aria-label="How comps are chosen">
        <button className="btn ghost close" onClick={onClose} aria-label="Close">Close</button>
        <h2>How comps are chosen</h2>
        <p>
          Comps are picked on <b>underlying skills only</b> — contact quality, batted-ball shape, approach — never on
          results like batting average or wRC+. Results are what we try to predict, so they stay out of the inputs.
        </p>

        <h3>1. Every metric is measured against its own season</h3>
        <p>
          A barrel rate is a z-score against that year's league, so a 2019 (juiced ball) hitter and a 2022 hitter are
          compared on how far above the league they were, not on raw numbers.
        </p>

        <h3>2. Correlated metrics are collapsed, not double-counted</h3>
        <p>
          Exit velocity, EV50, hard-hit% and barrel% all say "he hits it hard". The {meta.features.length} metrics are
          rotated into uncorrelated directions (PCA whitening), so the hard-hit cluster counts once. Distance in that
          space is the Mahalanobis distance.
        </p>

        <h3>3. The weights are learned from what predicts next season</h3>
        <p>
          A ridge regression learns how each direction predicts next-year xwOBA, wRC+, K%, BB%, ISO and BABIP. Two
          hitters are close when the model expects the same future from them <i>and</i> their decorrelated profiles look
          alike ({String((meta.config.profile_weight as number) ?? '')} weight on the profile term, chosen by backtest).
        </p>
        <div className="callout">
          Share of the learned weight by cluster:{' '}
          {Object.entries(meta.cluster_importance).map(([k, v]) => `${meta.clusters[k]} ${Math.round(v * 100)}%`).join(', ')}.
        </div>
        {imps.map(([f, v]) => (
          <div className="imp-row" key={f}>
            <span>{meta.feature_meta[f].label}</span>
            <div className="bar"><span className="fill" style={{ width: `${(v / max) * 100}%` }} /></div>
            <span className="pct">{(v * 100).toFixed(1)}%</span>
          </div>
        ))}

        {meta.context_features.includes('age') && (
          <>
            <h3>Age</h3>
            <p>
              Age is not a skill, so it is not part of the profile that comps are matched on. It enters the outcome
              regression (as age and age²), so an older hitter's expected next season is pulled down by the aging
              curve and his comps are hitters whose expected next season matches his.
            </p>
          </>
        )}

        <h3>4. Does it work? Walk-forward backtest</h3>
        <p>
          For each test season the model is refit using only what was knowable at the time, then the comps' following
          seasons are used to project each hitter's next year ({bt?.eval_min_pa}+ PA both years). Lower error is better.
        </p>
        {bt && (
          <>
            <div className="panel-note">Test seasons {bt.test_seasons.join(', ')} → next year. RMSE of wRC+ (points) and xwOBA.</div>
            <table className="bt-table">
              <thead>
                <tr><th>Method</th><th>wRC+ RMSE</th><th>xwOBA RMSE</th><th>r (wRC+)</th></tr>
              </thead>
              <tbody>
                {rows('wrc_plus').map((r) => {
                  const x = rows('xwoba').find((q) => q.method === r.method);
                  return (
                    <tr key={r.method} className={r.method.startsWith('comps') ? 'us' : r.method.startsWith('legacy') ? 'old' : ''}>
                      <td>{METHOD_LABEL[r.method] ?? r.method}</td>
                      <td>{r.rmse.toFixed(1)}</td>
                      <td>{x ? x.rmse.toFixed(4) : '–'}</td>
                      <td>{r.r.toFixed(3)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}
        <p style={{ marginTop: 12 }}>
          Trained on {meta.n_rows.toLocaleString()} hitter-seasons ({meta.seasons[0]}–{meta.seasons[meta.seasons.length - 1]}),{' '}
          {meta.train_pairs.toLocaleString()} season-to-season pairs. Similarity 90 means “as close as a typical best comp”.
        </p>
      </div>
    </>
  );
}
