"""Pitch model metric definitions and weights for per-pitch similarity."""

from typing import Dict

from .definitions import MetricDefinition


PITCH_METRIC_DEFINITIONS: Dict[str, MetricDefinition] = {
    "avg_velo": MetricDefinition(
        name="avg_velo",
        column="avg_velo",
        weight=1.0,
        higher_is_better=True,
        display_name="Velocity",
        format_str="{:.1f}",
        suffix=" mph",
    ),
    "avg_ivb": MetricDefinition(
        name="avg_ivb",
        column="avg_ivb",
        weight=0.9,
        higher_is_better=True,  # Neutral — varies by pitch type
        display_name="IVB",
        format_str="{:.1f}",
        suffix='"',
    ),
    "avg_ihb": MetricDefinition(
        name="avg_ihb",
        column="avg_ihb",
        weight=0.9,
        higher_is_better=True,  # Neutral — varies by pitch type
        display_name="IHB",
        format_str="{:.1f}",
        suffix='"',
    ),
    "avg_spin": MetricDefinition(
        name="avg_spin",
        column="avg_spin",
        weight=0.7,
        higher_is_better=True,
        display_name="Spin",
        format_str="{:.0f}",
        suffix=" rpm",
    ),
    "stuff_plus": MetricDefinition(
        name="stuff_plus",
        column="stuff_plus",
        weight=1.0,
        higher_is_better=True,
        display_name="Stuff+",
        format_str="{:.0f}",
        suffix="",
    ),
    "whiff_pct": MetricDefinition(
        name="whiff_pct",
        column="whiff_pct",
        weight=1.0,
        higher_is_better=True,
        display_name="Whiff%",
        format_str="{:.1f}",
        suffix="%",
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
    "zone_pct": MetricDefinition(
        name="zone_pct",
        column="zone_pct",
        weight=0.6,
        higher_is_better=True,
        display_name="Zone%",
        format_str="{:.1f}",
        suffix="%",
    ),
}

PITCH_METRIC_WEIGHTS: Dict[str, float] = {
    metric.name: metric.weight for metric in PITCH_METRIC_DEFINITIONS.values()
}

# Metrics used for similarity comparison (xSLG/xwOBA excluded — too noisy per pitch type)
PITCH_COMPARISON_METRICS = [
    "avg_velo",
    "avg_ivb",
    "avg_ihb",
    "avg_spin",
    "stuff_plus",
    "whiff_pct",
    "chase_pct",
    "zone_pct",
]

# Metrics where lower is better (for percentile display)
PITCH_LOWER_IS_BETTER: set = set()

MIN_PITCHES = 50       # Minimum to include a pitch type in the dataset (lookups)
MIN_COMP_PITCHES = 100  # Minimum for a pitch type to be a valid comp candidate
