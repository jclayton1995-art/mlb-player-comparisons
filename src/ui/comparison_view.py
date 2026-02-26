"""Side-by-side player cards with Squarespace-inspired light theme."""

from typing import Dict, Any, List
import streamlit as st
import streamlit.components.v1 as components


def get_percentile_color(percentile: float) -> str:
    """Get color based on percentile (red = good, blue = bad)."""
    if percentile >= 90:
        return "#dc2626"
    elif percentile >= 80:
        return "#ef4444"
    elif percentile >= 70:
        return "#f87171"
    elif percentile >= 60:
        return "#fca5a5"
    elif percentile >= 40:
        return "#9ca3af"
    elif percentile >= 30:
        return "#93c5fd"
    elif percentile >= 20:
        return "#60a5fa"
    elif percentile >= 10:
        return "#3b82f6"
    else:
        return "#2563eb"


def get_player_photo_url(mlbam_id: int) -> str:
    """Get Baseball Savant/MLB headshot URL for a player."""
    return f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{mlbam_id}/headshot/67/current"


# Batter metrics configuration
BATTER_METRICS_CONFIG = [
    ("exit_velocity", "Exit Velo", "{:.1f}", " mph"),
    ("max_exit_velocity", "Max EV", "{:.1f}", " mph"),
    ("barrel_pct", "Barrel %", "{:.1f}", "%"),
    ("hard_hit_pct", "Hard Hit %", "{:.1f}", "%"),
    ("pulled_fb_pct", "Pull Air %", "{:.1f}", "%"),
    ("xwoba", "xwOBA", "{:.3f}", ""),
    ("k_pct", "K %", "{:.1f}", "%"),
    ("bb_pct", "BB %", "{:.1f}", "%"),
    ("chase_rate", "Chase %", "{:.1f}", "%"),
    ("zone_contact_pct", "Z-Con %", "{:.1f}", "%"),
    ("whiff_pct", "Whiff %", "{:.1f}", "%"),
    ("swstr_pct", "SwStr %", "{:.1f}", "%"),
    ("gb_pct", "GB %", "{:.1f}", "%"),
]

# Pitcher metrics configuration
# Grouped: KPIs -> Ks -> Command -> Damage Control -> Luck
PITCHER_METRICS_CONFIG = [
    # KPIs
    ("xera", "xERA", "{:.2f}", ""),
    ("xfip", "xFIP", "{:.2f}", ""),
    ("k_bb_pct", "K-BB %", "{:.1f}", "%"),
    # Ks
    ("k_pct", "K %", "{:.1f}", "%"),
    ("whiff_pct", "Whiff %", "{:.1f}", "%"),
    ("chase_pct", "Chase %", "{:.1f}", "%"),
    ("zone_contact_pct", "Z-Con %", "{:.1f}", "%"),
    ("stuff_plus", "Stuff+", "{:.0f}", ""),
    # Command
    ("bb_pct", "BB %", "{:.1f}", "%"),
    ("zone_pct", "Zone %", "{:.1f}", "%"),
    ("arm_angle", "Arm Angle", "{:.1f}", "°"),
    # Damage Control
    ("hard_hit_pct_against", "Hard Hit %", "{:.1f}", "%"),
    ("barrel_pct_against", "Barrel %", "{:.1f}", "%"),
    ("gb_pct", "GB %", "{:.1f}", "%"),
    # Luck
    ("babip", "BABIP", "{:.3f}", ""),
    ("lob_pct", "LOB %", "{:.1f}", "%"),
]

# Batter results stats
BATTER_RESULTS_STATS = [
    ("G", "G", "{:.0f}"),
    ("PA", "PA", "{:.0f}"),
    ("AVG", "AVG", "{:.3f}"),
    ("OBP", "OBP", "{:.3f}"),
    ("SLG", "SLG", "{:.3f}"),
    ("OPS", "OPS", "{:.3f}"),
    ("wRC+", "wRC+", "{:.0f}"),
]

# Pitcher results stats
PITCHER_RESULTS_STATS = [
    ("G", "G", "{:.0f}"),
    ("GS", "GS", "{:.0f}"),
    ("IP", "IP", "{:.1f}"),
    ("ERA", "ERA", "{:.2f}"),
    ("W", "W", "{:.0f}"),
    ("L", "L", "{:.0f}"),
    ("K", "K", "{:.0f}"),
    ("BB", "BB", "{:.0f}"),
    ("WHIP", "WHIP", "{:.2f}"),
    ("FIP", "FIP", "{:.2f}"),
    ("WAR", "WAR", "{:.1f}"),
]


def render_player_card(
    player: Dict[str, Any],
    card_id: str = "",
    is_comp: bool = False,
    player_type: str = "Hitter",
) -> str:
    """Generate HTML for a player card."""
    name = player.get("name", "Unknown")
    season = player.get("season", "")
    mlbam_id = player.get("mlbam_id", 0)
    percentiles = player.get("percentiles", {})
    photo_url = get_player_photo_url(mlbam_id)

    # Different styling - target player gets blue header, comp gets light
    header_bg = "#fafafa" if is_comp else "#1e3a5f"
    header_border = "#e5e5e5" if is_comp else "#1e3a5f"
    name_color = "#000" if is_comp else "#fff"
    season_color = "#666" if is_comp else "#a0c4e8"
    label = "Best Match" if is_comp else "Your Player"
    label_color = "#999" if is_comp else "#a0c4e8"

    # Select metrics based on player type
    if player_type == "Pitcher":
        metrics_config = PITCHER_METRICS_CONFIG
    else:
        metrics_config = BATTER_METRICS_CONFIG

    rows_html = ""
    for metric_name, display_name, fmt, suffix in metrics_config:
        value = player.get(metric_name)
        pct = percentiles.get(f"{metric_name}_pct", 50)

        if value is None or str(value) == "nan":
            val_str = "—"
            pct = 50
        else:
            val_str = f"{fmt.format(value)}{suffix}"

        color = get_percentile_color(pct)

        rows_html += f"""
        <div class="stat-row">
            <span class="stat-name">{display_name}</span>
            <span class="stat-value">{val_str}</span>
            <div class="stat-bar">
                <div class="stat-bar-fill" style="width: {pct}%; background: {color};"></div>
            </div>
            <span class="stat-pct" style="background:{color};">{int(pct)}</span>
        </div>
        """

    return f"""
    <div class="player-card" id="{card_id}">
        <div class="card-top" style="background: {header_bg}; border-bottom-color: {header_border};">
            <div class="player-photo-wrapper">
                <img src="{photo_url}" class="player-photo" alt="{name}" onerror="this.style.display='none'">
            </div>
            <div class="player-info">
                <div class="card-label" style="color: {label_color};">{label}</div>
                <div class="player-name" style="color: {name_color};">{name}</div>
                <div class="player-season" style="color: {season_color};">{season}</div>
            </div>
        </div>
        <div class="card-stats">{rows_html}</div>
    </div>
    """


def render_results_section(player: Dict[str, Any], player_type: str = "Hitter") -> str:
    """Generate HTML for player results stats."""
    name = player.get("name", "Unknown")
    season = player.get("season", "")

    # Select stats based on player type
    if player_type == "Pitcher":
        stats = PITCHER_RESULTS_STATS
    else:
        stats = BATTER_RESULTS_STATS

    stats_html = ""
    for key, label, fmt in stats:
        value = player.get(key)
        if value is None or str(value) == "nan":
            val_str = "—"
        else:
            val_str = fmt.format(float(value))
        stats_html += f"""
        <div class="result-stat">
            <div class="result-label">{label}</div>
            <div class="result-value">{val_str}</div>
        </div>
        """

    return f"""
    <div class="results-card">
        <div class="results-header">{name} <span class="results-season">{season}</span></div>
        <div class="results-grid">{stats_html}</div>
    </div>
    """


def render_comparison(
    target_player: Dict[str, Any],
    similar_players: List[Dict[str, Any]],
    player_type: str = "Hitter",
) -> None:
    """Render full comparison view."""
    if not similar_players:
        st.warning("No similar players found.")
        return

    # Store similar players in session state for clickable cards
    if "similar_players" not in st.session_state:
        st.session_state.similar_players = similar_players
    else:
        st.session_state.similar_players = similar_players

    if "selected_comp_index" not in st.session_state:
        st.session_state.selected_comp_index = 0

    top = similar_players[st.session_state.selected_comp_index]
    score = top.get("similarity", 0)

    # Large similarity score display
    st.markdown(
        f"""
    <div style="text-align: center; padding: 0.5rem 0 1rem;">
        <div style="font-size: 0.65rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.2em; color: #999; margin-bottom: 0.25rem;">Similarity Score</div>
        <div style="font-family: 'DM Serif Display', serif; font-size: 5rem; font-weight: 400; color: #000; line-height: 1; letter-spacing: -0.02em;">{score:.1f}%</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Cards HTML
    left = render_player_card(
        target_player, "target-card", is_comp=False, player_type=player_type
    )
    right = render_player_card(
        top, "comp-card", is_comp=True, player_type=player_type
    )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet">
        <style>
            * {{ margin:0; padding:0; box-sizing:border-box; }}
            body {{
                font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
                background: transparent;
            }}
            .container {{
                display: flex;
                gap: 1.5rem;
                padding: 0.5rem 0;
            }}
            .card-column {{
                flex: 1;
                display: flex;
                flex-direction: column;
            }}
            .follow-banner {{
                text-align: center;
                font-size: 0.75rem;
                font-weight: 600;
                color: #666;
                margin-bottom: 0.5rem;
                letter-spacing: 0.02em;
            }}
            .follow-banner a {{
                color: #1e2a5a;
                text-decoration: none;
            }}
            .follow-banner a:hover {{
                text-decoration: underline;
            }}
            .player-card {{
                flex: 1;
                background: #fff;
                border: 1px solid #e5e5e5;
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 2px 8px rgba(0,0,0,0.04);
            }}
            .card-top {{
                background: #fafafa;
                padding: 1.25rem 1.5rem;
                border-bottom: 1px solid #e5e5e5;
                display: flex;
                align-items: center;
                gap: 1rem;
            }}
            .player-photo-wrapper {{
                width: 60px;
                height: 60px;
                border-radius: 50%;
                overflow: hidden;
                background: #f0f0f0;
                flex-shrink: 0;
                border: 2px solid #e5e5e5;
            }}
            .player-photo {{
                width: 100%;
                height: 100%;
                object-fit: cover;
            }}
            .player-info {{
                flex: 1;
            }}
            .player-name {{
                font-family: 'DM Serif Display', serif;
                font-size: 1.4rem;
                font-weight: 400;
                color: #000;
                letter-spacing: -0.02em;
            }}
            .card-label {{
                font-size: 0.65rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                margin-bottom: 0.2rem;
            }}
            .player-season {{
                font-size: 0.85rem;
                color: #666;
                margin-top: 0.1rem;
                font-weight: 500;
            }}
            .card-stats {{
                padding: 0.5rem 1.25rem 1rem;
            }}
            .stat-row {{
                display: flex;
                align-items: center;
                padding: 0.5rem 0;
                border-bottom: 1px solid #f0f0f0;
            }}
            .stat-row:last-child {{
                border-bottom: none;
            }}
            .stat-name {{
                width: 80px;
                font-size: 0.8rem;
                color: #666;
                font-weight: 500;
                flex-shrink: 0;
            }}
            .stat-value {{
                width: 70px;
                font-size: 0.85rem;
                font-weight: 600;
                color: #000;
                text-align: right;
                flex-shrink: 0;
            }}
            .stat-bar {{
                flex: 1;
                height: 8px;
                margin: 0 12px;
                background: #e5e5e5;
                border-radius: 4px;
                overflow: hidden;
            }}
            .stat-bar-fill {{
                height: 100%;
                border-radius: 4px;
                transition: width 0.3s ease;
            }}
            .stat-pct {{
                min-width: 36px;
                height: 24px;
                border-radius: 5px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 0.7rem;
                font-weight: 700;
                color: #fff;
                flex-shrink: 0;
            }}

            /* Mobile: stack cards, hide bars, compact layout */
            @media (max-width: 768px) {{
                .container {{
                    flex-direction: column;
                    gap: 1rem;
                }}
                .stat-bar {{
                    display: none;
                }}
                .stat-row {{
                    padding: 0.35rem 0;
                }}
                .stat-name {{
                    flex: 1;
                    width: auto;
                }}
                .stat-value {{
                    width: auto;
                    margin-right: 0.5rem;
                }}
                .card-stats {{
                    padding: 0.25rem 1rem 0.75rem;
                }}
                .player-name {{
                    font-size: 1.2rem;
                }}
                .card-top {{
                    padding: 1rem 1.25rem;
                }}
                .player-photo-wrapper {{
                    width: 48px;
                    height: 48px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card-column">
                <div class="follow-banner">Follow <a href="https://x.com/FungoMedia" target="_blank">@FungoMedia</a> on X/Twitter!</div>
                {left}
            </div>
            <div class="card-column">
                <div class="follow-banner">Follow <a href="https://x.com/FungoMedia" target="_blank">@FungoMedia</a> on X/Twitter!</div>
                {right}
            </div>
        </div>
    </body>
    </html>
    """

    # Adjust height based on number of metrics
    card_height = 750 if player_type == "Hitter" else 900
    components.html(html, height=card_height, scrolling=False)

    # Results stats section
    st.markdown(
        """
    <div style="margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid #f0f0f0;">
        <div style="font-family: 'DM Serif Display', serif; font-size: 1.25rem; color: #000; margin-bottom: 1rem; font-weight: 400;">Season Results</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    results_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet">
        <style>
            * {{ margin:0; padding:0; box-sizing:border-box; }}
            body {{
                font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
                background: transparent;
            }}
            .results-container {{
                display: flex;
                gap: 1.5rem;
            }}
            .results-card {{
                flex: 1;
                background: #fafafa;
                border-radius: 12px;
                padding: 1.25rem;
            }}
            .results-header {{
                font-weight: 600;
                color: #000;
                margin-bottom: 1rem;
                font-size: 0.95rem;
            }}
            .results-season {{
                color: #666;
                font-weight: 400;
            }}
            .results-grid {{
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
            }}
            .result-stat {{
                background: #fff;
                border: 1px solid #e5e5e5;
                border-radius: 8px;
                padding: 0.75rem 1rem;
                text-align: center;
                min-width: 70px;
            }}
            .result-label {{
                font-size: 0.7rem;
                color: #999;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 0.25rem;
            }}
            .result-value {{
                font-size: 1.1rem;
                font-weight: 700;
                color: #000;
            }}
        </style>
    </head>
    <body>
        <div class="results-container">
            {render_results_section(target_player, player_type)}
            {render_results_section(top, player_type)}
        </div>
    </body>
    </html>
    """

    # Adjust height based on player type (pitchers have more stats that wrap)
    results_height = 140 if player_type == "Hitter" else 240
    components.html(results_html, height=results_height, scrolling=False)

    # Other similar players (clickable)
    if len(similar_players) > 1:
        st.markdown(
            """
        <div style="margin-top: 2rem; padding-top: 2rem; border-top: 1px solid #f0f0f0;">
            <div style="font-family: 'DM Serif Display', serif; font-size: 1.25rem; color: #000; margin-bottom: 1.5rem; font-weight: 400;">Other Similar Seasons</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # Create columns for clickable cards
        cols = st.columns(min(5, len(similar_players) - 1))

        for i, p in enumerate(similar_players[1:6], 1):
            col_idx = i - 1
            with cols[col_idx]:
                player_name = p.get("name", "Unknown")
                player_season = p.get("season", "")
                sim_score = p.get("similarity", 0)

                # Use a button to make it clickable
                if st.button(
                    f"**{player_name}**\n{player_season}\n{sim_score:.1f}%",
                    key=f"comp_{i}",
                    use_container_width=True,
                ):
                    st.session_state.selected_comp_index = i
                    st.rerun()
