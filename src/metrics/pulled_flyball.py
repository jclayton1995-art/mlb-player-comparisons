"""Calculate Pulled Air Ball percentage from pitch-level Statcast data."""

import math
from typing import Optional
import pandas as pd
import numpy as np

from ..data.fetcher import DataFetcher
from ..data.cache_manager import CacheManager


class PulledFlyBallCalculator:
    """Calculates Pulled Air% from pitch-level Statcast data.

    Formula: Pulled non-ground balls / Total balls in play
    (Matches Baseball Savant methodology)
    """

    HOME_PLATE_X = 125.42
    HOME_PLATE_Y = 199.0

    # Spray angle threshold for "pulled" (degrees from center)
    # 17 degrees matches Baseball Savant's pull zone
    PULL_ANGLE_THRESHOLD = 17

    def __init__(
        self,
        fetcher: Optional[DataFetcher] = None,
        cache_manager: Optional[CacheManager] = None,
    ):
        self.cache = cache_manager or CacheManager()
        self.fetcher = fetcher or DataFetcher(self.cache)

    def calculate_spray_angle(self, hc_x: float, hc_y: float) -> float:
        """
        Calculate spray angle from hit coordinates.

        Returns angle in degrees where:
        - 0° is straight up the middle
        - Negative angles are to the left (pull side for RHB)
        - Positive angles are to the right (pull side for LHB)
        """
        x_adj = hc_x - self.HOME_PLATE_X
        y_adj = self.HOME_PLATE_Y - hc_y

        if y_adj <= 0:
            return 0.0

        angle_rad = math.atan2(x_adj, y_adj)
        angle_deg = math.degrees(angle_rad)

        return angle_deg

    def is_pulled(self, spray_angle: float, batter_hand: str) -> bool:
        """
        Determine if a ball is pulled based on spray angle and batter handedness.

        Args:
            spray_angle: Spray angle in degrees (negative = left field, positive = right field)
            batter_hand: 'L' for left-handed, 'R' for right-handed

        Returns:
            True if the ball is pulled
        """
        if batter_hand == "R":
            return spray_angle < -self.PULL_ANGLE_THRESHOLD
        elif batter_hand == "L":
            return spray_angle > self.PULL_ANGLE_THRESHOLD
        return False

    def is_air_ball(self, bb_type: Optional[str]) -> bool:
        """Determine if a batted ball is NOT a ground ball (i.e., FB, LD, or popup)."""
        return bb_type in ("fly_ball", "line_drive", "popup")

    def calculate_for_player_season(
        self, player_id: int, year: int
    ) -> Optional[float]:
        """
        Calculate Pulled Air% for a specific player-season.

        Formula: Pulled non-ground balls / Total balls in play
        (Matches Baseball Savant methodology)

        Returns percentage, or None if insufficient data.
        """
        cache_key = f"pulled_air_v4_{player_id}_{year}"
        cached = self.cache.get(cache_key)
        if cached is not None and not cached.empty:
            return cached.iloc[0]["pulled_fb_pct"]

        start_date = f"{year}-03-01"
        end_date = f"{year}-11-30"

        pitch_data = self.fetcher.get_statcast_batter_data(
            player_id, start_date, end_date
        )

        if pitch_data.empty:
            return None

        # Filter to balls in play
        batted_balls = pitch_data[
            pitch_data["type"] == "X"
        ].copy()

        if batted_balls.empty or len(batted_balls) < 20:
            return None

        # Need hit coordinates for spray angle
        batted_balls = batted_balls.dropna(subset=["hc_x", "hc_y"])

        if batted_balls.empty or len(batted_balls) < 20:
            return None

        total_bip = len(batted_balls)

        # Calculate spray angle for each batted ball
        batted_balls["spray_angle"] = batted_balls.apply(
            lambda row: self.calculate_spray_angle(row["hc_x"], row["hc_y"]),
            axis=1,
        )

        # Get non-ground balls (air balls = FB + LD + popup)
        batted_balls["is_air"] = batted_balls["bb_type"].apply(self.is_air_ball)
        air_balls = batted_balls[batted_balls["is_air"]].copy()

        if len(air_balls) < 10:
            return None

        # Determine if each air ball is pulled based on THAT AT-BAT's stance
        # (important for switch hitters)
        air_balls["is_pulled"] = air_balls.apply(
            lambda row: self.is_pulled(row["spray_angle"], row.get("stand", "R")),
            axis=1,
        )

        pulled_air_count = air_balls["is_pulled"].sum()

        # Formula: Pulled Air Balls / Total BIP
        pulled_fb_pct = (pulled_air_count / total_bip) * 100

        result_df = pd.DataFrame([{
            "player_id": player_id,
            "season": year,
            "pulled_fb_pct": pulled_fb_pct,
            "total_bip": total_bip,
            "pulled_air_count": pulled_air_count,
        }])
        self.cache.set(cache_key, result_df)

        return pulled_fb_pct

    def calculate_batch(
        self, player_seasons: list[tuple[int, int]]
    ) -> pd.DataFrame:
        """
        Calculate Pulled Air% for multiple player-seasons.

        Args:
            player_seasons: List of (player_id, year) tuples

        Returns:
            DataFrame with columns: mlbam_id, season, pulled_fb_pct
        """
        results = []

        for player_id, year in player_seasons:
            pulled_fb_pct = self.calculate_for_player_season(player_id, year)
            if pulled_fb_pct is not None:
                results.append({
                    "mlbam_id": player_id,
                    "season": year,
                    "pulled_fb_pct": pulled_fb_pct,
                })

        if not results:
            return pd.DataFrame(columns=["mlbam_id", "season", "pulled_fb_pct"])

        return pd.DataFrame(results)
