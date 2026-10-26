"""Turn the raw merged parquet into the canonical batter frame the model and API use.

The raw file mixes Statcast leaderboard rows (one per player with >=N batted balls),
FanGraphs rows, and pitchers who batted. This module keeps only real hitter-seasons,
fixes known scaling bugs, and names everything consistently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

RAW_CANDIDATES = ["batters.parquet", "full_dataset.parquet"]

# ---- Feature catalogue -------------------------------------------------------
# Each feature: display label, skill cluster, whether higher is "better" for
# percentile coloring, and a display format. Only features present in the data
# with enough coverage are actually used by the model (see FeatureSpec).
FEATURES: Dict[str, dict] = {
    # Contact quality
    "exit_velocity":  dict(label="Avg exit velo", cluster="power", higher_better=True,  fmt="{:.1f}", unit="mph"),
    "ev50":           dict(label="EV50",           cluster="power", higher_better=True,  fmt="{:.1f}", unit="mph"),
    "max_exit_velocity": dict(label="Max exit velo", cluster="power", higher_better=True, fmt="{:.1f}", unit="mph"),
    "hard_hit_pct":   dict(label="Hard-hit%",      cluster="power", higher_better=True,  fmt="{:.1f}", unit="%"),
    "barrel_pct":     dict(label="Barrel% (BBE)",  cluster="power", higher_better=True,  fmt="{:.1f}", unit="%"),
    "brl_pa":         dict(label="Barrel% (PA)",   cluster="power", higher_better=True,  fmt="{:.1f}", unit="%"),
    # Batted-ball shape
    "launch_angle":   dict(label="Avg launch angle", cluster="shape", higher_better=None, fmt="{:.1f}", unit="°"),
    "anglesweetspotpercent": dict(label="Sweet-spot%", cluster="shape", higher_better=True, fmt="{:.1f}", unit="%"),
    "gb_pct":         dict(label="Ground-ball%",   cluster="shape", higher_better=None,  fmt="{:.1f}", unit="%"),
    "ld_pct":         dict(label="Line-drive%",    cluster="shape", higher_better=True,  fmt="{:.1f}", unit="%"),
    "pull_pct":       dict(label="Pull%",          cluster="shape", higher_better=None,  fmt="{:.1f}", unit="%"),
    "pull_air_pct":   dict(label="Pulled air%",    cluster="shape", higher_better=True,  fmt="{:.1f}", unit="%"),
    "oppo_pct":       dict(label="Oppo%",          cluster="shape", higher_better=None,  fmt="{:.1f}", unit="%"),
    # Approach / contact skill
    "chase_rate":     dict(label="Chase%",         cluster="approach", higher_better=False, fmt="{:.1f}", unit="%"),
    "zone_swing_pct": dict(label="Zone-swing%",    cluster="approach", higher_better=None,  fmt="{:.1f}", unit="%"),
    "zone_contact_pct": dict(label="Zone-contact%", cluster="approach", higher_better=True, fmt="{:.1f}", unit="%"),
    # default=False: small denominator, noisy, and redundant with whiff%/zone-contact%; it took the top
    # ridge weight under whitening but removing it left the backtest unchanged (21.10 vs 21.14 wRC+ RMSE).
    "o_contact_pct":  dict(label="Chase-contact%", cluster="approach", higher_better=True,  fmt="{:.1f}", unit="%", default=False),
    "whiff_pct":      dict(label="Whiff%",         cluster="approach", higher_better=False, fmt="{:.1f}", unit="%"),
    "swstr_pct":      dict(label="SwStr%",         cluster="approach", higher_better=False, fmt="{:.1f}", unit="%"),
    "k_pct":          dict(label="K%",             cluster="approach", higher_better=False, fmt="{:.1f}", unit="%"),
    "bb_pct":         dict(label="BB%",            cluster="approach", higher_better=True,  fmt="{:.1f}", unit="%"),
    # Context
    "age":            dict(label="Age",            cluster="context", higher_better=None,  fmt="{:.0f}", unit=""),
    # Track record: career-to-date wRC+ above/below what xwOBA implies (see add_result_gap).
    # default=False until the backtest says otherwise.
    "result_gap":     dict(label="Results vs. contact quality", cluster="track", higher_better=True, fmt="{:+.0f}", unit="", default=False),
    # Statcast bat tracking (2024+). default=False: not used by the main model (too few
    # seasons); available to the modern-era experiment via an explicit feature list.
    "bat_speed":              dict(label="Bat speed",       cluster="swing", higher_better=True,  fmt="{:.1f}", unit="mph", default=False),
    "fast_swing_pct":         dict(label="Fast-swing%",     cluster="swing", higher_better=True,  fmt="{:.0f}", unit="%",   default=False),
    "squared_up_pct":         dict(label="Squared-up%",     cluster="swing", higher_better=True,  fmt="{:.0f}", unit="%",   default=False),
    "blast_pct":              dict(label="Blast%",          cluster="swing", higher_better=True,  fmt="{:.0f}", unit="%",   default=False),
    "swing_length":           dict(label="Swing length",    cluster="swing", higher_better=None,  fmt="{:.1f}", unit="ft",  default=False),
    "attack_angle":           dict(label="Attack angle",    cluster="swing", higher_better=None,  fmt="{:.0f}", unit="°",   default=False),
    "ideal_attack_angle_pct": dict(label="Ideal attack angle%", cluster="swing", higher_better=True, fmt="{:.0f}", unit="%", default=False),
}

# Sample-size shrinkage: each metric's season z-score is multiplied by n / (n + k),
# where n is the hitter's sample (PA or batted-ball events) and k is roughly the
# sample at which the metric is half signal / half noise (Carleton-style
# stabilization points, rounded). Small samples get pulled toward league average.
SHRINK: Dict[str, tuple] = {
    # (sample column, k)
    "exit_velocity": ("bbe", 40), "ev50": ("bbe", 40), "max_exit_velocity": ("bbe", 60),
    "hard_hit_pct": ("bbe", 50), "barrel_pct": ("bbe", 50), "brl_pa": ("pa", 200),
    "launch_angle": ("bbe", 50), "anglesweetspotpercent": ("bbe", 60), "gb_pct": ("bbe", 80),
    "ld_pct": ("bbe", 200), "pull_pct": ("bbe", 80), "oppo_pct": ("bbe", 80), "pull_air_pct": ("bbe", 100),
    "chase_rate": ("pa", 60), "zone_swing_pct": ("pa", 50), "zone_contact_pct": ("pa", 60),
    "o_contact_pct": ("pa", 80), "whiff_pct": ("pa", 50), "swstr_pct": ("pa", 50),
    "k_pct": ("pa", 60), "bb_pct": ("pa", 120),
    "bat_speed": ("pa", 30), "fast_swing_pct": ("pa", 40), "squared_up_pct": ("pa", 60),
    "blast_pct": ("pa", 60), "swing_length": ("pa", 30), "attack_angle": ("pa", 40),
    "ideal_attack_angle_pct": ("pa", 60),
}

CLUSTERS = {
    "power":    "Contact quality",
    "shape":    "Batted-ball shape",
    "approach": "Approach & contact",
    "swing":    "Swing (bat tracking)",
    "context":  "Context",
    "track":    "Track record",
}

# Bat tracking (Statcast, 2024+). Shown on the card; not a similarity input until there
# are enough seasons of it to compare across eras.
TRACKING: Dict[str, dict] = {
    "bat_speed":              dict(label="Bat speed",         fmt="{:.1f}", unit="mph", higher_better=True),
    "fast_swing_pct":         dict(label="Fast-swing%",       fmt="{:.0f}", unit="%",   higher_better=True),
    "squared_up_pct":         dict(label="Squared-up%",       fmt="{:.0f}", unit="%",   higher_better=True),
    "blast_pct":              dict(label="Blast%",            fmt="{:.0f}", unit="%",   higher_better=True),
    "swing_length":           dict(label="Swing length",      fmt="{:.1f}", unit="ft",  higher_better=None),
    "attack_angle":           dict(label="Attack angle",      fmt="{:.0f}", unit="°",   higher_better=None),
    "ideal_attack_angle_pct": dict(label="Ideal attack angle%", fmt="{:.0f}", unit="%", higher_better=True),
    "swords":                 dict(label="Swords",            fmt="{:.0f}", unit="",    higher_better=None),
}

# Outcome columns (results). Never used as similarity inputs; used as projection targets.
OUTCOMES: Dict[str, dict] = {
    "xwoba":    dict(label="xwOBA",  fmt="{:.3f}", higher_better=True),
    "wrc_plus": dict(label="wRC+",   fmt="{:.0f}", higher_better=True),
    "woba":     dict(label="wOBA",   fmt="{:.3f}", higher_better=True),
    "iso":      dict(label="ISO",    fmt="{:.3f}", higher_better=True),
    "babip":    dict(label="BABIP",  fmt="{:.3f}", higher_better=True),
    "avg":      dict(label="AVG",    fmt="{:.3f}", higher_better=True),
    "obp":      dict(label="OBP",    fmt="{:.3f}", higher_better=True),
    "slg":      dict(label="SLG",    fmt="{:.3f}", higher_better=True),
    "ops":      dict(label="OPS",    fmt="{:.3f}", higher_better=True),
    "hr":       dict(label="HR",     fmt="{:.0f}", higher_better=True),
    "sb":       dict(label="SB",     fmt="{:.0f}", higher_better=True),
    "war":      dict(label="WAR",    fmt="{:.1f}", higher_better=True),
    "xba":      dict(label="xBA",    fmt="{:.3f}", higher_better=True),
    "xslg":     dict(label="xSLG",   fmt="{:.3f}", higher_better=True),
}

# Columns where a value below 2 is impossible for a real hitter-season, so a value
# <= 1.5 must be a 0-1 decimal that escaped the merger's conversion.
PCT_COLS_0_100 = [
    "chase_rate", "zone_contact_pct", "whiff_pct", "k_pct", "gb_pct", "fb_pct", "pull_pct",
    "zone_swing_pct", "swing_pct", "o_contact_pct", "ld_pct", "oppo_pct", "anglesweetspotpercent",
]


def find_raw(processed_dir: Path) -> Path:
    for name in RAW_CANDIDATES:
        p = processed_dir / name
        if p.exists():
            return p
    raise FileNotFoundError(f"No batter parquet in {processed_dir}")


def _fix_scale(s: pd.Series) -> pd.Series:
    """Some rows carry 0-1 decimals where 0-100 percents are expected."""
    s = pd.to_numeric(s, errors="coerce")
    return s.where(~(s.abs() <= 1.5), s * 100)


def load_batters(processed_dir: Path, min_pa: int = 50) -> pd.DataFrame:
    raw = pd.read_parquet(find_raw(processed_dir))
    df = raw.copy()

    rename = {
        "wRC+": "wrc_plus", "AVG": "avg", "OBP": "obp", "SLG": "slg", "OPS": "ops",
        "PA": "pa_fg", "G": "g",
    }
    # Savant and FanGraphs both carry slg/woba/etc.; prefer FanGraphs, avoid duplicate names
    clash = [v for k, v in rename.items() if k in df.columns and v in df.columns]
    df = df.drop(columns=clash)
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    df = df.loc[:, ~df.columns.duplicated()]

    # Plate appearances: FanGraphs PA where present, else Savant pa
    pa = pd.to_numeric(df.get("pa_fg"), errors="coerce")
    if "pa" in df.columns:
        pa = pa.fillna(pd.to_numeric(df["pa"], errors="coerce"))
    df["pa"] = pa
    df["bbe"] = pd.to_numeric(df.get("attempts"), errors="coerce") if "attempts" in df.columns else np.nan

    keep = df["exit_velocity"].notna() & df["pa"].notna() & (df["pa"] >= min_pa)
    # Must have the core plate-discipline block too
    keep &= df["k_pct"].notna() & df["chase_rate"].notna()
    df = df[keep].copy()

    for c in PCT_COLS_0_100:
        if c in df.columns:
            df[c] = _fix_scale(df[c])

    df["season"] = df["season"].astype(int)
    df["mlbam_id"] = df["mlbam_id"].astype(int)
    df["name"] = (df["first_name"].fillna("") + " " + df["last_name"].fillna("")).str.strip()
    if "age" in df.columns:
        df["age"] = pd.to_numeric(df["age"], errors="coerce")
    if "team" not in df.columns:
        df["team"] = None
    if "bats" not in df.columns:
        df["bats"] = None

    # wOBA from Savant if FanGraphs' not present
    if "woba_fg" in df.columns:
        df["woba"] = pd.to_numeric(df["woba_fg"], errors="coerce").fillna(df.get("woba"))

    cols = ["mlbam_id", "name", "first_name", "last_name", "season", "team", "bats", "pa", "bbe", "g", "fb_pct", "swing_pct"]
    cols += [c for c in FEATURES if c in df.columns]
    cols += [c for c in OUTCOMES if c in df.columns]
    cols += [c for c in TRACKING if c in df.columns]
    cols = list(dict.fromkeys(c for c in cols if c in df.columns))   # dedupe (tracking metrics appear in two catalogues)
    df = df[cols].drop_duplicates(["mlbam_id", "season"])
    df = df.sort_values(["mlbam_id", "season"]).reset_index(drop=True)

    # Next-season link (for training + "what happened next" in the UI)
    link_cols = [c for c in list(OUTCOMES) + ["k_pct", "bb_pct"] if c in df.columns]
    nxt = df[["mlbam_id", "season", "pa"] + link_cols].copy()
    nxt["season"] = nxt["season"] - 1
    nxt = nxt.rename(columns={c: f"{c}_next" for c in nxt.columns if c not in ("mlbam_id", "season")})
    df = df.merge(nxt, on=["mlbam_id", "season"], how="left")
    prev = df[["mlbam_id", "season", "pa"] + link_cols].copy()
    prev["season"] = prev["season"] + 1
    prev = prev.rename(columns={c: f"{c}_prev" for c in prev.columns if c not in ("mlbam_id", "season")})
    df = df.merge(prev, on=["mlbam_id", "season"], how="left")
    df = add_result_gap(df)
    return df


def add_result_gap(df: pd.DataFrame, k_pa: float = 1000.0, min_pa: int = 100) -> pd.DataFrame:
    """Track record of results vs. contact quality.

    Each season, fit wRC+ on xwOBA across qualified hitters; a hitter's residual is how far
    his production ran above/below what his batted-ball quality implies (Kwan, Arraez: far
    above; many sluggers who sell out: below). `result_gap` is his PA-weighted career
    residual through the current season only (no look-ahead), shrunk toward 0 by
    N / (N + k_pa) so one lucky half-season doesn't count as a trait.
    """
    out = df.copy()
    out["_resid"] = np.nan
    for season, grp in out.groupby("season"):
        q = grp[(grp["pa"] >= min_pa) & grp["wrc_plus"].notna() & grp["xwoba"].notna()]
        if len(q) < 30:
            continue
        b, a = np.polyfit(q["xwoba"].astype(float), q["wrc_plus"].astype(float), 1)
        idx = grp.index[grp["wrc_plus"].notna() & grp["xwoba"].notna()]
        out.loc[idx, "_resid"] = out.loc[idx, "wrc_plus"].astype(float) - (a + b * out.loc[idx, "xwoba"].astype(float))
    out = out.sort_values(["mlbam_id", "season"])
    w = out["pa"].astype(float).where(out["_resid"].notna(), 0.0)
    num = (out["_resid"].fillna(0.0) * w).groupby(out["mlbam_id"]).cumsum()
    den = w.groupby(out["mlbam_id"]).cumsum()
    out["result_gap"] = (num / den.replace(0, np.nan)) * (den / (den + k_pa))
    out["result_gap_pa"] = den
    return out.drop(columns="_resid").sort_values(["mlbam_id", "season"]).reset_index(drop=True)


def add_percentiles(df: pd.DataFrame, cols: List[str], min_pa: int = 100) -> pd.DataFrame:
    """Within-season percentile (0-100) for each feature/outcome, oriented so that
    higher = better when the metric has a direction; raw rank otherwise."""
    out = df.copy()
    spec = {**FEATURES, **OUTCOMES, **TRACKING}
    for c in cols:
        if c not in out.columns:
            continue
        out[c] = pd.to_numeric(out[c], errors="coerce").astype(float)
        pct = pd.Series(np.nan, index=out.index)
        for season, grp in out.groupby("season"):
            base = grp[grp["pa"] >= min_pa][c].dropna()
            if len(base) < 20:
                base = grp[c].dropna()
            if base.empty:
                continue
            vals = grp[c].fillna(-np.inf)
            ranks = np.searchsorted(np.sort(base.values), vals.values, side="left") / len(base) * 100
            pct.loc[grp.index] = ranks
        hb = spec.get(c, {}).get("higher_better", True)
        if hb is False:
            pct = 100 - pct
        out[f"{c}_pct"] = pct.round(1).where(out[c].notna())
    return out
