#!/usr/bin/env python3
"""Append a single (partial) season to the existing processed parquet files.

Use this mid-season to bring 2026 (or any in-progress year) into the dataset
without rebuilding the full 2015+ history. Thresholds default to roughly half
the full-season build defaults; override on the command line if needed.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from scripts.build_dataset import (
    build_batter_dataset,
    build_pitcher_dataset,
    build_pitch_model_dataset,
)

PROCESSED_DIR = Path("data/processed")


def _resolve_batter_path() -> Path:
    """Prefer batters.parquet; fall back to legacy full_dataset.parquet."""
    new_path = PROCESSED_DIR / "batters.parquet"
    legacy_path = PROCESSED_DIR / "full_dataset.parquet"
    if new_path.exists():
        return new_path
    if legacy_path.exists():
        return legacy_path
    return new_path


def _snapshot(path: Path) -> pd.DataFrame | None:
    """Read the existing parquet into memory before any builder runs.

    build_*_dataset writes its single-season output to the same target file,
    which would shadow our multi-year history if we read it back afterward.
    """
    if path.exists():
        return pd.read_parquet(path)
    return None


def _merge_season_into(
    target_path: Path,
    season_df: pd.DataFrame,
    year: int,
    existing: pd.DataFrame | None,
) -> None:
    if season_df.empty:
        print(f"  No rows produced for {year} -> {target_path.name}; skipping")
        return

    if existing is not None:
        before = len(existing)
        existing = existing[existing["season"] != year]
        removed = before - len(existing)
        if removed:
            print(f"  Replaced {removed} existing {year} rows in {target_path.name}")
        combined = pd.concat([existing, season_df], ignore_index=True)
    else:
        combined = season_df

    target_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(target_path, index=False)
    print(f"  Wrote {len(combined)} total rows to {target_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True, help="Season to add")
    parser.add_argument("--min-pa", type=int, default=50, help="Min PA for batters (default: 50)")
    parser.add_argument("--min-ip", type=int, default=15, help="Min IP for pitchers (default: 15)")
    parser.add_argument(
        "--min-pitches",
        type=int,
        default=25,
        help="Min pitches of a type for the pitch model (default: 25)",
    )
    parser.add_argument(
        "--skip-pulled-fb",
        action="store_true",
        help="Skip Pulled FB%% calculation (faster)",
    )
    parser.add_argument(
        "--skip-plate-discipline",
        action="store_true",
        help="Skip raw Statcast plate discipline calculation for pitchers (faster)",
    )
    parser.add_argument(
        "--skip",
        nargs="*",
        choices=["batter", "pitcher", "pitch_model"],
        default=[],
        help="Datasets to skip",
    )
    args = parser.parse_args()

    year = args.year
    print(f"=== Adding partial season {year} ===\n")

    # Snapshot ALL targets up front — every build_*_dataset writes its
    # single-season output to the same file we'd otherwise read back.
    batter_target = _resolve_batter_path()
    pitcher_target = PROCESSED_DIR / "pitchers.parquet"
    pitch_model_target = PROCESSED_DIR / "pitch_models.parquet"
    batter_snapshot = _snapshot(batter_target)
    pitcher_snapshot = _snapshot(pitcher_target)
    pitch_model_snapshot = _snapshot(pitch_model_target)

    if "batter" not in args.skip:
        print(f"[1/3] Building batter data for {year} (min PA={args.min_pa})")
        batters = build_batter_dataset(
            start_year=year,
            end_year=year,
            min_pa=args.min_pa,
            calculate_pulled_fb=not args.skip_pulled_fb,
        )
        if batter_target.name == "full_dataset.parquet":
            # build_batter_dataset just wrote a single-season batters.parquet
            # alongside the legacy file; remove it so the app keeps reading
            # the merged full_dataset.parquet.
            (PROCESSED_DIR / "batters.parquet").unlink(missing_ok=True)
        _merge_season_into(batter_target, batters, year, batter_snapshot)
        print()

    if "pitcher" not in args.skip:
        print(f"[2/3] Building pitcher data for {year} (min IP={args.min_ip})")
        pitchers = build_pitcher_dataset(
            start_year=year,
            end_year=year,
            min_ip=args.min_ip,
            calculate_plate_discipline=not args.skip_plate_discipline,
        )
        _merge_season_into(pitcher_target, pitchers, year, pitcher_snapshot)
        print()

    if "pitch_model" not in args.skip:
        print(f"[3/3] Building pitch model data for {year} (min pitches={args.min_pitches})")
        pitch_models = build_pitch_model_dataset(
            start_year=year,
            end_year=year,
            min_pitches=args.min_pitches,
        )
        _merge_season_into(pitch_model_target, pitch_models, year, pitch_model_snapshot)
        print()

    print(f"=== Done. {year} merged into processed parquet files. ===")


if __name__ == "__main__":
    main()
