"""
ui/theme.py
===========
Centralized visual styling, retro pixel-computing aesthetic, 
custom CSS injection, and Plotly templates for the Sales Intelligence Dashboard.
Inspired by 90s vintage OS / Netscape retro web design.
"""

from __future__ import annotations
import plotly.graph_objects as go
import plotly.io as pio

# ---------------------------------------------------------------------------
# Brand & Theme Color Palette (Retro Computing / Vintage Web)
# ---------------------------------------------------------------------------
COLOR_CANVAS = "#F4EEDD"       # Warm vintage paper/cream background
COLOR_CARD = "#FAF7F2"         # Card / container background
COLOR_WINDOW_BAR = "#2B254E"   # Midnight navy/purple window titlebar
COLOR_PRIMARY = "#2B254E"      # Deep purple/navy
COLOR_SECONDARY = "#4B3F72"    # Muted royal purple
COLOR_TEAL = "#188A8D"         # Retro Netscape cyan/teal
COLOR_ORANGE = "#E65F2B"       # Warm 90s orange
COLOR_YELLOW = "#E5A93C"       # Retro CRT amber/yellow
COLOR_BORDER = "#222222"       # Crisp solid retro border
COLOR_TEXT_MAIN = "#1A1A1A"    # High contrast main text
COLOR_TEXT_MUTED = "#555555"   # Secondary muted text
COLOR_SUCCESS = "#107E57"      # Retro terminal green
COLOR_DANGER = "#C0392B"       # Retro warning red

# Plotly Color Palette
RETRO_COLORWAY = [
    "#2B254E",  # Midnight Purple
    "#188A8D",  # Retro Teal
    "#E65F2B",  # Vintage Orange
    "#E5A93C",  # CRT Amber
    "#4B3F72",  # Soft Navy
    "#27AE60",  # Terminal Green
    "#C0392B",  # Retro Red
    "#8E44AD",  # Vintage Violet
]

# ---------------------------------------------------------------------------
# Global Custom CSS
# ---------------------------------------------------------------------------
RETRO_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&family=VT323&display=swap');

/* Main container overrides */
html, body, [data-testid="stAppViewContainer"] {{
    background-color: {COLOR_CANVAS} !important;
    font-family: 'Space Mono', monospace, -apple-system, sans-serif !important;
    color: {COLOR_TEXT_MAIN} !important;
}}

[data-testid="stHeader"] {{
    background-color: {COLOR_CANVAS} !important;
    border-bottom: 2px solid {COLOR_BORDER};
}}

/* Sidebar Styling */
[data-testid="stSidebar"] {{
    background-color: #EDE6D3 !important;
    border-right: 3px solid {COLOR_BORDER} !important;
}}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
    font-family: 'VT323', monospace !important;
    letter-spacing: 1px;
    color: {COLOR_PRIMARY} !important;
    font-size: 1.6rem !important;
}}

/* Headings */
h1, h2, h3 {{
    font-family: 'VT323', monospace !important;
    letter-spacing: 1.5px;
    color: {COLOR_PRIMARY} !important;
}}
h1 {{ font-size: 2.6rem !important; }}
h2 {{ font-size: 2.1rem !important; }}
h3 {{ font-size: 1.6rem !important; }}

/* Retro Window Container */
.retro-window {{
    background-color: {COLOR_CARD};
    border: 2px solid {COLOR_BORDER};
    box-shadow: 4px 4px 0px {COLOR_BORDER};
    border-radius: 0px;
    margin-bottom: 1.2rem;
    overflow: hidden;
}}

.retro-window-bar {{
    background-color: {COLOR_WINDOW_BAR};
    color: #FFFFFF;
    padding: 6px 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid {COLOR_BORDER};
    font-family: 'Space Mono', monospace;
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.5px;
}}

.retro-window-controls {{
    display: flex;
    gap: 6px;
}}

.retro-window-btn {{
    width: 13px;
    height: 13px;
    border: 1px solid #111111;
    display: inline-block;
    box-shadow: 1px 1px 0px #000000;
}}
.btn-min {{ background-color: {COLOR_YELLOW}; }}
.btn-max {{ background-color: {COLOR_TEAL}; }}
.btn-close {{ background-color: {COLOR_ORANGE}; }}

.retro-window-body {{
    padding: 14px 16px;
    color: {COLOR_TEXT_MAIN};
}}

/* Retro KPI Cards */
.retro-kpi-card {{
    background-color: {COLOR_CARD};
    border: 2px solid {COLOR_BORDER};
    box-shadow: 3px 3px 0px {COLOR_BORDER};
    padding: 14px;
    text-align: center;
    margin-bottom: 10px;
    position: relative;
}}

.retro-kpi-label {{
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    color: {COLOR_TEXT_MUTED};
    letter-spacing: 1px;
    margin-bottom: 4px;
}}

.retro-kpi-value {{
    font-family: 'VT323', monospace;
    font-size: 2.2rem;
    font-weight: 700;
    color: {COLOR_PRIMARY};
    line-height: 1.1;
    margin-bottom: 4px;
}}

.retro-kpi-delta-up {{
    color: {COLOR_SUCCESS};
    font-size: 0.82rem;
    font-weight: 700;
}}
.retro-kpi-delta-down {{
    color: {COLOR_DANGER};
    font-size: 0.82rem;
    font-weight: 700;
}}
.retro-kpi-delta-neutral {{
    color: {COLOR_TEXT_MUTED};
    font-size: 0.82rem;
}}

/* Retro Pills / Badges */
.retro-badge {{
    display: inline-block;
    padding: 3px 8px;
    border: 1px solid {COLOR_BORDER};
    box-shadow: 2px 2px 0px {COLOR_BORDER};
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.badge-teal {{ background-color: {COLOR_TEAL}; color: #FFFFFF; }}
.badge-orange {{ background-color: {COLOR_ORANGE}; color: #FFFFFF; }}
.badge-yellow {{ background-color: {COLOR_YELLOW}; color: #000000; }}
.badge-navy {{ background-color: {COLOR_PRIMARY}; color: #FFFFFF; }}

/* Retro Button Style Overrides */
.stButton > button {{
    background-color: {COLOR_CARD} !important;
    color: {COLOR_PRIMARY} !important;
    border: 2px solid {COLOR_BORDER} !important;
    box-shadow: 3px 3px 0px {COLOR_BORDER} !important;
    border-radius: 0px !important;
    font-family: 'Space Mono', monospace !important;
    font-weight: 700 !important;
    padding: 6px 14px !important;
    transition: all 0.1s ease;
}}
.stButton > button:hover {{
    transform: translate(1px, 1px);
    box-shadow: 2px 2px 0px {COLOR_BORDER} !important;
}}
.stButton > button:active {{
    transform: translate(3px, 3px);
    box-shadow: 0px 0px 0px {COLOR_BORDER} !important;
}}

/* Form inputs & selectboxes */
div[data-baseweb="select"] > div {{
    border: 2px solid {COLOR_BORDER} !important;
    border-radius: 0px !important;
    background-color: #FFFFFF !important;
    box-shadow: 2px 2px 0px {COLOR_BORDER} !important;
}}

/* Notice / Callout */
.retro-callout {{
    background-color: #FFF9E6;
    border: 2px solid {COLOR_BORDER};
    box-shadow: 3px 3px 0px {COLOR_BORDER};
    padding: 10px 14px;
    margin-bottom: 1rem;
    font-size: 0.88rem;
}}
</style>
"""

# ---------------------------------------------------------------------------
# Plotly Retro Theme
# ---------------------------------------------------------------------------
def get_retro_plotly_layout(title: str = "", height: int = 400) -> dict:
    """Return common retro layout dictionary for Plotly figures."""
    return dict(
        title=dict(
            text=f"<b>{title}</b>" if title else "",
            font=dict(family="'Space Mono', monospace", size=14, color=COLOR_PRIMARY),
            x=0.02,
        ),
        paper_bgcolor=COLOR_CARD,
        plot_bgcolor="#FFFFFF",
        colorway=RETRO_COLORWAY,
        font=dict(family="'Space Mono', monospace", size=11, color=COLOR_TEXT_MAIN),
        margin=dict(l=40, r=30, t=50 if title else 25, b=40),
        height=height,
        xaxis=dict(
            gridcolor="#E5DEC9",
            linecolor=COLOR_BORDER,
            linewidth=1.5,
            zerolinecolor="#CCCCCC",
        ),
        yaxis=dict(
            gridcolor="#E5DEC9",
            linecolor=COLOR_BORDER,
            linewidth=1.5,
            zerolinecolor="#CCCCCC",
        ),
        legend=dict(
            bgcolor="rgba(250, 247, 242, 0.9)",
            bordercolor=COLOR_BORDER,
            borderwidth=1,
            font=dict(family="'Space Mono', monospace", size=10),
        ),
    )

def apply_retro_theme_to_figure(fig: go.Figure, title: str = "", height: int = 400) -> go.Figure:
    """Apply retro styling directly onto an existing Plotly figure."""
    layout_dict = get_retro_plotly_layout(title=title, height=height)
    fig.update_layout(**layout_dict)
    return fig
