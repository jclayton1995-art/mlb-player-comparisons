"""Feature engineering for college WR -> NFL fantasy football prediction.

Transforms raw college stats and athletic measurables into model-ready features.
Key feature categories:
  1. College production (per-game rates, efficiency)
  2. Athletic profile (speed, explosiveness, agility scores)
  3. Draft capital (round/pick value)
  4. Physical profile (size-speed composite)
  5. Breakout age / early declare signal
"""

import pandas as pd
import numpy as np


# Feature columns used by the model (order matters for training)
FEATURE_COLUMNS = [
    "rec_per_game",
    "rec_yds_per_game",
    "rec_td_per_game",
    "college_ypr",
    "college_target_share",
    "college_dom_rating",
    "college_ypc",
    "draft_value",
    "speed_score",
    "height_adj_speed",
    "burst_score",
    "agility_score",
    "bmi",
    "breakout_age",
    "bench_press",
]


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Transform raw prospect data into model features.

    Args:
        df: Raw prospect data with college stats and measurables.

    Returns:
        DataFrame with engineered feature columns added.
    """
    out = df.copy()

    # Per-game college production
    out["rec_per_game"] = out["college_rec"] / out["college_games"]
    out["rec_yds_per_game"] = out["college_rec_yds"] / out["college_games"]
    out["rec_td_per_game"] = out["college_rec_td"] / out["college_games"]

    # Draft value: higher for earlier picks (logarithmic decay)
    out["draft_value"] = _draft_pick_value(out["draft_pick"])

    # Athletic composites
    out["speed_score"] = _speed_score(out["weight_lbs"], out["forty_yard"])
    out["height_adj_speed"] = _height_adjusted_speed(
        out["height_inches"], out["forty_yard"]
    )
    out["burst_score"] = _burst_score(out["vertical_jump"], out["broad_jump"])
    out["agility_score"] = _agility_score(out["three_cone"], out["shuttle"])

    # BMI (body mass index as a size proxy)
    out["bmi"] = (out["weight_lbs"] * 703) / (out["height_inches"] ** 2)

    return out


def _draft_pick_value(picks: pd.Series) -> pd.Series:
    """Convert draft pick number to a value score.

    Uses the classic Jimmy Johnson trade value chart concept
    scaled to a 0-100 range. Pick 1 ~ 100, pick 256 ~ 1.
    """
    return 100 * np.exp(-0.018 * (picks - 1))


def _speed_score(weight: pd.Series, forty: pd.Series) -> pd.Series:
    """Bill Kelley's Speed Score: (weight * 200) / (forty_time ^ 4).

    Adjusts raw 40 time for player weight. Heavier players who run
    fast score higher.
    """
    return (weight * 200) / (forty**4)


def _height_adjusted_speed(height: pd.Series, forty: pd.Series) -> pd.Series:
    """Height-adjusted speed: taller players who run fast are more rare.

    Score = height_inches / forty_time.
    """
    return height / forty


def _burst_score(vertical: pd.Series, broad: pd.Series) -> pd.Series:
    """Explosiveness composite from vertical and broad jump.

    Standardizes both to a common scale and averages.
    Vertical: mean ~36, std ~3; Broad: mean ~125, std ~5
    """
    vert_z = (vertical - 36.0) / 3.0
    broad_z = (broad - 125.0) / 5.0
    return (vert_z + broad_z) / 2.0


def _agility_score(three_cone: pd.Series, shuttle: pd.Series) -> pd.Series:
    """Agility composite from 3-cone and shuttle.

    Lower times are better, so we invert (negate z-scores).
    3-cone: mean ~6.90, std ~0.15; Shuttle: mean ~4.15, std ~0.10
    """
    tc_z = -(three_cone - 6.90) / 0.15
    sh_z = -(shuttle - 4.15) / 0.10
    return (tc_z + sh_z) / 2.0


def get_feature_descriptions() -> dict:
    """Return human-readable descriptions of each feature."""
    return {
        "rec_per_game": "Receptions per game in final college season",
        "rec_yds_per_game": "Receiving yards per game in final college season",
        "rec_td_per_game": "Receiving TDs per game in final college season",
        "college_ypr": "Yards per reception (college)",
        "college_target_share": "Share of team pass targets",
        "college_dom_rating": "Dominator rating (% of team receiving production)",
        "college_ypc": "Yards per catch (college)",
        "draft_value": "Draft capital value (higher = earlier pick)",
        "speed_score": "Weight-adjusted 40-yard dash (Bill Kelley)",
        "height_adj_speed": "Height / 40-time ratio",
        "burst_score": "Vertical + broad jump composite",
        "agility_score": "3-cone + shuttle composite (inverted)",
        "bmi": "Body mass index (size proxy)",
        "breakout_age": "Age of first major college production",
        "bench_press": "Bench press reps at 225 lbs",
    }
