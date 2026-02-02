"""Metric definitions and weights for similarity calculations."""

from dataclasses import dataclass
from typing import Dict


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
