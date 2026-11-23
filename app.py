"""
app.py
======
Production-Quality Retail Sales Dashboard with Report Upload and AI-Powered Product Insights.
Built with Streamlit, Plotly, statsmodels, and Google Gemini.
"""

from __future__ import annotations
import os
import io
from datetime import datetime
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# Local modules
import config
from config import (
    DEFAULT_GEMINI_MODEL,
    FALLBACK_GEMINI_MODEL,
    STATUS_COLORS,
    RECOMMENDATION_COLORS,
    CATEGORY_COLORS,
    PLOTLY_TEMPLATE,
    DECISION_THRESHOLDS,
)
from utils import (
    format_currency,
    format_percentage,
    format_number,
    format_delta_arrow,
    to_csv_bytes,
    to_excel_bytes,
    create_pdf_report,
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
from ai_insights import (
    get_gemini_api_key,
    build_summary_payload,
    generate_gemini_insights,
    generate_rule_based_fallback,
    answer_data_question,
)

# ---------------------------------------------------------------------------
# Streamlit App Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Retail Sales Intelligence Dashboard",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for polished aesthetic in both Light and Dark mode
st.markdown("""
<style>
    .kpi-card {
        background-color: rgba(128, 128, 128, 0.08);
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
        margin-bottom: 12px;
    }
    .kpi-label {
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        color: rgba(128, 128, 128, 0.9);
        margin-bottom: 4px;
    }
    .kpi-value {
        font-size: 1.6rem;
        font-weight: 700;
        margin-bottom: 2px;
    }
    .kpi-delta-up { color: #10B981; font-size: 0.82rem; font-weight: 600; }
    .kpi-delta-down { color: #EF4444; font-size: 0.82rem; font-weight: 600; }
    .kpi-delta-neutral { color: #6B7280; font-size: 0.82rem; }
    .info-callout {
        background-color: rgba(59, 130, 246, 0.08);
        border-left: 4px solid #3B82F6;
        padding: 10px 14px;
        border-radius: 4px;
        margin-bottom: 15px;
        font-size: 0.88rem;
    }
    .rec-badge-inc { background-color: rgba(16, 185, 129, 0.2); color: #047857; padding: 4px 10px; border-radius: 16px; font-weight: 600; }
    .rec-badge-disc { background-color: rgba(239, 68, 68, 0.2); color: #B91C1C; padding: 4px 10px; border-radius: 16px; font-weight: 600; }
    .rec-badge-rev { background-color: rgba(245, 158, 11, 0.2); color: #B45309; padding: 4px 10px; border-radius: 16px; font-weight: 600; }
    .rec-badge-maint { background-color: rgba(100, 116, 139, 0.2); color: #475569; padding: 4px 10px; border-radius: 16px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar: Upload & Global Filters
# ---------------------------------------------------------------------------
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

# Handle single date vs tuple
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

# Apply Global Filters to working dataset
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

# Header Section
st.title("🛍️ Retail Sales Intelligence Dashboard")
st.markdown(
    "Comprehensive sales monitoring, product lifecycle optimization, customer cohort dynamics, "
    "and **AI-powered strategic recommendations**."
)

# Mandatory Disclaimers
st.markdown("""
<div class="info-callout">
    💡 <strong>Notice:</strong> <em>Estimated profit</em> is calculated using average product unit costs from the inventory model.
    Some order statuses in the baseline dataset are simulated for demonstration. Walk-in retail store transactions without customer IDs are included in sales & product metrics but excluded from customer loyalty analytics.
</div>
""", unsafe_allow_html=True)

if df.empty:
    st.warning("⚠️ No data matches the selected filter combination. Please broaden your sidebar filters.")
    st.stop()

# ---------------------------------------------------------------------------
# Pre-Compute Core Aggregations & Models
# ---------------------------------------------------------------------------
with st.spinner("Crunching analytics, forecasts, and decision algorithms..."):
    kpis = calculate_kpis(df)
    monthly_df = get_monthly_metrics(df)
    forecast_results = generate_all_forecasts(df)
    inventory_df = pd.read_csv("data/inventory_summary.csv") if os.path.exists("data/inventory_summary.csv") else None
    product_decisions = evaluate_product_decisions(
        df,
        thresholds=user_thresholds,
        product_forecasts=forecast_results.get("products", {}),
        inventory_data=inventory_df
    )
    customer_stats = compute_customer_summary_stats(df)
    rfm_df = compute_customer_rfm(df)
    cohort_counts, cohort_pcts = compute_cohort_retention(df)

# ---------------------------------------------------------------------------
# Navigation Tabs
# ---------------------------------------------------------------------------
tab_overview, tab_category_product, tab_status, tab_customers, tab_forecast, tab_decisions, tab_ai, tab_data = st.tabs([
    "1️⃣ Overview",
    "2️⃣ Category & Products",
    "3️⃣ Order Status",
    "4️⃣ Customer Dynamics",
    "5️⃣ Demand Forecast",
    "6️⃣ Product Decision Engine",
    "7️⃣ AI Insights Engine",
    "8️⃣ Data & Upload Report",
])

# ===========================================================================
# TAB 1: OVERVIEW
# ===========================================================================
with tab_overview:
    st.subheader("Executive KPI Scorecard")

    deltas = kpis.get("mom_deltas", {})
    def render_metric_card(label: str, val: str, delta_val: Optional[float], suffix="%"):
        delta_str = format_delta_arrow(delta_val, suffix=suffix)
        css_class = "kpi-delta-up" if (delta_val and delta_val > 0) else ("kpi-delta-down" if (delta_val and delta_val < 0) else "kpi-delta-neutral")
        return f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{val}</div>
            <div class="{css_class}">{delta_str} MoM</div>
        </div>
        """

    # Top Row: Revenue & Profit
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(render_metric_card("Net Revenue", format_currency(kpis["net_revenue"]), deltas.get("net_revenue")), unsafe_allow_html=True)
    with c2:
        st.markdown(render_metric_card("Gross Billed Sales", format_currency(kpis["gross_sales"]), deltas.get("gross_sales")), unsafe_allow_html=True)
    with c3:
        st.markdown(render_metric_card("Estimated Profit", format_currency(kpis["est_profit"]), deltas.get("est_profit")), unsafe_allow_html=True)
    with c4:
        st.markdown(render_metric_card("Estimated Margin", format_percentage(kpis["est_margin_pct"]), None), unsafe_allow_html=True)

    # Second Row: Volume & Customers
    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.markdown(render_metric_card("Total Orders", format_number(kpis["total_orders"]), deltas.get("total_orders")), unsafe_allow_html=True)
    with c6:
        st.markdown(render_metric_card("Average Order Value (AOV)", format_currency(kpis["aov"]), None), unsafe_allow_html=True)
    with c7:
        st.markdown(render_metric_card("Unique Customers", format_number(kpis["unique_customers"]), deltas.get("unique_customers")), unsafe_allow_html=True)
    with c8:
        st.markdown(render_metric_card("Returning Customer %", format_percentage(kpis["returning_pct"]), None), unsafe_allow_html=True)

    # Third Row: Fulfillment Health Rates
    c9, c10, c11 = st.columns(3)
    with c9:
        st.markdown(render_metric_card("Return Rate", format_percentage(kpis["return_rate_pct"]), None), unsafe_allow_html=True)
    with c10:
        st.markdown(render_metric_card("Cancellation Rate", format_percentage(kpis["cancellation_rate_pct"]), None), unsafe_allow_html=True)
    with c11:
        st.markdown(render_metric_card("Replacement Rate", format_percentage(kpis["replacement_rate_pct"]), None), unsafe_allow_html=True)

    st.markdown("---")

    # Main Monthly Trend Charts
    col_chart1, col_chart2 = st.columns([1.4, 1.0])

    with col_chart1:
        st.markdown("##### 📈 Monthly Net Revenue & 3-Month Moving Average")
        if not monthly_df.empty:
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Bar(
                x=monthly_df["year_month"],
                y=monthly_df["net_revenue"],
                name="Net Revenue",
                marker_color="#3B82F6",
                opacity=0.85,
                hovertemplate="%{x}<br>Net Revenue: $%{y:,.2f}<extra></extra>"
            ))
            fig_trend.add_trace(go.Scatter(
                x=monthly_df["year_month"],
                y=monthly_df["net_revenue_ma3"],
                name="3-Month Moving Avg",
                line=dict(color="#10B981", width=3, dash="solid"),
                mode="lines+markers",
                hovertemplate="%{x}<br>3M MA: $%{y:,.2f}<extra></extra>"
            ))
            fig_trend.update_layout(
                template=PLOTLY_TEMPLATE,
                margin=dict(l=20, r=20, t=30, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=380,
                xaxis_title="Month",
                yaxis_title="Revenue ($)"
            )
            st.plotly_chart(fig_trend, use_container_width=True)

    with col_chart2:
        st.markdown("##### ⚖️ Monthly Net Revenue vs Estimated Profit (Dual-Axis)")
        if not monthly_df.empty:
            fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
            fig_dual.add_trace(
                go.Scatter(
                    x=monthly_df["year_month"], y=monthly_df["net_revenue"],
                    name="Net Revenue", line=dict(color="#3B82F6", width=2), mode="lines+markers"
                ),
                secondary_y=False
            )
            fig_dual.add_trace(
                go.Scatter(
                    x=monthly_df["year_month"], y=monthly_df["est_profit"],
                    name="Estimated Profit", line=dict(color="#10B981", width=2, dash="dash"), mode="lines+markers"
                ),
                secondary_y=True
            )
            fig_dual.update_layout(
                template=PLOTLY_TEMPLATE,
                margin=dict(l=20, r=20, t=30, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=380,
                xaxis_title="Month"
            )
            fig_dual.update_yaxes(title_text="Net Revenue ($)", secondary_y=False)
            fig_dual.update_yaxes(title_text="Estimated Profit ($)", secondary_y=True)
            st.plotly_chart(fig_dual, use_container_width=True)

    # Channel & Regional Breakdown
    row2_1, row2_2 = st.columns(2)
    with row2_1:
        st.markdown("##### 🌐 Net Revenue by Sales Channel")
        if "channel" in df.columns:
            ch_rev = df.groupby("channel")["net_revenue"].sum().reset_index().sort_values("net_revenue", ascending=False)
            fig_ch = px.bar(
                ch_rev, x="channel", y="net_revenue", color="channel",
                text_auto=".2s", template=PLOTLY_TEMPLATE,
                color_discrete_sequence=px.colors.qualitative.Safe
            )
            fig_ch.update_layout(showlegend=False, height=320, margin=dict(l=20, r=20, t=20, b=20), yaxis_title="Revenue ($)")
            st.plotly_chart(fig_ch, use_container_width=True)

    with row2_2:
        st.markdown("##### 📍 Net Revenue by Region (Excluding Walk-in)")
        if "region" in df.columns:
            reg_rev = df.dropna(subset=["region"]).groupby("region")["net_revenue"].sum().reset_index().sort_values("net_revenue", ascending=False)
            fig_reg = px.bar(
                reg_rev, x="region", y="net_revenue", color="region",
                text_auto=".2s", template=PLOTLY_TEMPLATE,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_reg.update_layout(showlegend=False, height=320, margin=dict(l=20, r=20, t=20, b=20), yaxis_title="Revenue ($)")
            st.plotly_chart(fig_reg, use_container_width=True)

# ===========================================================================
# TAB 2: CATEGORY & PRODUCT ANALYSIS
# ===========================================================================
with tab_category_product:
    st.subheader("Category Performance & Product Drill-Down")

    c_top1, c_top2 = st.columns([1.2, 1.0])
    with c_top1:
        st.markdown("##### 📊 Sales by Category")
        cat_df = df.groupby("category").agg(
            net_revenue=("net_revenue", "sum"),
            est_profit=("est_profit", "sum"),
            units_sold=("quantity", "sum"),
            orders=("order_id", "count") if "order_id" in df.columns else ("net_revenue", "count")
        ).reset_index().sort_values("net_revenue", ascending=False)
        cat_df["margin_pct"] = (cat_df["est_profit"] / cat_df["net_revenue"] * 100.0).round(1)

        fig_cat_bar = px.bar(
            cat_df, x="category", y="net_revenue",
            color="category",
            color_discrete_map=CATEGORY_COLORS,
            text_auto=".2s",
            template=PLOTLY_TEMPLATE
        )
        fig_cat_bar.update_layout(showlegend=False, height=340, margin=dict(l=20, r=20, t=20, b=20), yaxis_title="Net Revenue ($)")
        st.plotly_chart(fig_cat_bar, use_container_width=True)

    with c_top2:
        st.markdown("##### 🍩 Category Revenue Contribution Share")
        fig_donut = px.pie(
            cat_df, names="category", values="net_revenue",
            hole=0.45,
            color="category",
            color_discrete_map=CATEGORY_COLORS,
            template=PLOTLY_TEMPLATE
        )
        fig_donut.update_traces(textposition="inside", textinfo="percent+label")
        fig_donut.update_layout(showlegend=False, height=340, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_donut, use_container_width=True)

    st.markdown("---")
    st.markdown("##### 🏆 Product Performance Rankings")
    p_col1, p_col2 = st.columns(2)

    with p_col1:
        st.markdown("**Top & Bottom Products by Net Revenue**")
        p_rev = df.groupby("product")["net_revenue"].sum().reset_index().sort_values("net_revenue", ascending=True)
        fig_p_rev = px.bar(
            p_rev, y="product", x="net_revenue", orientation="h",
            text_auto=".2s", template=PLOTLY_TEMPLATE, color="net_revenue",
            color_continuous_scale="Blues"
        )
        fig_p_rev.update_layout(height=340, margin=dict(l=20, r=20, t=20, b=20), coloraxis_showscale=False, xaxis_title="Revenue ($)")
        st.plotly_chart(fig_p_rev, use_container_width=True)

    with p_col2:
        st.markdown("**Top & Bottom Products by Estimated Profit**")
        p_prof = df.groupby("product")["est_profit"].sum().reset_index().sort_values("est_profit", ascending=True)
        fig_p_prof = px.bar(
            p_prof, y="product", x="est_profit", orientation="h",
            text_auto=".2s", template=PLOTLY_TEMPLATE, color="est_profit",
            color_continuous_scale="Greens"
        )
        fig_p_prof.update_layout(height=340, margin=dict(l=20, r=20, t=20, b=20), coloraxis_showscale=False, xaxis_title="Estimated Profit ($)")
        st.plotly_chart(fig_p_prof, use_container_width=True)

    # Seasonality Heatmap
    st.markdown("---")
    st.markdown("##### 🗓️ Category Seasonality Matrix (Category x Month Revenue Heatmap)")
    pivot_heat = df.pivot_table(index="category", columns="year_month", values="net_revenue", aggfunc="sum", fill_value=0)
    fig_heat = px.imshow(
        pivot_heat,
        labels=dict(x="Year-Month", y="Category", color="Revenue ($)"),
        color_continuous_scale="Blues",
        aspect="auto",
        template=PLOTLY_TEMPLATE
    )
    fig_heat.update_layout(height=260, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_heat, use_container_width=True)

    # Regional Sales Discount vs Profit Scatter
    if "channel" in df.columns and "discount_pct" in df.columns:
        st.markdown("---")
        st.markdown("##### 💸 Discount vs Profit Impact (Regional Sales Channel)")
        reg_sales_df = df[df["channel"] == "Regional Sales"]
        if not reg_sales_df.empty:
            fig_scatter = px.scatter(
                reg_sales_df,
                x="discount_pct",
                y="est_profit",
                color="product",
                size="quantity",
                hover_data=["order_id", "total_sales", "net_revenue"],
                labels={"discount_pct": "Discount Rate (0.0 - 1.0)", "est_profit": "Estimated Profit ($)"},
                template=PLOTLY_TEMPLATE,
            )
            fig_scatter.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Break-even Profit Line")
            fig_scatter.update_layout(height=360, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_scatter, use_container_width=True)

# ===========================================================================
# TAB 3: ORDER STATUS
# ===========================================================================
with tab_status:
    st.subheader("Order Fulfillment & Status Analysis")
    st.caption("Fulfillment lifecycle breakdown across Delivered, Returned, Replaced, and Cancelled orders.")

    st_col1, st_col2 = st.columns([1.0, 1.4])

    with st_col1:
        st.markdown("##### 🎯 Overall Order Status Share")
        status_counts = df["order_status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        fig_stat_donut = px.pie(
            status_counts, names="status", values="count",
            hole=0.45,
            color="status",
            color_discrete_map=STATUS_COLORS,
            template=PLOTLY_TEMPLATE
        )
        fig_stat_donut.update_traces(textposition="inside", textinfo="percent+label")
        fig_stat_donut.update_layout(showlegend=False, height=350, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_stat_donut, use_container_width=True)

    with st_col2:
        st.markdown("##### 📅 Monthly Order Status Distribution (Stacked)")
        m_status = df.groupby(["year_month", "order_status"]).size().reset_index(name="order_count")
        fig_m_stat = px.bar(
            m_status, x="year_month", y="order_count", color="order_status",
            color_discrete_map=STATUS_COLORS,
            barmode="stack",
            template=PLOTLY_TEMPLATE
        )
        fig_m_stat.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=350,
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis_title="Month",
            yaxis_title="Total Orders"
        )
        st.plotly_chart(fig_m_stat, use_container_width=True)

    st.markdown("---")
    st.markdown("##### 📦 Fulfillment Status Breakdown by Product & Channel")

    stat_p1, stat_p2 = st.columns(2)
    with stat_p1:
        st.markdown("**Status Mix by Product**")
        prod_stat = pd.crosstab(df["product"], df["order_status"], normalize="index") * 100.0
        prod_stat = prod_stat.reset_index().melt(id_vars="product", value_name="pct")
        fig_prod_stat = px.bar(
            prod_stat, x="product", y="pct", color="order_status",
            color_discrete_map=STATUS_COLORS,
            barmode="stack",
            template=PLOTLY_TEMPLATE
        )
        fig_prod_stat.update_layout(
            height=340, margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis_title="% Share of Product Orders"
        )
        st.plotly_chart(fig_prod_stat, use_container_width=True)

    with stat_p2:
        st.markdown("**Status Mix by Sales Channel**")
        if "channel" in df.columns:
            ch_stat = pd.crosstab(df["channel"], df["order_status"], normalize="index") * 100.0
            ch_stat = ch_stat.reset_index().melt(id_vars="channel", value_name="pct")
            fig_ch_stat = px.bar(
                ch_stat, x="channel", y="pct", color="order_status",
                color_discrete_map=STATUS_COLORS,
                barmode="stack",
                template=PLOTLY_TEMPLATE
            )
            fig_ch_stat.update_layout(
                height=340, margin=dict(l=20, r=20, t=20, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                yaxis_title="% Share of Channel Orders"
            )
            st.plotly_chart(fig_ch_stat, use_container_width=True)

# ===========================================================================
# TAB 4: CUSTOMERS (NEW VS RETURNING, COHORTS, RFM)
# ===========================================================================
with tab_customers:
    st.subheader("Customer Dynamics, Frequency & Retention Analytics")
    st.caption("Excludes walk-in retail POS customers (who lack customer IDs) and cancelled transactions.")

    if not dq_report.get("has_customer_id", False) or df["customer_id"].dropna().empty:
        st.info("ℹ️ Customer analytics require a 'customer_id' field. The current dataset does not include trackable customer IDs.")
    else:
        # Customer KPI summaries
        cust_c1, cust_c2, cust_c3, cust_c4 = st.columns(4)
        with cust_c1:
            st.metric("Total Identified Customers", format_number(customer_stats["total_unique_customers"]))
        with cust_c2:
            st.metric("Repeat Buyers (> 1 Order)", f"{customer_stats['repeat_customers']} ({customer_stats['repeat_purchase_rate']}%)")
        with cust_c3:
            st.metric("Avg Days Between Orders", f"{customer_stats['avg_days_between_orders']:.1f} days")
        with cust_c4:
            st.metric("Avg Customer Lifetime Spend", format_currency(customer_stats["avg_clv"]))

        st.markdown("---")

        # New vs Returning Over Time
        cust_chart1, cust_chart2 = st.columns([1.3, 1.0])

        with cust_chart1:
            st.markdown("##### 👥 New vs Returning Customers per Month")
            fig_cust_trend = go.Figure()
            fig_cust_trend.add_trace(go.Bar(
                x=monthly_df["year_month"], y=monthly_df["new_customers"],
                name="New Customers", marker_color="#3B82F6"
            ))
            fig_cust_trend.add_trace(go.Bar(
                x=monthly_df["year_month"], y=monthly_df["returning_customers"],
                name="Returning Customers", marker_color="#10B981"
            ))
            fig_cust_trend.update_layout(
                barmode="stack",
                template=PLOTLY_TEMPLATE,
                height=350,
                margin=dict(l=20, r=20, t=20, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis_title="Month",
                yaxis_title="Active Customers"
            )
            st.plotly_chart(fig_cust_trend, use_container_width=True)

        with cust_chart2:
            st.markdown("##### 📈 Returning Customer Share (%) Over Time")
            fig_ret_line = px.line(
                monthly_df, x="year_month", y="returning_customer_pct",
                markers=True, template=PLOTLY_TEMPLATE,
                labels={"year_month": "Month", "returning_customer_pct": "Returning Customer %"}
            )
            fig_ret_line.update_traces(line_color="#10B981", line_width=3)
            fig_ret_line.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_ret_line, use_container_width=True)

        st.markdown("---")

        # Buying Frequency Breakdown
        freq_c1, freq_c2 = st.columns([1.0, 1.2])
        with freq_c1:
            st.markdown("##### 🛒 Buying Frequency Segments")
            freq_df = customer_stats["frequency_distribution"]
            if not freq_df.empty:
                fig_freq = px.bar(
                    freq_df, x="orders_count", y="customer_count",
                    text_auto=True, template=PLOTLY_TEMPLATE,
                    labels={"orders_count": "Orders Placed", "customer_count": "Number of Customers"},
                    color="orders_count", color_continuous_scale="Purples"
                )
                fig_freq.update_layout(showlegend=False, coloraxis_showscale=False, height=330, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig_freq, use_container_width=True)

        with freq_c2:
            st.markdown("##### 💎 RFM Behavioral Customer Segmentation")
            if not rfm_df.empty:
                rfm_summary = rfm_df.groupby("segment").agg(
                    customer_count=("customer_id", "count"),
                    total_revenue=("monetary", "sum"),
                    avg_monetary=("monetary", "mean")
                ).reset_index().sort_values("total_revenue", ascending=False)
                
                fig_rfm = px.bar(
                    rfm_summary, x="segment", y="customer_count",
                    color="segment", text_auto=True, template=PLOTLY_TEMPLATE,
                    color_discrete_sequence=px.colors.qualitative.Prism
                )
                fig_rfm.update_layout(showlegend=False, height=330, margin=dict(l=20, r=20, t=20, b=20), yaxis_title="Customer Count")
                st.plotly_chart(fig_rfm, use_container_width=True)

        # Cohort Retention Matrix Heatmap
        st.markdown("---")
        st.markdown("##### 🧬 Cohort Retention Heatmap (% of Customers Returning in Month M+x)")
        if not cohort_pcts.empty:
            # Display first 12 periods for clarity
            display_cohort = cohort_pcts.iloc[:, :12]
            fig_cohort = px.imshow(
                display_cohort,
                labels=dict(x="Months Since First Order", y="Cohort Month", color="Retention %"),
                color_continuous_scale="Viridis",
                text_auto=".1f",
                aspect="auto",
                template=PLOTLY_TEMPLATE
            )
            fig_cohort.update_layout(height=420, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_cohort, use_container_width=True)

        # Top 10 High-Value Customers Table
        st.markdown("---")
        st.markdown("##### 👑 Top 10 Customers by Historical Spend")
        top_10 = customer_stats.get("top_10_customers", pd.DataFrame())
        if not top_10.empty:
            st.dataframe(
                top_10.style.format({"total_net_spend": "${:,.2f}"}),
                use_container_width=True
            )

# ===========================================================================
# TAB 5: DEMAND FORECAST
# ===========================================================================
with tab_forecast:
    st.subheader("Statistical Demand & Revenue Forecasting (Next 3 Months)")
    st.caption("Time-series projection using Holt-Winters Exponential Smoothing with confidence bands and accuracy benchmarking.")

    overall_fc = forecast_results.get("overall", {})
    if not overall_fc:
        st.info("ℹ️ Insufficient time-series history for forecasting.")
    else:
        fc_df = overall_fc["forecast_df"]
        hist_s = forecast_results["overall_history"]

        # Metric banners
        fc_c1, fc_c2, fc_c3 = st.columns(3)
        with fc_c1:
            st.metric("Model Architecture", overall_fc["model_name"])
        with fc_c2:
            mape_display = f"{overall_fc['mape']:.1f}%" if overall_fc['mape'] is not None else "N/A"
            st.metric("Backtest Error (MAPE)", mape_display, help="Mean Absolute Percentage Error on 3-month holdout test set.")
        with fc_c3:
            st.metric("Projected 3-Month Growth", f"{overall_fc['forecast_growth_pct']:+.1f}%")

        # Forecast Chart
        fig_fc = go.Figure()
        # Historical Trace
        fig_fc.add_trace(go.Scatter(
            x=hist_s.index, y=hist_s.values,
            name="Historical Net Revenue",
            line=dict(color="#3B82F6", width=2.5),
            mode="lines+markers"
        ))
        # Upper Bound
        fig_fc.add_trace(go.Scatter(
            x=fc_df["ds"], y=fc_df["yhat_upper"],
            name="90% Upper Bound",
            line=dict(width=0),
            mode="lines",
            showlegend=False
        ))
        # Lower Bound + Fill
        fig_fc.add_trace(go.Scatter(
            x=fc_df["ds"], y=fc_df["yhat_lower"],
            name="Confidence Interval",
            fill="tonexty",
            fillcolor="rgba(16, 185, 129, 0.2)",
            line=dict(width=0),
            mode="lines"
        ))
        # Forecast Projection Line
        fig_fc.add_trace(go.Scatter(
            x=fc_df["ds"], y=fc_df["yhat"],
            name="3-Month Forecast Projection",
            line=dict(color="#10B981", width=3, dash="dash"),
            mode="lines+markers"
        ))

        fig_fc.update_layout(
            template=PLOTLY_TEMPLATE,
            height=420,
            margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_title="Date",
            yaxis_title="Revenue ($)"
        )
        st.plotly_chart(fig_fc, use_container_width=True)

        st.markdown("##### 🔮 Category Forecast Projections")
        cat_fc_dict = forecast_results.get("categories", {})
        cat_fc_rows = []
        for cat, c_data in cat_fc_dict.items():
            f_df = c_data["forecast_df"]
            cat_fc_rows.append({
                "Category": cat,
                "Model": c_data["model_name"],
                "Confidence": c_data["confidence"],
                "Test MAPE": f"{c_data['mape']:.1f}%" if c_data['mape'] is not None else "N/A",
                "Month 1 Projected": f"${f_df['yhat'].iloc[0]:,.2f}",
                "Month 2 Projected": f"${f_df['yhat'].iloc[1]:,.2f}",
                "Month 3 Projected": f"${f_df['yhat'].iloc[2]:,.2f}",
                "Projected 3M Growth": f"{c_data['forecast_growth_pct']:+.1f}%"
            })
        st.dataframe(pd.DataFrame(cat_fc_rows), use_container_width=True)

# ===========================================================================
# TAB 6: PRODUCT DECISION ENGINE
# ===========================================================================
with tab_decisions:
    st.subheader("Algorithmic Product Decision Engine")
    st.markdown(
        "Synthesizes growth velocity, margin quality, demand volatility, forecast momentum, and stock risk "
        "to deliver prescriptive recommendations: **Increase Production**, **Discontinue**, **Review / Reprice**, or **Maintain**."
    )

    st.caption("ℹ️ *Note: Thresholds can be adjusted via the sidebar expander. In datasets with 7 products, relative rankings provide clear directional benchmarks.*")

    if not product_decisions.empty:
        # Decision Count Badges
        rec_counts = product_decisions["recommendation"].value_counts()
        badge_cols = st.columns(4)
        with badge_cols[0]:
            st.markdown(f"**Increase Production:** {rec_counts.get('Increase Production', 0)}")
        with badge_cols[1]:
            st.markdown(f"**Discontinue:** {rec_counts.get('Discontinue', 0)}")
        with badge_cols[2]:
            st.markdown(f"**Review / Reprice:** {rec_counts.get('Review / Reprice', 0)}")
        with badge_cols[3]:
            st.markdown(f"**Maintain:** {rec_counts.get('Maintain', 0)}")

        st.markdown("---")

        # BCG Quadrant Scatter Plot
        bcg_fig = px.scatter(
            product_decisions,
            x="rev_share_pct",
            y="growth_3m_pct",
            color="recommendation",
            size="net_revenue",
            text="product",
            color_discrete_map=RECOMMENDATION_COLORS,
            template=PLOTLY_TEMPLATE,
            labels={"rev_share_pct": "Revenue Contribution Share (%)", "growth_3m_pct": "3-Month Growth (%)"},
            title="BCG Portfolio Matrix & Action Overlay"
        )
        bcg_fig.add_hline(y=0, line_dash="dot", line_color="gray")
        bcg_fig.add_vline(x=product_decisions["rev_share_pct"].median(), line_dash="dot", line_color="gray")
        bcg_fig.update_traces(textposition="top center")
        bcg_fig.update_layout(height=380, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(bcg_fig, use_container_width=True)

        st.markdown("---")
        st.markdown("##### 📋 Prescriptive Product Decision Table")

        # Color-coded recommendation table
        def highlight_recommendations(val):
            if val == "Increase Production":
                return "background-color: #D1FAE5; color: #065F46; font-weight: bold;"
            elif val == "Discontinue":
                return "background-color: #FEE2E2; color: #991B1B; font-weight: bold;"
            elif val == "Review / Reprice":
                return "background-color: #FEF3C7; color: #92400E; font-weight: bold;"
            return "background-color: #F1F5F9; color: #334155;"

        display_cols = [
            "product", "category", "recommendation", "confidence",
            "health_score", "margin_pct", "growth_3m_pct", "forecast_growth_pct",
            "return_rate_pct", "rev_share_pct", "abc_class", "bcg_quadrant",
            "current_stock", "reorder_point", "reason"
        ]
        table_df = product_decisions[display_cols].copy()

        # Compatible with both pandas Styler.map (new) and Styler.applymap (old)
        styler = table_df.style
        if hasattr(styler, "map"):
            styler = styler.map(highlight_recommendations, subset=["recommendation"])
        else:
            styler = styler.applymap(highlight_recommendations, subset=["recommendation"])

        st.dataframe(
            styler.format({
                "margin_pct": "{:.1f}%",
                "growth_3m_pct": "{:+.1f}%",
                "forecast_growth_pct": "{:+.1f}%",
                "return_rate_pct": "{:.1f}%",
                "rev_share_pct": "{:.1f}%",
                "health_score": "{:.1f}",
            }),
            use_container_width=True
        )

# ===========================================================================
# TAB 7: AI INSIGHTS ENGINE
# ===========================================================================
with tab_ai:
    st.subheader("🤖 Strategic AI Insight Engine (Google Gemini)")
    st.markdown(
        "Leverages Google Gemini to synthesize the full performance scorecard into an executive-level "
        "strategic report. Operates strictly on pre-computed summary tables (never raw rows) to respect privacy and speed."
    )

    api_key_to_use = user_api_key or get_gemini_api_key()

    # Pre-generate JSON summary payload
    summary_json_payload = build_summary_payload(
        kpi_dict=kpis,
        monthly_df=monthly_df,
        product_decisions_df=product_decisions,
        customer_stats=customer_stats,
        dq_report=dq_report,
    )

    col_btn, col_status = st.columns([1.2, 3.0])
    with col_btn:
        generate_btn = st.button("🚀 Generate AI Strategic Report", type="primary")

    with col_status:
        if api_key_to_use:
            st.success(f"Connected to Google Gemini (Model: `{DEFAULT_GEMINI_MODEL}`)")
        else:
            st.warning("No Gemini API Key detected. Clicking generate will activate high-precision rule-based engine.")

    # Storage in session state to avoid re-billing on tab switches
    if "ai_report_cache" not in st.session_state:
        st.session_state["ai_report_cache"] = None

    if generate_btn:
        with st.spinner("Synthesizing strategic insights with Gemini..."):
            if api_key_to_use:
                report_out, success = generate_gemini_insights(
                    summary_json=summary_json_payload,
                    api_key=api_key_to_use,
                    model_name=DEFAULT_GEMINI_MODEL
                )
                if not success:
                    st.error("Encountered API issue; displaying rule-based fallback below.")
                    report_out = generate_rule_based_fallback(product_decisions, kpis)
            else:
                report_out = generate_rule_based_fallback(product_decisions, kpis)

            st.session_state["ai_report_cache"] = report_out

    # Render Report
    current_report = st.session_state.get("ai_report_cache")
    if current_report:
        st.markdown("---")
        st.markdown(current_report)

        # Download Buttons
        st.markdown("---")
        d_c1, d_c2 = st.columns(2)
        with d_c1:
            st.download_button(
                label="📄 Download Report (TXT)",
                data=current_report.encode("utf-8"),
                file_name=f"executive_sales_report_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain"
            )
        with d_c2:
            pdf_bytes = create_pdf_report(current_report)
            st.download_button(
                label="📕 Download Report (PDF)",
                data=bytes(pdf_bytes),
                file_name=f"executive_sales_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )

    st.markdown("---")
    st.markdown("##### 💬 Chat with Your Sales Data")
    st.caption("Ask questions about product performance, return anomalies, or category trends (e.g. *'Why is Printer being flagged for discontinuation?'* or *'What is driving Computers revenue?'*).")

    user_q = st.text_input("Enter your business question:")
    if user_q:
        with st.spinner("Analyzing data tables..."):
            ans = answer_data_question(
                question=user_q,
                summary_json=summary_json_payload,
                api_key=api_key_to_use,
                model_name=DEFAULT_GEMINI_MODEL
            )
            st.info(ans)

# ===========================================================================
# TAB 8: DATA & UPLOAD REPORT
# ===========================================================================
with tab_data:
    st.subheader("Data Architecture & Quality Audit Report")

    # Data Quality Report Card
    dq_c1, dq_c2, dq_c3, dq_c4 = st.columns(4)
    with dq_c1:
        st.metric("Cleaned Rows", format_number(dq_report.get("cleaned_rows", 0)))
    with dq_c2:
        st.metric("Total Products", format_number(dq_report.get("num_products", 0)))
    with dq_c3:
        st.metric("Outlier Transactions Flagged", format_number(dq_report.get("outlier_count", 0)))
    with dq_c4:
        sim_share = dq_report.get("simulated_status_share", 0.0)
        st.metric("Simulated Status Share", f"{sim_share:.1f}%")

    st.markdown("---")
    st.markdown("##### 🔍 Data Cleaning & Quality Expander")
    with st.expander("View Audit Details", expanded=True):
        st.write(f"- **Date Span:** {dq_report.get('date_range', ('N/A', 'N/A'))[0]} to {dq_report.get('date_range', ('N/A', 'N/A'))[1]}")
        st.write(f"- **Dropped Rows / Anomaly Fixes:** {dq_report.get('dropped_info', 'None')}")
        st.write(f"- **Missing Value Counts per Column:** {dq_report.get('null_counts', 'None')}")

    st.markdown("---")
    st.markdown("##### 🗃️ Active Dataset Preview (First 20 Filtered Rows)")
    st.dataframe(df.head(20), use_container_width=True)

    st.markdown("---")
    st.markdown("##### 📥 Global Export Center")
    exp_c1, exp_c2, exp_c3, exp_c4 = st.columns(4)

    with exp_c1:
        st.download_button(
            "Download Cleaned CSV",
            data=to_csv_bytes(df),
            file_name="cleaned_sales_data.csv",
            mime="text/csv"
        )
    with exp_c2:
        st.download_button(
            "Download Product Decisions (CSV)",
            data=to_csv_bytes(product_decisions),
            file_name="product_recommendations.csv",
            mime="text/csv"
        )
    with exp_c3:
        excel_payload = to_excel_bytes({
            "Monthly Metrics": monthly_df,
            "Product Decisions": product_decisions,
            "Customer RFM": rfm_df.head(1000) if not rfm_df.empty else pd.DataFrame(),
        })
        st.download_button(
            "Download Multi-Tab Excel",
            data=excel_payload,
            file_name="sales_intelligence_summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    with exp_c4:
        if not rfm_df.empty:
            st.download_button(
                "Download Customer RFM (CSV)",
                data=to_csv_bytes(rfm_df),
                file_name="customer_rfm_segments.csv",
                mime="text/csv"
            )

