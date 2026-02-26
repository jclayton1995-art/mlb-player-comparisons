"""Metric definitions and weights for similarity calculations."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Set, List, Optional


class PlayerType(Enum):
    """Type of player for comparison."""
    BATTER = "batter"
    PITCHER = "pitcher"


@dataclass
class MetricDefinition:
    """Definition of a metric used in similarity calculations."""

    name: str
    column: str
    weight: float
    higher_is_better: bool
    display_name: str
    format_str: str = "{:.1f}"
    suffix: str = ""


METRIC_DEFINITIONS: Dict[str, MetricDefinition] = {
    "exit_velocity": MetricDefinition(
        name="exit_velocity",
        column="exit_velocity",
        weight=1.0,
        higher_is_better=True,
        display_name="Exit Velocity",
        format_str="{:.1f}",
        suffix=" mph",
    ),
    "max_exit_velocity": MetricDefinition(
        name="max_exit_velocity",
        column="max_exit_velocity",
        weight=0.8,
        higher_is_better=True,
        display_name="Max Exit Velocity",
        format_str="{:.1f}",
        suffix=" mph",
    ),
    "launch_angle": MetricDefinition(
        name="launch_angle",
        column="launch_angle",
        weight=0.7,
        higher_is_better=True,
        display_name="Launch Angle",
        format_str="{:.1f}",
        suffix="°",
    ),
    "barrel_pct": MetricDefinition(
        name="barrel_pct",
        column="barrel_pct",
        weight=1.0,
        higher_is_better=True,
        display_name="Barrel%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "hard_hit_pct": MetricDefinition(
        name="hard_hit_pct",
        column="hard_hit_pct",
        weight=0.9,
        higher_is_better=True,
        display_name="Hard Hit%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "pulled_fb_pct": MetricDefinition(
        name="pulled_fb_pct",
        column="pulled_fb_pct",
        weight=0.8,
        higher_is_better=True,
        display_name="Pulled FB%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "chase_rate": MetricDefinition(
        name="chase_rate",
        column="chase_rate",
        weight=0.9,
        higher_is_better=False,
        display_name="Chase Rate",
        format_str="{:.1f}",
        suffix="%",
    ),
    "whiff_pct": MetricDefinition(
        name="whiff_pct",
        column="whiff_pct",
        weight=0.9,
        higher_is_better=False,
        display_name="Whiff%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "swstr_pct": MetricDefinition(
        name="swstr_pct",
        column="swstr_pct",
        weight=0.8,
        higher_is_better=False,
        display_name="SwStr%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "k_pct": MetricDefinition(
        name="k_pct",
        column="k_pct",
        weight=0.8,
        higher_is_better=False,
        display_name="K%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "bb_pct": MetricDefinition(
        name="bb_pct",
        column="bb_pct",
        weight=0.8,
        higher_is_better=True,
        display_name="BB%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "zone_contact_pct": MetricDefinition(
        name="zone_contact_pct",
        column="zone_contact_pct",
        weight=0.8,
        higher_is_better=True,
        display_name="Z-Contact%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "gb_pct": MetricDefinition(
        name="gb_pct",
        column="gb_pct",
        weight=0.6,
        higher_is_better=True,
        display_name="GB%",
        format_str="{:.1f}",
        suffix="%",
    ),
}

METRIC_WEIGHTS: Dict[str, float] = {
    metric.name: metric.weight for metric in METRIC_DEFINITIONS.values()
}

PRIMARY_METRICS = [
    "exit_velocity",
    "max_exit_velocity",
    "launch_angle",
    "barrel_pct",
    "hard_hit_pct",
    "pulled_fb_pct",
    "chase_rate",
    "zone_contact_pct",
    "whiff_pct",
    "swstr_pct",
    "k_pct",
    "bb_pct",
    "gb_pct",
]

SANITY_CHECK_METRIC = "xwoba"
SANITY_CHECK_TOLERANCE = 0.030

BATTED_BALL_METRICS = [
    "exit_velocity",
    "max_exit_velocity",
    "launch_angle",
    "barrel_pct",
    "hard_hit_pct",
    "pulled_fb_pct",
]

PLATE_DISCIPLINE_METRICS = [
    "chase_rate",
    "zone_contact_pct",
    "whiff_pct",
    "swstr_pct",
    "k_pct",
    "bb_pct",
]

BATTED_BALL_PROFILE_METRICS = [
    "gb_pct",
]

# Lower is better metrics for batters (for percentile calculations)
BATTER_LOWER_IS_BETTER: Set[str] = {
    "chase_rate",
    "whiff_pct",
    "swstr_pct",
    "k_pct",
    "gb_pct",
}


@dataclass
class MetricConfig:
    """Configuration for player-type-specific metric settings."""

    player_type: PlayerType
    metric_definitions: Dict[str, MetricDefinition]
    metric_weights: Dict[str, float]
    primary_metrics: List[str]
    sanity_check_metric: str
    sanity_check_tolerance: float
    lower_is_better: Set[str]
    result_stats: List[str] = field(default_factory=list)

    @property
    def dataset_filename(self) -> str:
        """Get the parquet filename for this player type."""
        if self.player_type == PlayerType.BATTER:
            return "batters.parquet"
        return "pitchers.parquet"


def get_metric_config(player_type: PlayerType) -> MetricConfig:
    """
    Get the metric configuration for a player type.

    Args:
        player_type: BATTER or PITCHER

    Returns:
        MetricConfig with all settings for the player type
    """
    if player_type == PlayerType.BATTER:
        return MetricConfig(
            player_type=PlayerType.BATTER,
            metric_definitions=METRIC_DEFINITIONS,
            metric_weights=METRIC_WEIGHTS,
            primary_metrics=PRIMARY_METRICS,
            sanity_check_metric=SANITY_CHECK_METRIC,
            sanity_check_tolerance=SANITY_CHECK_TOLERANCE,
            lower_is_better=BATTER_LOWER_IS_BETTER,
            result_stats=["G", "PA", "AVG", "OBP", "SLG", "OPS", "wRC+"],
        )
    else:
        # Import pitcher definitions here to avoid circular imports
        from .pitcher_definitions import (
            PITCHER_METRIC_DEFINITIONS,
            PITCHER_METRIC_WEIGHTS,
            PITCHER_PRIMARY_METRICS,
            PITCHER_SANITY_CHECK_METRIC,
            PITCHER_SANITY_CHECK_TOLERANCE,
            PITCHER_LOWER_IS_BETTER,
        )
        return MetricConfig(
            player_type=PlayerType.PITCHER,
            metric_definitions=PITCHER_METRIC_DEFINITIONS,
            metric_weights=PITCHER_METRIC_WEIGHTS,
            primary_metrics=PITCHER_PRIMARY_METRICS,
            sanity_check_metric=PITCHER_SANITY_CHECK_METRIC,
            sanity_check_tolerance=PITCHER_SANITY_CHECK_TOLERANCE,
            lower_is_better=PITCHER_LOWER_IS_BETTER,
            result_stats=["G", "GS", "IP", "ERA", "W", "L", "K", "BB", "WHIP", "FIP", "WAR"],
        )
