"""Custom CSS styles for the app."""

CUSTOM_CSS = """
<style>
/* Clean, Claude-like base styling */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

.stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background-color: #f8f9fa;
}

/* Hide Streamlit branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Main container */
.main .block-container {
    max-width: 1000px;
    padding-top: 2rem;
    padding-bottom: 2rem;
}

/* Title styling */
h1 {
    font-weight: 600;
    font-size: 1.75rem;
    color: #1a1a1a;
    margin-bottom: 0.25rem;
}

.subtitle {
    color: #666;
    font-size: 0.95rem;
    margin-bottom: 2rem;
}

/* Search section */
.search-container {
    background: white;
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    margin-bottom: 2rem;
}

/* Similarity badge */
.similarity-badge {
    text-align: center;
    padding: 1.5rem;
    margin: 1rem 0;
}

.similarity-score {
    font-size: 3rem;
    font-weight: 700;
    color: #1a1a1a;
    line-height: 1;
}

.similarity-label {
    color: #666;
    font-size: 0.9rem;
    margin-top: 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Baseball Savant-style Card */
.savant-card {
    background: white;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    overflow: hidden;
    height: 100%;
}

.card-header {
    padding: 1rem 1.25rem;
    background: #fafafa;
    border-bottom: 1px solid #eee;
}

.card-player-name {
    font-size: 1.1rem;
    font-weight: 600;
    color: #1a1a1a;
}

.card-player-season {
    font-size: 0.85rem;
    color: #666;
    margin-top: 0.15rem;
}

.card-body {
    padding: 0.75rem 1.25rem 1.25rem;
}

/* Metric row in card */
.metric-row-card {
    display: flex;
    align-items: center;
    padding: 0.5rem 0;
    border-bottom: 1px solid #f0f0f0;
}

.metric-row-card:last-child {
    border-bottom: none;
}

.metric-name {
    width: 100px;
    font-size: 0.8rem;
    color: #666;
    flex-shrink: 0;
}

.metric-value-card {
    width: 70px;
    font-size: 0.85rem;
    font-weight: 600;
    color: #1a1a1a;
    text-align: right;
    padding-right: 1rem;
    flex-shrink: 0;
}

.percentile-bar {
    flex: 1;
    height: 8px;
    background: linear-gradient(to right, #b91c1c 0%, #ef4444 20%, #f87171 35%, #9ca3af 50%, #60a5fa 65%, #3b82f6 80%, #1a56db 100%);
    border-radius: 4px;
    position: relative;
    min-width: 80px;
}

.percentile-fill {
    display: none;
}

.percentile-marker {
    position: absolute;
    top: -4px;
    width: 3px;
    height: 16px;
    background: #1a1a1a;
    border-radius: 2px;
    transform: translateX(-50%);
}

.percentile-value {
    width: 32px;
    font-size: 0.85rem;
    font-weight: 700;
    text-align: right;
    flex-shrink: 0;
    padding-left: 0.5rem;
}

/* Section headers */
.section-header {
    font-size: 0.75rem;
    font-weight: 600;
    color: #999;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 1.5rem 0 0.75rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #eee;
}

/* Other similar players */
.other-players {
    background: white;
    border-radius: 12px;
    padding: 1.5rem;
    margin-top: 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.other-player-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 0;
    border-bottom: 1px solid #f0f0f0;
}

.other-player-row:last-child {
    border-bottom: none;
}

.other-player-name {
    font-weight: 500;
    color: #1a1a1a;
}

.other-player-similarity {
    color: #666;
    font-size: 0.9rem;
    font-weight: 600;
}

/* Button styling */
.stButton > button {
    background-color: #1a1a1a;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.5rem 1.5rem;
    font-weight: 500;
    transition: background-color 0.2s;
}

.stButton > button:hover {
    background-color: #333;
}

/* Selectbox styling */
.stSelectbox > div > div {
    background-color: white;
    border-radius: 8px;
}
</style>
"""
