"""Pitch Model comparison view — per-pitch-type similarity UI."""

from typing import Dict, List, Any
import streamlit as st
import streamlit.components.v1 as components

from .comparison_view import get_player_photo_url


# Metrics shown in the arsenal overview table
OVERVIEW_METRICS = [
    ("avg_velo", "Velo", "{:.1f}"),
    ("avg_ivb", "IVB", "{:.1f}"),
    ("avg_ihb", "IHB", "{:.1f}"),
    ("avg_spin", "Spin", "{:.0f}"),
    ("stuff_plus", "Stf+", "{:.0f}"),
]

# Full comp card metrics for the detailed section
COMP_METRICS = [
    ("avg_velo", "Velo", "{:.1f}", " mph"),
    ("avg_ivb", "IVB", "{:.1f}", '"'),
    ("avg_ihb", "IHB", "{:.1f}", '"'),
    ("avg_spin", "Spin", "{:.0f}", ""),
    ("stuff_plus", "Stf+", "{:.0f}", ""),
    ("whiff_pct", "Whiff%", "{:.1f}", "%"),
    ("chase_pct", "Chase%", "{:.1f}", "%"),
    ("zone_pct", "Zone%", "{:.1f}", "%"),
]


def _format_val(value, fmt, suffix=""):
    """Format a metric value or return dash if missing."""
    if value is None or str(value) == "nan":
        return "—"
    return f"{fmt.format(value)}{suffix}"


def _render_arsenal_overview(
    pitcher_info: Dict[str, Any],
    pitches: List[Dict[str, Any]],
    similar_pitches: Dict[str, List[Dict[str, Any]]],
) -> None:
    """Render the screenshot-friendly arsenal overview card."""
    name = pitcher_info.get("name", "Unknown")
    season = pitcher_info.get("season", "")
    mlbam_id = pitcher_info.get("mlbam_id", 0)
    arm_angle = pitcher_info.get("arm_angle")
    photo_url = get_player_photo_url(mlbam_id)

    arm_angle_str = f"Arm Angle: {arm_angle:.1f}°" if arm_angle else ""
    separator = "  ·  " if arm_angle else ""

    # Build pitch rows
    pitch_rows_html = ""
    for pitch in pitches:
        pt = pitch.get("pitch_type", "")
        pn = pitch.get("pitch_name", pt)

        # Metric cells
        metric_cells = ""
        for metric, _, fmt in OVERVIEW_METRICS:
            val = pitch.get(metric)
            metric_cells += f'<td class="ar-metric">{_format_val(val, fmt)}</td>'

        # Comp line with photo, name, and their stats
        matches = similar_pitches.get(pt, [])
        comp_html = ""
        if matches:
            m = matches[0]
            comp_name = m.get("name", "Unknown")
            comp_season = m.get("season", "")
            similarity = m.get("similarity", 0)
            comp_mlbam = m.get("mlbam_id", 0)
            comp_photo = get_player_photo_url(comp_mlbam)

            # Comp's stats in the same columns
            comp_metric_cells = ""
            for metric, _, fmt in OVERVIEW_METRICS:
                val = m.get(metric)
                comp_metric_cells += f'<td class="ar-comp-metric">{_format_val(val, fmt)}</td>'

            comp_html = f"""
            <tr class="ar-comp-row">
                <td class="ar-comp-sim-cell"><span class="ar-comp-sim">{similarity:.1f}%</span></td>
                <td class="ar-comp-name-cell">
                    <div class="ar-comp-info">
                        <img src="{comp_photo}" class="ar-comp-photo" onerror="this.style.display='none'">
                        <span class="ar-comp-name">{comp_name}</span>
                        <span class="ar-comp-season">{comp_season}</span>
                    </div>
                </td>
                {comp_metric_cells}
            </tr>
            """

        pitch_rows_html += f"""
        <tr class="ar-pitch-row">
            <td class="ar-badge-cell"><span class="ar-badge">{pt}</span></td>
            <td class="ar-name-cell">{pn}</td>
            {metric_cells}
        </tr>
        {comp_html}
        """

    # Build metric header cells
    metric_headers = ""
    for _, label, _ in OVERVIEW_METRICS:
        metric_headers += f'<th class="ar-metric-header">{label}</th>'

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
            .arsenal-card {{
                background: #fff;
                border: 1px solid #e0e0e0;
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 2px 12px rgba(0,0,0,0.06);
                max-width: 680px;
                margin: 0 auto;
            }}
            .arsenal-header {{
                background: #1e3a5f;
                padding: 1.25rem 1.5rem;
                display: flex;
                align-items: center;
                gap: 1rem;
            }}
            .arsenal-photo {{
                width: 60px;
                height: 60px;
                border-radius: 50%;
                overflow: hidden;
                background: #2a4a6f;
                flex-shrink: 0;
                border: 2px solid #3a5a7f;
            }}
            .arsenal-photo img {{
                width: 100%;
                height: 100%;
                object-fit: cover;
            }}
            .arsenal-info {{
                flex: 1;
            }}
            .arsenal-label {{
                font-size: 0.65rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                color: #a0c4e8;
                margin-bottom: 0.15rem;
            }}
            .arsenal-name {{
                font-family: 'DM Serif Display', serif;
                font-size: 1.4rem;
                color: #fff;
                letter-spacing: -0.02em;
            }}
            .arsenal-meta {{
                font-size: 0.85rem;
                color: #a0c4e8;
                font-weight: 500;
            }}

            /* Arsenal table */
            .arsenal-table {{
                width: 100%;
                border-collapse: collapse;
            }}
            .ar-header-row th {{
                padding: 0.6rem 0.5rem 0.4rem;
                font-size: 0.65rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                color: #999;
                border-bottom: 1px solid #eee;
            }}
            .ar-header-row th:first-child {{
                padding-left: 1.25rem;
            }}
            .ar-metric-header {{
                text-align: right;
                width: 60px;
            }}
            .ar-pitch-row td {{
                padding: 0.55rem 0.5rem;
                border-bottom: none;
                vertical-align: middle;
            }}
            .ar-pitch-row td:first-child {{
                padding-left: 1.25rem;
                width: 50px;
            }}
            .ar-badge {{
                background: #1e3a5f;
                color: #fff;
                font-size: 0.65rem;
                font-weight: 700;
                padding: 0.2rem 0.45rem;
                border-radius: 4px;
                letter-spacing: 0.05em;
                white-space: nowrap;
            }}
            .ar-name-cell {{
                font-size: 0.85rem;
                font-weight: 500;
                color: #444;
                padding-left: 0.25rem !important;
            }}
            .ar-metric {{
                text-align: right;
                font-size: 0.85rem;
                font-weight: 600;
                color: #222;
                font-variant-numeric: tabular-nums;
                width: 60px;
            }}
            .ar-comp-row td {{
                padding: 0.1rem 0.5rem 0.65rem;
                border-bottom: 1px solid #f0f0f0;
            }}
            .ar-comp-row td:first-child {{
                padding-left: 1.25rem;
            }}
            .ar-comp-sim-cell {{
                padding-left: 1.25rem;
                width: 50px;
                vertical-align: middle;
            }}
            .ar-comp-sim {{
                font-size: 0.7rem;
                font-weight: 700;
                color: #1e3a5f;
                white-space: nowrap;
            }}
            .ar-comp-info {{
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }}
            .ar-comp-photo {{
                width: 28px;
                height: 28px;
                border-radius: 50%;
                object-fit: cover;
                background: #f0f0f0;
                border: 1px solid #e0e0e0;
                flex-shrink: 0;
            }}
            .ar-comp-name {{
                font-size: 0.85rem;
                font-weight: 700;
                color: #1e3a5f;
            }}
            .ar-comp-season {{
                font-size: 0.75rem;
                color: #999;
                font-weight: 500;
            }}
            .ar-comp-metric {{
                text-align: right;
                font-size: 0.78rem;
                font-weight: 500;
                color: #999;
                font-variant-numeric: tabular-nums;
                width: 60px;
            }}
            /* Last comp row: no bottom border */
            .arsenal-table tr.ar-comp-row:last-child td,
            .arsenal-table tr.ar-pitch-row:last-child td {{
                border-bottom: none;
            }}
        </style>
    </head>
    <body>
        <div class="follow-banner">Follow <a href="https://x.com/FungoMedia" target="_blank">@FungoMedia</a> on X/Twitter!</div>
        <div class="arsenal-card">
            <div class="arsenal-header">
                <div class="arsenal-photo">
                    <img src="{photo_url}" alt="{name}" onerror="this.style.display='none'">
                </div>
                <div class="arsenal-info">
                    <div class="arsenal-label">Pitch Arsenal</div>
                    <div class="arsenal-name">{name}</div>
                    <div class="arsenal-meta">{season}{separator}{arm_angle_str}</div>
                </div>
            </div>
            <table class="arsenal-table">
                <tr class="ar-header-row">
                    <th></th>
                    <th style="text-align:left;">Pitch</th>
                    {metric_headers}
                </tr>
                {pitch_rows_html}
            </table>
        </div>
    </body>
    </html>
    """

    n_pitches = len(pitches)
    height = 150 + n_pitches * 90
    components.html(html, height=height, scrolling=False)


def _render_detailed_comps(
    pitches: List[Dict[str, Any]],
    similar_pitches: Dict[str, List[Dict[str, Any]]],
) -> None:
    """Render detailed comparison cards — one row per pitch, up to 4 comps across."""
    pitch_sections_html = ""
    for pitch in pitches:
        pt = pitch.get("pitch_type", "")
        pn = pitch.get("pitch_name", pt)
        matches = similar_pitches.get(pt, [])
        if not matches:
            continue

        # Build comp cards for this pitch type (up to 4)
        cards_html = ""
        for match in matches[:4]:
            match_name = match.get("name", "Unknown")
            match_season = match.get("season", "")
            similarity = match.get("similarity", 0)
            match_mlbam = match.get("mlbam_id", 0)
            photo_url = get_player_photo_url(match_mlbam)

            # Build metric rows
            metrics_html = ""
            for metric, label, fmt, suffix in COMP_METRICS:
                target_val = pitch.get(metric)
                match_val = match.get(metric)
                t_str = _format_val(target_val, fmt, suffix)
                m_str = _format_val(match_val, fmt, suffix)
                metrics_html += f"""
                <div class="dc-metric-row">
                    <span class="dc-metric-label">{label}</span>
                    <span class="dc-metric-val dc-target">{t_str}</span>
                    <span class="dc-metric-arrow">→</span>
                    <span class="dc-metric-val dc-match">{m_str}</span>
                </div>
                """

            cards_html += f"""
            <div class="dc-card">
                <div class="dc-match-info">
                    <img src="{photo_url}" class="dc-photo" onerror="this.style.display='none'">
                    <div class="dc-match-details">
                        <div class="dc-match-name">{match_name}</div>
                        <div class="dc-match-season">{match_season}</div>
                    </div>
                    <span class="dc-similarity">{similarity:.1f}%</span>
                </div>
                <div class="dc-header-labels">
                    <span class="dc-hl-spacer"></span>
                    <span class="dc-hl-label">Target</span>
                    <span class="dc-hl-spacer-sm"></span>
                    <span class="dc-hl-label">Comp</span>
                </div>
                <div class="dc-metrics">{metrics_html}</div>
            </div>
            """

        pitch_sections_html += f"""
        <div class="dc-pitch-section">
            <div class="dc-pitch-header">
                <span class="dc-badge">{pt}</span>
                <span class="dc-pitch-name">{pn}</span>
            </div>
            <div class="dc-row">
                {cards_html}
            </div>
        </div>
        """

    if not pitch_sections_html:
        return

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
            .dc-pitch-section {{
                margin-bottom: 1.25rem;
            }}
            .dc-pitch-header {{
                display: flex;
                align-items: center;
                gap: 0.5rem;
                margin-bottom: 0.6rem;
            }}
            .dc-badge {{
                background: #1e3a5f;
                color: #fff;
                font-size: 0.65rem;
                font-weight: 700;
                padding: 0.2rem 0.45rem;
                border-radius: 4px;
                letter-spacing: 0.05em;
            }}
            .dc-pitch-name {{
                font-weight: 600;
                font-size: 0.95rem;
                color: #333;
            }}
            .dc-row {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 0.75rem;
            }}
            .dc-card {{
                background: #fff;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                padding: 0.85rem 1rem;
                box-shadow: 0 2px 8px rgba(0,0,0,0.04);
            }}
            .dc-match-info {{
                display: flex;
                align-items: center;
                gap: 0.6rem;
                margin-bottom: 0.65rem;
                padding-bottom: 0.55rem;
                border-bottom: 1px solid #f0f0f0;
            }}
            .dc-photo {{
                width: 36px;
                height: 36px;
                border-radius: 50%;
                object-fit: cover;
                background: #f0f0f0;
                border: 1px solid #e5e5e5;
                flex-shrink: 0;
            }}
            .dc-match-details {{
                flex: 1;
                min-width: 0;
            }}
            .dc-match-name {{
                font-weight: 600;
                font-size: 0.82rem;
                color: #000;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .dc-match-season {{
                font-size: 0.72rem;
                color: #666;
            }}
            .dc-similarity {{
                font-family: 'DM Serif Display', serif;
                font-size: 1rem;
                color: #1e3a5f;
                flex-shrink: 0;
            }}
            .dc-header-labels {{
                display: flex;
                align-items: center;
                margin-bottom: 0.2rem;
            }}
            .dc-hl-spacer {{
                width: 48px;
                flex-shrink: 0;
            }}
            .dc-hl-spacer-sm {{
                width: 24px;
                flex-shrink: 0;
            }}
            .dc-hl-label {{
                width: 58px;
                text-align: right;
                font-size: 0.6rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                color: #aaa;
                flex-shrink: 0;
            }}
            .dc-metrics {{
                display: flex;
                flex-direction: column;
                gap: 0.1rem;
            }}
            .dc-metric-row {{
                display: flex;
                align-items: center;
                font-size: 0.75rem;
                padding: 0.12rem 0;
            }}
            .dc-metric-label {{
                width: 48px;
                color: #999;
                font-weight: 500;
                flex-shrink: 0;
            }}
            .dc-metric-val {{
                width: 58px;
                text-align: right;
                font-weight: 600;
                flex-shrink: 0;
                font-variant-numeric: tabular-nums;
            }}
            .dc-target {{
                color: #666;
            }}
            .dc-match {{
                color: #000;
            }}
            .dc-metric-arrow {{
                width: 24px;
                text-align: center;
                color: #ccc;
                flex-shrink: 0;
            }}
        </style>
    </head>
    <body>
        {pitch_sections_html}
    </body>
    </html>
    """

    n_sections = sum(1 for p in pitches if similar_pitches.get(p.get("pitch_type", "")))
    height = n_sections * 340
    components.html(html, height=height, scrolling=True)


def render_pitch_model(
    pitcher_info: Dict[str, Any],
    pitches: List[Dict[str, Any]],
    similar_pitches: Dict[str, List[Dict[str, Any]]],
) -> None:
    """
    Render the full Pitch Model comparison view.

    Args:
        pitcher_info: Dict with name, season, arm_angle, mlbam_id
        pitches: List of dicts (one per pitch type) with metrics
        similar_pitches: Dict mapping pitch_type -> list of best matches
    """
    if not pitches:
        st.warning("No pitch data available for this pitcher/season.")
        return

    # Section 1: Screenshot-friendly arsenal overview
    _render_arsenal_overview(pitcher_info, pitches, similar_pitches)

    # Section 2: Detailed comparisons
    st.markdown("### Detailed Comparisons")
    _render_detailed_comps(pitches, similar_pitches)
