#!/usr/bin/env python3
"""Add (or refresh) a single partial season into the existing master parquet files.

Typical use during the 2026 season:
    python scripts/add_partial_season.py --year 2026

The script is idempotent — re-running replaces any existing rows for the target
year. Designed for use mid-season when minimums need to be relaxed compared to
the full-season defaults baked into ``scripts/build_dataset.py``.

The expensive Pulled-FB% and pitcher plate-discipline calculations are OFF by
default (they fetch pitch-by-pitch data per player and can take 30+ minutes for
a full year). Pass --with-pulled-fb / --with-plate-discipline to include them.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

# Make the project root importable when running this file directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.cache_manager import CacheManager
from src.data.merger import DataMerger
from src.data.pitcher_merger import PitcherDataMerger
from src.data.pitch_model_fetcher import PitchModelFetcher
from src.metrics.pulled_flyball import PulledFlyBallCalculator
from src.metrics.pitcher_plate_discipline import PitcherPlateDisciplineCalculator


PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Master parquet files the Streamlit app reads (with fallback names)
BATTER_OUTPUTS = ["batters.parquet", "full_dataset.parquet"]
PITCHER_OUTPUT = "pitchers.parquet"
PITCH_MODEL_OUTPUT = "pitch_models.parquet"


def _resolve_existing(filenames):
    """Return the first existing path from ``filenames`` under PROCESSED_DIR."""
    for name in filenames:
        path = PROCESSED_DIR / name
        if path.exists():
            return path
    return None


def _bust_year_cache(cache: CacheManager, year: int) -> None:
    """Drop any cached entries for the given year so we re-fetch fresh data."""
    patterns = [
        f"merged_season_{year}",
        f"merged_full_{year}_{year}",
        f"pitcher_merged_season_{year}",
        f"pitcher_merged_full_{year}_{year}",
        f"pitch_model_{year}",
    ]
    for key in patterns:
        if cache.exists(key):
            cache.delete(key)
            print(f"  cleared cache key: {key}")


def _replace_year_rows(existing: pd.DataFrame, new_rows: pd.DataFrame, year: int) -> pd.DataFrame:
    """Drop existing rows for ``year`` from ``existing`` and append ``new_rows``."""
    if existing is None or existing.empty:
        return new_rows.copy()
    kept = existing[existing["season"].astype(int) != int(year)].copy()
    return pd.concat([kept, new_rows], ignore_index=True)


def update_batters(year: int, min_pa: int, with_pulled_fb: bool, cache: CacheManager) -> None:
    print(f"\n=== Batters ({year}) ===  min_pa={min_pa}  pulled_fb={with_pulled_fb}")
    _bust_year_cache(cache, year)

    merger = DataMerger(cache_manager=cache)
    new_rows = merger.build_full_dataset(year, year, min_pa)
    if new_rows.empty:
        print("  fetched 0 rows — Baseball Savant/FanGraphs returned nothing. Skipping.")
        return
    print(f"  fetched {len(new_rows)} batter rows")

    if with_pulled_fb:
        print("  calculating Pulled FB% (this is the slow part)...")
        calc = PulledFlyBallCalculator(cache_manager=cache)
        records = []
        total = len(new_rows)
        for i, (_, row) in enumerate(new_rows.iterrows(), start=1):
            if pd.isna(row.get("mlbam_id")):
                continue
            pid = int(row["mlbam_id"])
            val = calc.calculate_for_player_season(pid, year)
            if val is not None:
                records.append({"mlbam_id": pid, "season": year, "pulled_fb_pct": val})
            if i % 25 == 0 or i == total:
                print(f"    {i}/{total}")
        if records:
            pfb = pd.DataFrame(records)
            new_rows = new_rows.merge(pfb, on=["mlbam_id", "season"], how="left")
            print(f"  added Pulled FB% for {len(records)} player-seasons")

    target_path = _resolve_existing(BATTER_OUTPUTS) or PROCESSED_DIR / BATTER_OUTPUTS[0]
    existing = pd.read_parquet(target_path) if target_path.exists() else pd.DataFrame()
    combined = _replace_year_rows(existing, new_rows, year)
    combined.to_parquet(target_path, index=False)
    print(f"  wrote {len(combined)} rows to {target_path.relative_to(PROJECT_ROOT)}")


def update_pitchers(year: int, min_ip: int, with_plate_discipline: bool, cache: CacheManager) -> None:
    print(f"\n=== Pitchers ({year}) ===  min_ip={min_ip}  plate_discipline={with_plate_discipline}")
    _bust_year_cache(cache, year)

    merger = PitcherDataMerger(cache_manager=cache)
    new_rows = merger.build_full_dataset(year, year, min_ip)
    if new_rows.empty:
        print("  fetched 0 rows. Skipping.")
        return
    print(f"  fetched {len(new_rows)} pitcher rows")

    # Backfill FanGraphs for any pitchers missing it
    new_rows = merger.backfill_fangraphs(new_rows, year, year, min_ip)

    if with_plate_discipline:
        print("  calculating plate discipline from raw Statcast (slow)...")
        calc = PitcherPlateDisciplineCalculator(cache_manager=cache)
        seasons = [
            (int(r["mlbam_id"]), year)
            for _, r in new_rows.iterrows()
            if pd.notna(r.get("mlbam_id"))
        ]
        pd_df = calc.calculate_batch(seasons, verbose=True)
        if not pd_df.empty:
            cols = ["zone_pct", "chase_pct", "zone_contact_pct", "whiff_pct"]
            pd_df = pd_df.set_index(["mlbam_id", "season"])
            new_rows = new_rows.set_index(["mlbam_id", "season"])
            for col in cols:
                if col in pd_df.columns:
                    new_rows[col] = pd_df[col].combine_first(
                        new_rows[col] if col in new_rows.columns else pd.Series(dtype=float)
                    )
            new_rows = new_rows.reset_index()
            print(f"  updated plate discipline for {len(pd_df)} pitcher-seasons")

    target_path = PROCESSED_DIR / PITCHER_OUTPUT
    existing = pd.read_parquet(target_path) if target_path.exists() else pd.DataFrame()
    combined = _replace_year_rows(existing, new_rows, year)
    combined.to_parquet(target_path, index=False)
    print(f"  wrote {len(combined)} rows to {target_path.relative_to(PROJECT_ROOT)}")


def update_pitch_models(year: int, min_pitches: int, cache: CacheManager) -> None:
    print(f"\n=== Pitch Models ({year}) ===  min_pitches={min_pitches}")
    _bust_year_cache(cache, year)

    fetcher = PitchModelFetcher(cache_manager=cache)
    new_rows = fetcher.build_pitch_dataset(year, year, min_pitches)
    if new_rows.empty:
        print("  fetched 0 rows. Skipping.")
        return
    print(f"  fetched {len(new_rows)} pitch-type rows ({new_rows['mlbam_id'].nunique()} unique pitchers)")

    target_path = PROCESSED_DIR / PITCH_MODEL_OUTPUT
    existing = pd.read_parquet(target_path) if target_path.exists() else pd.DataFrame()
    combined = _replace_year_rows(existing, new_rows, year)
    combined.to_parquet(target_path, index=False)
    print(f"  wrote {len(combined)} rows to {target_path.relative_to(PROJECT_ROOT)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--year", type=int, default=2026, help="Target season (default: 2026)")
    parser.add_argument("--min-pa", type=int, default=30, help="Minimum PA for batters (partial-season default: 30)")
    parser.add_argument("--min-ip", type=int, default=10, help="Minimum IP for pitchers (partial-season default: 10)")
    parser.add_argument("--min-pitches", type=int, default=30, help="Minimum pitches per pitch-type (partial-season default: 30)")
    parser.add_argument("--skip-batters", action="store_true")
    parser.add_argument("--skip-pitchers", action="store_true")
    parser.add_argument("--skip-pitch-models", action="store_true")
    parser.add_argument(
        "--with-pulled-fb",
        action="store_true",
        help="Run the (slow) Pulled FB%% calculation for batters",
    )
    parser.add_argument(
        "--with-plate-discipline",
        action="store_true",
        help="Run the (slow) raw-Statcast plate-discipline calc for pitchers",
    )
    args = parser.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    cache = CacheManager()

    if not args.skip_batters:
        update_batters(args.year, args.min_pa, args.with_pulled_fb, cache)
    if not args.skip_pitchers:
        update_pitchers(args.year, args.min_ip, args.with_plate_discipline, cache)
    if not args.skip_pitch_models:
        update_pitch_models(args.year, args.min_pitches, cache)

    print("\nDone. Restart the Streamlit app (or wait for its TTL cache) to see the new season.")


if __name__ == "__main__":
    main()
