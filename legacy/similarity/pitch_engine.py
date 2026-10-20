"""Per-pitch-type similarity engine for the Pitch Model page."""

from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

from .normalizer import MetricNormalizer
from .distance import DistanceCalculator
from ..metrics.pitch_model_definitions import (
    PITCH_METRIC_WEIGHTS,
    PITCH_COMPARISON_METRICS,
    MIN_COMP_PITCHES,
)


class PitchSimilarityEngine:
    """Finds similar pitches across pitchers by pitch type."""

    def __init__(self, dataset: pd.DataFrame):
        """
        Initialize the pitch similarity engine.

        Args:
            dataset: DataFrame with one row per (pitcher, season, pitch_type)
                     containing aggregated pitch metrics.
        """
        self.dataset = dataset.copy()
        self.weights = PITCH_METRIC_WEIGHTS
        self.metrics = [
            m for m in PITCH_COMPARISON_METRICS if m in self.dataset.columns
        ]

        if not self.metrics:
            raise ValueError("Dataset missing all pitch comparison metrics")

        self.distance_calc = DistanceCalculator(self.weights)

        # Normalize metrics *within each pitch type* so comparisons are fair
        self._normalizers: Dict[str, MetricNormalizer] = {}
        self._z_columns = [f"{m}_z" for m in self.metrics]
        self._normalize_by_pitch_type()

    def _normalize_by_pitch_type(self) -> None:
        """Compute z-scores for each metric grouped by pitch type."""
        normalized_parts = []

        for pitch_type, group in self.dataset.groupby("pitch_type"):
            normalizer = MetricNormalizer()
            available = [m for m in self.metrics if m in group.columns]
            if not available:
                normalized_parts.append(group)
                continue

            normalized = normalizer.fit_transform(group, available)
            self._normalizers[pitch_type] = normalizer
            normalized_parts.append(normalized)

        if normalized_parts:
            self.dataset = pd.concat(normalized_parts, ignore_index=True)

        # Calculate max distance for similarity scoring
        z_ranges = []
        for col in self._z_columns:
            if col in self.dataset.columns:
                col_data = self.dataset[col].dropna()
                if len(col_data) > 0:
                    z_ranges.append(col_data.max() - col_data.min())

        if z_ranges:
            total_weight = sum(
                self.weights.get(c.replace("_z", ""), 1.0) for c in self._z_columns
            )
            avg_range = sum(z_ranges) / len(z_ranges)
            self.max_distance = avg_range * (total_weight ** 0.5) * 1.5
        else:
            self.max_distance = 10.0

    def get_pitcher_pitches(
        self, player_id: int, season: int
    ) -> List[Dict[str, Any]]:
        """
        Get all pitch types thrown by a pitcher in a season.

        Returns:
            List of dicts, one per pitch type, with all metrics.
        """
        mask = (
            (self.dataset["mlbam_id"] == player_id)
            & (self.dataset["season"] == season)
        )
        rows = self.dataset[mask]

        if rows.empty:
            return []

        pitches = []
        for _, row in rows.iterrows():
            pitch = {
                "pitch_type": row["pitch_type"],
                "pitch_name": row.get("pitch_name", row["pitch_type"]),
                "n_pitches": int(row.get("n_pitches", 0)),
            }
            for metric in self.metrics:
                if metric in row and pd.notna(row[metric]):
                    pitch[metric] = row[metric]

            if "arm_angle" in row and pd.notna(row["arm_angle"]):
                pitch["arm_angle"] = row["arm_angle"]

            pitches.append(pitch)

        # Sort by n_pitches descending
        pitches.sort(key=lambda p: p.get("n_pitches", 0), reverse=True)
        return pitches

    def find_similar_pitches(
        self, player_id: int, season: int, top_n: int = 1
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        For each pitch type the target pitcher throws, find the best matching
        pitch from other pitchers.

        Args:
            player_id: MLBAM ID of the target pitcher
            season: Season year
            top_n: Number of top matches per pitch type

        Returns:
            Dict mapping pitch_type to list of best match dicts, each containing:
            - mlbam_id, first_name, last_name, season, similarity, distance
            - All pitch metrics for the matching pitch
        """
        target_mask = (
            (self.dataset["mlbam_id"] == player_id)
            & (self.dataset["season"] == season)
        )
        target_rows = self.dataset[target_mask]

        if target_rows.empty:
            return {}

        results = {}
        for _, target in target_rows.iterrows():
            pitch_type = target["pitch_type"]

            # Get all candidates with the same pitch type, excluding same pitcher
            # Only allow comps with enough pitches and Stuff+ data
            candidates = self.dataset[
                (self.dataset["pitch_type"] == pitch_type)
                & (self.dataset["mlbam_id"] != player_id)
                & (self.dataset["n_pitches"] >= MIN_COMP_PITCHES)
                & (self.dataset["stuff_plus"].notna())
            ]

            # Filter by role: starters comp to starters, relievers to relievers
            # Uses is_starter flag based on GS/G ratio (not IP)
            if "is_starter" in self.dataset.columns:
                target_starter = target.get("is_starter")
                if pd.notna(target_starter):
                    candidates = candidates[
                        candidates["is_starter"] == target_starter
                    ]

            if candidates.empty:
                continue

            # Calculate distances using z-scored metrics
            available_z = [z for z in self._z_columns if z in candidates.columns]
            if not available_z:
                continue

            distances = self.distance_calc.calculate_all_distances(
                target, candidates, available_z
            )

            candidates = candidates.copy()
            candidates["distance"] = distances
            candidates = candidates[candidates["distance"] < float("inf")]

            if candidates.empty:
                continue

            candidates["similarity"] = candidates["distance"].apply(
                lambda d: self.distance_calc.distance_to_similarity(
                    d, self.max_distance
                )
            )

            top_matches = candidates.nsmallest(top_n, "distance")

            matches = []
            for _, match in top_matches.iterrows():
                match_dict = {
                    "mlbam_id": int(match["mlbam_id"]),
                    "season": int(match["season"]),
                    "similarity": round(match["similarity"], 1),
                    "distance": round(match["distance"], 4),
                    "pitch_type": pitch_type,
                    "pitch_name": match.get("pitch_name", pitch_type),
                    "n_pitches": int(match.get("n_pitches", 0)),
                }

                if "first_name" in match and "last_name" in match:
                    match_dict["name"] = (
                        f"{match['first_name']} {match['last_name']}"
                    )

                for metric in self.metrics:
                    if metric in match and pd.notna(match[metric]):
                        match_dict[metric] = match[metric]

                if "arm_angle" in match and pd.notna(match["arm_angle"]):
                    match_dict["arm_angle"] = match["arm_angle"]

                matches.append(match_dict)

            results[pitch_type] = matches

        return results

    def get_pitcher_info(
        self, player_id: int, season: int
    ) -> Optional[Dict[str, Any]]:
        """Get pitcher name and arm angle from the dataset."""
        mask = (
            (self.dataset["mlbam_id"] == player_id)
            & (self.dataset["season"] == season)
        )
        rows = self.dataset[mask]
        if rows.empty:
            return None

        first_row = rows.iloc[0]
        info = {
            "mlbam_id": player_id,
            "season": season,
        }
        if "first_name" in first_row and "last_name" in first_row:
            info["name"] = f"{first_row['first_name']} {first_row['last_name']}"

        # Arm angle: take the mean across all pitch types for this pitcher-season
        if "arm_angle" in rows.columns:
            avg_arm = rows["arm_angle"].dropna().mean()
            if not np.isnan(avg_arm):
                info["arm_angle"] = round(avg_arm, 1)

        return info
