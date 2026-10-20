"""Bulk pitch-level Statcast: one download per season, then per-hitter metrics in one pass.

Produces, per (batter, season):
    bip             balls in play with hit coordinates
    pull_air_pct    pulled non-ground balls / balls in play  (Savant's "Pulled Air%", 17° pull zone)
    air_pct         non-ground balls / balls in play
    pull_pct_sc     pulled balls / balls in play (any trajectory)
    bat_speed       mean bat speed over competitive swings (bottom 10% of a hitter's swings dropped,
                    which is how Savant defines it)                                         2024+
    swing_length    mean swing length (ft) over the same swings                               2024+
    fast_swing_pct  share of competitive swings at 75+ mph                                    2024+
    swings_tracked  number of tracked swings                                                  2024+

The per-season download is cached as data/cache/statcast_<year>.parquet (only the
columns we need, ~30 MB/season) so re-runs are instant.
"""

from __future__ import annotations

import math
import time
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

HOME_PLATE_X = 125.42
HOME_PLATE_Y = 199.0
PULL_ANGLE = 17.0
KEEP = [
    "game_date", "game_type", "batter", "stand", "type", "events", "description",
    "bb_type", "hc_x", "hc_y", "launch_speed", "launch_angle", "bat_speed", "swing_length",
]
SEASON_WINDOW = {  # regular season, generous; filtered by game_type == 'R' anyway
    2020: ("2020-07-20", "2020-10-01"),
}


def season_window(year: int):
    return SEASON_WINDOW.get(year, (f"{year}-03-18", f"{year}-10-06"))


def _month_chunks(start: str, end: str):
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    cur = s
    while cur <= e:
        nxt = min(cur + timedelta(days=20), e)
        yield cur.isoformat(), nxt.isoformat()
        cur = nxt + timedelta(days=1)


def fetch_season(year: int, cache_dir: Path, force: bool = False, verbose: bool = True) -> pd.DataFrame:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"statcast_{year}.parquet"
    if path.exists() and not force:
        return pd.read_parquet(path)

    from pybaseball import statcast

    start, end = season_window(year)
    frames: List[pd.DataFrame] = []
    t0 = time.time()
    for a, b in _month_chunks(start, end):
        for attempt in range(3):
            try:
                df = statcast(start_dt=a, end_dt=b, verbose=False)
                break
            except Exception as exc:
                if verbose:
                    print(f"    {a}..{b} failed ({exc}); retry {attempt + 1}/3")
                time.sleep(5)
                df = None
        if df is None or df.empty:
            continue
        cols = [c for c in KEEP if c in df.columns]
        df = df[cols]
        if "game_type" in df.columns:
            df = df[df["game_type"] == "R"]
        frames.append(df)
        if verbose:
            print(f"    {year}: through {b}, {sum(len(f) for f in frames):,} pitches, {time.time() - t0:.0f}s")
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=KEEP)
    for c in ["hc_x", "hc_y", "launch_speed", "launch_angle", "bat_speed", "swing_length"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    out.to_parquet(path, index=False)
    return out


def spray_angle(hc_x: np.ndarray, hc_y: np.ndarray) -> np.ndarray:
    """Degrees from straightaway; negative = left field (pull side for RHB)."""
    x = hc_x - HOME_PLATE_X
    y = HOME_PLATE_Y - hc_y
    ang = np.degrees(np.arctan2(x, np.where(y <= 0, np.nan, y)))
    return np.where(y <= 0, 0.0, ang)


def batter_metrics(pitches: pd.DataFrame, season: int, min_bip: int = 20) -> pd.DataFrame:
    if pitches.empty:
        return pd.DataFrame()
    p = pitches

    # ---- batted balls
    bb = p[(p["type"] == "X")].dropna(subset=["hc_x", "hc_y"]).copy()
    ang = spray_angle(bb["hc_x"].values.astype(float), bb["hc_y"].values.astype(float))
    stand = bb["stand"].astype(str).values
    pulled = np.where(stand == "R", ang < -PULL_ANGLE, np.where(stand == "L", ang > PULL_ANGLE, False))
    air = bb["bb_type"].isin(["fly_ball", "line_drive", "popup"]).values
    bb["_pulled"] = pulled
    bb["_air"] = air
    bb["_pull_air"] = pulled & air
    g = bb.groupby("batter")
    out = pd.DataFrame({
        "bip": g.size(),
        "pull_air_pct": g["_pull_air"].mean() * 100,
        "air_pct": g["_air"].mean() * 100,
        "pull_pct_sc": g["_pulled"].mean() * 100,
    })
    out = out[out["bip"] >= min_bip]

    # ---- bat tracking (2024+)
    if "bat_speed" in p.columns and p["bat_speed"].notna().any():
        sw = p.dropna(subset=["bat_speed"]).copy()
        rows = []
        for batter, grp in sw.groupby("batter"):
            bs = grp["bat_speed"].values.astype(float)
            if len(bs) < 25:
                continue
            cut = np.quantile(bs, 0.10)          # competitive swings: drop the slowest 10%
            comp = grp[grp["bat_speed"] >= cut]
            rows.append({
                "batter": batter,
                "bat_speed": float(comp["bat_speed"].mean()),
                "swing_length": float(comp["swing_length"].mean()) if "swing_length" in comp else np.nan,
                "fast_swing_pct": float((comp["bat_speed"] >= 75).mean() * 100),
                "swings_tracked": int(len(comp)),
            })
        if rows:
            bt = pd.DataFrame(rows).set_index("batter")
            out = out.join(bt, how="outer")

    out = out.reset_index().rename(columns={"batter": "mlbam_id", "index": "mlbam_id"})
    out["mlbam_id"] = out["mlbam_id"].astype(int)
    out["season"] = season
    return out


def build_all(years: List[int], cache_dir: Path, force_years: Optional[List[int]] = None, verbose: bool = True) -> pd.DataFrame:
    frames = []
    for y in years:
        t0 = time.time()
        force = bool(force_years and y in force_years)
        if verbose:
            cached = (cache_dir / f"statcast_{y}.parquet").exists() and not force
            print(f"  {y}: {'cached' if cached else 'downloading (several minutes)'}")
        pitches = fetch_season(y, cache_dir, force=force, verbose=verbose)
        m = batter_metrics(pitches, y)
        if verbose:
            print(f"  {y}: {len(pitches):,} pitches -> {len(m)} hitters, {time.time() - t0:.0f}s")
        frames.append(m)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def merge_into(target_path: Path, metrics: pd.DataFrame) -> None:
    df = pd.read_parquet(target_path)
    tracking = {"bat_speed", "swing_length", "fast_swing_pct", "swings_tracked"}
    cols = [c for c in metrics.columns if c not in ("mlbam_id", "season")]
    own = [c for c in cols if c not in tracking]
    df = df.drop(columns=[c for c in own if c in df.columns], errors="ignore")
    df["mlbam_id"] = df["mlbam_id"].astype(int)
    df["season"] = df["season"].astype(int)
    merged = df.merge(metrics, on=["mlbam_id", "season"], how="left", suffixes=("", "_sc"))
    # FanGraphs-published bat tracking (if present) wins; bulk values only fill gaps
    for c in tracking:
        if f"{c}_sc" in merged.columns:
            merged[c] = merged[c].combine_first(merged[f"{c}_sc"]) if c in merged.columns else merged[f"{c}_sc"]
            merged = merged.drop(columns=[f"{c}_sc"])
    merged.to_parquet(target_path, index=False)
    hit = merged["pull_air_pct"].notna().sum() if "pull_air_pct" in merged else 0
    print(f"  pull-air% attached to {hit}/{len(merged)} rows; bat speed on {merged['bat_speed'].notna().sum() if 'bat_speed' in merged else 0}")
