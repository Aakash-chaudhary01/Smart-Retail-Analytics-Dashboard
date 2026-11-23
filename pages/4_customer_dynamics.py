"""
pages/4_customer_dynamics.py
============================
Customer Dynamics & Retention Analytics Page: Cohort analysis,
New vs Returning customer trends, RFM behavioral clustering, and CLV in INR (₹).
"""

from __future__ import annotations
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from currency import format_inr, format_inr_compact
from utils import format_number
from ui.theme import apply_retro_theme_to_figure, RETRO_COLORWAY
from ui.components import render_kpi_card, render_retro_header, render_notice

render_retro_header(
    title="Customer Dynamics & Retention",
    subtitle="Cohort retention matrix, RFM segmentation, customer lifetime value, and repeat behavior in INR (₹)",
    badge="LINEAGE (₹)"
)

df = st.session_state.get("df")
dq_report = st.session_state.get("dq_report", {})
customer_stats = st.session_state.get("customer_stats", {})
monthly_df = st.session_state.get("monthly_df")
rfm_df = st.session_state.get("rfm_df", pd.DataFrame())
cohort_pcts = st.session_state.get("cohort_pcts", pd.DataFrame())

if df is None or df.empty:
    st.warning("⚠️ No data available. Adjust filters in the sidebar.")
    st.stop()

if not dq_report.get("has_customer_id", False) or df["customer_id"].dropna().empty:
    st.info("ℹ️ Customer analytics require a trackable 'customer_id' column. Anonymous walk-in transactions cannot support cohort retention.")
    st.stop()

# 1. Customer KPI Cards
st.markdown("""
<div class="retro-window">
    <div class="retro-window-bar">
        <span>👥 CUSTOMER_KPI_SUMMARY_INR.DAT</span>
        <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
    </div>
    <div class="retro-window-body">
""", unsafe_allow_html=True)

cust_c1, cust_c2, cust_c3, cust_c4 = st.columns(4)
with cust_c1:
    st.markdown(render_kpi_card("Identified Customers", format_number(customer_stats.get("total_unique_customers", 0))), unsafe_allow_html=True)
with cust_c2:
    rep_val = f"{customer_stats.get('repeat_customers', 0)} ({customer_stats.get('repeat_purchase_rate', 0.0)}%)"
    st.markdown(render_kpi_card("Repeat Buyers (>1 Order)", rep_val), unsafe_allow_html=True)
with cust_c3:
    st.markdown(render_kpi_card("Avg Order Interval", f"{customer_stats.get('avg_days_between_orders', 0.0):.1f} days"), unsafe_allow_html=True)
with cust_c4:
    st.markdown(render_kpi_card("Avg Lifetime Spend", format_inr(customer_stats.get("avg_clv", 0.0))), unsafe_allow_html=True)

st.markdown("</div></div>", unsafe_allow_html=True)

# 2. New vs Returning Trends
st.markdown("### 📈 Customer Acquisition & Retention Trends")
cust_chart1, cust_chart2 = st.columns([1.3, 1.0])

with cust_chart1:
    st.markdown("""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>📅 NEW_VS_RETURNING.DAT</span>
            <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
        </div>
        <div class="retro-window-body">
    """, unsafe_allow_html=True)
    if monthly_df is not None and not monthly_df.empty:
        fig_cust_trend = go.Figure()
        fig_cust_trend.add_trace(go.Bar(
            x=monthly_df["year_month"], y=monthly_df["new_customers"],
            name="New Customers", marker_color=RETRO_COLORWAY[0]
        ))
        fig_cust_trend.add_trace(go.Bar(
            x=monthly_df["year_month"], y=monthly_df["returning_customers"],
            name="Returning Customers", marker_color=RETRO_COLORWAY[1]
        ))
        apply_retro_theme_to_figure(fig_cust_trend, title="Monthly Active Customers", height=340)
        fig_cust_trend.update_layout(
            barmode="stack",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_title="Month",
            yaxis_title="Active Customers"
        )
        st.plotly_chart(fig_cust_trend, use_container_width=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

with cust_chart2:
    st.markdown("""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>📈 RETURNING_SHARE_PCT.DAT</span>
            <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
        </div>
        <div class="retro-window-body">
    """, unsafe_allow_html=True)
    if monthly_df is not None and not monthly_df.empty:
        fig_ret_line = px.line(
            monthly_df, x="year_month", y="returning_customer_pct",
            markers=True,
            labels={"year_month": "Month", "returning_customer_pct": "Returning Customer %"}
        )
        fig_ret_line.update_traces(line_color=RETRO_COLORWAY[2], line_width=3)
        apply_retro_theme_to_figure(fig_ret_line, title="Returning Customer % Trend", height=340)
        st.plotly_chart(fig_ret_line, use_container_width=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

# 3. Frequency & RFM Segmentation
st.markdown("### 💎 Segmentation & Lifetime Value")
freq_c1, freq_c2 = st.columns([1.0, 1.2])

with freq_c1:
    st.markdown("""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>🛒 BUYING_FREQUENCY.DAT</span>
            <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
        </div>
        <div class="retro-window-body">
    """, unsafe_allow_html=True)
    freq_df = customer_stats.get("frequency_distribution", pd.DataFrame())
    if not freq_df.empty:
        fig_freq = px.bar(
            freq_df, x="orders_count", y="customer_count",
            text_auto=True,
            labels={"orders_count": "Orders Placed", "customer_count": "Customers"},
            color="orders_count", color_continuous_scale="Purples"
        )
        apply_retro_theme_to_figure(fig_freq, title="Order Frequency Breakdown", height=320)
        fig_freq.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig_freq, use_container_width=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

with freq_c2:
    st.markdown("""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>🏷️ RFM_SEGMENTATION.DAT</span>
            <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
        </div>
        <div class="retro-window-body">
    """, unsafe_allow_html=True)
    if not rfm_df.empty:
        rfm_summary = rfm_df.groupby("segment").agg(
            customer_count=("customer_id", "count"),
            total_revenue=("monetary", "sum"),
            avg_monetary=("monetary", "mean")
        ).reset_index().sort_values("total_revenue", ascending=False)
        
        rfm_hover = rfm_summary["total_revenue"].apply(lambda v: format_inr(v))

        fig_rfm = px.bar(
            rfm_summary, x="segment", y="customer_count",
            color="segment", text_auto=True,
            color_discrete_sequence=RETRO_COLORWAY
        )
        fig_rfm.update_traces(
            customdata=rfm_hover,
            hovertemplate="%{x}<br>Customers: %{y}<br>Segment Revenue: %{customdata}<extra></extra>"
        )
        apply_retro_theme_to_figure(fig_rfm, title="RFM Behavioral Cohort Size", height=320)
        fig_rfm.update_layout(showlegend=False, yaxis_title="Customer Count")
        st.plotly_chart(fig_rfm, use_container_width=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

# 4. Cohort Retention Heatmap
st.markdown("### 🧬 Cohort Retention Matrix (% Customers Active in Month M+x)")
st.markdown("""
<div class="retro-window">
    <div class="retro-window-bar">
        <span>🧪 COHORT_RETENTION_MATRIX.DAT</span>
        <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
    </div>
    <div class="retro-window-body">
""", unsafe_allow_html=True)
if not cohort_pcts.empty:
    display_cohort = cohort_pcts.iloc[:, :12]
    fig_cohort = px.imshow(
        display_cohort,
        labels=dict(x="Months Since First Order", y="Cohort Month", color="Retention %"),
        color_continuous_scale="Viridis",
        text_auto=".1f",
        aspect="auto"
    )
    apply_retro_theme_to_figure(fig_cohort, title="Customer Retention Rate by Inception Cohort", height=400)
    st.plotly_chart(fig_cohort, use_container_width=True)
st.markdown("</div></div>", unsafe_allow_html=True)

# 5. Top 10 High Value Customers
st.markdown("### 👑 Top 10 High-Value Customers by Historical Net Spend (INR)")
top_10 = customer_stats.get("top_10_customers", pd.DataFrame())
if not top_10.empty:
    top_10_display = top_10.copy()
    top_10_display["total_net_spend"] = top_10_display["total_net_spend"].apply(lambda v: format_inr(v))
    st.dataframe(
        top_10_display,
        use_container_width=True
    )
