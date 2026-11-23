"""
app.py
======
Production-Quality Retail Sales Dashboard with Report Upload and AI-Powered Product Insights.
Retro Web / Netscape-inspired aesthetic using Streamlit 1.67+ st.navigation and st.Page.
"""

from __future__ import annotations
import os
import io
from datetime import datetime
from typing import Optional
import pandas as pd
import streamlit as st

# Local modules
import config
from config import (
    DEFAULT_GEMINI_MODEL,
    DECISION_THRESHOLDS,
)
from utils import (
    format_currency,
    format_percentage,
    format_number,
    format_delta_arrow,
    to_csv_bytes,
    to_excel_bytes,
)
from analysis import (
    clean_and_derive_features,
    calculate_kpis,
    get_monthly_metrics,
)
from upload import render_upload_interface
from customers import (
    compute_customer_rfm,
    compute_cohort_retention,
    compute_customer_summary_stats,
)
from forecasting import generate_all_forecasts
from decision_engine import evaluate_product_decisions
from ai_insights import get_gemini_api_key

# UI Theme & Reusable Components
from ui.theme import RETRO_CSS
from ui.components import render_notice

# ---------------------------------------------------------------------------
# Streamlit App Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Retail Sales Intelligence Dashboard",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject Global Retro Theme CSS
st.markdown(RETRO_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar: Upload, Filter Slicers, and Configuration
# ---------------------------------------------------------------------------
st.sidebar.markdown("""
<div style="text-align: center; margin-bottom: 1rem; border-bottom: 2px solid #222222; padding-bottom: 0.8rem;">
    <span style="font-family: 'VT323', monospace; font-size: 2.2rem; font-weight: 700; color: #2B254E;">🛍️ RETRO SALES</span><br>
    <span class="retro-badge badge-teal">NETSCAPE EDITION</span>
</div>
""", unsafe_allow_html=True)

df_raw, dq_report, is_uploaded = render_upload_interface()

if df_raw.empty:
    st.warning("⚠️ No sales data available. Please verify your dataset or use the default sample.")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 Global Slicers & Filters")

# Date range filter
min_date = df_raw["order_date"].min().date()
max_date = df_raw["order_date"].max().date()
date_range = st.sidebar.date_input(
    "Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_d, end_d = date_range
else:
    start_d, end_d = min_date, max_date

# Category & Product multiselects
avail_cats = sorted(df_raw["category"].dropna().unique().tolist())
selected_cats = st.sidebar.multiselect("Category", options=avail_cats, default=avail_cats)

# Filter available products dynamically based on selected categories
avail_prods = sorted(df_raw[df_raw["category"].isin(selected_cats)]["product"].dropna().unique().tolist())
selected_prods = st.sidebar.multiselect("Product", options=avail_prods, default=avail_prods)

# Channel filter
avail_channels = sorted(df_raw["channel"].dropna().unique().tolist()) if "channel" in df_raw.columns else []
selected_channels = st.sidebar.multiselect("Sales Channel", options=avail_channels, default=avail_channels) if avail_channels else []

# Order Status filter
avail_statuses = ["Delivered", "Returned", "Replaced", "Cancelled"]
selected_statuses = st.sidebar.multiselect("Order Status", options=avail_statuses, default=avail_statuses)

# Region filter
avail_regions = sorted(df_raw["region"].dropna().unique().tolist()) if "region" in df_raw.columns else []
selected_regions = st.sidebar.multiselect("Region", options=avail_regions, default=avail_regions) if avail_regions else []

# Decision Threshold Customization Sliders
st.sidebar.markdown("---")
with st.sidebar.expander("⚙️ Decision Engine Sliders", expanded=False):
    slider_inc_growth = st.slider("Min Growth % (Increase)", 5.0, 40.0, float(DECISION_THRESHOLDS["increase_growth_pct"]), 1.0)
    slider_inc_margin = st.slider("Min Margin % (Increase)", 5.0, 35.0, float(DECISION_THRESHOLDS["increase_margin_pct"]), 1.0)
    slider_max_return = st.slider("Max Return % (Increase)", 2.0, 15.0, float(DECISION_THRESHOLDS["increase_max_return_rate"]), 0.5)
    slider_disc_growth = st.slider("Max Contraction % (Discontinue)", -40.0, -5.0, float(DECISION_THRESHOLDS["discontinue_growth_pct"]), 1.0)
    slider_disc_return = st.slider("Critical Return % (Discontinue)", 10.0, 40.0, float(DECISION_THRESHOLDS["discontinue_return_rate"]), 1.0)

user_thresholds = {
    "increase_growth_pct": slider_inc_growth,
    "increase_margin_pct": slider_inc_margin,
    "increase_max_return_rate": slider_max_return,
    "discontinue_growth_pct": slider_disc_growth,
    "discontinue_return_rate": slider_disc_return,
}

# Optional API Key input in sidebar if not in environment or secrets
st.sidebar.markdown("---")
st.sidebar.markdown("### 🤖 Google Gemini AI")
existing_key = get_gemini_api_key()
user_api_key = st.sidebar.text_input(
    "Gemini API Key",
    value=existing_key or "",
    type="password",
    help="Required for AI Insights tab. Read from GEMINI_API_KEY or GOOGLE_API_KEY by default."
)

# ---------------------------------------------------------------------------
# Apply Global Filters to working dataset
# ---------------------------------------------------------------------------
mask = (
    (df_raw["order_date"].dt.date >= start_d) &
    (df_raw["order_date"].dt.date <= end_d) &
    (df_raw["category"].isin(selected_cats)) &
    (df_raw["product"].isin(selected_prods)) &
    (df_raw["order_status"].isin(selected_statuses))
)
if selected_channels and "channel" in df_raw.columns:
    mask = mask & (df_raw["channel"].isin(selected_channels))
if selected_regions and "region" in df_raw.columns:
    mask = mask & (df_raw["region"].isin(selected_regions))

df = df_raw[mask].copy()

if df.empty:
    st.warning("⚠️ No data matches the selected filter combination. Please broaden your sidebar filters.")
    st.stop()

# ---------------------------------------------------------------------------
# Pre-Compute Core Aggregations & Models into Session State
# ---------------------------------------------------------------------------
with st.spinner("Processing analytics engine..."):
    st.session_state["df"] = df
    st.session_state["df_raw"] = df_raw
    st.session_state["dq_report"] = dq_report
    st.session_state["user_api_key"] = user_api_key
    st.session_state["user_thresholds"] = user_thresholds
    
    st.session_state["kpis"] = calculate_kpis(df)
    st.session_state["monthly_df"] = get_monthly_metrics(df)
    st.session_state["forecast_results"] = generate_all_forecasts(df)
    
    inventory_df = pd.read_csv("data/inventory_summary.csv") if os.path.exists("data/inventory_summary.csv") else None
    st.session_state["inventory_df"] = inventory_df
    
    st.session_state["product_decisions"] = evaluate_product_decisions(
        df,
        thresholds=user_thresholds,
        product_forecasts=st.session_state["forecast_results"].get("products", {}),
        inventory_data=inventory_df
    )
    st.session_state["customer_stats"] = compute_customer_summary_stats(df)
    st.session_state["rfm_df"] = compute_customer_rfm(df)
    cohort_counts, cohort_pcts = compute_cohort_retention(df)
    st.session_state["cohort_counts"] = cohort_counts
    st.session_state["cohort_pcts"] = cohort_pcts

# ---------------------------------------------------------------------------
# Modern Page Navigation using st.navigation and st.Page
# ---------------------------------------------------------------------------
pages = [
    st.Page("pages/1_overview.py", title="1. Overview & Scorecard", icon="📊", default=True),
    st.Page("pages/2_categories_products.py", title="2. Categories & Products", icon="📦"),
    st.Page("pages/3_order_status.py", title="3. Order Status & Logistics", icon="🚚"),
    st.Page("pages/4_customer_dynamics.py", title="4. Customer Dynamics & Retention", icon="👥"),
    st.Page("pages/5_demand_forecast.py", title="5. Demand Forecasting", icon="📈"),
    st.Page("pages/6_decision_engine.py", title="6. Product Decision Engine", icon="🧠"),
    st.Page("pages/7_ai_insights.py", title="7. AI Strategic Insights", icon="🤖"),
    st.Page("pages/8_data_upload.py", title="8. Data & Quality Audit", icon="📁"),
]

pg = st.navigation(pages)
pg.run()
