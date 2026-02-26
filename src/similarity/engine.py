"""Main similarity engine for finding comparable player-seasons."""

from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np

from .normalizer import MetricNormalizer
from .distance import DistanceCalculator
from ..metrics.definitions import (
    METRIC_WEIGHTS,
    PRIMARY_METRICS,
    SANITY_CHECK_METRIC,
    SANITY_CHECK_TOLERANCE,
    BATTER_LOWER_IS_BETTER,
    MetricConfig,
    PlayerType,
    get_metric_config,
)


class SimilarityEngine:
    """Engine for finding similar player-seasons."""

    def __init__(
        self,
        dataset: pd.DataFrame,
        weights: Optional[Dict[str, float]] = None,
        xwoba_tolerance: Optional[float] = None,
        config: Optional[MetricConfig] = None,
    ):
        """
        Initialize the similarity engine.

        Args:
            dataset: Full dataset of player-seasons with all metrics
            weights: Custom metric weights (defaults to config's weights or METRIC_WEIGHTS)
            xwoba_tolerance: Maximum sanity check metric difference for valid comparisons
            config: MetricConfig for player-type-specific settings (defaults to BATTER)
        """
        self.dataset = dataset.copy()
        self.config = config or get_metric_config(PlayerType.BATTER)

        self.weights = weights or self.config.metric_weights
        self.sanity_tolerance = xwoba_tolerance or self.config.sanity_check_tolerance
        self.sanity_metric = self.config.sanity_check_metric
        self.primary_metrics = self.config.primary_metrics
        self.lower_is_better = self.config.lower_is_better
        self.result_stats = self.config.result_stats
        self.is_batter = self.config.player_type == PlayerType.BATTER

        self.normalizer = MetricNormalizer()
        self.distance_calc = DistanceCalculator(self.weights)

        # Only initialize pulled FB calculator for batters
        self.pulled_fb_calc = None
        if self.is_batter:
            from ..metrics.pulled_flyball import PulledFlyBallCalculator
            self.pulled_fb_calc = PulledFlyBallCalculator()

        self._prepare_dataset()

    def _prepare_dataset(self) -> None:
        """Prepare the dataset by computing z-scores."""
        available_metrics = [
            m for m in self.primary_metrics if m in self.dataset.columns
        ]

        if not available_metrics:
            raise ValueError("Dataset missing all primary metrics")

        self.metrics_used = available_metrics
        self.z_columns = [f"{m}_z" for m in available_metrics]

        self.dataset = self.normalizer.fit_transform(
            self.dataset, available_metrics
        )

        # Estimate max distance from z-score range instead of computing all pairs
        z_ranges = []
        for col in self.z_columns:
            if col in self.dataset.columns:
                col_data = self.dataset[col].dropna()
                if len(col_data) > 0:
                    z_range = col_data.max() - col_data.min()
                    z_ranges.append(z_range)

        if z_ranges:
            total_weight = sum(
                self.weights.get(c.replace("_z", ""), 1.0) for c in self.z_columns
            )
            avg_range = sum(z_ranges) / len(z_ranges)
            self.max_distance = avg_range * (total_weight**0.5) * 1.5
        else:
            self.max_distance = 10.0

    def find_similar(
        self,
        player_id: int,
        season: int,
        top_n: int = 5,
        exclude_same_player: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Find the most similar player-seasons to a given player-season.

        Args:
            player_id: MLBAM player ID
            season: Season year
            top_n: Number of similar players to return
            exclude_same_player: Whether to exclude other seasons of the same player

        Returns:
            List of dictionaries with similar player info and similarity scores
        """
        target_mask = (
            (self.dataset["mlbam_id"] == player_id)
            & (self.dataset["season"] == season)
        )

        if not target_mask.any():
            return []

        target = self.dataset[target_mask].iloc[0]

        candidates = self.dataset.copy()
        candidates = candidates[~target_mask]

        if exclude_same_player:
            candidates = candidates[candidates["mlbam_id"] != player_id]

        # Apply sanity check metric filter
        if (
            self.sanity_metric in candidates.columns
            and self.sanity_metric in target.index
        ):
            target_sanity = target[self.sanity_metric]
            if pd.notna(target_sanity):
                candidates = candidates[
                    (candidates[self.sanity_metric] >= target_sanity - self.sanity_tolerance)
                    & (candidates[self.sanity_metric] <= target_sanity + self.sanity_tolerance)
                ]

        if candidates.empty:
            return []

        # Apply pitcher role filter (starters vs relievers)
        if not self.is_batter:
            candidates = self._filter_by_pitcher_role(target, candidates)

        if candidates.empty:
            return []

        # Filter out candidates missing key metrics
        candidates = self._filter_candidates_by_metrics(candidates)

        if candidates.empty:
            return []

        distances = self.distance_calc.calculate_all_distances(
            target, candidates, self.z_columns
        )

        candidates = candidates.copy()
        candidates["distance"] = distances

        # Filter out candidates with infinite distance (too many missing values)
        candidates = candidates[candidates["distance"] < float("inf")]

        if candidates.empty:
            return []

        candidates["similarity"] = candidates["distance"].apply(
            lambda d: self.distance_calc.distance_to_similarity(d, self.max_distance)
        )

        top_matches = candidates.nsmallest(top_n, "distance")

        results = []
        for _, row in top_matches.iterrows():
            result = {
                "mlbam_id": int(row["mlbam_id"]),
                "season": int(row["season"]),
                "similarity": round(row["similarity"], 1),
                "distance": round(row["distance"], 4),
            }

            if "first_name" in row and "last_name" in row:
                result["name"] = f"{row['first_name']} {row['last_name']}"

            for metric in self.metrics_used:
                if metric in row:
                    result[metric] = row[metric]

            if self.sanity_metric in row:
                result[self.sanity_metric] = row[self.sanity_metric]

            # Add results stats
            for stat in self.result_stats:
                if stat in row and pd.notna(row[stat]):
                    result[stat] = row[stat]

            # Add pulled FB% for batters (calculated on-demand)
            if self.is_batter:
                pulled_fb = self._get_pulled_fb_pct(
                    int(row["mlbam_id"]), int(row["season"])
                )
                if pulled_fb is not None:
                    result["pulled_fb_pct"] = pulled_fb

            # Add percentiles
            result = self._add_percentiles(result)

            results.append(result)

        return results

    def _filter_candidates_by_metrics(self, candidates: pd.DataFrame) -> pd.DataFrame:
        """Filter candidates based on having sufficient metrics."""
        if self.is_batter:
            # Must have at least 2 batted ball metrics AND 2 plate discipline metrics
            batted_ball_z = [
                f"{m}_z"
                for m in ["exit_velocity", "barrel_pct", "hard_hit_pct", "launch_angle"]
                if f"{m}_z" in self.z_columns
            ]
            plate_disc_z = [
                f"{m}_z"
                for m in ["chase_rate", "whiff_pct", "k_pct", "bb_pct"]
                if f"{m}_z" in self.z_columns
            ]

            bb_counts = (
                candidates[batted_ball_z].notna().sum(axis=1) if batted_ball_z else 0
            )
            pd_counts = (
                candidates[plate_disc_z].notna().sum(axis=1) if plate_disc_z else 0
            )

            return candidates[(bb_counts >= 2) & (pd_counts >= 2)]
        else:
            # Pitchers: Must have at least 2 stuff metrics AND 2 control/results metrics
            stuff_z = [
                f"{m}_z"
                for m in ["k_pct", "whiff_pct", "chase_pct", "stuff_plus"]
                if f"{m}_z" in self.z_columns
            ]
            control_z = [
                f"{m}_z"
                for m in ["bb_pct", "xfip", "xera", "zone_pct"]
                if f"{m}_z" in self.z_columns
            ]

            stuff_counts = (
                candidates[stuff_z].notna().sum(axis=1) if stuff_z else 0
            )
            control_counts = (
                candidates[control_z].notna().sum(axis=1) if control_z else 0
            )

            return candidates[(stuff_counts >= 2) & (control_counts >= 2)]

    def _filter_by_pitcher_role(
        self, target: pd.Series, candidates: pd.DataFrame
    ) -> pd.DataFrame:
        """Filter pitcher candidates to same role (starter vs reliever).

        Role is determined by GS/G ratio (>= 0.5 = starter), not IP.
        A starter with a small sample (e.g. call-up) still comps TO starters,
        but comp candidates must have enough IP to be statistically reliable.
        """
        from ..metrics.pitcher_definitions import (
            STARTER_GS_RATIO,
            MIN_STARTER_COMP_IP,
        )

        # Determine target's role from GS/G ratio
        target_g = target.get("G") if "G" in target.index else None
        target_gs = target.get("GS") if "GS" in target.index else None

        if target_g is None or pd.isna(target_g) or float(target_g) == 0:
            return candidates
        if target_gs is None or pd.isna(target_gs):
            return candidates

        target_is_starter = (float(target_gs) / float(target_g)) >= STARTER_GS_RATIO

        # Classify candidates by GS/G ratio
        if "G" not in candidates.columns or "GS" not in candidates.columns:
            return candidates

        cand_g = candidates["G"].fillna(0).astype(float)
        cand_gs = candidates["GS"].fillna(0).astype(float)
        cand_is_starter = (cand_gs / cand_g.replace(0, float("nan"))) >= STARTER_GS_RATIO

        if target_is_starter:
            # Target is a starter → comp to starters with enough IP
            return candidates[
                cand_is_starter
                & (candidates["IP"].fillna(0).astype(float) >= MIN_STARTER_COMP_IP)
            ]
        else:
            # Target is a reliever → comp to relievers
            return candidates[~cand_is_starter]

    def _calculate_percentile(
        self, metric: str, value: float, season: int, higher_is_better: bool = True
    ) -> float:
        """Calculate percentile for a metric value within a specific season."""
        if value is None or str(value) == "nan":
            return 50.0

        if metric not in self.dataset.columns:
            return 50.0

        # Filter to the specific season only
        season_data = self.dataset[self.dataset["season"] == season]
        col_data = season_data[metric].dropna()

        if len(col_data) == 0:
            return 50.0

        # Calculate percentile rank within that season
        pct = (col_data < value).sum() / len(col_data) * 100

        # Flip if lower is better
        if not higher_is_better:
            pct = 100 - pct

        return max(1, min(99, pct))

    def _add_percentiles(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Add percentile rankings to a player result (within their season)."""
        season = result.get("season")
        if season is None:
            season = 2024  # fallback

        percentiles = {}
        for metric in self.metrics_used:
            if metric in result and result[metric] is not None:
                higher_is_better = metric not in self.lower_is_better
                percentiles[f"{metric}_pct"] = self._calculate_percentile(
                    metric, result[metric], season, higher_is_better
                )

        # Add sanity check metric percentile
        if self.sanity_metric in result:
            # For batters, xwoba higher is better; for pitchers, xera lower is better
            higher_is_better = self.sanity_metric not in self.lower_is_better
            percentiles[f"{self.sanity_metric}_pct"] = self._calculate_percentile(
                self.sanity_metric, result[self.sanity_metric], season, higher_is_better
            )

        # Add pulled_fb_pct percentile for batters (higher is better for power hitters)
        if self.is_batter and "pulled_fb_pct" in result and result["pulled_fb_pct"] is not None:
            # Estimate percentile based on typical ranges with 17° threshold
            val = result["pulled_fb_pct"]
            pct = min(99, max(1, (val - 8) / 17 * 100))
            percentiles["pulled_fb_pct_pct"] = pct

        result["percentiles"] = percentiles
        return result

    def _get_pulled_fb_pct(self, player_id: int, season: int) -> Optional[float]:
        """Get pulled FB% for a player-season, calculating if needed."""
        if not self.is_batter or self.pulled_fb_calc is None:
            return None

        # Check if already in dataset
        mask = (self.dataset["mlbam_id"] == player_id) & (
            self.dataset["season"] == season
        )
        if mask.any():
            row = self.dataset[mask].iloc[0]
            if "pulled_fb_pct" in row and pd.notna(row["pulled_fb_pct"]):
                return row["pulled_fb_pct"]

        # Calculate on-demand
        try:
            return self.pulled_fb_calc.calculate_for_player_season(player_id, season)
        except Exception:
            return None

    def get_player_season(
        self, player_id: int, season: int
    ) -> Optional[Dict[str, Any]]:
        """Get data for a specific player-season."""
        mask = (
            (self.dataset["mlbam_id"] == player_id)
            & (self.dataset["season"] == season)
        )

        if not mask.any():
            return None

        row = self.dataset[mask].iloc[0]

        result = {
            "mlbam_id": int(row["mlbam_id"]),
            "season": int(row["season"]),
        }

        if "first_name" in row and "last_name" in row:
            result["name"] = f"{row['first_name']} {row['last_name']}"

        for metric in self.metrics_used:
            if metric in row:
                result[metric] = row[metric]

        if self.sanity_metric in row:
            result[self.sanity_metric] = row[self.sanity_metric]

        # Add results stats
        for stat in self.result_stats:
            if stat in row and pd.notna(row[stat]):
                result[stat] = row[stat]

        # Add pulled FB% for batters (calculated on-demand)
        if self.is_batter:
            pulled_fb = self._get_pulled_fb_pct(int(row["mlbam_id"]), int(row["season"]))
            if pulled_fb is not None:
                result["pulled_fb_pct"] = pulled_fb

        # Add percentiles
        result = self._add_percentiles(result)

        return result

    def get_available_players(self) -> pd.DataFrame:
        """Get list of all available player-seasons."""
        cols = ["mlbam_id", "season"]
        if "first_name" in self.dataset.columns:
            cols.append("first_name")
        if "last_name" in self.dataset.columns:
            cols.append("last_name")

        return self.dataset[cols].drop_duplicates()

    def search_players(self, name_query: str) -> pd.DataFrame:
        """Search for players by name."""
        df = self.get_available_players()

        if "first_name" not in df.columns or "last_name" not in df.columns:
            return pd.DataFrame()

        query_lower = name_query.lower()
        mask = df["first_name"].str.lower().str.contains(
            query_lower, na=False
        ) | df["last_name"].str.lower().str.contains(query_lower, na=False)

        return df[mask].sort_values(["last_name", "first_name", "season"])
