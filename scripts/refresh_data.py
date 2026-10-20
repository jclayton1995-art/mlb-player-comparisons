#!/usr/bin/env python3
"""Refresh the master datasets with one or more seasons and enrich with FanGraphs context.

Run this on a machine with internet access (pybaseball pulls from Baseball Savant
and FanGraphs):

    python scripts/refresh_data.py                 # refreshes 2025 + 2026 (default)
    python scripts/refresh_data.py --years 2026    # just 2026
    python scripts/refresh_data.py --enrich-only   # skip fetching, only add Age/ISO/etc.

What it does
------------
1. For each requested year, re-pulls batters, pitchers and pitch-type rows and
   replaces that year's rows in data/processed/*.parquet (idempotent).
2. Enriches EVERY season in the batter and pitcher files with FanGraphs context
   columns that the comparison model needs and that the original pipeline did
   not keep: Age, ISO, BABIP, wOBA, WAR, HR, SB, BsR, Spd, LD%, IFFB%, HR/FB,
   Swing%, Z-Swing%, O-Contact%, Zone%, F-Strike%, CStr%, CSW%, Hard%, Oppo%.
3. Downloads pitch-level Statcast once per season (cached in data/cache/) and computes
   Pulled Air% for every hitter-season plus bat tracking (bat speed, swing length,
   fast-swing%) for 2024+.
4. Writes data/processed/refresh_log.txt with a summary.

Expensive per-player Statcast calculations (Pulled FB%, pitcher plate discipline
from raw pitches) are off by default; pass --with-pulled-fb / --with-plate-discipline.
"""

import argparse
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from src.data.cache_manager import CacheManager  # noqa: E402
from src.data import statcast_bulk  # noqa: E402
from add_partial_season import (  # noqa: E402
    PROCESSED_DIR,
    BATTER_OUTPUTS,
    PITCHER_OUTPUT,
    _resolve_existing,
    update_batters,
    update_pitchers,
    update_pitch_models,
)

FG_BATTING_CONTEXT = [
    "Age", "Team", "Bats", "ISO", "BABIP", "wOBA", "WAR", "HR", "SB", "BsR", "Spd",
    "LD%", "IFFB%", "HR/FB", "Swing%", "Z-Swing%", "O-Contact%", "Zone%",
    "F-Strike%", "CStr%", "CSW%", "Hard%", "Oppo%", "Cent%",
    # Statcast bat tracking (2024+), as published by FanGraphs
    "AvgBatSpeed", "FastSwing%", "SwingLength", "SquaredUpContact%", "SquaredUpSwing%",
    "BlastContact%", "BlastSwing%", "Swords", "CompetitiveSwings", "AttackAngle",
    "AttackDirection", "IdealAttackAngle%",
]
FG_PITCHING_CONTEXT = [
    "Age", "Team", "SIERA", "K-BB%", "HR/FB", "LD%", "FB%", "Swing%", "Z-Swing%",
    "O-Contact%", "F-Strike%", "CStr%", "CSW%", "Hard%", "vFA (pi)", "Stuff+",
    "Location+", "Pitching+",
]
# FanGraphs columns that come as decimals (0.231) and should be stored as percents (23.1)
DECIMAL_PCT_COLS = {
    "LD%", "IFFB%", "HR/FB", "Swing%", "Z-Swing%", "O-Contact%", "Zone%",
    "F-Strike%", "CStr%", "CSW%", "Hard%", "Oppo%", "Cent%", "K-BB%", "FB%",
    "FastSwing%", "SquaredUpContact%", "SquaredUpSwing%", "BlastContact%", "BlastSwing%", "IdealAttackAngle%",
}
RENAME = {
    "Age": "age", "Team": "team", "ISO": "iso", "BABIP": "babip", "wOBA": "woba_fg",
    "WAR": "war", "HR": "hr", "SB": "sb", "BsR": "bsr", "Spd": "spd",
    "LD%": "ld_pct", "IFFB%": "iffb_pct", "HR/FB": "hr_fb_pct", "Swing%": "swing_pct",
    "Z-Swing%": "zone_swing_pct", "O-Contact%": "o_contact_pct", "Zone%": "zone_pct_seen",
    "F-Strike%": "f_strike_pct", "CStr%": "cstr_pct", "CSW%": "csw_pct",
    "Hard%": "hard_pct_fg", "Oppo%": "oppo_pct", "Cent%": "cent_pct",
    "SIERA": "siera", "K-BB%": "k_bb_pct_fg", "FB%": "fb_pct", "vFA (pi)": "fb_velo",
    "Stuff+": "stuff_plus_fg", "Location+": "location_plus", "Pitching+": "pitching_plus",
    "Bats": "bats", "AvgBatSpeed": "bat_speed", "FastSwing%": "fast_swing_pct", "SwingLength": "swing_length",
    "SquaredUpContact%": "squared_up_pct", "SquaredUpSwing%": "squared_up_swing_pct",
    "BlastContact%": "blast_pct", "BlastSwing%": "blast_swing_pct", "Swords": "swords",
    "CompetitiveSwings": "competitive_swings", "AttackAngle": "attack_angle",
    "AttackDirection": "attack_direction", "IdealAttackAngle%": "ideal_attack_angle_pct",
}


def _norm_name(s) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(s.lower().replace(".", "").split())


def _fetch_fg(kind: str, start: int, end: int, qual: int) -> pd.DataFrame:
    from src.data.fangraphs_api import batting_stats, pitching_stats

    frames = []
    for year in range(start, end + 1):
        for attempt in range(3):
            try:
                fn = batting_stats if kind == "bat" else pitching_stats
                df = fn(year, year, qual=qual)
                if df is not None and not df.empty:
                    frames.append(df)
                print(f"  FanGraphs {kind} {year}: {0 if df is None else len(df)} rows")
                break
            except Exception as exc:  # network hiccups are common
                print(f"  FanGraphs {kind} {year} failed ({exc}); retry {attempt + 1}/3")
                time.sleep(3)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def enrich(target_path: Path, kind: str, qual: int) -> None:
    """Add FanGraphs context columns to every row of the given parquet file."""
    if not target_path.exists():
        print(f"  {target_path.name} missing, skipping enrichment")
        return
    df = pd.read_parquet(target_path)
    years = sorted(int(y) for y in df["season"].dropna().unique())
    print(f"\n=== Enriching {target_path.name} ({len(df)} rows, {years[0]}-{years[-1]}) ===")

    fg = _fetch_fg(kind, years[0], years[-1], qual)
    if fg.empty:
        print("  no FanGraphs data returned; skipping")
        return

    wanted = FG_BATTING_CONTEXT if kind == "bat" else FG_PITCHING_CONTEXT
    cols = [c for c in wanted if c in fg.columns]
    id_cols = ["IDfg", "Season", "Name"] + (["key_mlbam"] if "key_mlbam" in fg.columns else [])
    ctx = fg[id_cols + cols].copy()
    for c in cols:
        if c in DECIMAL_PCT_COLS and pd.api.types.is_numeric_dtype(ctx[c]):
            if ctx[c].abs().max() <= 1.5:
                ctx[c] = ctx[c] * 100
    ctx = ctx.rename(columns={c: RENAME.get(c, c) for c in cols})
    new_cols = [RENAME.get(c, c) for c in cols]
    ctx["_name"] = ctx["Name"].map(_norm_name)
    ctx["Season"] = ctx["Season"].astype(int)

    # Drop any previous enrichment so re-runs stay clean
    df = df.drop(columns=[c for c in new_cols if c in df.columns], errors="ignore")
    df["_name"] = (df["first_name"].fillna("") + " " + df["last_name"].fillna("")).map(_norm_name)
    df["_season"] = df["season"].astype(int)

    # 0) match on MLBAM id (the API returns it) — exact, no name trouble
    df["_mlbam"] = pd.to_numeric(df["mlbam_id"], errors="coerce").astype("Int64")
    if "key_mlbam" in ctx.columns:
        by_mlbam = ctx.drop(columns=["Name", "_name", "IDfg"]).dropna(subset=["key_mlbam"]).drop_duplicates(["key_mlbam", "Season"])
        df = df.merge(by_mlbam, how="left", left_on=["_mlbam", "_season"], right_on=["key_mlbam", "Season"], suffixes=("", "_ctx"))
        df = df.drop(columns=[c for c in ["key_mlbam_ctx", "Season_ctx"] if c in df.columns])
        matched0 = df["age"].notna().sum() if "age" in df.columns else 0
        print(f"  matched by MLBAM id: {matched0}/{len(df)}")
        ctx = ctx.drop(columns=["key_mlbam"])
    # 1) match on FanGraphs id for whatever is left
    df["_fgid"] = df["IDfg"] if "IDfg" in df.columns else pd.NA
    if "key_fangraphs" in df.columns:
        df["_fgid"] = df["_fgid"].fillna(df["key_fangraphs"].where(df["key_fangraphs"] > 0))
    by_id = ctx.drop(columns=["Name", "_name"]).drop_duplicates(["IDfg", "Season"])
    need = df["age"].isna() if "age" in df.columns else pd.Series(True, index=df.index)
    if need.any():
        fill = df.loc[need, ["_fgid", "_season"]].merge(by_id, how="left", left_on=["_fgid", "_season"], right_on=["IDfg", "Season"])
        fill.index = df.index[need]
        for c in new_cols:
            if c in fill.columns:
                if c not in df.columns:
                    df[c] = pd.NA
                df.loc[need, c] = fill[c].values
    merged = df
    # 2) fallback: match on normalized name
    by_name = ctx.drop(columns=["IDfg", "Name"]).drop_duplicates(["_name", "Season"])
    miss = merged["age"].isna() if "age" in merged.columns else pd.Series(False, index=merged.index)
    if miss.any():
        fallback = merged.loc[miss, ["_name", "_season"]].merge(
            by_name, how="left", left_on=["_name", "_season"], right_on=["_name", "Season"]
        )
        fallback.index = merged.index[miss]
        for c in new_cols:
            if c in fallback.columns:
                merged.loc[miss, c] = fallback[c].values
    matched = merged["age"].notna().sum() if "age" in merged.columns else 0
    print(f"  matched context for {matched}/{len(merged)} rows")

    drop = [c for c in ["_name", "_season", "_fgid", "_mlbam", "IDfg_ctx", "Season_ctx"] if c in merged.columns]
    merged = merged.drop(columns=drop)
    merged.to_parquet(target_path, index=False)
    print(f"  wrote {target_path.relative_to(PROJECT_ROOT)}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--years", type=int, nargs="+", default=[2025, 2026])
    p.add_argument("--min-pa", type=int, default=50)
    p.add_argument("--min-ip", type=int, default=20)
    p.add_argument("--min-pitches", type=int, default=50)
    p.add_argument("--skip-batters", action="store_true")
    p.add_argument("--skip-pitchers", action="store_true")
    p.add_argument("--skip-pitch-models", action="store_true")
    p.add_argument("--with-pulled-fb", action="store_true")
    p.add_argument("--with-plate-discipline", action="store_true")
    p.add_argument("--enrich-only", action="store_true", help="Skip fetching seasons; only run enrichment")
    p.add_argument("--skip-statcast", action="store_true", help="Skip the bulk pitch-level Statcast stage")
    p.add_argument("--statcast-only", action="store_true", help="Only run the bulk Statcast stage")
    args = p.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    cache = CacheManager(str(PROJECT_ROOT / "data" / "cache"))
    t0 = time.time()

    if not args.enrich_only and not args.statcast_only:
        for year in args.years:
            if not args.skip_batters:
                update_batters(year, args.min_pa, args.with_pulled_fb, cache)
            if not args.skip_pitchers:
                update_pitchers(year, args.min_ip, args.with_plate_discipline, cache)
            if not args.skip_pitch_models:
                update_pitch_models(year, args.min_pitches, cache)

    batter_path = _resolve_existing(BATTER_OUTPUTS)
    if not args.statcast_only:
        if batter_path and not args.skip_batters:
            enrich(batter_path, "bat", qual=args.min_pa)
        if not args.skip_pitchers:
            enrich(PROCESSED_DIR / PITCHER_OUTPUT, "pit", qual=args.min_ip)

    if batter_path and not args.skip_statcast and not args.skip_batters:
        bat = pd.read_parquet(batter_path)
        years = sorted(int(y) for y in bat["season"].dropna().unique())
        print(f"\n=== Bulk Statcast: pull-air% + bat tracking for {years[0]}-{years[-1]} ===")
        print("  (first run downloads every season; later runs use data/cache/statcast_<year>.parquet)")
        metrics = statcast_bulk.build_all(years, PROJECT_ROOT / "data" / "cache", force_years=args.years)
        if not metrics.empty:
            statcast_bulk.merge_into(batter_path, metrics)

    lines = [f"refresh finished in {time.time() - t0:.0f}s"]
    for name in [batter_path.name if batter_path else "batters.parquet", PITCHER_OUTPUT, "pitch_models.parquet"]:
        path = PROCESSED_DIR / name
        if path.exists():
            d = pd.read_parquet(path)
            counts = d.groupby(d["season"].astype(int)).size().to_dict()
            lines.append(f"{name}: {len(d)} rows, {len(d.columns)} cols, by season {counts}")
    (PROCESSED_DIR / "refresh_log.txt").write_text("\n".join(lines))
    print("\n" + "\n".join(lines))
    print("\nNext: python scripts/train_model.py   (rebuilds the comparison model on the new data)")


if __name__ == "__main__":
    main()
