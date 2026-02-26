"""Merge Statcast and FanGraphs pitcher data by player ID."""

from typing import Optional
import numpy as np
import pandas as pd

from .pitcher_fetcher import PitcherDataFetcher
from .player_lookup import PlayerRegistry
from .cache_manager import CacheManager


class PitcherDataMerger:
    """Merges pitcher data from Statcast and FanGraphs sources."""

    def __init__(
        self,
        fetcher: Optional[PitcherDataFetcher] = None,
        registry: Optional[PlayerRegistry] = None,
        cache_manager: Optional[CacheManager] = None,
    ):
        self.cache = cache_manager or CacheManager()
        self.fetcher = fetcher or PitcherDataFetcher(self.cache)
        self.registry = registry or PlayerRegistry(self.cache)

    def build_season_dataset(self, year: int, min_ip: int = 30) -> pd.DataFrame:
        """Build a merged pitcher dataset for a single season."""
        cache_key = f"merged_pitcher_season_{year}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        # Use a low BBE threshold for Statcast to capture call-ups and late arrivals.
        # FanGraphs min_ip handles the actual roster filter.
        min_bf = 50

        statcast_data = self.fetcher.get_all_statcast_for_year(year, min_bf)
        fangraphs_data = self.fetcher.get_fangraphs_pitching(year, year, min_ip)

        if statcast_data.empty:
            return pd.DataFrame()

        statcast_data["season"] = year

        if fangraphs_data.empty:
            result = self._standardize_columns(statcast_data)
            result = self._add_arm_angles(result, year)
            return result

        mlbam_ids = statcast_data["player_id"].dropna().astype(int).tolist()
        player_info = self.registry.lookup_by_mlbam(mlbam_ids)

        if player_info.empty:
            return self._standardize_columns(statcast_data)

        statcast_with_fg = pd.merge(
            statcast_data,
            player_info[["key_mlbam", "key_fangraphs"]],
            left_on="player_id",
            right_on="key_mlbam",
            how="left",
        )

        fg_cols_to_keep = [
            "IDfg",
            "Season",
            "G",
            "GS",
            "IP",
            "W",
            "L",
            "ERA",
            "WHIP",
            "FIP",
            "xFIP",
            "WAR",
            "K%",
            "BB%",
            "K-BB%",
            "GB%",
            "LOB%",
            "BABIP",
            "O-Swing% (sc)",  # Statcast version (Chase%)
            "SwStr%",
            "Swing% (sc)",
            "Zone% (sc)",  # Statcast version
            "Z-Contact% (sc)",  # Statcast version
            "Stuff+",
            "SO",
            "BB",
        ]
        fg_cols_available = [c for c in fg_cols_to_keep if c in fangraphs_data.columns]

        if not fg_cols_available:
            return self._standardize_columns(statcast_data)

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
                merged["full_name_lower"] = (
                    merged["first_name"].fillna("")
                    + " "
                    + merged["last_name"].fillna("")
                ).str.lower().str.strip()

                # For rows missing FanGraphs data, try to match by name and season
                for idx in merged[missing_fg].index:
                    player_name = merged.loc[idx, "full_name_lower"]
                    player_season = merged.loc[idx, "season"]

                    # Find match in FanGraphs data (exact full name)
                    fg_match = fg_subset[
                        (fg_subset["fg_name"] == player_name)
                        & (fg_subset["Season"] == player_season)
                    ]

                    # Fallback: match by last name only (handles Cam vs Cameron etc.)
                    if fg_match.empty:
                        last_name = merged.loc[idx, "last_name"]
                        if pd.notna(last_name):
                            last_lower = last_name.lower().strip()
                            fg_match = fg_subset[
                                (fg_subset["fg_name"].str.endswith(f" {last_lower}"))
                                & (fg_subset["Season"] == player_season)
                            ]

                    if not fg_match.empty:
                        for col in fg_cols_available:
                            if col not in ["IDfg", "Season"] and col in fg_match.columns:
                                merged.loc[idx, col] = fg_match.iloc[0][col]

                merged = merged.drop(columns=["full_name_lower"], errors="ignore")

        # Clean up temporary columns
        if "fg_name" in merged.columns:
            merged = merged.drop(columns=["fg_name"], errors="ignore")

        merged = self._standardize_columns(merged)

        # Calculate arm angle from cached pitch-level data
        merged = self._add_arm_angles(merged, year)

        self.cache.set(cache_key, merged)
        return merged

    def backfill_fangraphs(
        self, dataset: pd.DataFrame, start_year: int, end_year: int, min_ip: int = 30
    ) -> pd.DataFrame:
        """Fill missing FanGraphs data for players added from non-Statcast sources.

        Some players (e.g. from Savant scraper) enter the dataset without FanGraphs
        data because they weren't in the initial Statcast pull. This method fetches
        FanGraphs data and fills it in by last-name fallback.
        """
        fg_cols = [
            "G", "GS", "IP", "W", "L", "ERA", "WHIP", "FIP", "WAR",
            "K%", "BB%", "K-BB%", "GB%", "LOB%", "BABIP", "Stuff+", "SO", "BB",
            "xFIP",
        ]

        # Identify rows missing FG data (no G column populated)
        if "G" not in dataset.columns:
            return dataset
        missing_mask = dataset["G"].isna()
        if not missing_mask.any():
            return dataset

        filled = 0
        for year in range(start_year, end_year + 1):
            year_missing = dataset[missing_mask & (dataset["season"] == year)]
            if year_missing.empty:
                continue

            fg_data = self.fetcher.get_fangraphs_pitching(year, year, min_ip)
            if fg_data.empty or "Name" not in fg_data.columns:
                continue

            fg_data = fg_data[fg_data["Season"] == year].copy()
            fg_data["fg_name"] = fg_data["Name"].str.lower().str.strip()

            for idx in year_missing.index:
                last_name = dataset.loc[idx, "last_name"]
                if pd.isna(last_name):
                    continue
                last_lower = last_name.lower().strip()

                fg_match = fg_data[fg_data["fg_name"].str.endswith(f" {last_lower}")]
                if fg_match.empty:
                    continue

                row = fg_match.iloc[0]
                col_map = {
                    "G": "G", "GS": "GS", "IP": "IP", "W": "W", "L": "L",
                    "SO": "K", "BB": "BB",
                    "ERA": "ERA", "WHIP": "WHIP", "FIP": "FIP", "WAR": "WAR",
                    "xFIP": "xfip", "K%": "k_pct", "BB%": "bb_pct",
                    "K-BB%": "k_bb_pct", "GB%": "gb_pct", "LOB%": "lob_pct",
                    "BABIP": "babip", "Stuff+": "stuff_plus",
                }
                # FanGraphs returns pct columns as decimals (0.276 = 27.6%)
                pct_fg_cols = {"K%", "BB%", "K-BB%", "GB%", "LOB%"}
                for fg_col, ds_col in col_map.items():
                    if fg_col in row.index and pd.notna(row[fg_col]) and ds_col in dataset.columns:
                        val = row[fg_col]
                        if fg_col in pct_fg_cols and abs(val) < 1:
                            val = val * 100
                        dataset.loc[idx, ds_col] = val
                filled += 1

        if filled > 0:
            print(f"  Backfilled FanGraphs data for {filled} pitcher-seasons via name match")
        return dataset

    def build_full_dataset(
        self, start_year: int = 2015, end_year: int = 2024, min_ip: int = 30
    ) -> pd.DataFrame:
        """Build a merged pitcher dataset for multiple seasons."""
        cache_key = f"merged_pitcher_full_{start_year}_{end_year}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        all_seasons = []
        for year in range(start_year, end_year + 1):
            season_data = self.build_season_dataset(year, min_ip)
            if not season_data.empty:
                all_seasons.append(season_data)

        if not all_seasons:
            return pd.DataFrame()

        full_dataset = pd.concat(all_seasons, ignore_index=True)
        self.cache.set(cache_key, full_dataset)
        return full_dataset

    def _add_arm_angles(self, df: pd.DataFrame, year: int) -> pd.DataFrame:
        """Add average arm angle per pitcher from cached pitch-level data."""
        if df.empty or "mlbam_id" not in df.columns:
            return df

        arm_angles = []
        for mlbam_id in df["mlbam_id"].dropna().unique():
            cache_key = f"statcast_pitcher_pitches_{int(mlbam_id)}_{year}"
            pitch_data = self.cache.get(cache_key)
            if pitch_data is None or pitch_data.empty:
                continue
            if "arm_angle" not in pitch_data.columns:
                continue
            avg_angle = pitch_data["arm_angle"].dropna().mean()
            if not np.isnan(avg_angle):
                arm_angles.append({"mlbam_id": int(mlbam_id), "arm_angle": round(avg_angle, 1)})

        if arm_angles:
            angle_df = pd.DataFrame(arm_angles)
            df = pd.merge(df, angle_df, on="mlbam_id", how="left")

        return df

    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names for consistency."""
        column_mapping = {
            "player_id": "mlbam_id",
            # Statcast exit velo/barrels columns (pitcher perspective)
            "brl_percent": "barrel_pct_against",
            "ev95percent": "hard_hit_pct_against",
            # Statcast expected stats
            "xera": "xera",  # Already correct name
            "xwoba": "xwoba_against",
            # FanGraphs pitching columns
            "K%": "k_pct",
            "BB%": "bb_pct",
            "K-BB%": "k_bb_pct",
            "GB%": "gb_pct",
            "xFIP": "xfip",
            "LOB%": "lob_pct",
            "BABIP": "babip",
            "SO": "K",
            "O-Swing% (sc)": "chase_pct",
            "Zone% (sc)": "zone_pct",
            "Z-Contact% (sc)": "zone_contact_pct",
            "Stuff+": "stuff_plus",
        }

        df = df.rename(
            columns={k: v for k, v in column_mapping.items() if k in df.columns}
        )

        # Calculate Whiff% = SwStr% / Swing% (swinging strikes per swing, not per pitch)
        if "SwStr%" in df.columns and "Swing% (sc)" in df.columns:
            mask = df["Swing% (sc)"] > 0
            df.loc[mask, "whiff_pct"] = df.loc[mask, "SwStr%"] / df.loc[mask, "Swing% (sc)"] * 100
            df = df.drop(columns=["SwStr%", "Swing% (sc)"], errors="ignore")
        elif "SwStr%" in df.columns:
            # Fallback: use SwStr% directly (less accurate)
            df = df.rename(columns={"SwStr%": "whiff_pct"})

        # Convert FanGraphs decimal percentages to actual percentages
        pct_columns = [
            "k_pct",
            "bb_pct",
            "k_bb_pct",
            "gb_pct",
            "lob_pct",
            "chase_pct",
            "zone_pct",
            "zone_contact_pct",
        ]
        for col in pct_columns:
            if col in df.columns:
                # Only convert if values appear to be decimals (< 1)
                if df[col].max() < 1:
                    df[col] = df[col] * 100

        # BABIP is typically expressed as a decimal (like batting average)
        # Keep it as-is

        core_columns = [
            "mlbam_id",
            "first_name",
            "last_name",
            "season",
            # Stuff metrics
            "k_pct",
            "whiff_pct",
            "chase_pct",
            "stuff_plus",
            # Control metrics
            "bb_pct",
            "zone_pct",
            # Results metrics
            "k_bb_pct",
            "xfip",
            "xera",
            "babip",
            "lob_pct",
            # Contact quality metrics
            "barrel_pct_against",
            "hard_hit_pct_against",
            "zone_contact_pct",
            # Style metrics
            "gb_pct",
            # Volume/results
            "G",
            "GS",
            "IP",
            "W",
            "L",
            "K",
            "BB",
            "ERA",
            "WHIP",
            "FIP",
            "WAR",
            "xwoba_against",
            "arm_angle",
        ]

        available_columns = [c for c in core_columns if c in df.columns]
        extra_columns = [c for c in df.columns if c not in core_columns]

        return df[available_columns + extra_columns]
