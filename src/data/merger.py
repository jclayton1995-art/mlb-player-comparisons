"""Merge Statcast and FanGraphs data by player ID."""

from typing import Optional, List
import pandas as pd

from .fetcher import DataFetcher
from .player_lookup import PlayerRegistry
from .cache_manager import CacheManager


class DataMerger:
    """Merges data from Statcast and FanGraphs sources."""

    def __init__(
        self,
        fetcher: Optional[DataFetcher] = None,
        registry: Optional[PlayerRegistry] = None,
        cache_manager: Optional[CacheManager] = None,
    ):
        self.cache = cache_manager or CacheManager()
        self.fetcher = fetcher or DataFetcher(self.cache)
        self.registry = registry or PlayerRegistry(self.cache)

    def build_season_dataset(
        self, year: int, min_pa: int = 100
    ) -> pd.DataFrame:
        """Build a merged dataset for a single season."""
        cache_key = f"merged_season_{year}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        statcast_data = self.fetcher.get_all_statcast_for_year(year, min_pa)
        fangraphs_data = self.fetcher.get_fangraphs_batting(year, year, min_pa)

        if statcast_data.empty:
            return pd.DataFrame()

        statcast_data["season"] = year

        if fangraphs_data.empty:
            return statcast_data

        mlbam_ids = statcast_data["player_id"].dropna().astype(int).tolist()
        player_info = self.registry.lookup_by_mlbam(mlbam_ids)

        if player_info.empty:
            return statcast_data

        statcast_with_fg = pd.merge(
            statcast_data,
            player_info[["key_mlbam", "key_fangraphs"]],
            left_on="player_id",
            right_on="key_mlbam",
            how="left",
        )

        fg_cols_to_keep = [
            "IDfg", "Season", "O-Swing%", "Contact%", "Z-Contact%", "SwStr%", "K%", "BB%", "GB%", "FB%", "Pull%",
            "G", "PA", "AVG", "OBP", "SLG", "OPS", "wRC+"
        ]
        fg_cols_available = [c for c in fg_cols_to_keep if c in fangraphs_data.columns]

        if not fg_cols_available:
            return statcast_data

        fg_subset = fangraphs_data[fg_cols_available].copy()

        # Add name columns to fg_subset for name-based fallback matching
        if "Name" in fangraphs_data.columns:
            fg_subset["fg_name"] = fangraphs_data["Name"].str.lower().str.strip()

        merged = pd.merge(
            statcast_with_fg,
            fg_subset,
            left_on=["key_fangraphs", "season"],
            right_on=["IDfg", "Season"],
            how="left",
        )

        # Fallback: try name-based merge for players without FanGraphs ID
        if "fg_name" in fg_subset.columns:
            missing_fg = merged["IDfg"].isna() | (merged["key_fangraphs"] == -1)
            if missing_fg.any():
                # Create full name for matching
                merged["full_name_lower"] = (merged["first_name"].fillna("") + " " + merged["last_name"].fillna("")).str.lower().str.strip()

                # For rows missing FanGraphs data, try to match by name and season
                for idx in merged[missing_fg].index:
                    player_name = merged.loc[idx, "full_name_lower"]
                    player_season = merged.loc[idx, "season"]

                    # Find match in FanGraphs data
                    fg_match = fg_subset[(fg_subset["fg_name"] == player_name) & (fg_subset["Season"] == player_season)]
                    if not fg_match.empty:
                        for col in fg_cols_available:
                            if col not in ["IDfg", "Season"] and col in fg_match.columns:
                                merged.loc[idx, col] = fg_match.iloc[0][col]

                merged = merged.drop(columns=["full_name_lower"], errors="ignore")

        # Clean up temporary columns
        if "fg_name" in merged.columns:
            merged = merged.drop(columns=["fg_name"], errors="ignore")

        merged = self._standardize_columns(merged)

        self.cache.set(cache_key, merged)
        return merged

    def build_full_dataset(
        self, start_year: int = 2015, end_year: int = 2024, min_pa: int = 100
    ) -> pd.DataFrame:
        """Build a merged dataset for multiple seasons."""
        cache_key = f"merged_full_{start_year}_{end_year}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        all_seasons = []
        for year in range(start_year, end_year + 1):
            season_data = self.build_season_dataset(year, min_pa)
            if not season_data.empty:
                all_seasons.append(season_data)

        if not all_seasons:
            return pd.DataFrame()

        full_dataset = pd.concat(all_seasons, ignore_index=True)
        self.cache.set(cache_key, full_dataset)
        return full_dataset

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names for consistency."""
        column_mapping = {
            "player_id": "mlbam_id",
            "avg_hit_speed": "exit_velocity",
            "max_hit_speed": "max_exit_velocity",
            "avg_hit_angle": "launch_angle",
            "brl_percent": "barrel_pct",
            "ev95percent": "hard_hit_pct",
            "O-Swing%": "chase_rate",
            "Z-Contact%": "zone_contact_pct",
            "SwStr%": "swstr_pct",
            "K%": "k_pct",
            "BB%": "bb_pct",
            "GB%": "gb_pct",
            "FB%": "fb_pct",
            "Pull%": "pull_pct",
            "est_woba": "xwoba",
            "est_ba": "xba",
            "est_slg": "xslg",
        }

        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

        # Calculate Whiff% from Contact% (Whiff% = 1 - Contact%)
        if "Contact%" in df.columns:
            df["whiff_pct"] = 1 - df["Contact%"]
            df = df.drop(columns=["Contact%"])

        # Convert FanGraphs decimal percentages to actual percentages
        pct_columns = ["chase_rate", "zone_contact_pct", "whiff_pct", "swstr_pct", "k_pct", "bb_pct", "gb_pct", "fb_pct", "pull_pct"]
        for col in pct_columns:
            if col in df.columns:
                # Only convert if values appear to be decimals (< 1)
                if df[col].max() < 1:
                    df[col] = df[col] * 100

        core_columns = [
            "mlbam_id", "first_name", "last_name", "season",
            "exit_velocity", "max_exit_velocity", "launch_angle",
            "barrel_pct", "hard_hit_pct",
            "chase_rate", "zone_contact_pct", "whiff_pct", "swstr_pct", "k_pct", "bb_pct",
            "gb_pct", "fb_pct", "pull_pct",
            "xwoba", "xba", "xslg",
            "G", "PA", "AVG", "OBP", "SLG", "OPS", "wRC+",
        ]

        available_columns = [c for c in core_columns if c in df.columns]
        extra_columns = [c for c in df.columns if c not in core_columns]

        return df[available_columns + extra_columns]
