export type Stat = { value: number | null; pct: number | null; z?: number | null };

export type PlayerSeason = {
  row: number;
  mlbam_id: number;
  name: string;
  season: number;
  team: string | null;
  bats: string | null;
  pa: number | null;
  g: number | null;
  age: number | null;
  result_gap: number | null;
  features: Record<string, Stat>;
  outcomes: Record<string, Stat>;
  tracking: Record<string, Stat> | null;
  next: (Record<string, number | null> & { pa: number | null }) | null;
  prev: (Record<string, number | null> & { pa: number | null }) | null;
  model_next: Record<string, number | null>;
};

export type Comp = PlayerSeason & {
  similarity: number;
  distance: number;
  z_diff: Record<string, number | null>;
};

export type ProjValue = {
  value: number | null; low: number | null; high: number | null; n: number;
  /** wRC+ only: track-record adjustment applied (beta × career gap), and the unadjusted comps estimate */
  track_adj?: number; track_gap?: number; comps_only?: number;
};

/** Below this best-comp similarity the projection is flagged as borrowed from weak matches (typical best ≈ 90). */
export const LOW_CONFIDENCE = 85;

export type CompareResponse = {
  target: PlayerSeason;
  comps: Comp[];
  projection: {
    season: number;
    method: string;
    n_comps: number;
    best_similarity: number | null;
    track_beta: number;
    values: Record<string, ProjValue>;
    model_direct: Record<string, number | null>;
    actual: (Record<string, number | null> & { pa: number | null }) | null;
    comps_used: { mlbam_id: number; name: string; season: number; similarity: number; next: Record<string, number | null>; pa_next: number | null }[];
  };
};

export type FeatureMeta = {
  label: string;
  cluster: string;
  cluster_label: string;
  higher_better: boolean | null;
  fmt: string;
  unit: string;
};

export type BacktestRow = { outcome: string; method: string; rmse: number; mae: number; r: number; n: number };

export type Meta = {
  features: string[];
  feature_meta: Record<string, FeatureMeta>;
  clusters: Record<string, string>;
  cluster_importance: Record<string, number>;
  feature_importance: Record<string, number>;
  targets: string[];
  outcomes: Record<string, { label: string; fmt: string; higher_better: boolean }>;
  tracking: Record<string, { label: string; fmt: string; unit: string; higher_better: boolean | null }>;
  context_features: string[];
  seasons: number[];
  n_rows: number;
  train_pairs: number;
  trained_at: string | null;
  config: Record<string, unknown>;
  backtest: { test_seasons: number[]; eval_min_pa: number; summary: BacktestRow[]; by_season: (BacktestRow & { test_season: number })[] } | null;
  explained_variance_ratio: number[];
};

export type SearchHit = {
  mlbam_id: number;
  name: string;
  seasons: number[];
  latest_season: number;
  team: string | null;
  career_wrc: number | null;
};

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}: ${await r.text()}`);
  return r.json();
}

export type ExploreRow = {
  row: number; mlbam_id: number; name: string; season: number; team: string | null; age: number | null; pa: number;
  wrc_plus: number | null; xwoba: number | null; next_wrc: number | null; proj_wrc: number | null;
  similarity: number | null; comp_id: number; comp_name: string | null; comp_season: number; comp_next_wrc: number | null;
  pct: Record<string, number>;   // within-season percentile per metric, higher = better where directional
  val: Record<string, number>;   // raw value per metric
};

export const api = {
  meta: () => get<Meta>('/api/meta'),
  explore: () => get<ExploreRow[]>('/api/explore'),
  search: (q: string) => get<SearchHit[]>(`/api/search?q=${encodeURIComponent(q)}`),
  compare: (id: number, season: number, k = 10) => get<CompareResponse>(`/api/compare/${id}/${season}?k=${k}`),
  player: (id: number) => get<{ mlbam_id: number; name: string; seasons: PlayerSeason[] }>(`/api/players/${id}`),
};

export const headshot = (id: number, w = 240) =>
  `https://img.mlbstatic.com/mlb-photos/image/upload/w_${w},q_auto:best/v1/people/${id}/headshot/67/current`;

/** Format a number using the python-style fmt string from the API ("{:.1f}"). */
export function fmt(v: number | null | undefined, f: string = '{:.1f}'): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '–';
  const m = f.match(/\.(\d)f/);
  const d = m ? parseInt(m[1]) : 1;
  const s = v.toFixed(d);
  // baseball convention: .463 not 0.463 for rate stats
  return d === 3 && Math.abs(v) < 1 ? s.replace(/^(-?)0\./, '$1.') : s;
}

/** Last name without generational suffixes: "Bobby Witt Jr." -> "Witt". */
export function shortName(name: string): string {
  const parts = name.split(' ').filter((p) => !/^(jr\.?|sr\.?|ii|iii|iv)$/i.test(p));
  return parts[parts.length - 1] ?? name;
}
