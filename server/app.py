"""FastAPI backend: serves the comparison model and the built frontend.

    uvicorn server.app:app --reload --port 8000
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.model.engine import ComparisonModel, CompIndex, project_from_comps  # noqa: E402
from src.model.prepare import FEATURES, OUTCOMES, CLUSTERS  # noqa: E402

MODEL_DIR = PROJECT_ROOT / "data" / "model"
DIST = PROJECT_ROOT / "frontend" / "dist"

app = FastAPI(title="MLB Comps API", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=2048)


class State:
    model: ComparisonModel
    df: pd.DataFrame
    index: CompIndex
    meta: dict
    Z: np.ndarray
    players: pd.DataFrame
    pool_mask: np.ndarray
    show_mask: np.ndarray
    latest_season: int
    explore: pd.DataFrame


S = State()


def load_state() -> None:
    if not (MODEL_DIR / "batter_model.joblib").exists():
        raise RuntimeError("Model artifacts missing. Run: python scripts/train_model.py")
    S.model = ComparisonModel.load(MODEL_DIR / "batter_model.joblib")
    S.df = pd.read_parquet(MODEL_DIR / "batters.parquet").reset_index(drop=True)
    S.meta = json.loads((MODEL_DIR / "batter_meta.json").read_text())
    S.index = CompIndex(S.model, S.df)
    S.Z = S.model.standardize(S.df)
    S.pool_mask = (S.df["pa_next"].notna() & (S.df["pa_next"] >= 100)).values
    # Displayed comps must have a known next season (so "what happened next" is answerable),
    # except seasons from the latest year, whose next season simply hasn't happened yet.
    S.latest_season = int(S.df["season"].max())
    S.show_mask = S.pool_mask | (S.df["season"].values == S.latest_season)
    g = S.df.sort_values("season").groupby("mlbam_id")
    S.players = pd.DataFrame({
        "mlbam_id": g["mlbam_id"].first(),
        "name": g["name"].last(),
        "seasons": g["season"].apply(lambda s: sorted(int(x) for x in s)),
        "latest_season": g["season"].max(),
        "latest_team": g["team"].last(),
        "max_pa": g["pa"].max(),
        "career_wrc": g.apply(lambda x: float((x["wrc_plus"] * x["pa"]).sum() / x["pa"].sum()) if x["pa"].sum() else None),
    }).reset_index(drop=True)
    S.players["name_lc"] = S.players["name"].str.lower()
    S.players["name_ascii"] = S.players["name_lc"].str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii")
    S.explore = build_explore()


def build_explore(min_pa: int = 100) -> pd.DataFrame:
    """One row per hitter-season: his single best comp (any other player, any season)
    and the comp-based projection — precomputed so the explorer can sort the whole league."""
    E = S.index.E
    df = S.df
    n = len(df)
    pa = df["pa"].values
    pid = df["mlbam_id"].values
    cand = (pa >= min_pa) & S.show_mask     # who can be a displayed comp
    pool = cand & S.pool_mask               # who can feed a projection
    kproj = S.model.cfg.k_default
    h = S.model.cfg.kernel_scale * S.model.tau
    wrc_next = df["wrc_plus_next"].values.astype(float)
    pa_next = df["pa_next"].fillna(0).values.astype(float)
    best_i = np.full(n, -1); best_d = np.full(n, np.nan); proj = np.full(n, np.nan)
    sq = (E ** 2).sum(axis=1)
    for s in range(0, n, 256):
        e = slice(s, min(n, s + 256))
        D = np.sqrt(np.maximum(sq[e, None] + sq[None, :] - 2 * E[e] @ E.T, 0))
        same = pid[e, None] == pid[None, :]
        Dc = np.where(cand[None, :] & ~same, D, np.inf)
        j = Dc.argmin(axis=1); best_i[e] = j; best_d[e] = Dc[np.arange(len(j)), j]
        Dp = np.where(pool[None, :] & ~same, D, np.inf)
        nn = np.argpartition(Dp, kproj, axis=1)[:, :kproj]
        dn = np.take_along_axis(Dp, nn, axis=1)
        w = np.exp(-0.5 * (dn / h) ** 2) * np.sqrt(np.minimum(pa[nn], pa_next[nn]) / 600.0)
        w[~np.isfinite(dn)] = 0
        proj[e] = (w * wrc_next[nn]).sum(axis=1) / np.where(w.sum(axis=1) > 0, w.sum(axis=1), np.nan)
    out = pd.DataFrame({
        "row": np.arange(n), "mlbam_id": pid, "name": df["name"].values, "season": df["season"].values,
        "team": df["team"].values if "team" in df else None, "age": df["age"].values if "age" in df else np.nan, "pa": pa,
        "wrc_plus": df["wrc_plus"].values, "xwoba": df["xwoba"].values,
        "next_wrc": df["wrc_plus_next"].values, "proj_wrc": proj,
        "comp_row": best_i, "similarity": S.model.similarity(best_d),
    })
    ok = best_i >= 0
    out["comp_id"] = np.where(ok, pid[best_i], -1)
    out["comp_name"] = np.where(ok, df["name"].values[best_i], None)
    out["comp_season"] = np.where(ok, df["season"].values[best_i], -1)
    out["comp_next_wrc"] = np.where(ok, wrc_next[best_i], np.nan)
    # Within-season percentile of every feature + tracking metric (oriented so higher = better where
    # the metric has a direction), so the explorer can filter "70th+ in zone-contact and EV50".
    pct_cols = [f for f in S.model.features] + [t for t in S.meta.get("tracking", {})]
    for c in pct_cols:
        col = f"{c}_pct"
        if col in df.columns:
            out[f"p_{c}"] = pd.to_numeric(df[col], errors="coerce").round(0).values
    return out


load_state()


# ----------------------------------------------------------------- helpers
def _num(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(f) or math.isinf(f)) else f


def _row_payload(i: int, with_next: bool = True) -> Dict[str, Any]:
    r = S.df.iloc[i]
    feats = {}
    for j, f in enumerate(S.model.features):
        feats[f] = {"value": _num(r.get(f)), "pct": _num(r.get(f"{f}_pct")), "z": _num(S.Z[i, j])}
    outs = {}
    for o in S.meta["outcomes"]:
        outs[o] = {"value": _num(r.get(o)), "pct": _num(r.get(f"{o}_pct"))}
    tracking = {}
    for t in S.meta.get("tracking", {}):
        v = _num(r.get(t))
        if v is not None:
            tracking[t] = {"value": v, "pct": _num(r.get(f"{t}_pct"))}
    payload = {
        "row": int(i),
        "tracking": tracking or None,
        "mlbam_id": int(r["mlbam_id"]),
        "name": r["name"],
        "season": int(r["season"]),
        "team": r.get("team") if isinstance(r.get("team"), str) else None,
        "bats": r.get("bats") if isinstance(r.get("bats"), str) else None,
        "pa": _num(r.get("pa")),
        "g": _num(r.get("g")),
        "age": _num(r.get("age")),
        "features": feats,
        "outcomes": outs,
    }
    if with_next:
        nxt = {o: _num(r.get(f"{o}_next")) for o in S.meta["outcomes"]}
        nxt["pa"] = _num(r.get("pa_next"))
        payload["next"] = nxt if nxt["pa"] is not None else None
        prv = {o: _num(r.get(f"{o}_prev")) for o in S.meta["outcomes"]}
        prv["pa"] = _num(r.get("pa_prev"))
        payload["prev"] = prv if prv["pa"] is not None else None
        payload["model_next"] = {t: _num(r.get(f"{t}_model_next")) for t in S.model.targets}
    return payload


def _player_row(mlbam_id: int, season: int) -> int:
    m = (S.df["mlbam_id"] == mlbam_id) & (S.df["season"] == season)
    if not m.any():
        raise HTTPException(404, f"No season {season} for player {mlbam_id}")
    return int(np.flatnonzero(m.values)[0])


# ----------------------------------------------------------------- routes
@app.get("/api/meta")
def meta():
    m = S.meta
    return {
        "features": m["features"],
        "feature_meta": m["feature_meta"],
        "clusters": CLUSTERS,
        "cluster_importance": m["cluster_importance"],
        "feature_importance": m["feature_importance"],
        "targets": m["targets"],
        "outcomes": m["outcomes"],
        "tracking": m.get("tracking", {}),
        "context_features": m.get("context_features", []),
        "seasons": m["seasons"],
        "n_rows": m["n_rows"],
        "train_pairs": m["train_pairs"],
        "trained_at": m.get("trained_at"),
        "config": m["config"],
        "backtest": m.get("backtest"),
        "explained_variance_ratio": m["explained_variance_ratio"],
    }


@app.get("/api/search")
def search(q: str = Query("", min_length=0), limit: int = 12):
    q = q.strip().lower()
    p = S.players
    if not q:
        top = p.sort_values(["latest_season", "max_pa"], ascending=False).head(limit)
    else:
        parts = q.split()
        mask = np.ones(len(p), dtype=bool)
        for part in parts:
            mask &= p["name_ascii"].str.contains(part, regex=False).values | p["name_lc"].str.contains(part, regex=False).values
        hits = p[mask].copy()
        hits["starts"] = hits["name_ascii"].str.startswith(parts[0]) | hits["name_ascii"].str.contains(" " + parts[0], regex=False)
        top = hits.sort_values(["starts", "latest_season", "max_pa"], ascending=False).head(limit)
    return [
        {
            "mlbam_id": int(r.mlbam_id), "name": r.name, "seasons": list(r.seasons),
            "latest_season": int(r.latest_season), "team": r.latest_team if isinstance(r.latest_team, str) else None,
            "career_wrc": _num(r.career_wrc),
        }
        for r in top.itertuples()
    ]


@app.get("/api/players/{mlbam_id}")
def player(mlbam_id: int):
    rows = S.df.index[S.df["mlbam_id"] == mlbam_id]
    if len(rows) == 0:
        raise HTTPException(404, "Unknown player")
    seasons = [_row_payload(int(i), with_next=True) for i in sorted(rows, key=lambda i: S.df.at[i, "season"])]
    return {"mlbam_id": mlbam_id, "name": seasons[-1]["name"], "seasons": seasons}


@app.get("/api/compare/{mlbam_id}/{season}")
def compare(mlbam_id: int, season: int, k: int = 10, min_pa: int = 100, same_player: bool = False):
    i = _player_row(mlbam_id, season)
    target = _row_payload(i)
    # Display comps: any season, any player except self
    shown = S.index.find(i, k=k, candidate_mask=S.show_mask, exclude_same_player=not same_player, min_pa=min_pa)
    comps = []
    for r in shown.itertuples():
        c = _row_payload(int(r.row_idx))
        c["similarity"] = round(float(r.similarity), 1)
        c["distance"] = round(float(r.distance), 4)
        # per-feature profile difference (season-relative z)
        c["z_diff"] = {f: _num(S.Z[int(r.row_idx), j] - S.Z[i, j]) for j, f in enumerate(S.model.features)}
        comps.append(c)
    # Projection comps: only seasons whose next season is known
    kproj = S.model.cfg.k_default
    pool = S.index.find(i, k=kproj, candidate_mask=S.pool_mask, exclude_same_player=True, min_pa=min_pa)
    outcomes = [o for o in S.meta["outcomes"] if f"{o}_next" in S.df.columns]
    proj = project_from_comps(S.df.iloc[i], pool, S.model, outcomes, method="direct")
    proj_comps = [
        {"mlbam_id": int(r.mlbam_id), "name": r.name, "season": int(r.season), "similarity": round(float(r.similarity), 1),
         "next": {o: _num(getattr(r, f"{o}_next", None)) for o in ("wrc_plus", "xwoba")}, "pa_next": _num(r.pa_next)}
        for r in pool.itertuples()
    ]
    return {
        "target": target,
        "comps": comps,
        "projection": {
            "season": season + 1,
            "method": "kernel-weighted mean of the next seasons of the 40 nearest comps",
            "n_comps": int(len(pool)),
            "values": proj,
            "model_direct": target["model_next"],
            "actual": target["next"],
            "comps_used": proj_comps,
        },
    }


HEADSHOT_DIR = PROJECT_ROOT / "data" / "cache" / "headshots"


@app.get("/api/headshot/{mlbam_id}")
def headshot(mlbam_id: int, w: int = 240):
    """Same-origin headshot so the share card can be exported to PNG (cross-origin
    images taint the canvas). Fetched once from MLB's CDN and cached on disk."""
    import urllib.request
    HEADSHOT_DIR.mkdir(parents=True, exist_ok=True)
    w = 480 if w > 240 else 240
    path = HEADSHOT_DIR / f"{mlbam_id}_{w}.jpg"
    if not path.exists():
        url = f"https://img.mlbstatic.com/mlb-photos/image/upload/w_{w},q_auto:best/v1/people/{mlbam_id}/headshot/67/current"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                path.write_bytes(r.read())
        except Exception:  # noqa: BLE001
            raise HTTPException(404, "no headshot")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=604800"})


_EXPLORE_CACHE: List[dict] = []


@app.get("/api/explore")
def explore():
    """Every hitter-season with its best comp, projection, and per-metric percentiles; the client sorts and filters."""
    if not _EXPLORE_CACHE:
        _EXPLORE_CACHE.extend(_explore_rows())
    return _EXPLORE_CACHE


def _explore_rows() -> List[dict]:
    cols =["row", "mlbam_id", "name", "season", "team", "age", "pa", "wrc_plus", "xwoba", "next_wrc", "proj_wrc",
            "similarity", "comp_id", "comp_name", "comp_season", "comp_next_wrc"]
    pcols = [c for c in S.explore.columns if c.startswith("p_")]
    rows = S.explore[cols + pcols].to_dict("records")
    for r in rows:
        pct = {}
        for k in pcols:
            v = _num(r.pop(k))
            if v is not None:
                pct[k[2:]] = int(v)
        r["pct"] = pct
        for k, v in r.items():
            if isinstance(v, (np.floating, float)):
                v = _num(v)
                r[k] = None if v is None else round(v, 3 if k == "xwoba" else 1)
            elif isinstance(v, np.integer):
                r[k] = int(v)
    # raw values for the metrics too, so a filtered table can show the numbers, not just ranks
    vals = S.df[[c for c in pct_candidates() if c in S.df.columns]]
    for r, (_, vr) in zip(rows, vals.iterrows()):
        r["val"] = {k: round(_num(v), 1) for k, v in vr.items() if _num(v) is not None}
    return rows


def pct_candidates() -> List[str]:
    return list(S.model.features) + list(S.meta.get("tracking", {}).keys())


@app.get("/api/leaders/{season}")
def leaders(season: int, sort: str = "wrc_plus", limit: int = 30, min_pa: int = 300):
    sub = S.df[(S.df["season"] == season) & (S.df["pa"] >= min_pa)]
    if sort not in sub.columns:
        raise HTTPException(400, "bad sort column")
    sub = sub.sort_values(sort, ascending=False).head(limit)
    return [_row_payload(int(i), with_next=False) for i in sub.index]


# ----------------------------------------------------------------- frontend
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        file = DIST / path
        if path and file.exists() and file.is_file():
            return FileResponse(file)
        return FileResponse(DIST / "index.html")
