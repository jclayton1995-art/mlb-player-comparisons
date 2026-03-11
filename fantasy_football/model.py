"""Fantasy football prediction model for college WR prospects.

Uses a Gradient Boosting regressor trained on historical college WR data
to predict NFL fantasy output (PPR points per game).

Predicts three targets:
  - Year 1 PPR PPG (rookie season)
  - Best PPR PPG in first 3 NFL seasons
  - Overall ceiling tier (classification)
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

from fantasy_football.data import build_historical_dataset
from fantasy_football.features import FEATURE_COLUMNS, engineer_features


class WRProspectModel:
    """Predicts NFL fantasy output for college WR prospects."""

    def __init__(self):
        self.scaler = StandardScaler()
        self.model_year1 = None
        self.model_best = None
        self.is_trained = False
        self._cv_scores = {}

    def train(self) -> dict:
        """Train the model on historical data. Returns training metrics."""
        df = build_historical_dataset()
        df = engineer_features(df)

        X = df[FEATURE_COLUMNS].values
        y_year1 = df["nfl_year1_ppr_ppg"].values
        y_best = df["nfl_best_ppr_ppg"].values

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Train Year 1 model
        self.model_year1 = GradientBoostingRegressor(
            n_estimators=150,
            max_depth=3,
            learning_rate=0.08,
            min_samples_leaf=4,
            subsample=0.8,
            random_state=42,
        )
        self.model_year1.fit(X_scaled, y_year1)

        # Train Best Season model
        self.model_best = GradientBoostingRegressor(
            n_estimators=150,
            max_depth=3,
            learning_rate=0.08,
            min_samples_leaf=4,
            subsample=0.8,
            random_state=42,
        )
        self.model_best.fit(X_scaled, y_best)

        # Cross-validation scores
        cv_year1 = cross_val_score(
            self.model_year1, X_scaled, y_year1, cv=5, scoring="r2"
        )
        cv_best = cross_val_score(
            self.model_best, X_scaled, y_best, cv=5, scoring="r2"
        )

        self._cv_scores = {
            "year1_r2_mean": float(np.mean(cv_year1)),
            "year1_r2_std": float(np.std(cv_year1)),
            "best_r2_mean": float(np.mean(cv_best)),
            "best_r2_std": float(np.std(cv_best)),
        }

        self.is_trained = True
        return self._cv_scores

    def predict(self, prospects_df: pd.DataFrame) -> pd.DataFrame:
        """Predict fantasy output for prospect data.

        Args:
            prospects_df: Raw prospect data (same schema as training data,
                          minus NFL outcome columns).

        Returns:
            DataFrame with predictions added.
        """
        if not self.is_trained:
            self.train()

        df = engineer_features(prospects_df)
        X = df[FEATURE_COLUMNS].values
        X_scaled = self.scaler.transform(X)

        df = df.copy()
        df["pred_year1_ppg"] = np.clip(self.model_year1.predict(X_scaled), 0, 30)
        df["pred_best_ppg"] = np.clip(self.model_best.predict(X_scaled), 0, 30)

        # Fantasy tier classification based on predicted best PPG
        df["tier"] = df["pred_best_ppg"].apply(_classify_tier)

        # Historical comparison: find most similar historical WR
        df["comp_player"] = self._find_comps(df)

        return df

    def get_feature_importance(self) -> pd.DataFrame:
        """Return feature importance rankings from the best-season model."""
        if not self.is_trained:
            self.train()

        importance = self.model_best.feature_importances_
        fi_df = pd.DataFrame(
            {"feature": FEATURE_COLUMNS, "importance": importance}
        ).sort_values("importance", ascending=False)
        fi_df["importance_pct"] = (
            fi_df["importance"] / fi_df["importance"].sum() * 100
        )
        return fi_df

    def _find_comps(self, prospects_df: pd.DataFrame) -> list:
        """Find the most similar historical WR for each prospect."""
        hist_df = build_historical_dataset()
        hist_df = engineer_features(hist_df)

        hist_X = self.scaler.transform(hist_df[FEATURE_COLUMNS].values)
        prospect_X = self.scaler.transform(prospects_df[FEATURE_COLUMNS].values)

        comps = []
        for i in range(len(prospect_X)):
            distances = np.sqrt(
                np.sum((hist_X - prospect_X[i]) ** 2, axis=1)
            )
            closest_idx = np.argmin(distances)
            comp_name = hist_df.iloc[closest_idx]["name"]
            comp_best = hist_df.iloc[closest_idx]["nfl_best_ppr_ppg"]
            comps.append(f"{comp_name} ({comp_best:.1f} PPG)")
        return comps

    def get_cv_scores(self) -> dict:
        """Return cross-validation scores from training."""
        return self._cv_scores


def _classify_tier(ppg: float) -> str:
    """Classify a WR prospect into a fantasy tier based on predicted PPG."""
    if ppg >= 18.0:
        return "Elite (WR1)"
    elif ppg >= 14.0:
        return "Strong Starter (WR2)"
    elif ppg >= 10.0:
        return "Flex / WR3"
    elif ppg >= 6.0:
        return "Bench / Depth"
    else:
        return "Longshot"
