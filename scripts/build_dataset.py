#!/usr/bin/env python3
"""One-time script to build the full dataset with all metrics."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

import pandas as pd

from src.data.cache_manager import CacheManager
from src.data.fetcher import DataFetcher
from src.data.merger import DataMerger
from src.data.pitcher_fetcher import PitcherDataFetcher
from src.data.pitcher_merger import PitcherDataMerger
from src.data.player_lookup import PlayerRegistry
from src.metrics.pulled_flyball import PulledFlyBallCalculator
from src.metrics.pitcher_plate_discipline import PitcherPlateDisciplineCalculator
from src.data.pitch_model_fetcher import PitchModelFetcher


def build_batter_dataset(
    start_year: int = 2015,
    end_year: int = 2024,
    min_pa: int = 100,
    calculate_pulled_fb: bool = True,
) -> pd.DataFrame:
    """
    Build the complete batter dataset with all metrics.

    Args:
        start_year: First year to include
        end_year: Last year to include
        min_pa: Minimum plate appearances
        calculate_pulled_fb: Whether to calculate Pulled FB% (expensive)

    Returns:
        Complete merged batter dataset
    """
    print(f"Building batter dataset for {start_year}-{end_year}...")

    cache_manager = CacheManager()
    merger = DataMerger(cache_manager=cache_manager)

    print("Fetching and merging Statcast + FanGraphs batting data...")
    dataset = merger.build_full_dataset(start_year, end_year, min_pa)

    if dataset.empty:
        print("ERROR: Failed to fetch batter data. Check your internet connection.")
        return dataset

    print(f"  Found {len(dataset)} batter player-seasons")

    if calculate_pulled_fb:
        print("Calculating Pulled FB% for all player-seasons...")
        print("  (This may take a while - ~5-10 seconds per player)")

        calculator = PulledFlyBallCalculator(cache_manager=cache_manager)

        player_seasons = [
            (int(row["mlbam_id"]), int(row["season"]))
            for _, row in dataset.iterrows()
            if pd.notna(row.get("mlbam_id"))
        ]

        total = len(player_seasons)
        pulled_fb_results = []

        for i, (player_id, year) in enumerate(player_seasons):
            if (i + 1) % 50 == 0 or i == 0:
                print(f"  Processing {i + 1}/{total}...")

            result = calculator.calculate_for_player_season(player_id, year)
            if result is not None:
                pulled_fb_results.append(
                    {
                        "mlbam_id": player_id,
                        "season": year,
                        "pulled_fb_pct": result,
                    }
                )

        if pulled_fb_results:
            pulled_fb_df = pd.DataFrame(pulled_fb_results)
            dataset = pd.merge(
                dataset,
                pulled_fb_df,
                on=["mlbam_id", "season"],
                how="left",
            )
            print(f"  Calculated Pulled FB% for {len(pulled_fb_results)} player-seasons")

    output_path = Path("data/processed/batters.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_parquet(output_path, index=False)
    print(f"Batter dataset saved to {output_path}")

    print("\nBatter dataset summary:")
    print(f"  Total player-seasons: {len(dataset)}")
    print(f"  Years covered: {dataset['season'].min()} - {dataset['season'].max()}")
    print(f"  Columns: {list(dataset.columns)}")

    return dataset


def build_pitcher_dataset(
    start_year: int = 2015,
    end_year: int = 2024,
    min_ip: int = 30,
    calculate_plate_discipline: bool = True,
) -> pd.DataFrame:
    """
    Build the complete pitcher dataset with all metrics.

    Args:
        start_year: First year to include
        end_year: Last year to include
        min_ip: Minimum innings pitched
        calculate_plate_discipline: Whether to calc plate discipline from raw Statcast

    Returns:
        Complete merged pitcher dataset
    """
    print(f"Building pitcher dataset for {start_year}-{end_year}...")

    cache_manager = CacheManager()
    merger = PitcherDataMerger(cache_manager=cache_manager)

    print("Fetching and merging Statcast + FanGraphs pitching data...")
    dataset = merger.build_full_dataset(start_year, end_year, min_ip)

    if dataset.empty:
        print("ERROR: Failed to fetch pitcher data. Check your internet connection.")
        return dataset

    print(f"  Found {len(dataset)} pitcher player-seasons")

    # Backfill FanGraphs data for players missing it (e.g. from Savant scraper)
    dataset = merger.backfill_fangraphs(dataset, start_year, end_year, min_ip)

    if calculate_plate_discipline:
        print("Calculating plate discipline from raw Statcast pitch data...")
        print("  (This will take a while - fetching pitch-by-pitch data)")

        calculator = PitcherPlateDisciplineCalculator(cache_manager=cache_manager)

        player_seasons = [
            (int(row["mlbam_id"]), int(row["season"]))
            for _, row in dataset.iterrows()
            if pd.notna(row.get("mlbam_id"))
        ]

        plate_disc_df = calculator.calculate_batch(player_seasons, verbose=True)

        if not plate_disc_df.empty:
            # Update with raw Statcast values where available,
            # keeping FanGraphs values as fallback
            plate_disc_cols = ['zone_pct', 'chase_pct', 'zone_contact_pct', 'whiff_pct']
            plate_disc_df = plate_disc_df.set_index(["mlbam_id", "season"])
            dataset = dataset.set_index(["mlbam_id", "season"])

            for col in plate_disc_cols:
                if col in plate_disc_df.columns:
                    dataset[col] = plate_disc_df[col].combine_first(
                        dataset[col] if col in dataset.columns else pd.Series(dtype=float)
                    )

            dataset = dataset.reset_index()
            print(f"  Calculated plate discipline for {len(plate_disc_df)} pitcher-seasons")
            fg_fallback = dataset['zone_pct'].notna().sum() - len(plate_disc_df)
            if fg_fallback > 0:
                print(f"  Using FanGraphs (sc) fallback for {fg_fallback} pitcher-seasons")

    output_path = Path("data/processed/pitchers.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_parquet(output_path, index=False)
    print(f"Pitcher dataset saved to {output_path}")

    print("\nPitcher dataset summary:")
    print(f"  Total player-seasons: {len(dataset)}")
    print(f"  Years covered: {dataset['season'].min()} - {dataset['season'].max()}")
    print(f"  Columns: {list(dataset.columns)}")

    return dataset


def build_pitch_model_dataset(
    start_year: int = 2015,
    end_year: int = 2024,
    min_pitches: int = 50,
) -> pd.DataFrame:
    """
    Build the pitch model dataset (one row per pitcher-season-pitch_type).

    Args:
        start_year: First year to include
        end_year: Last year to include
        min_pitches: Minimum pitches thrown of a type to include

    Returns:
        Complete pitch model dataset
    """
    print(f"Building pitch model dataset for {start_year}-{end_year}...")

    cache_manager = CacheManager()
    fetcher = PitchModelFetcher(cache_manager=cache_manager)

    dataset = fetcher.build_pitch_dataset(start_year, end_year, min_pitches)

    if dataset.empty:
        print("ERROR: Failed to build pitch model data.")
        return dataset

    output_path = Path("data/processed/pitch_models.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_parquet(output_path, index=False)
    print(f"Pitch model dataset saved to {output_path}")

    print("\nPitch model dataset summary:")
    print(f"  Total rows (pitcher-season-pitch_type): {len(dataset)}")
    print(f"  Unique pitchers: {dataset['mlbam_id'].nunique()}")
    print(f"  Years covered: {dataset['season'].min()} - {dataset['season'].max()}")
    print(f"  Pitch types: {sorted(dataset['pitch_type'].unique())}")
    print(f"  Columns: {list(dataset.columns)}")

    return dataset


def main():
    parser = argparse.ArgumentParser(
        description="Build MLB player comparison dataset"
    )
    parser.add_argument(
        "--type",
        type=str,
        choices=["batter", "pitcher", "pitch_model", "both", "all"],
        default="both",
        help="Type of dataset to build: batter, pitcher, pitch_model, both, or all (default: both)",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2015,
        help="First year to include (default: 2015)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2024,
        help="Last year to include (default: 2024)",
    )
    parser.add_argument(
        "--min-pa",
        type=int,
        default=100,
        help="Minimum plate appearances for batters (default: 100)",
    )
    parser.add_argument(
        "--min-ip",
        type=int,
        default=30,
        help="Minimum innings pitched for pitchers (default: 30)",
    )
    parser.add_argument(
        "--skip-pulled-fb",
        action="store_true",
        help="Skip Pulled FB%% calculation for batters (faster)",
    )
    parser.add_argument(
        "--skip-plate-discipline",
        action="store_true",
        help="Skip raw Statcast plate discipline calculation for pitchers (faster)",
    )

    args = parser.parse_args()

    if args.type in ("batter", "both", "all"):
        build_batter_dataset(
            start_year=args.start_year,
            end_year=args.end_year,
            min_pa=args.min_pa,
            calculate_pulled_fb=not args.skip_pulled_fb,
        )

    if args.type in ("pitcher", "both", "all"):
        build_pitcher_dataset(
            start_year=args.start_year,
            end_year=args.end_year,
            min_ip=args.min_ip,
            calculate_plate_discipline=not args.skip_plate_discipline,
        )

    if args.type in ("pitch_model", "all"):
        # Pitch model starts from 2020 by default (Stuff+ availability)
        pitch_model_start = max(args.start_year, 2020)
        build_pitch_model_dataset(
            start_year=pitch_model_start,
            end_year=args.end_year,
        )


if __name__ == "__main__":
    main()
