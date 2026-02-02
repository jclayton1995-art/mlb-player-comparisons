#!/usr/bin/env python3
"""One-time script to build the full dataset with all metrics."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
from datetime import datetime

import pandas as pd

from src.data.cache_manager import CacheManager
from src.data.fetcher import DataFetcher
from src.data.merger import DataMerger
from src.data.player_lookup import PlayerRegistry
from src.metrics.pulled_flyball import PulledFlyBallCalculator


def build_dataset(
    start_year: int = 2015,
    end_year: int = 2024,
    min_pa: int = 100,
    calculate_pulled_fb: bool = True,
) -> pd.DataFrame:
    """
    Build the complete dataset with all metrics.

    Args:
        start_year: First year to include
        end_year: Last year to include
        min_pa: Minimum plate appearances
        calculate_pulled_fb: Whether to calculate Pulled FB% (expensive)

    Returns:
        Complete merged dataset
    """
    print(f"Building dataset for {start_year}-{end_year}...")

    cache_manager = CacheManager()
    merger = DataMerger(cache_manager=cache_manager)

    print("Fetching and merging Statcast + FanGraphs data...")
    dataset = merger.build_full_dataset(start_year, end_year, min_pa)

    if dataset.empty:
        print("ERROR: Failed to fetch data. Check your internet connection.")
        return dataset

    print(f"  Found {len(dataset)} player-seasons")

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
                pulled_fb_results.append({
                    "mlbam_id": player_id,
                    "season": year,
                    "pulled_fb_pct": result,
                })

        if pulled_fb_results:
            pulled_fb_df = pd.DataFrame(pulled_fb_results)
            dataset = pd.merge(
                dataset,
                pulled_fb_df,
                on=["mlbam_id", "season"],
                how="left",
            )
            print(f"  Calculated Pulled FB% for {len(pulled_fb_results)} player-seasons")

    output_path = Path("data/processed/full_dataset.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_parquet(output_path, index=False)
    print(f"Dataset saved to {output_path}")

    print("\nDataset summary:")
    print(f"  Total player-seasons: {len(dataset)}")
    print(f"  Years covered: {dataset['season'].min()} - {dataset['season'].max()}")
    print(f"  Columns: {list(dataset.columns)}")

    return dataset


def main():
    parser = argparse.ArgumentParser(
        description="Build MLB player comparison dataset"
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
        help="Minimum plate appearances (default: 100)",
    )
    parser.add_argument(
        "--skip-pulled-fb",
        action="store_true",
        help="Skip Pulled FB% calculation (faster)",
    )

    args = parser.parse_args()

    build_dataset(
        start_year=args.start_year,
        end_year=args.end_year,
        min_pa=args.min_pa,
        calculate_pulled_fb=not args.skip_pulled_fb,
    )


if __name__ == "__main__":
    main()
