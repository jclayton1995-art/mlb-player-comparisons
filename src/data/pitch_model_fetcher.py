"""Fetch and aggregate pitch-level data for the Pitch Model comparison."""

import signal
from typing import Optional
import numpy as np
import pandas as pd
from pybaseball import statcast_pitcher

from .cache_manager import CacheManager
from .pitcher_fetcher import PitcherDataFetcher
from .pitcher_merger import PitcherDataMerger
from .player_lookup import PlayerRegistry


# Statcast pitch_type code → human-readable name
PITCH_TYPE_NAMES = {
    "FF": "4-Seam Fastball",
    "SI": "Sinker",
    "FC": "Cutter",
    "SL": "Slider",
    "ST": "Sweeper",
    "CU": "Curveball",
    "KC": "Knuckle Curve",
    "CH": "Changeup",
    "FS": "Splitter",
    "KN": "Knuckleball",
    "SV": "Slurve",
}

# Statcast pitch_type → FanGraphs Stuff+ column name
PITCH_TYPE_TO_STUFF_PLUS = {
    "FF": "Stf+ FA",
    "SI": "Stf+ SI",
    "SL": "Stf+ SL",
    "CH": "Stf+ CH",
    "CU": "Stf+ CU",
    "FC": "Stf+ FC",
    "FS": "Stf+ FS",
    "ST": "Stf+ SL",  # Sweeper uses slider Stuff+
    "KC": "Stf+ KC",
}

# Swing descriptions for plate discipline calculations
SWING_EVENTS = [
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "hit_into_play",
    "foul_bunt",
    "missed_bunt",
]

WHIFF_EVENTS = [
    "swinging_strike",
    "swinging_strike_blocked",
]

IN_ZONE = [1, 2, 3, 4, 5, 6, 7, 8, 9]
OUT_ZONE = [11, 12, 13, 14]

MIN_PITCHES = 50


class PitchModelFetcher:
    """Fetches and aggregates pitch-level data for pitch model comparisons."""

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.cache = cache_manager or CacheManager()
        self.registry = PlayerRegistry(self.cache)

    def build_pitch_dataset(
        self,
        start_year: int = 2015,
        end_year: int = 2024,
        min_pitches: int = MIN_PITCHES,
    ) -> pd.DataFrame:
        """
        Build the pitch model dataset: one row per (pitcher, season, pitch_type).

        Args:
            start_year: First season to include
            end_year: Last season to include
            min_pitches: Minimum pitches thrown of a type to include

        Returns:
            DataFrame with aggregated per-pitch-type metrics
        """
        # First, get the pitcher roster from the pitcher merger dataset
        merger = PitcherDataMerger(cache_manager=self.cache)
        pitcher_dataset = merger.build_full_dataset(start_year, end_year, min_ip=30)

        if pitcher_dataset.empty:
            print("ERROR: No pitcher data available.")
            return pd.DataFrame()

        # Also fetch FanGraphs data for per-pitch Stuff+
        fetcher = PitcherDataFetcher(self.cache)
        fg_stuff_plus = self._fetch_fangraphs_stuff_plus(fetcher, start_year, end_year)

        # Build MLBAM → FanGraphs ID mapping from pitcher dataset
        # (the merger already resolved these via player registry)
        self._mlbam_to_fg = {}
        if "key_fangraphs" in pitcher_dataset.columns:
            for _, row in pitcher_dataset.iterrows():
                mlbam = row.get("mlbam_id")
                fg = row.get("key_fangraphs")
                if pd.notna(mlbam) and pd.notna(fg) and int(fg) > 0:
                    self._mlbam_to_fg[int(mlbam)] = int(fg)
            print(f"  FanGraphs ID crosswalk: {len(self._mlbam_to_fg)} pitchers mapped")

        # Build name-based fallback for players missing FG ID
        self._name_to_fg_row = {}
        if not fg_stuff_plus.empty and "Name" in fg_stuff_plus.columns:
            for _, row in fg_stuff_plus.iterrows():
                name_key = (str(row["Name"]).lower().strip(), int(row["Season"]))
                self._name_to_fg_row[name_key] = row

        all_rows = []
        player_seasons = []
        for _, row in pitcher_dataset.iterrows():
            if pd.isna(row.get("mlbam_id")):
                continue
            g = float(row["G"]) if pd.notna(row.get("G")) else 0
            gs = float(row["GS"]) if pd.notna(row.get("GS")) else 0
            if g > 0:
                is_starter = (gs / g >= 0.5)
            else:
                # G/GS missing — will infer from Statcast data later
                is_starter = None
            player_seasons.append((
                int(row["mlbam_id"]), int(row["season"]),
                row.get("first_name", ""), row.get("last_name", ""),
                is_starter,
            ))

        total = len(player_seasons)
        for i, (mlbam_id, season, first_name, last_name, is_starter) in enumerate(player_seasons):
            if (i + 1) % 50 == 0 or i == 0:
                print(f"  Processing pitch model {i + 1}/{total}...")

            rows = self._aggregate_pitcher_pitches(
                mlbam_id, season, first_name, last_name, min_pitches, is_starter
            )
            if rows:
                # Merge Stuff+ from FanGraphs
                rows = self._merge_stuff_plus(
                    rows, mlbam_id, season, fg_stuff_plus
                )
                all_rows.extend(rows)

        if not all_rows:
            return pd.DataFrame()

        df = pd.DataFrame(all_rows)
        return df

    def _fetch_fangraphs_stuff_plus(
        self, fetcher: PitcherDataFetcher, start_year: int, end_year: int
    ) -> pd.DataFrame:
        """Fetch FanGraphs data with per-pitch Stuff+ columns."""
        all_fg = []
        for year in range(start_year, end_year + 1):
            fg_data = fetcher.get_fangraphs_pitching(year, year, min_ip=30)
            if not fg_data.empty:
                fg_data = fg_data.copy()
                fg_data["season"] = year
                all_fg.append(fg_data)

        if not all_fg:
            return pd.DataFrame()

        return pd.concat(all_fg, ignore_index=True)

    def _fetch_pitch_data(self, mlbam_id: int, season: int) -> pd.DataFrame:
        """Fetch pitch-level Statcast data, using cache when available."""
        cache_key = f"statcast_pitcher_pitches_{mlbam_id}_{season}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            def timeout_handler(signum, frame):
                raise TimeoutError("Request timed out")

            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(30)

            try:
                start_dt = f"{season}-03-01"
                end_dt = f"{season}-11-30"
                data = statcast_pitcher(start_dt, end_dt, mlbam_id)
            finally:
                signal.alarm(0)

            if data is not None and not data.empty:
                self.cache.set(cache_key, data)
                return data
            return pd.DataFrame()
        except TimeoutError:
            print(f"    Timeout fetching pitch data for {mlbam_id} {season}")
            return pd.DataFrame()
        except Exception as e:
            print(f"    Error fetching pitch data for {mlbam_id} {season}: {e}")
            return pd.DataFrame()

    @staticmethod
    def _infer_starter_from_pitches(pitch_data: pd.DataFrame) -> bool:
        """Infer starter/reliever from Statcast pitch data.

        A pitcher is a starter if they appeared in the 1st inning in >= 50%
        of their games (by game_pk).
        """
        if "game_pk" not in pitch_data.columns or "inning" not in pitch_data.columns:
            return False

        games = pitch_data.groupby("game_pk")["inning"].min()
        if len(games) == 0:
            return False

        games_started = (games == 1).sum()
        return games_started / len(games) >= 0.5

    def _aggregate_pitcher_pitches(
        self,
        mlbam_id: int,
        season: int,
        first_name: str,
        last_name: str,
        min_pitches: int,
        is_starter=None,
    ) -> list:
        """Aggregate pitch-level data into per-pitch-type rows."""
        pitch_data = self._fetch_pitch_data(mlbam_id, season)

        if pitch_data is None or pitch_data.empty:
            return []

        if "pitch_type" not in pitch_data.columns:
            return []

        # Infer starter/reliever from Statcast data when G/GS unavailable
        if is_starter is None:
            is_starter = self._infer_starter_from_pitches(pitch_data)

        # Filter to known pitch types
        known_types = set(PITCH_TYPE_NAMES.keys())
        pitch_data = pitch_data[pitch_data["pitch_type"].isin(known_types)]

        if pitch_data.empty:
            return []

        rows = []
        for pitch_type, group in pitch_data.groupby("pitch_type"):
            n_pitches = len(group)
            if n_pitches < min_pitches:
                continue

            row = {
                "mlbam_id": mlbam_id,
                "first_name": first_name,
                "last_name": last_name,
                "season": season,
                "pitch_type": pitch_type,
                "pitch_name": PITCH_TYPE_NAMES.get(pitch_type, pitch_type),
                "n_pitches": n_pitches,
                "is_starter": is_starter,
            }

            # Average velocity
            if "release_speed" in group.columns:
                row["avg_velo"] = round(group["release_speed"].dropna().mean(), 1)

            # Induced vertical break (pfx_z in feet → inches)
            if "pfx_z" in group.columns:
                row["avg_ivb"] = round(group["pfx_z"].dropna().mean() * 12, 1)

            # Induced horizontal break (pfx_x in feet → inches)
            if "pfx_x" in group.columns:
                row["avg_ihb"] = round(group["pfx_x"].dropna().mean() * 12, 1)

            # Spin rate
            if "release_spin_rate" in group.columns:
                row["avg_spin"] = round(group["release_spin_rate"].dropna().mean(), 0)

            # Arm angle
            if "arm_angle" in group.columns:
                avg_angle = group["arm_angle"].dropna().mean()
                if not np.isnan(avg_angle):
                    row["arm_angle"] = round(avg_angle, 1)

            # Plate discipline metrics
            row.update(self._calculate_plate_discipline(group))

            # xSLG and xwOBA on batted balls only
            row.update(self._calculate_batted_ball_expected(group))

            rows.append(row)

        return rows

    def _calculate_plate_discipline(self, group: pd.DataFrame) -> dict:
        """Calculate whiff%, chase%, zone% for a pitch type group."""
        result = {}

        if "description" not in group.columns:
            return result

        total_pitches = len(group)

        # Swings
        swings = group[group["description"].isin(SWING_EVENTS)]
        total_swings = len(swings)

        # Whiff% = whiffs / swings
        whiffs = group[group["description"].isin(WHIFF_EVENTS)]
        if total_swings > 0:
            result["whiff_pct"] = round(len(whiffs) / total_swings * 100, 1)

        # Zone classification
        if "zone" in group.columns:
            in_zone = group[group["zone"].isin(IN_ZONE)]
            out_zone = group[group["zone"].isin(OUT_ZONE)]

            # Zone%
            if total_pitches > 0:
                result["zone_pct"] = round(len(in_zone) / total_pitches * 100, 1)

            # Chase% = swings outside zone / pitches outside zone
            if len(out_zone) > 0:
                swings_out = out_zone[out_zone["description"].isin(SWING_EVENTS)]
                result["chase_pct"] = round(len(swings_out) / len(out_zone) * 100, 1)

        return result

    def _calculate_batted_ball_expected(self, group: pd.DataFrame) -> dict:
        """Calculate xSLG and xwOBA on batted balls only."""
        result = {}

        if "description" not in group.columns:
            return result

        batted_balls = group[group["description"] == "hit_into_play"]

        if batted_balls.empty:
            return result

        if "estimated_slg_using_speedangle" in batted_balls.columns:
            vals = batted_balls["estimated_slg_using_speedangle"].dropna()
            if len(vals) > 0:
                result["xslg"] = round(vals.mean(), 3)

        if "estimated_woba_using_speedangle" in batted_balls.columns:
            vals = batted_balls["estimated_woba_using_speedangle"].dropna()
            if len(vals) > 0:
                result["xwoba"] = round(vals.mean(), 3)

        return result

    def _merge_stuff_plus(
        self,
        rows: list,
        mlbam_id: int,
        season: int,
        fg_data: pd.DataFrame,
    ) -> list:
        """Merge per-pitch Stuff+ from FanGraphs data."""
        if fg_data.empty:
            return rows

        # Look up FanGraphs ID from pre-built crosswalk
        fg_id = self._mlbam_to_fg.get(mlbam_id)
        fg_row = None

        if fg_id is not None:
            match = fg_data[
                (fg_data["IDfg"] == fg_id) & (fg_data["Season"] == season)
            ]
            if not match.empty:
                fg_row = match.iloc[0]

        # Fallback: match by name
        if fg_row is None and rows:
            first = rows[0].get("first_name", "")
            last = rows[0].get("last_name", "")
            full_name = f"{first} {last}".lower().strip()
            name_key = (full_name, season)
            if name_key in self._name_to_fg_row:
                fg_row = self._name_to_fg_row[name_key]

        # Fallback: match by last name only (handles Cam vs Cameron etc.)
        if fg_row is None and rows:
            last = rows[0].get("last_name", "").lower().strip()
            if last:
                for (fg_name, fg_season), fg_candidate in self._name_to_fg_row.items():
                    if fg_season == season and fg_name.endswith(f" {last}"):
                        fg_row = fg_candidate
                        break

        if fg_row is None:
            return rows

        for row in rows:
            pitch_type = row["pitch_type"]
            stuff_col = PITCH_TYPE_TO_STUFF_PLUS.get(pitch_type)
            if stuff_col and stuff_col in fg_row.index:
                val = fg_row[stuff_col]
                if pd.notna(val):
                    row["stuff_plus"] = float(val)

        return rows
