"""Z-score normalization for metrics."""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np


class MetricNormalizer:
    """Handles z-score normalization of metrics across the dataset."""

    def __init__(self):
        self._means: Dict[str, float] = {}
        self._stds: Dict[str, float] = {}
        self._fitted = False

    def fit(self, df: pd.DataFrame, columns: List[str]) -> "MetricNormalizer":
        """
        Compute means and standard deviations for normalization.

        Args:
            df: DataFrame containing the data
            columns: List of column names to normalize

        Returns:
            self for method chaining
        """
        for col in columns:
            if col in df.columns:
                col_data = df[col].dropna()
                self._means[col] = col_data.mean()
                self._stds[col] = col_data.std()
                if self._stds[col] == 0:
                    self._stds[col] = 1.0

        self._fitted = True
        return self

    def transform(
        self, df: pd.DataFrame, columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Apply z-score normalization to the specified columns.

        Args:
            df: DataFrame to transform
            columns: List of columns to normalize (defaults to all fitted columns)

        Returns:
            DataFrame with normalized columns (suffixed with '_z')
        """
        if not self._fitted:
            raise ValueError("Normalizer must be fitted before transforming")

        result = df.copy()
        cols_to_transform = columns or list(self._means.keys())

        for col in cols_to_transform:
            if col in df.columns and col in self._means:
                z_col = f"{col}_z"
                result[z_col] = (df[col] - self._means[col]) / self._stds[col]

        return result

    def fit_transform(
        self, df: pd.DataFrame, columns: List[str]
    ) -> pd.DataFrame:
        """Fit and transform in one step."""
        self.fit(df, columns)
        return self.transform(df, columns)

    def get_z_score(self, column: str, value: float) -> float:
        """Get z-score for a single value."""
        if column not in self._means:
            raise ValueError(f"Column {column} not fitted")
        return (value - self._means[column]) / self._stds[column]

    def get_stats(self, column: str) -> Dict[str, float]:
        """Get mean and std for a column."""
        if column not in self._means:
            raise ValueError(f"Column {column} not fitted")
        return {"mean": self._means[column], "std": self._stds[column]}

    @property
    def fitted_columns(self) -> List[str]:
        """Return list of fitted column names."""
        return list(self._means.keys())
