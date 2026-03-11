"""Streamlit UI for college WR fantasy football prediction model."""

import streamlit as st
import pandas as pd
import numpy as np

from src.football.model import WRProspectModel
from src.football.data import get_sample_prospects
from src.football.features import get_feature_descriptions, FEATURE_COLUMNS


TIER_COLORS = {
    "Elite (WR1)": "#2ecc40",
    "Strong Starter (WR2)": "#0074d9",
    "Flex / WR3": "#ff851b",
    "Bench / Depth": "#aaaaaa",
    "Longshot": "#ff4136",
}


def render_football_predictions():
    """Render the full fantasy football WR prediction page."""

    # Train model (cached)
    model = _get_trained_model()

    # --- Input mode selector ---
    input_mode = st.radio(
        "Prospect Input",
        options=["2025 Draft Class", "Custom Prospect"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if input_mode == "2025 Draft Class":
        prospects = get_sample_prospects()
        predictions = _cached_predict(model, "2025_class")

        st.markdown("""
        <div style="text-align: center; margin-bottom: 1.5rem;">
            <div style="font-size: 0.8rem; color: #999; text-transform: uppercase; letter-spacing: 0.15em;">
                2025 Draft Class Predictions
            </div>
        </div>
        """, unsafe_allow_html=True)

        _render_predictions_table(predictions)
        _render_detailed_cards(predictions)

    else:
        _render_custom_prospect_form(model)

    # --- Feature Importance ---
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; margin: 1.5rem 0;">
        <div style="font-family: 'DM Serif Display', serif; font-size: 1.25rem;">
            What Drives the Model?
        </div>
    </div>
    """, unsafe_allow_html=True)

    _render_feature_importance(model)


@st.cache_resource
def _get_trained_model() -> WRProspectModel:
    """Train and cache the WR prospect model."""
    model = WRProspectModel()
    model.train()
    return model


@st.cache_data
def _cached_predict(_model, cache_key: str) -> pd.DataFrame:
    """Cache predictions for the default prospect set."""
    prospects = get_sample_prospects()
    return _model.predict(prospects)


def _render_predictions_table(predictions: pd.DataFrame):
    """Render the summary predictions table."""
    display_cols = [
        "name", "college", "draft_round", "draft_pick",
        "pred_year1_ppg", "pred_best_ppg", "tier", "comp_player",
    ]
    display_df = predictions[display_cols].copy()
    display_df.columns = [
        "Player", "College", "Rd", "Pick",
        "Yr 1 PPG", "Best PPG", "Tier", "Closest Comp",
    ]
    display_df = display_df.sort_values("Best PPG", ascending=False).reset_index(
        drop=True
    )
    display_df.index = display_df.index + 1
    display_df.index.name = "Rank"

    # Format floats
    display_df["Yr 1 PPG"] = display_df["Yr 1 PPG"].map("{:.1f}".format)
    display_df["Best PPG"] = display_df["Best PPG"].map("{:.1f}".format)

    # Build HTML table
    html = '<div style="max-width: 900px; margin: 0 auto; overflow-x: auto;">'
    html += '<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">'
    html += '<thead><tr style="border-bottom: 2px solid #000;">'
    html += '<th style="padding: 0.5rem; text-align: left; font-weight: 600;">#</th>'
    for col in display_df.columns:
        align = "left" if col in ("Player", "College", "Tier", "Closest Comp") else "center"
        html += f'<th style="padding: 0.5rem; text-align: {align}; font-weight: 600;">{col}</th>'
    html += "</tr></thead><tbody>"

    for idx, row in display_df.iterrows():
        tier = row["Tier"]
        tier_color = TIER_COLORS.get(tier, "#666")
        html += f'<tr style="border-bottom: 1px solid #eee;">'
        html += f'<td style="padding: 0.5rem; font-weight: 600;">{idx}</td>'
        for col in display_df.columns:
            val = row[col]
            align = "left" if col in ("Player", "College", "Tier", "Closest Comp") else "center"
            style = f"padding: 0.5rem; text-align: {align};"
            if col == "Tier":
                style += f" color: {tier_color}; font-weight: 600;"
            if col == "Player":
                style += " font-weight: 600;"
            if col == "Best PPG":
                style += " font-weight: 700; font-family: 'DM Serif Display', serif; font-size: 1rem;"
            html += f'<td style="{style}">{val}</td>'
        html += "</tr>"

    html += "</tbody></table></div>"
    st.markdown(html, unsafe_allow_html=True)


def _render_detailed_cards(predictions: pd.DataFrame):
    """Render detailed prospect cards with breakdowns."""
    st.markdown("""
    <div style="margin-top: 2rem; text-align: center;">
        <div style="font-family: 'DM Serif Display', serif; font-size: 1.25rem; margin-bottom: 1rem;">
            Prospect Profiles
        </div>
    </div>
    """, unsafe_allow_html=True)

    sorted_preds = predictions.sort_values("pred_best_ppg", ascending=False)

    for _, row in sorted_preds.iterrows():
        tier_color = TIER_COLORS.get(row["tier"], "#666")

        html = f"""
        <div style="max-width: 900px; margin: 0.75rem auto; background: #fff; border-radius: 12px;
                    padding: 1.25rem 1.5rem; border-left: 4px solid {tier_color};">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 1rem;">
                <div>
                    <div style="font-family: 'DM Serif Display', serif; font-size: 1.3rem;">{row['name']}</div>
                    <div style="color: #666; font-size: 0.85rem;">{row['college']} &mdash; Round {row['draft_round']}, Pick {row['draft_pick']}</div>
                    <div style="color: {tier_color}; font-weight: 600; font-size: 0.8rem; text-transform: uppercase;
                                letter-spacing: 0.1em; margin-top: 0.25rem;">{row['tier']}</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-family: 'DM Serif Display', serif; font-size: 2.2rem; line-height: 1;">
                        {row['pred_best_ppg']:.1f}
                    </div>
                    <div style="font-size: 0.7rem; color: #999; text-transform: uppercase; letter-spacing: 0.1em;">
                        Projected Best PPG
                    </div>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                        gap: 0.5rem; margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid #f0f0f0;">
                <div>
                    <div style="font-size: 0.65rem; color: #999; text-transform: uppercase; letter-spacing: 0.1em;">Yr 1 PPG</div>
                    <div style="font-weight: 600; font-size: 1.1rem;">{row['pred_year1_ppg']:.1f}</div>
                </div>
                <div>
                    <div style="font-size: 0.65rem; color: #999; text-transform: uppercase; letter-spacing: 0.1em;">College YPR</div>
                    <div style="font-weight: 600;">{row['college_ypr']:.1f}</div>
                </div>
                <div>
                    <div style="font-size: 0.65rem; color: #999; text-transform: uppercase; letter-spacing: 0.1em;">40 Time</div>
                    <div style="font-weight: 600;">{row['forty_yard']:.2f}s</div>
                </div>
                <div>
                    <div style="font-size: 0.65rem; color: #999; text-transform: uppercase; letter-spacing: 0.1em;">Target Share</div>
                    <div style="font-weight: 600;">{row['college_target_share']:.0%}</div>
                </div>
                <div>
                    <div style="font-size: 0.65rem; color: #999; text-transform: uppercase; letter-spacing: 0.1em;">Breakout Age</div>
                    <div style="font-weight: 600;">{row['breakout_age']:.1f}</div>
                </div>
                <div>
                    <div style="font-size: 0.65rem; color: #999; text-transform: uppercase; letter-spacing: 0.1em;">Closest Comp</div>
                    <div style="font-weight: 600; font-size: 0.85rem;">{row['comp_player']}</div>
                </div>
            </div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)


def _render_custom_prospect_form(model: WRProspectModel):
    """Render form for custom prospect input."""
    st.markdown("""
    <div style="max-width: 900px; margin: 0 auto 1rem;">
        <div style="font-family: 'DM Serif Display', serif; font-size: 1.1rem; margin-bottom: 0.5rem;">
            Enter Prospect Details
        </div>
        <div style="font-size: 0.8rem; color: #666;">
            Input college stats and athletic measurables to generate a fantasy prediction.
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("custom_prospect_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Player Name", value="Custom Prospect")
            college = st.text_input("College", value="")
            draft_round = st.number_input("Draft Round", 1, 7, 2)
            draft_pick = st.number_input("Draft Pick (Overall)", 1, 262, 40)

        with col2:
            height_inches = st.number_input("Height (inches)", 65, 80, 73)
            weight_lbs = st.number_input("Weight (lbs)", 155, 250, 200)
            forty_yard = st.number_input("40-Yard Dash", 4.20, 5.00, 4.45, step=0.01)
            breakout_age = st.number_input("Breakout Age", 17.0, 23.0, 19.5, step=0.1)

        st.markdown("**College Production (Final Season)**")
        col3, col4, col5 = st.columns(3)
        with col3:
            college_rec = st.number_input("Receptions", 0, 200, 65)
            college_rec_yds = st.number_input("Receiving Yards", 0, 3000, 1000)
        with col4:
            college_rec_td = st.number_input("Receiving TDs", 0, 30, 8)
            college_games = st.number_input("Games Played", 1, 16, 12)
        with col5:
            college_target_share = st.number_input("Target Share", 0.05, 0.60, 0.25, step=0.01)
            college_dom_rating = st.number_input("Dominator Rating", 0.05, 0.60, 0.28, step=0.01)

        st.markdown("**Athletic Testing**")
        col6, col7, col8 = st.columns(3)
        with col6:
            vertical_jump = st.number_input("Vertical Jump (in)", 25.0, 48.0, 36.0, step=0.5)
            broad_jump = st.number_input("Broad Jump (in)", 100, 145, 125)
        with col7:
            bench_press = st.number_input("Bench Press (reps)", 0, 35, 13)
            three_cone = st.number_input("3-Cone Drill", 6.20, 7.60, 6.90, step=0.01)
        with col8:
            shuttle = st.number_input("20-Yard Shuttle", 3.80, 4.70, 4.15, step=0.01)

        submitted = st.form_submit_button("Generate Prediction", type="primary")

    if submitted:
        prospect_data = pd.DataFrame([{
            "name": name,
            "college": college,
            "draft_year": 2025,
            "draft_round": draft_round,
            "draft_pick": draft_pick,
            "college_rec": college_rec,
            "college_rec_yds": college_rec_yds,
            "college_rec_td": college_rec_td,
            "college_games": college_games,
            "college_ypr": college_rec_yds / max(college_rec, 1),
            "college_target_share": college_target_share,
            "college_dom_rating": college_dom_rating,
            "college_ypc": college_rec_yds / max(college_games, 1) / max(college_rec / max(college_games, 1), 1),
            "height_inches": height_inches,
            "weight_lbs": weight_lbs,
            "forty_yard": forty_yard,
            "vertical_jump": vertical_jump,
            "broad_jump": broad_jump,
            "bench_press": bench_press,
            "three_cone": three_cone,
            "shuttle": shuttle,
            "breakout_age": breakout_age,
        }])

        predictions = model.predict(prospect_data)
        _render_detailed_cards(predictions)


def _render_feature_importance(model: WRProspectModel):
    """Render feature importance chart."""
    fi = model.get_feature_importance()
    descriptions = get_feature_descriptions()

    html = '<div style="max-width: 700px; margin: 0 auto;">'
    for _, row in fi.iterrows():
        feat = row["feature"]
        pct = row["importance_pct"]
        desc = descriptions.get(feat, feat)
        bar_width = min(pct * 3, 100)  # Scale for visual

        html += f"""
        <div style="margin-bottom: 0.5rem;">
            <div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 0.15rem;">
                <span style="font-weight: 600;">{desc}</span>
                <span style="color: #999;">{pct:.1f}%</span>
            </div>
            <div style="background: #f0f0f0; border-radius: 4px; height: 8px; overflow: hidden;">
                <div style="background: #1e3a5f; height: 100%; width: {bar_width}%; border-radius: 4px;"></div>
            </div>
        </div>
        """
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
