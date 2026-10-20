"""Weighted Euclidean distance calculation for similarity."""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd


class DistanceCalculator:
    """Calculates weighted Euclidean distance between player-seasons."""

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Initialize the distance calculator.

        Args:
            weights: Dictionary mapping metric names to their weights
        """
        self.weights = weights or {}

    def set_weights(self, weights: Dict[str, float]) -> None:
        """Set the metric weights."""
        self.weights = weights

    def calculate_distance(
        self,
        target: pd.Series,
        candidate: pd.Series,
        z_columns: List[str],
    ) -> float:
        """
        Calculate weighted Euclidean distance between two player-seasons.

        Args:
            target: Series containing target player's z-scores
            candidate: Series containing candidate player's z-scores
            z_columns: List of z-score column names to use

        Returns:
            Weighted Euclidean distance (lower = more similar)
        """
        total_distance = 0.0
        total_weight = 0.0

        for z_col in z_columns:
            base_col = z_col.replace("_z", "")
            weight = self.weights.get(base_col, 1.0)

            target_val = target.get(z_col)
            candidate_val = candidate.get(z_col)

            if pd.isna(target_val) or pd.isna(candidate_val):
                continue

            diff = target_val - candidate_val
            total_distance += weight * (diff ** 2)
            total_weight += weight

        if total_weight == 0:
            return float("inf")

        return np.sqrt(total_distance)

    def calculate_all_distances(
        self,
        target: pd.Series,
        candidates: pd.DataFrame,
        z_columns: List[str],
    ) -> pd.Series:
        """
        Calculate distances from target to all candidates.

        Args:
            target: Series containing target player's z-scores
            candidates: DataFrame containing candidate players' z-scores
            z_columns: List of z-score column names to use

        Returns:
            Series of distances indexed by candidate DataFrame index
        """
        distances = candidates.apply(
            lambda row: self.calculate_distance(target, row, z_columns),
            axis=1,
        )
        return distances

    def distance_to_similarity(
        self, distance: float, max_distance: float
    ) -> float:
        """
        Convert distance to a similarity percentage (0-100%).

        Args:
            distance: The calculated distance
            max_distance: Maximum distance in the dataset (for normalization)

        Returns:
            Similarity score from 0 to 100
        """
        if max_distance == 0:
            return 100.0
        similarity = (1 - distance / max_distance) * 100
        return max(0.0, min(100.0, similarity))
