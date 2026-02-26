"""Fetch pitcher data from pybaseball APIs with caching."""

from typing import Optional
import pandas as pd
from pybaseball import (
    statcast_pitcher_exitvelo_barrels,
    statcast_pitcher_expected_stats,
    pitching_stats,
)

from .cache_manager import CacheManager


class PitcherDataFetcher:
    """Fetches pitcher data from various sources with caching."""

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.cache = cache_manager or CacheManager()

    def _parse_name_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """Parse 'last_name, first_name' column into separate columns."""
        if df.empty:
            return df

        name_col = "last_name, first_name"
        if name_col in df.columns:
            df = df.copy()
            names = df[name_col].str.split(", ", n=1, expand=True)
            df["last_name"] = names[0] if 0 in names.columns else ""
            df["first_name"] = names[1] if 1 in names.columns else ""
            df = df.drop(columns=[name_col])
        return df

    def get_pitcher_exit_velo_barrels(
        self, year: int, min_bf: int = 100
    ) -> pd.DataFrame:
        """Fetch exit velocity and barrel data allowed for a season."""
        cache_key = f"statcast_pitcher_ev_barrels_{year}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            data = statcast_pitcher_exitvelo_barrels(year, minBBE=min_bf)
            if data is not None and not data.empty:
                data = self._parse_name_column(data)
                self.cache.set(cache_key, data)
            return data if data is not None else pd.DataFrame()
        except Exception as e:
            print(f"Error fetching pitcher exit velo/barrels for {year}: {e}")
            return pd.DataFrame()

    def get_pitcher_expected_stats(self, year: int, min_bf: int = 100) -> pd.DataFrame:
        """Fetch expected stats (xERA, xwOBA against) for a season."""
        cache_key = f"statcast_pitcher_expected_{year}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            data = statcast_pitcher_expected_stats(year, minPA=min_bf)
            if data is not None and not data.empty:
                data = self._parse_name_column(data)
                self.cache.set(cache_key, data)
            return data if data is not None else pd.DataFrame()
        except Exception as e:
            print(f"Error fetching pitcher expected stats for {year}: {e}")
            return pd.DataFrame()

    def get_fangraphs_pitching(
        self, start_year: int, end_year: int, min_ip: int = 30
    ) -> pd.DataFrame:
        """Fetch FanGraphs pitching stats for a range of seasons."""
        cache_key = f"fangraphs_pitching_{start_year}_{end_year}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            data = pitching_stats(start_year, end_year, qual=min_ip)
            if data is not None and not data.empty:
                self.cache.set(cache_key, data)
            return data if data is not None else pd.DataFrame()
        except Exception as e:
            print(f"Error fetching FanGraphs pitching stats: {e}")
            return pd.DataFrame()

    def get_all_statcast_for_year(self, year: int, min_bf: int = 100) -> pd.DataFrame:
        """Fetch and merge all Statcast pitcher data for a year."""
        ev_data = self.get_pitcher_exit_velo_barrels(year, min_bf)
        expected_data = self.get_pitcher_expected_stats(year, min_bf)

        if ev_data.empty and expected_data.empty:
            return pd.DataFrame()

        if ev_data.empty:
            return expected_data
        if expected_data.empty:
            return ev_data

        merged = pd.merge(
            ev_data,
            expected_data,
            on=["player_id"],
            how="outer",
            suffixes=("", "_expected"),
        )

        # Consolidate name columns (prefer ev_data names)
        if "last_name" in merged.columns and "last_name_expected" in merged.columns:
            merged["last_name"] = merged["last_name"].fillna(
                merged["last_name_expected"]
            )
            merged = merged.drop(columns=["last_name_expected"])
        if "first_name" in merged.columns and "first_name_expected" in merged.columns:
            merged["first_name"] = merged["first_name"].fillna(
                merged["first_name_expected"]
            )
            merged = merged.drop(columns=["first_name_expected"])

        return merged
