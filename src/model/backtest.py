"""Walk-forward backtest: do the comps project next season better than baselines?

For each test season T:
  * the model is fit as-of T: season stats for seasons <= T, supervised part on
    pairs (s -> s+1) with s+1 <= T;
  * the comp pool is every player-season s <= T-1 that has an s+1 season
    (so "what happened next" was knowable at the time);
  * targets are hitters with >= eval_min_pa in both T and T+1;
  * the projection is scored against the actual T+1 outcome.

Baselines:
  naive   : next = this season
  marcel  : regress this season toward the league mean by PA / (PA + K)
  model   : ridge regression directly (no comps) — the ceiling the comps chase
  legacy  : the old app's hand-weighted z-score Euclidean comps (same delta
            projection) — the thing we are replacing
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .engine import ComparisonModel, ModelConfig, CompIndex, project_from_comps

LEGACY_WEIGHTS = {
    "exit_velocity": 1.0, "max_exit_velocity": 0.8, "launch_angle": 0.7, "barrel_pct": 1.0,
    "hard_hit_pct": 0.9, "chase_rate": 0.9, "zone_contact_pct": 0.8, "whiff_pct": 0.9,
    "swstr_pct": 0.8, "k_pct": 0.8, "bb_pct": 0.8, "gb_pct": 0.6,
}


def _score(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    ok = ~np.isnan(y_true) & ~np.isnan(y_pred)
    yt, yp = y_true[ok], y_pred[ok]
    if len(yt) < 5:
        return {"rmse": np.nan, "mae": np.nan, "r": np.nan, "n": int(len(yt))}
    return {
        "rmse": float(np.sqrt(np.mean((yt - yp) ** 2))),
        "mae": float(np.mean(np.abs(yt - yp))),
        "r": float(np.corrcoef(yt, yp)[0, 1]),
        "n": int(len(yt)),
    }


def _marcel(df: pd.DataFrame, y: str, K: float) -> np.ndarray:
    out = np.full(len(df), np.nan)
    for season, grp in df.groupby("season"):
        qual = grp[grp["pa"] >= 100]
        mu = float((qual[y] * qual["pa"]).sum() / qual["pa"].sum())
        pa = grp["pa"].values
        out[grp.index] = (pa * grp[y].values + K * mu) / (pa + K)
    return out


class LegacyEmbedding:
    """Old approach: global z-scores x sqrt(weight), Euclidean."""

    def __init__(self, df: pd.DataFrame):
        self.cols = [c for c in LEGACY_WEIGHTS if c in df.columns]
        self.mu = df[self.cols].mean()
        self.sd = df[self.cols].std().replace(0, 1)
        self.w = np.sqrt(np.array([LEGACY_WEIGHTS[c] for c in self.cols]))

    def embed(self, df: pd.DataFrame) -> np.ndarray:
        Z = ((df[self.cols] - self.mu) / self.sd).fillna(0).values
        return Z * self.w


def run_backtest(
    df: pd.DataFrame,
    test_seasons: List[int],
    config: Optional[ModelConfig] = None,
    k_values: List[int] = (10, 20),
    outcomes: List[str] = ("wrc_plus", "xwoba"),
    eval_min_pa: int = 200,
    include_legacy: bool = True,
    methods: List[str] = ("delta", "direct"),
    verbose: bool = True,
    return_preds: bool = False,
) -> pd.DataFrame:
    """Walk-forward backtest. With return_preds=True, returns one row per (player-season, outcome)
    with every method's prediction and the actual, for slicing error by subgroup."""
    cfg = config or ModelConfig()
    df = df.reset_index(drop=True)
    rows = []
    pred_rows = []
    for T in test_seasons:
        hist = df[df["season"] <= T].reset_index(drop=True)
        train_mask = (hist["season"] + 1) <= T          # pairs whose outcome was known at T
        model = ComparisonModel(cfg).fit(hist, train_mask=train_mask)
        index = CompIndex(model, hist)
        pool = ((hist["season"] <= T - 1) & hist["pa_next"].notna()).values

        targets = hist[(hist["season"] == T) & (hist["pa"] >= eval_min_pa) & (hist["pa_next"] >= eval_min_pa)]
        preds: Dict[str, Dict[str, list]] = {}
        direct = model.predict_next(targets)

        legacy_index = None
        if include_legacy:
            leg = LegacyEmbedding(hist)
            leg_E = leg.embed(hist)

        for i in targets.index:
            t = hist.loc[i]
            for k in k_values:
                comps = index.find(i, k=k, candidate_mask=pool)
                for method in methods:
                    proj = project_from_comps(t, comps, model, outcomes, method=method)
                    for y in outcomes:
                        preds.setdefault(f"comps_{method}_k{k}", {}).setdefault(y, []).append(proj[y]["value"] if proj[y]["value"] is not None else np.nan)
                if include_legacy and k == k_values[0]:
                    d = np.sqrt(((leg_E[pool] - leg_E[i]) ** 2).sum(axis=1))
                    idx = np.flatnonzero(pool)
                    same = hist.loc[idx, "mlbam_id"].values == t["mlbam_id"]
                    d[same] = np.inf
                    order = np.argsort(d)[:k]
                    lcomps = hist.iloc[idx[order]].copy()
                    lcomps["distance"] = d[order]
                    # legacy kernel: use the same relative kernel width
                    tmp_model = replace(model.cfg)  # noqa
                    class _M:  # minimal shim for project_from_comps
                        cfg = model.cfg
                        tau = float(np.median(d[order])) or 1.0
                    for method in methods:
                        proj = project_from_comps(t, lcomps, _M, outcomes, method=method)
                        for y in outcomes:
                            preds.setdefault(f"legacy_{method}_k{k}", {}).setdefault(y, []).append(proj[y]["value"] if proj[y]["value"] is not None else np.nan)

        for y in outcomes:
            y_true = targets[f"{y}_next"].values.astype(float)
            y_now = targets[y].values.astype(float)
            results = {
                "naive": y_now,
                "marcel_k300": _marcel(hist, y, 300)[targets.index],
                "marcel_k600": _marcel(hist, y, 600)[targets.index],
                "model_direct": direct[y].values if y in direct.columns else np.full(len(targets), np.nan),
            }
            for name, d in preds.items():
                results[name] = np.array(d[y], dtype=float)
            for name, yp in results.items():
                s = _score(y_true, yp)
                rows.append({"test_season": T, "outcome": y, "method": name, **s})
            if return_preds:
                pr = pd.DataFrame({"mlbam_id": targets["mlbam_id"].values, "name": targets["name"].values,
                                   "season": T, "outcome": y, "actual": y_true})
                for name, yp in results.items():
                    pr[name] = np.asarray(yp, dtype=float)
                if "result_gap" in targets.columns:
                    pr["result_gap"] = targets["result_gap"].values
                pred_rows.append(pr)
        if verbose:
            sub = pd.DataFrame([r for r in rows if r["test_season"] == T])
            print(f"\n== Test season {T} -> {T + 1}  (n={len(targets)} hitters, train pairs={model.train_pairs})")
            print(sub.pivot(index="method", columns="outcome", values="rmse").round(4).to_string())
    if return_preds:
        return pd.concat(pred_rows, ignore_index=True)
    return pd.DataFrame(rows)


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    """Average metrics across test seasons."""
    g = results.groupby(["outcome", "method"]).agg(rmse=("rmse", "mean"), mae=("mae", "mean"), r=("r", "mean"), n=("n", "sum"))
    return g.reset_index().sort_values(["outcome", "rmse"])
