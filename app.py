"""MLB Player Comparison Tool - Streamlit App."""

import streamlit as st
import pandas as pd
from pathlib import Path

from src.data.cache_manager import CacheManager
from src.data.merger import DataMerger
from src.data.pitcher_merger import PitcherDataMerger
from src.similarity.engine import SimilarityEngine
from src.similarity.pitch_engine import PitchSimilarityEngine
from src.metrics.definitions import PlayerType, get_metric_config
from src.ui.comparison_view import render_comparison
from src.ui.pitch_model_view import render_pitch_model

st.set_page_config(
    page_title="MLB Player Comparisons",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Squarespace-inspired CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&family=Pacifico&display=swap');

    /* Base styles */
    .stApp {
        font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        background: #F5F4EF;
    }

    /* Hide Streamlit elements */
    #MainMenu, footer, header, .stDeployButton {display: none !important;}
    .block-container {padding: 1rem 4rem !important; max-width: 100% !important;}

    /* Navigation */
    .nav {
        padding: 0.75rem 4rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-bottom: 1px solid #E8E6E1;
        background: #F5F4EF;
    }

    .nav-brand {
        font-family: 'DM Serif Display', serif;
        font-size: 1.25rem;
        color: #000;
        letter-spacing: -0.02em;
    }

    .nav-links {
        display: flex;
        gap: 2rem;
        font-size: 0.85rem;
        color: #666;
    }

    /* Hero */
    .hero {
        padding: 1.5rem 0 1rem;
        text-align: center;
        max-width: 900px;
        margin: 0 auto;
    }

    .hero h1 {
        font-family: 'DM Serif Display', serif;
        font-size: 2.5rem;
        font-weight: 400;
        color: #000;
        line-height: 1.1;
        margin: 0 0 0.5rem 0;
        letter-spacing: -0.02em;
    }

    .hero p {
        font-size: 1rem;
        color: #666;
        line-height: 1.5;
        margin: 0 auto;
    }

    /* Search section */
    .search-section {
        padding: 0 0 1rem;
        max-width: 900px;
        margin: 0 auto;
    }

    /* Streamlit overrides */
    .stSelectbox > div > div {
        background: #FFFFFE !important;
        border: 1px solid #D9D6CF !important;
        border-radius: 8px !important;
    }

    .stSelectbox > div > div:focus-within {
        border-color: #000 !important;
        box-shadow: none !important;
    }

    /* Ensure selectbox text is visible */
    .stSelectbox > div > div > div {
        color: #000 !important;
    }

    .stSelectbox input {
        color: #000 !important;
    }

    .stSelectbox [data-baseweb="select"] span {
        color: #000 !important;
    }

    .stButton > button {
        background: #000 !important;
        color: #fff !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.75rem 2rem !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        letter-spacing: 0.02em !important;
        transition: all 0.2s ease !important;
    }

    .stButton > button:hover {
        background: #333 !important;
        transform: translateY(-1px) !important;
    }

    /* Radio button styling */
    .stRadio > div {
        display: flex;
        gap: 1rem;
        justify-content: center;
        margin-bottom: 1rem;
    }

    .stRadio > div > label {
        background: #fff;
        border: 1px solid #D9D6CF;
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        cursor: pointer;
        transition: all 0.2s ease;
    }

    .stRadio > div > label:hover {
        border-color: #000;
    }

    .stRadio > div > label:has(input:checked) {
        background: #000;
        color: #fff !important;
        border-color: #000;
    }

    .stRadio > div > label:has(input:checked) * {
        color: #fff !important;
    }

    /* Results */
    .results-section {
        padding: 0 0 2rem;
        max-width: 900px;
        margin: 0 auto;
    }

    /* Similarity display */
    .similarity-display {
        text-align: center;
        padding: 2rem 0 3rem;
    }

    .similarity-eyebrow {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.2em;
        color: #999;
        margin-bottom: 0.75rem;
    }

    .similarity-score {
        font-family: 'DM Serif Display', serif;
        font-size: 5rem;
        font-weight: 400;
        color: #000;
        line-height: 1;
        letter-spacing: -0.02em;
    }

    .similarity-label {
        font-size: 0.9rem;
        color: #666;
        margin-top: 0.5rem;
    }

    /* Other players section */
    .other-section {
        padding: 1.5rem 0;
        max-width: 900px;
        margin: 0 auto;
        border-top: 1px solid #f0f0f0;
    }

    .other-header {
        font-family: 'DM Serif Display', serif;
        font-size: 1.25rem;
        color: #000;
        margin-bottom: 1rem;
        font-weight: 400;
    }

    .other-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 1rem;
    }

    .other-card {
        background: #fafafa;
        border-radius: 12px;
        padding: 1.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: all 0.2s ease;
    }

    .other-card:hover {
        background: #f5f5f5;
    }

    .other-info {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .other-rank {
        width: 32px;
        height: 32px;
        background: #fff;
        border: 1px solid #e0e0e0;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.8rem;
        font-weight: 600;
        color: #666;
    }

    .other-name {
        font-weight: 600;
        color: #000;
    }

    .other-season {
        color: #999;
        font-size: 0.85rem;
    }

    .other-similarity {
        font-family: 'DM Serif Display', serif;
        font-size: 1.5rem;
        color: #000;
    }

    /* Footer */
    .footer {
        padding: 1.5rem;
        text-align: center;
        border-top: 1px solid #E8E6E1;
        background: #ECEAE5;
        margin-top: 2rem;
    }

    .footer p {
        font-size: 0.75rem;
        color: #999;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_batter_dataset() -> pd.DataFrame:
    """Load batter dataset from parquet file or build it."""
    processed_path = Path("data/processed/batters.parquet")
    if processed_path.exists():
        return pd.read_parquet(processed_path)
    # Fallback to old filename for backwards compatibility
    old_path = Path("data/processed/full_dataset.parquet")
    if old_path.exists():
        return pd.read_parquet(old_path)
    # Build dataset if not found
    cache_manager = CacheManager()
    merger = DataMerger(cache_manager=cache_manager)
    dataset = merger.build_full_dataset(start_year=2015, end_year=2025, min_pa=50)
    if not dataset.empty:
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        dataset.to_parquet(processed_path, index=False)
    return dataset


@st.cache_data(ttl=3600)
def load_pitcher_dataset() -> pd.DataFrame:
    """Load pitcher dataset from parquet file or build it."""
    processed_path = Path("data/processed/pitchers.parquet")
    if processed_path.exists():
        return pd.read_parquet(processed_path)
    # Build dataset if not found
    cache_manager = CacheManager()
    merger = PitcherDataMerger(cache_manager=cache_manager)
    dataset = merger.build_full_dataset(start_year=2015, end_year=2025, min_ip=30)
    if not dataset.empty:
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        dataset.to_parquet(processed_path, index=False)
    return dataset


@st.cache_resource
def get_batter_engine(_dataset: pd.DataFrame) -> SimilarityEngine:
    """Get similarity engine for batters."""
    config = get_metric_config(PlayerType.BATTER)
    return SimilarityEngine(_dataset, config=config)


@st.cache_resource
def get_pitcher_engine(_dataset: pd.DataFrame) -> SimilarityEngine:
    """Get similarity engine for pitchers."""
    config = get_metric_config(PlayerType.PITCHER)
    return SimilarityEngine(_dataset, config=config)


@st.cache_data(ttl=3600)
def load_pitch_model_dataset() -> pd.DataFrame:
    """Load pitch model dataset from parquet file."""
    processed_path = Path("data/processed/pitch_models.parquet")
    if processed_path.exists():
        return pd.read_parquet(processed_path)
    return pd.DataFrame()


@st.cache_resource
def get_pitch_engine(_dataset: pd.DataFrame) -> PitchSimilarityEngine:
    """Get pitch similarity engine."""
    return PitchSimilarityEngine(_dataset)


@st.cache_data(ttl=3600)
def cached_find_similar(_engine, player_id: int, season: int, top_n: int = 6):
    """Cache similarity search results."""
    return _engine.find_similar(player_id, season, top_n=top_n, exclude_same_player=True)


@st.cache_data(ttl=3600)
def cached_find_similar_pitches(_engine, player_id: int, season: int, top_n: int = 4):
    """Cache pitch similarity search results."""
    return _engine.find_similar_pitches(player_id, season, top_n=top_n)


@st.cache_data(ttl=3600)
def get_player_options(_dataset: pd.DataFrame) -> dict:
    """Build dictionary of player options from dataset."""
    df = _dataset[_dataset["first_name"].notna() & _dataset["last_name"].notna()].copy()
    df["name"] = df["first_name"] + " " + df["last_name"]
    df["mlbam_id"] = df["mlbam_id"].astype(int)
    df["season"] = df["season"].astype(int)

    players = {}
    for mlbam_id, group in df.groupby("mlbam_id"):
        players[mlbam_id] = {
            "name": group.iloc[0]["name"],
            "seasons": sorted(group["season"].unique().tolist(), reverse=True),
        }
    return players


def main():
    # Initialize session state
    if "player_type" not in st.session_state:
        st.session_state.player_type = "Hitter"
    if "search_player_id" not in st.session_state:
        st.session_state.search_player_id = None
    if "search_season" not in st.session_state:
        st.session_state.search_season = None
    if "selected_comp_index" not in st.session_state:
        st.session_state.selected_comp_index = 0

    # Navigation
    st.markdown("""
    <div class="nav">
        <div class="nav-brand">MLB Comps</div>
        <div class="nav-links">
            <span>Statcast Era 2015–2025</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Hero
    st.markdown("""
    <div class="hero">
        <div style="font-family: 'Pacifico', cursive; font-size: 3.2rem; color: #1e2a5a; margin-bottom: -0.75rem; letter-spacing: 0.01em;">Fungo's</div>
        <h1>MLB Comparison Machine</h1>
        <p>Find statistically similar player seasons using Statcast data (2015-2025)</p>
    </div>
    <div style="max-width: 720px; margin: 0 auto 1rem; text-align: center;">
        <div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 0.75rem 1.25rem; font-size: 0.85rem; color: #664d03; margin-bottom: 0.5rem;">
            This tool is currently in <strong>BETA</strong>. Expect the site to be slow while final adjustments are made. If you notice issues, bugs or have feedback &mdash; please reach out on X/Twitter <a href="https://x.com/FungoMedia" target="_blank" style="color: #664d03; font-weight: 600;">@FungoMedia</a>. Thanks!
        </div>
        <div style="font-size: 0.8rem; color: #666; font-weight: 500;">
            Follow <a href="https://x.com/FungoMedia" target="_blank" style="color: #1e2a5a; text-decoration: none; font-weight: 600;">@FungoMedia</a> on X/Twitter for more MLB analysis &amp; insights
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Player type toggle
    st.markdown('<div class="search-section">', unsafe_allow_html=True)

    # Track previous player type to detect changes
    prev_player_type = st.session_state.player_type

    player_type = st.radio(
        "Player Type",
        options=["Hitter", "Pitcher Profile", "Pitch Model"],
        horizontal=True,
        label_visibility="collapsed",
        key="player_type_radio",
    )

    # Update session state and reset search if type changed
    if player_type != prev_player_type:
        st.session_state.player_type = player_type
        st.session_state.search_player_id = None
        st.session_state.search_season = None
        st.session_state.selected_comp_index = 0
        st.rerun()

    st.session_state.player_type = player_type

    # Load appropriate dataset and engine
    pitch_engine = None
    if player_type == "Hitter":
        dataset = load_batter_dataset()
        if dataset.empty:
            st.error("Unable to load batter data. Run: python scripts/build_dataset.py --type batter")
            return
        engine = get_batter_engine(dataset)
    elif player_type == "Pitcher Profile":
        dataset = load_pitcher_dataset()
        if dataset.empty:
            st.error("Unable to load pitcher data. Run: python scripts/build_dataset.py --type pitcher")
            return
        engine = get_pitcher_engine(dataset)
    else:  # Pitch Model
        pitch_dataset = load_pitch_model_dataset()
        if pitch_dataset.empty:
            st.error("Unable to load pitch model data. Run: python scripts/build_dataset.py --type pitch_model")
            return
        pitch_engine = get_pitch_engine(pitch_dataset)
        # Use pitcher dataset for player list (pitch model has multiple rows per player)
        dataset = load_pitcher_dataset()
        if dataset.empty:
            # Fallback: build player list from pitch model data
            dataset = pitch_dataset.drop_duplicates(subset=["mlbam_id", "season"])
        engine = None

    player_options = get_player_options(dataset)

    player_names = sorted(
        [(pid, info["name"]) for pid, info in player_options.items()],
        key=lambda x: x[1],
    )
    player_name_to_id = {name: (pid, name) for pid, name in player_names}

    col1, col2, col3 = st.columns([4, 2, 2])

    with col1:
        selected_player_str = st.selectbox(
            "Player",
            options=[""] + list(player_name_to_id.keys()),
            format_func=lambda x: "Select a pitcher" if x == "" and player_type != "Hitter" else (f"Select a {player_type.lower()}" if x == "" else x),
            label_visibility="collapsed",
        )

    selected_player_id = None
    selected_season = None

    if selected_player_str and selected_player_str in player_name_to_id:
        selected_player_id, _ = player_name_to_id[selected_player_str]
        with col2:
            selected_season = st.selectbox(
                "Season",
                options=player_options[selected_player_id]["seasons"],
                label_visibility="collapsed",
            )
        with col3:
            find_button = st.button("Compare", type="primary", use_container_width=True)
    else:
        with col2:
            st.selectbox(
                "Season", options=["—"], disabled=True, label_visibility="collapsed"
            )
        with col3:
            find_button = st.button(
                "Compare", type="primary", disabled=True, use_container_width=True
            )

    st.markdown("</div>", unsafe_allow_html=True)

    # Handle new search
    if find_button and selected_player_id and selected_season:
        st.session_state.search_player_id = selected_player_id
        st.session_state.search_season = selected_season
        st.session_state.selected_comp_index = 0

    # Results (show if we have a search in session state)
    if st.session_state.search_player_id and st.session_state.search_season:
        st.markdown('<div class="results-section">', unsafe_allow_html=True)

        if player_type == "Pitch Model" and pitch_engine is not None:
            # Pitch Model rendering path
            pitcher_info = pitch_engine.get_pitcher_info(
                st.session_state.search_player_id, st.session_state.search_season
            )
            if pitcher_info is None:
                st.error("Could not find pitch data for this pitcher/season. Make sure pitch model data is built.")
            else:
                pitches = pitch_engine.get_pitcher_pitches(
                    st.session_state.search_player_id, st.session_state.search_season
                )
                similar_pitches = cached_find_similar_pitches(
                    pitch_engine,
                    st.session_state.search_player_id, st.session_state.search_season,
                    top_n=4,
                )
                render_pitch_model(pitcher_info, pitches, similar_pitches)
        elif engine is not None:
            # Standard comparison rendering path (Hitter / Pitcher Profile)
            target_data = engine.get_player_season(
                st.session_state.search_player_id, st.session_state.search_season
            )
            if target_data is None:
                st.error("Could not find data for this player/season.")
            else:
                # Pass "Pitcher" for Pitcher Profile so the view uses pitcher metrics
                view_type = "Pitcher" if player_type == "Pitcher Profile" else player_type
                similar_players = cached_find_similar(
                    engine,
                    st.session_state.search_player_id,
                    st.session_state.search_season,
                    top_n=6,
                )
                render_comparison(target_data, similar_players, player_type=view_type)

        st.markdown("</div>", unsafe_allow_html=True)

    # Footer
    st.markdown("""
    <div class="footer">
        <p>Data from Baseball Savant & FanGraphs via pybaseball</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
