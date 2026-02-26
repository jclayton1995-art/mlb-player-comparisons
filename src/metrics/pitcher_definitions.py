"""Pitcher metric definitions and weights for similarity calculations."""

from dataclasses import dataclass
from typing import Dict, Set

from .definitions import MetricDefinition


PITCHER_METRIC_DEFINITIONS: Dict[str, MetricDefinition] = {
    "ip": MetricDefinition(
        name="ip",
        column="ip",
        weight=1.2,
        higher_is_better=True,
        display_name="IP",
        format_str="{:.1f}",
        suffix="",
    ),
    "k_pct": MetricDefinition(
        name="k_pct",
        column="k_pct",
        weight=1.0,
        higher_is_better=True,
        display_name="K%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "bb_pct": MetricDefinition(
        name="bb_pct",
        column="bb_pct",
        weight=1.0,
        higher_is_better=False,
        display_name="BB%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "k_bb_pct": MetricDefinition(
        name="k_bb_pct",
        column="k_bb_pct",
        weight=1.0,
        higher_is_better=True,
        display_name="K-BB%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "gb_pct": MetricDefinition(
        name="gb_pct",
        column="gb_pct",
        weight=0.8,
        higher_is_better=True,
        display_name="GB%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "xera": MetricDefinition(
        name="xera",
        column="xera",
        weight=0.5,
        higher_is_better=False,
        display_name="xERA",
        format_str="{:.2f}",
        suffix="",
    ),
    "xfip": MetricDefinition(
        name="xfip",
        column="xfip",
        weight=0.9,
        higher_is_better=False,
        display_name="xFIP",
        format_str="{:.2f}",
        suffix="",
    ),
    "barrel_pct_against": MetricDefinition(
        name="barrel_pct_against",
        column="barrel_pct_against",
        weight=1.0,
        higher_is_better=False,
        display_name="Barrel%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "hard_hit_pct_against": MetricDefinition(
        name="hard_hit_pct_against",
        column="hard_hit_pct_against",
        weight=0.9,
        higher_is_better=False,
        display_name="Hard Hit%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "stuff_plus": MetricDefinition(
        name="stuff_plus",
        column="stuff_plus",
        weight=0.8,
        higher_is_better=True,
        display_name="Stuff+",
        format_str="{:.0f}",
        suffix="",
    ),
    "lob_pct": MetricDefinition(
        name="lob_pct",
        column="lob_pct",
        weight=0.6,
        higher_is_better=True,
        display_name="LOB%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "babip": MetricDefinition(
        name="babip",
        column="babip",
        weight=0.5,
        higher_is_better=False,
        display_name="BABIP",
        format_str="{:.3f}",
        suffix="",
    ),
    "chase_pct": MetricDefinition(
        name="chase_pct",
        column="chase_pct",
        weight=0.8,
        higher_is_better=True,
        display_name="Chase%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "whiff_pct": MetricDefinition(
        name="whiff_pct",
        column="whiff_pct",
        weight=0.9,
        higher_is_better=True,
        display_name="Whiff%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "zone_pct": MetricDefinition(
        name="zone_pct",
        column="zone_pct",
        weight=0.7,
        higher_is_better=True,  # Neutral, but higher control
        display_name="Zone%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "zone_contact_pct": MetricDefinition(
        name="zone_contact_pct",
        column="zone_contact_pct",
        weight=0.8,
        higher_is_better=False,
        display_name="Z-Con%",
        format_str="{:.1f}",
        suffix="%",
    ),
    "arm_angle": MetricDefinition(
        name="arm_angle",
        column="arm_angle",
        weight=0.5,
        higher_is_better=False,  # Neutral — not directionally better
        display_name="Arm Angle",
        format_str="{:.1f}",
        suffix="°",
    ),
}

PITCHER_METRIC_WEIGHTS: Dict[str, float] = {
    metric.name: metric.weight for metric in PITCHER_METRIC_DEFINITIONS.values()
}

PITCHER_PRIMARY_METRICS = [
    "k_pct",
    "bb_pct",
    "k_bb_pct",
    "barrel_pct_against",
    "hard_hit_pct_against",
    "whiff_pct",
    "xfip",
    "chase_pct",
    "stuff_plus",
    "gb_pct",
    "zone_contact_pct",
    "zone_pct",
    "lob_pct",
    "babip",
    "xera",
    "ip",
    "arm_angle",
]

PITCHER_SANITY_CHECK_METRIC = "xera"
PITCHER_SANITY_CHECK_TOLERANCE = 0.50

# Metrics where lower values are better (for percentile calculations)
PITCHER_LOWER_IS_BETTER: Set[str] = {
    "bb_pct",
    "xera",
    "xfip",
    "barrel_pct_against",
    "hard_hit_pct_against",
    "babip",
    "zone_contact_pct",
}

# Metric groupings for display/analysis
STUFF_METRICS = [
    "k_pct",
    "whiff_pct",
    "chase_pct",
    "stuff_plus",
]

COMMAND_METRICS = [
    "bb_pct",
    "zone_pct",
    "arm_angle",
]

RESULTS_METRICS = [
    "xfip",
    "xera",
    "babip",
    "lob_pct",
]

CONTACT_QUALITY_METRICS = [
    "barrel_pct_against",
    "hard_hit_pct_against",
    "zone_contact_pct",
]

STYLE_METRICS = [
    "gb_pct",
]

VOLUME_METRICS = [
    "ip",
]

# Role classification threshold (starters have 100+ IP)
STARTER_IP_THRESHOLD = 100.0  # Legacy, kept for reference
STARTER_GS_RATIO = 0.5  # GS/G >= 0.5 → classified as starter
MIN_STARTER_COMP_IP = 80.0  # Minimum IP to be a valid starter comp candidate
