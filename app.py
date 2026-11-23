"""
app.py
======
Production-Quality Retail Sales Dashboard with Report Upload and AI-Powered Product Insights.
Configured with INR (₹) base currency, Indian number formatting, and 1-time currency conversion.
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
from currency import (
    BASE_CURRENCY,
    CURRENCY_SYMBOL,
    USD_TO_INR_RATE,
    detect_dataset_currency,
    convert_dataframe_currency,
    convert_amount,
    format_inr,
    format_inr_compact,
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
    page_title="Retail Sales Intelligence Dashboard (INR)",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject Global Retro Theme CSS
st.markdown(RETRO_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar: Brand Banner & Data Source
# ---------------------------------------------------------------------------
st.sidebar.markdown("""
<div style="text-align: center; margin-bottom: 1rem; border-bottom: 2px solid #222222; padding-bottom: 0.8rem;">
    <span style="font-family: 'VT323', monospace; font-size: 2.2rem; font-weight: 700; color: #2B254E;">🛍️ RETRO SALES</span><br>
    <span class="retro-badge badge-teal">INR (₹) EDITION</span>
</div>
""", unsafe_allow_html=True)

df_raw, dq_report, is_uploaded = render_upload_interface()

if df_raw.empty:
    st.warning("⚠️ No sales data available. Please verify your dataset or use the default sample.")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar: Currency Detection, Selection & Exchange Rate Information
# ---------------------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.markdown("### 💱 Currency & Exchange")

detected_curr = detect_dataset_currency(df_raw)

# If detected, use detected currency; otherwise let user choose via selector
if detected_curr:
    source_currency = detected_curr
    st.sidebar.success(f"Detected Dataset Currency: **{source_currency}**")
else:
    if "source_currency" not in st.session_state:
        st.session_state["source_currency"] = "USD"
    source_currency = st.sidebar.selectbox(
        "Select Dataset Currency",
        options=["USD", "INR"],
        index=0 if st.session_state["source_currency"] == "USD" else 1,
        help="Specify whether raw figures are in USD or INR. Dashboard displays all metrics in INR (₹)."
    )
    st.session_state["source_currency"] = source_currency

conversion_active = (source_currency == "USD")
applied_rate = USD_TO_INR_RATE if conversion_active else 1.0

st.sidebar.markdown(f"""
<div style="font-size: 0.82rem; background: #FFF9E6; border: 2px solid #222; box-shadow: 2px 2px 0px #222; padding: 8px 10px; margin-bottom: 10px;">
    <strong>Reporting Currency:</strong> INR (₹)<br>
    <strong>Source Currency:</strong> {source_currency}<br>
    <strong>Exchange Rate:</strong> 1 USD = ₹{USD_TO_INR_RATE:.2f}<br>
    <strong>Status:</strong> {'Converted 1x to INR' if conversion_active else 'Native INR (No conversion)'}
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# One-Time Currency Conversion (Original df_raw kept completely unchanged)
# ---------------------------------------------------------------------------
st.session_state["df_raw_original"] = df_raw.copy()
st.session_state["source_currency"] = source_currency
st.session_state["applied_rate"] = applied_rate

if conversion_active:
    # Convert every monetary column exactly once before KPI calculations
    df_working = convert_dataframe_currency(df_raw, from_currency="USD", to_currency="INR", rate=applied_rate)
else:
    df_working = df_raw.copy()

# ---------------------------------------------------------------------------
# Sidebar: Global Slicers & Filters
# ---------------------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 Global Slicers & Filters")

# Date range filter
min_date = df_working["order_date"].min().date()
max_date = df_working["order_date"].max().date()
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
avail_cats = sorted(df_working["category"].dropna().unique().tolist())
selected_cats = st.sidebar.multiselect("Category", options=avail_cats, default=avail_cats)

# Filter available products dynamically based on selected categories
avail_prods = sorted(df_working[df_working["category"].isin(selected_cats)]["product"].dropna().unique().tolist())
selected_prods = st.sidebar.multiselect("Product", options=avail_prods, default=avail_prods)

# Channel filter
avail_channels = sorted(df_working["channel"].dropna().unique().tolist()) if "channel" in df_working.columns else []
selected_channels = st.sidebar.multiselect("Sales Channel", options=avail_channels, default=avail_channels) if avail_channels else []

# Order Status filter
avail_statuses = ["Delivered", "Returned", "Replaced", "Cancelled"]
selected_statuses = st.sidebar.multiselect("Order Status", options=avail_statuses, default=avail_statuses)

# Region filter
avail_regions = sorted(df_working["region"].dropna().unique().tolist()) if "region" in df_working.columns else []
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
    (df_working["order_date"].dt.date >= start_d) &
    (df_working["order_date"].dt.date <= end_d) &
    (df_working["category"].isin(selected_cats)) &
    (df_working["product"].isin(selected_prods)) &
    (df_working["order_status"].isin(selected_statuses))
)
if selected_channels and "channel" in df_working.columns:
    mask = mask & (df_working["channel"].isin(selected_channels))
if selected_regions and "region" in df_working.columns:
    mask = mask & (df_working["region"].isin(selected_regions))

df = df_working[mask].copy()

if df.empty:
    st.warning("⚠️ No data matches the selected filter combination. Please broaden your sidebar filters.")
    st.stop()

# ---------------------------------------------------------------------------
# Pre-Compute Core Aggregations & Models in INR into Session State
# ---------------------------------------------------------------------------
with st.spinner("Processing analytics engine in INR (₹)..."):
    st.session_state["df"] = df
    st.session_state["df_raw"] = df_raw
    st.session_state["df_working"] = df_working
    st.session_state["dq_report"] = dq_report
    st.session_state["user_api_key"] = user_api_key
    st.session_state["user_thresholds"] = user_thresholds
    
    # KPIs calculated in INR
    st.session_state["kpis"] = calculate_kpis(df)
    st.session_state["monthly_df"] = get_monthly_metrics(df)
    st.session_state["forecast_results"] = generate_all_forecasts(df)
    
    # Inventory catalog with scaled unit costs
    inventory_df = pd.read_csv("data/inventory_summary.csv") if os.path.exists("data/inventory_summary.csv") else None
    if inventory_df is not None and conversion_active:
        if "estimated_unit_cost" in inventory_df.columns:
            inventory_df["estimated_unit_cost"] = convert_amount(inventory_df["estimated_unit_cost"], "USD", "INR", applied_rate)
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
# Navigation Pages Registration
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
