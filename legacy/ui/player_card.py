"""Player card component for displaying player stats."""

from typing import Dict, Any, Optional
import streamlit as st

from ..metrics.definitions import (
    METRIC_DEFINITIONS,
    BATTED_BALL_METRICS,
    PLATE_DISCIPLINE_METRICS,
    BATTED_BALL_PROFILE_METRICS,
)


class PlayerCard:
    """Renders a player card with stats."""

    def __init__(self, player_data: Dict[str, Any]):
        """
        Initialize the player card.

        Args:
            player_data: Dictionary containing player metrics and info
        """
        self.data = player_data

    def _format_metric(self, metric_name: str, value: Any) -> str:
        """Format a metric value for display."""
        if value is None or (isinstance(value, float) and str(value) == "nan"):
            return "—"

        if metric_name in METRIC_DEFINITIONS:
            definition = METRIC_DEFINITIONS[metric_name]
            try:
                formatted = definition.format_str.format(value)
                return f"{formatted}{definition.suffix}"
            except (ValueError, TypeError):
                return str(value)

        if isinstance(value, float):
            if metric_name == "xwoba":
                return f"{value:.3f}"
            return f"{value:.1f}"

        return str(value)

    def _get_display_name(self, metric_name: str) -> str:
        """Get the display name for a metric."""
        if metric_name in METRIC_DEFINITIONS:
            return METRIC_DEFINITIONS[metric_name].display_name
        return metric_name.replace("_", " ").title()

    def render(self, show_similarity: Optional[float] = None) -> None:
        """
        Render the player card.

        Args:
            show_similarity: Optional similarity score to display
        """
        name = self.data.get("name", "Unknown Player")
        season = self.data.get("season", "")

        st.markdown(f"### {name} ({season})")

        if show_similarity is not None:
            st.markdown(f"**Similarity: {show_similarity:.1f}%**")

        st.markdown("---")

        st.markdown("**Batted Ball Quality**")
        for metric in BATTED_BALL_METRICS:
            if metric in self.data:
                display_name = self._get_display_name(metric)
                formatted_value = self._format_metric(metric, self.data[metric])
                st.markdown(f"{display_name}: {formatted_value}")

        st.markdown("")
        st.markdown("**Plate Discipline**")
        for metric in PLATE_DISCIPLINE_METRICS:
            if metric in self.data:
                display_name = self._get_display_name(metric)
                formatted_value = self._format_metric(metric, self.data[metric])
                st.markdown(f"{display_name}: {formatted_value}")

        if any(m in self.data for m in BATTED_BALL_PROFILE_METRICS):
            st.markdown("")
            st.markdown("**Batted Ball Profile**")
            for metric in BATTED_BALL_PROFILE_METRICS:
                if metric in self.data:
                    display_name = self._get_display_name(metric)
                    formatted_value = self._format_metric(metric, self.data[metric])
                    st.markdown(f"{display_name}: {formatted_value}")

        if "xwoba" in self.data:
            st.markdown("")
            st.markdown("**Expected Stats**")
            formatted_xwoba = self._format_metric("xwoba", self.data["xwoba"])
            st.markdown(f"xwOBA: {formatted_xwoba}")


def render_player_card(
    player_data: Dict[str, Any], show_similarity: Optional[float] = None
) -> None:
    """Convenience function to render a player card."""
    card = PlayerCard(player_data)
    card.render(show_similarity)
