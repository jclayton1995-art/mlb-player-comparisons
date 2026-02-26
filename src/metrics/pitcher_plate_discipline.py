"""Calculate pitcher plate discipline metrics from raw Statcast pitch data."""

from typing import Optional, Dict
import pandas as pd
from pybaseball import statcast_pitcher

from ..data.cache_manager import CacheManager


class PitcherPlateDisciplineCalculator:
    """Calculates plate discipline metrics from pitch-level Statcast data."""

    # Events that count as swings
    SWING_EVENTS = [
        'swinging_strike',
        'swinging_strike_blocked',
        'foul',
        'foul_tip',
        'hit_into_play',
        'foul_bunt',
        'missed_bunt',
    ]

    # Events that count as whiffs (swinging strikes)
    WHIFF_EVENTS = [
        'swinging_strike',
        'swinging_strike_blocked',
    ]

    # Events that count as contact
    CONTACT_EVENTS = [
        'foul',
        'foul_tip',
        'hit_into_play',
        'foul_bunt',
    ]

    # Zones 1-9 are in the strike zone
    IN_ZONE = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    # Zones 11-14 are outside the strike zone
    OUT_ZONE = [11, 12, 13, 14]

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.cache = cache_manager or CacheManager()

    def _get_pitch_data(self, player_id: int, season: int) -> pd.DataFrame:
        """Fetch pitch-level data for a pitcher-season."""
        cache_key = f"statcast_pitcher_pitches_{player_id}_{season}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError("Request timed out")

            # Set 30 second timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(30)

            try:
                # Fetch full season of pitch data
                start_dt = f"{season}-03-01"
                end_dt = f"{season}-11-30"
                data = statcast_pitcher(start_dt, end_dt, player_id)
            finally:
                signal.alarm(0)  # Cancel the alarm

            if data is not None and not data.empty:
                self.cache.set(cache_key, data)
                return data
            return pd.DataFrame()
        except TimeoutError:
            print(f"Timeout fetching pitch data for {player_id} {season}")
            return pd.DataFrame()
        except Exception as e:
            print(f"Error fetching pitch data for {player_id} {season}: {e}")
            return pd.DataFrame()

    def calculate_for_player_season(
        self, player_id: int, season: int
    ) -> Optional[Dict[str, float]]:
        """
        Calculate plate discipline metrics for a pitcher-season.

        Returns dict with:
            - zone_pct: % of pitches in the strike zone
            - chase_pct: % of pitches outside zone that are swung at
            - zone_contact_pct: % of in-zone swings that result in contact
            - whiff_pct: % of swings that are whiffs (swinging strikes)
        """
        pitches = self._get_pitch_data(player_id, season)

        if pitches.empty:
            return None

        total_pitches = len(pitches)
        if total_pitches == 0:
            return None

        # Classify pitches by zone
        def is_in_zone(zone):
            return zone in self.IN_ZONE if pd.notna(zone) else False

        def is_out_zone(zone):
            return zone in self.OUT_ZONE if pd.notna(zone) else False

        pitches_in_zone = pitches[pitches['zone'].apply(is_in_zone)]
        pitches_out_zone = pitches[pitches['zone'].apply(is_out_zone)]

        # Zone% = pitches in zone / total pitches
        zone_pct = len(pitches_in_zone) / total_pitches * 100

        # Get swings
        all_swings = pitches[pitches['description'].isin(self.SWING_EVENTS)]
        total_swings = len(all_swings)

        # Whiff% = whiffs / swings
        whiffs = pitches[pitches['description'].isin(self.WHIFF_EVENTS)]
        whiff_pct = len(whiffs) / total_swings * 100 if total_swings > 0 else 0

        # Chase% = swings outside zone / pitches outside zone
        swings_out_zone = pitches_out_zone[
            pitches_out_zone['description'].isin(self.SWING_EVENTS)
        ]
        chase_pct = (
            len(swings_out_zone) / len(pitches_out_zone) * 100
            if len(pitches_out_zone) > 0
            else 0
        )

        # Z-Contact% = contact on in-zone swings / in-zone swings
        swings_in_zone = pitches_in_zone[
            pitches_in_zone['description'].isin(self.SWING_EVENTS)
        ]
        contact_in_zone = swings_in_zone[
            swings_in_zone['description'].isin(self.CONTACT_EVENTS)
        ]
        zone_contact_pct = (
            len(contact_in_zone) / len(swings_in_zone) * 100
            if len(swings_in_zone) > 0
            else 0
        )

        return {
            'zone_pct': round(zone_pct, 1),
            'chase_pct': round(chase_pct, 1),
            'zone_contact_pct': round(zone_contact_pct, 1),
            'whiff_pct': round(whiff_pct, 1),
        }

    def calculate_batch(
        self, player_seasons: list, verbose: bool = True
    ) -> pd.DataFrame:
        """
        Calculate plate discipline for multiple pitcher-seasons.

        Args:
            player_seasons: List of (player_id, season) tuples
            verbose: Print progress updates

        Returns:
            DataFrame with mlbam_id, season, and calculated metrics
        """
        results = []
        total = len(player_seasons)

        for i, (player_id, season) in enumerate(player_seasons):
            if verbose and ((i + 1) % 25 == 0 or i == 0):
                print(f"  Calculating plate discipline {i + 1}/{total}...")

            metrics = self.calculate_for_player_season(player_id, season)
            if metrics is not None:
                results.append({
                    'mlbam_id': player_id,
                    'season': season,
                    **metrics,
                })

        return pd.DataFrame(results)
