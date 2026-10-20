"""The comparison model.

Pipeline
--------
1. Season-relative standardization: every underlying metric becomes a z-score
   against that season's league (PA-qualified) distribution, so a 2019 juiced-ball
   barrel rate and a 2022 dead-ball barrel rate are compared as "how far above
   the league" rather than raw.
2. Whitening (PCA): the standardized feature block is rotated into uncorrelated,
   unit-variance components. This is the fix for the "six ways of saying he hits
   it hard" problem — correlated metrics collapse into one direction instead of
   being counted six times. Distance in this space is the Mahalanobis distance.
3. Supervised weighting: a ridge regression learns how each whitened direction
   predicts NEXT-season outcomes (xwOBA, wRC+, K%, BB%, ISO, BABIP). Two players
   are then embedded as
        e = [ B^T w * pred_weight ,  w * profile_weight ]
   so distance = (difference in what the model expects next year)
               + (difference in underlying profile, decorrelated).
   The second term keeps comps that *look* alike; the first makes them *project*
   alike. The balance is chosen by the backtest, not by hand.
4. Similarity score: distance is calibrated against the distribution of nearest-
   neighbour distances so "90" means "as close as a typical best comp".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge

from .prepare import FEATURES, CLUSTERS, SHRINK

DEFAULT_TARGETS = ["xwoba", "wrc_plus", "k_pct", "bb_pct", "iso", "babip"]


@dataclass
class ModelConfig:
    features: Optional[List[str]] = None        # None = auto-select by coverage
    targets: List[str] = field(default_factory=lambda: list(DEFAULT_TARGETS))
    min_coverage: float = 0.6                   # drop features missing in >40% of rows
    qual_pa: int = 100                          # rows used to fit season means/stds
    train_min_pa: int = 200                     # both seasons of a training pair
    ridge_alpha: float = 10.0
    pred_weight: float = 1.0
    profile_weight: float = 0.35
    n_components: Optional[int] = None          # None = keep all (full whitening)
    k_default: int = 10
    kernel_scale: float = 1.0                   # comp-weight kernel width, in units of tau
    age_mode: str = "predict"                   # "predict": age (and age^2) feed the outcome regression only;
                                                # "profile": age is a similarity feature like any other;
                                                # "none": ignore age
    age_center: float = 27.0
    age_scale: float = 5.0
    shrink: bool = True                         # sample-size shrinkage of z-scores (see prepare.SHRINK)
    shrink_scale: float = 2.0                   # multiplier on the stabilization constants (backtest-chosen)
    min_season: Optional[int] = None            # e.g. 2024 for a modern-era model

    def to_dict(self):
        return asdict(self)


class ComparisonModel:
    def __init__(self, config: Optional[ModelConfig] = None):
        self.cfg = config or ModelConfig()
        self.features: List[str] = []           # profile (similarity) features
        self.context_features: List[str] = []   # e.g. age: used by the outcome regression only
        self.targets: List[str] = []
        self.season_stats: Dict[int, Dict[str, Dict[str, float]]] = {}
        self.global_stats: Dict[str, Dict[str, float]] = {}
        self.target_stats: Dict[int, Dict[str, Dict[str, float]]] = {}
        self.pca: Optional[PCA] = None
        self.ridge: Optional[Ridge] = None
        self.tau: float = 1.0
        self.feature_importance: Dict[str, float] = {}
        self.cluster_importance: Dict[str, float] = {}
        self.train_pairs: int = 0
        self.fit_seasons: List[int] = []

    # ------------------------------------------------------------------ fitting
    def _select_features(self, df: pd.DataFrame) -> List[str]:
        if self.cfg.features:
            out = [f for f in self.cfg.features if f in df.columns]
        else:
            out = [f for f in FEATURES if FEATURES[f].get("default", True) and f in df.columns
                   and df[f].notna().mean() >= self.cfg.min_coverage]
        self.context_features = []
        has_age = "age" in df.columns and df["age"].notna().mean() >= self.cfg.min_coverage
        if self.cfg.age_mode == "predict":
            out = [f for f in out if f != "age"]
            if has_age:
                self.context_features = ["age"]
        elif self.cfg.age_mode == "none":
            out = [f for f in out if f != "age"]
        elif has_age and "age" not in out:
            out.append("age")
        return out

    def context_matrix(self, df: pd.DataFrame) -> np.ndarray:
        """Centered age and age^2 (aging curves are not linear); missing age -> peak age."""
        if not self.context_features:
            return np.zeros((len(df), 0))
        a = pd.to_numeric(df["age"], errors="coerce").values.astype(float)
        a = (a - self.cfg.age_center) / self.cfg.age_scale
        a = np.nan_to_num(a, nan=0.0)
        return np.column_stack([a, a ** 2])

    def _fit_standardizer(self, df: pd.DataFrame) -> None:
        self.season_stats = {}
        qual = df[df["pa"] >= self.cfg.qual_pa]
        for season, grp in qual.groupby("season"):
            stats = {}
            for f in self.features:
                if f == "age":
                    continue
                col = grp[f].dropna()
                if len(col) >= 30:
                    stats[f] = {"mean": float(col.mean()), "std": float(col.std(ddof=0) or 1.0)}
            self.season_stats[int(season)] = stats
        self.global_stats = {}
        for f in self.features:
            col = qual[f].dropna()
            self.global_stats[f] = {"mean": float(col.mean()), "std": float(col.std(ddof=0) or 1.0)}
        # Targets are standardized against their own season too
        self.target_stats = {}
        for season, grp in qual.groupby("season"):
            stats = {}
            for t in self.targets:
                col = grp[t].dropna()
                if len(col) >= 30:
                    stats[t] = {"mean": float(col.mean()), "std": float(col.std(ddof=0) or 1.0)}
            self.target_stats[int(season)] = stats

    def standardize(self, df: pd.DataFrame) -> np.ndarray:
        """Season-relative z-scores, NaN -> 0 (league average)."""
        Z = np.zeros((len(df), len(self.features)))
        seasons = df["season"].astype(int).values
        latest = max(self.season_stats) if self.season_stats else None
        for j, f in enumerate(self.features):
            x = pd.to_numeric(df[f], errors="coerce").values.astype(float)
            if f == "age":
                g = self.global_stats[f]
                z = (x - g["mean"]) / g["std"]
            else:
                mean = np.empty(len(df)); std = np.empty(len(df))
                for i, s in enumerate(seasons):
                    st = self.season_stats.get(int(s), self.season_stats.get(latest, {})).get(f) or self.global_stats[f]
                    mean[i], std[i] = st["mean"], st["std"]
                z = (x - mean) / std
            if self.cfg.shrink and f in SHRINK:
                col, k = SHRINK[f]
                k = k * self.cfg.shrink_scale
                n = pd.to_numeric(df[col], errors="coerce").values.astype(float) if col in df.columns else np.full(len(df), np.nan)
                n = np.where(np.isnan(n), pd.to_numeric(df["pa"], errors="coerce").values.astype(float) * (0.65 if col == "bbe" else 1.0), n)
                z = z * (n / (n + k))
            Z[:, j] = np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)
        return Z

    def standardize_targets(self, df: pd.DataFrame, suffix: str = "_next", season_offset: int = 1) -> np.ndarray:
        Y = np.full((len(df), len(self.targets)), np.nan)
        seasons = df["season"].astype(int).values + season_offset
        latest = max(self.target_stats)
        for j, t in enumerate(self.targets):
            x = pd.to_numeric(df[f"{t}{suffix}"], errors="coerce").values.astype(float)
            mean = np.empty(len(df)); std = np.empty(len(df))
            for i, s in enumerate(seasons):
                st = self.target_stats.get(int(s), self.target_stats[latest]).get(t)
                if st is None:
                    st = self.target_stats[latest].get(t, {"mean": 0, "std": 1})
                mean[i], std[i] = st["mean"], st["std"]
            Y[:, j] = (x - mean) / std
        return Y

    def fit(self, df: pd.DataFrame, train_mask: Optional[pd.Series] = None) -> "ComparisonModel":
        """Fit on `df`. Supervised part uses only rows where train_mask is True
        (default: all rows that have a next season)."""
        self.features = self._select_features(df)
        self.targets = [t for t in self.cfg.targets if f"{t}_next" in df.columns]
        self._fit_standardizer(df)
        self.fit_seasons = sorted(int(s) for s in df["season"].unique())

        Z = self.standardize(df)
        n_comp = self.cfg.n_components or Z.shape[1]
        self.pca = PCA(n_components=n_comp, whiten=True, random_state=0).fit(Z)
        W = self.pca.transform(Z)

        if train_mask is None:
            train_mask = pd.Series(True, index=df.index)
        pair_ok = (
            train_mask.values
            & df["pa_next"].notna().values
            & (df["pa"].values >= self.cfg.train_min_pa)
            & (df["pa_next"].values >= self.cfg.train_min_pa)
        )
        Y = self.standardize_targets(df)
        pair_ok &= ~np.isnan(Y).any(axis=1)
        self.train_pairs = int(pair_ok.sum())
        weights = np.sqrt(np.minimum(df["pa"].values, df["pa_next"].values)[pair_ok] / 600.0)
        C = self.context_matrix(df)
        X = np.hstack([W, C])
        self.ridge = Ridge(alpha=self.cfg.ridge_alpha).fit(X[pair_ok], Y[pair_ok], sample_weight=weights)

        # Calibrate similarity scale on the fitted population
        E = self._embed_from_whitened(W, C)
        self.tau = self._calibrate_tau(E)
        self._compute_importance()
        return self

    # ---------------------------------------------------------------- embedding
    def _embed_from_whitened(self, W: np.ndarray, C: np.ndarray) -> np.ndarray:
        P = self.ridge.predict(np.hstack([W, C])) * self.cfg.pred_weight
        return np.hstack([P, W * self.cfg.profile_weight])

    def embed(self, df: pd.DataFrame) -> np.ndarray:
        return self._embed_from_whitened(self.pca.transform(self.standardize(df)), self.context_matrix(df))

    def predict_next(self, df: pd.DataFrame) -> pd.DataFrame:
        """Direct model projection of next-season outcomes, in raw units."""
        W = self.pca.transform(self.standardize(df))
        P = self.ridge.predict(np.hstack([W, self.context_matrix(df)]))
        out = pd.DataFrame(index=df.index)
        seasons = df["season"].astype(int).values + 1
        latest = max(self.target_stats)
        for j, t in enumerate(self.targets):
            vals = np.empty(len(df))
            for i, s in enumerate(seasons):
                st = self.target_stats.get(int(s), self.target_stats[latest]).get(t) or self.target_stats[latest][t]
                vals[i] = P[i, j] * st["std"] + st["mean"]
            out[t] = vals
        return out

    def _calibrate_tau(self, E: np.ndarray) -> float:
        """tau = median distance to the single nearest neighbour (excluding self)."""
        n = len(E)
        idx = np.random.RandomState(0).choice(n, size=min(n, 1500), replace=False)
        d = np.sqrt(((E[idx, None, :] - E[None, :, :]) ** 2).sum(-1))
        d[np.arange(len(idx)), idx] = np.inf
        return float(np.median(d.min(axis=1)))

    def similarity(self, dist: np.ndarray) -> np.ndarray:
        """100 at distance 0; 90 at the typical best-comp distance (tau)."""
        return 100.0 * np.exp(-(dist / self.tau) * np.log(100 / 90))

    def _compute_importance(self) -> None:
        # Map ridge coefficients back to standardized-feature space:
        # pred = B^T (Z V / sqrt(lambda))  =>  feature loading = V diag(1/sqrt(lambda)) B
        V = self.pca.components_.T                     # (n_feat, n_comp)
        scale = 1.0 / np.sqrt(self.pca.explained_variance_)
        n_comp = self.pca.n_components_
        B = self.ridge.coef_.T[:n_comp]                # (n_comp, n_targets)
        L = (V * scale) @ B                            # (n_feat, n_targets)
        imp = list(np.linalg.norm(L, axis=1))
        names = list(self.features)
        if self.context_features:
            # age + age^2 coefficients, on the same (unit-variance-ish) scale as whitened components
            Bc = self.ridge.coef_.T[n_comp:]
            imp.append(float(np.linalg.norm(Bc)))
            names.append("age")
        imp = np.array(imp) / np.sum(imp)
        self.feature_importance = {f: float(v) for f, v in zip(names, imp)}
        self.cluster_importance = {}
        for f, v in self.feature_importance.items():
            c = FEATURES[f]["cluster"]
            self.cluster_importance[c] = self.cluster_importance.get(c, 0.0) + v

    # -------------------------------------------------------------- persistence
    def save(self, path: Path) -> None:
        joblib.dump(self, path)

    @staticmethod
    def load(path: Path) -> "ComparisonModel":
        return joblib.load(path)

    def summary(self) -> dict:
        return {
            "config": self.cfg.to_dict(),
            "features": self.features,
            "feature_meta": {f: {"label": FEATURES[f]["label"], "cluster": FEATURES[f]["cluster"],
                                 "cluster_label": CLUSTERS[FEATURES[f]["cluster"]],
                                 "higher_better": FEATURES[f]["higher_better"],
                                 "fmt": FEATURES[f]["fmt"], "unit": FEATURES[f]["unit"]}
                             for f in self.features + self.context_features},
            "context_features": self.context_features,
            "targets": self.targets,
            "feature_importance": self.feature_importance,
            "cluster_importance": self.cluster_importance,
            "explained_variance_ratio": [float(x) for x in self.pca.explained_variance_ratio_],
            "train_pairs": self.train_pairs,
            "seasons": self.fit_seasons,
            "tau": self.tau,
        }


# ---------------------------------------------------------------- comp search
class CompIndex:
    """Nearest-neighbour search over a fitted model's embedding of a frame."""

    def __init__(self, model: ComparisonModel, df: pd.DataFrame):
        self.model = model
        self.df = df.reset_index(drop=True)
        self.E = model.embed(self.df)

    def find(self, row_idx: int, k: int = 10, candidate_mask: Optional[np.ndarray] = None,
             exclude_same_player: bool = True, min_pa: int = 100) -> pd.DataFrame:
        target = self.df.iloc[row_idx]
        mask = np.ones(len(self.df), dtype=bool) if candidate_mask is None else candidate_mask.copy()
        mask[row_idx] = False
        if exclude_same_player:
            mask &= (self.df["mlbam_id"].values != target["mlbam_id"])
        mask &= self.df["pa"].values >= min_pa
        idx = np.flatnonzero(mask)
        d = np.sqrt(((self.E[idx] - self.E[row_idx]) ** 2).sum(axis=1))
        order = np.argsort(d)[:k]
        out = self.df.iloc[idx[order]].copy()
        out["distance"] = d[order]
        out["similarity"] = self.model.similarity(d[order])
        out["row_idx"] = idx[order]
        return out


# ---------------------------------------------------------------- projection
def project_from_comps(target: pd.Series, comps: pd.DataFrame, model: ComparisonModel,
                       outcomes: Sequence[str], method: str = "delta") -> Dict[str, dict]:
    """Comp-based projection of the target's next season.

    delta  : target_now + weighted mean of (comp_next - comp_now)   [default]
    direct : weighted mean of comp_next
    Weights: Gaussian kernel on distance (scale = kernel_scale * tau) x sqrt(PA).
    """
    h = model.cfg.kernel_scale * model.tau
    w_dist = np.exp(-0.5 * (comps["distance"].values / h) ** 2)
    w_pa = np.sqrt(np.minimum(comps["pa"].values, comps["pa_next"].fillna(0).values) / 600.0)
    out = {}
    for y in outcomes:
        nxt = pd.to_numeric(comps.get(f"{y}_next"), errors="coerce").values.astype(float)
        now = pd.to_numeric(comps.get(y), errors="coerce").values.astype(float)
        tnow = pd.to_numeric(pd.Series([target.get(y)]), errors="coerce").iloc[0]
        ok = ~np.isnan(nxt) & ~np.isnan(now)
        if ok.sum() == 0 or (method == "delta" and pd.isna(tnow)):
            out[y] = {"value": None, "low": None, "high": None, "n": 0}
            continue
        w = (w_dist * w_pa)[ok]
        w = w / w.sum()
        if method == "delta":
            vals = tnow + (nxt[ok] - now[ok])
        else:
            vals = nxt[ok]
        est = float((w * vals).sum())
        # Weighted 20th/80th percentile band from comp outcomes
        order = np.argsort(vals)
        cw = np.cumsum(w[order])
        low = float(vals[order][np.searchsorted(cw, 0.2)])
        high = float(vals[order][min(np.searchsorted(cw, 0.8), len(order) - 1)])
        out[y] = {"value": est, "low": low, "high": high, "n": int(ok.sum())}
    return out
