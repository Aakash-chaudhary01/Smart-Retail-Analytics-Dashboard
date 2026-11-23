"""
pages/3_order_status.py
=======================
Order Status & Fulfillment Health Page: Fulfillment breakdown across
Delivered, Returned, Replaced, and Cancelled orders by time, product, and channel.
"""

from __future__ import annotations
import streamlit as st
import pandas as pd
import plotly.express as px

from config import STATUS_COLORS
from ui.theme import apply_retro_theme_to_figure
from ui.components import render_retro_header, render_notice

render_retro_header(
    title="Order Status & Fulfillment Logistics",
    subtitle="Tracking order completion, returns, replacements, and cancellation rates",
    badge="FULFILLMENT OPS"
)

df = st.session_state.get("df")
if df is None or df.empty:
    st.warning("⚠️ No data available. Adjust filters in the sidebar.")
    st.stop()

# 1. Top Section: Donut Share & Stacked Monthly
st_col1, st_col2 = st.columns([1.0, 1.4])

with st_col1:
    st.markdown("""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>🎯 STATUS_SHARE_DONUT.DAT</span>
            <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
        </div>
        <div class="retro-window-body">
    """, unsafe_allow_html=True)
    status_counts = df["order_status"].value_counts().reset_index()
    status_counts.columns = ["status", "count"]
    fig_stat_donut = px.pie(
        status_counts, names="status", values="count",
        hole=0.45,
        color="status",
        color_discrete_map=STATUS_COLORS
    )
    fig_stat_donut.update_traces(textposition="inside", textinfo="percent+label")
    apply_retro_theme_to_figure(fig_stat_donut, title="Overall Fulfillment Status Share", height=340)
    fig_stat_donut.update_layout(showlegend=False)
    st.plotly_chart(fig_stat_donut, use_container_width=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

with st_col2:
    st.markdown("""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>📅 MONTHLY_STATUS_VOLUME.DAT</span>
            <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
        </div>
        <div class="retro-window-body">
    """, unsafe_allow_html=True)
    m_status = df.groupby(["year_month", "order_status"]).size().reset_index(name="order_count")
    fig_m_stat = px.bar(
        m_status, x="year_month", y="order_count", color="order_status",
        color_discrete_map=STATUS_COLORS,
        barmode="stack"
    )
    apply_retro_theme_to_figure(fig_m_stat, title="Monthly Order Volume by Status", height=340)
    fig_m_stat.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_title="Month",
        yaxis_title="Total Orders"
    )
    st.plotly_chart(fig_m_stat, use_container_width=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

# 2. Breakdown by Product & Channel
st.markdown("### 📦 Status Mix Analysis")
stat_p1, stat_p2 = st.columns(2)

with stat_p1:
    st.markdown("""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>💻 PRODUCT_STATUS_MIX.DAT</span>
            <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
        </div>
        <div class="retro-window-body">
    """, unsafe_allow_html=True)
    prod_stat = pd.crosstab(df["product"], df["order_status"], normalize="index") * 100.0
    prod_stat = prod_stat.reset_index().melt(id_vars="product", value_name="pct")
    fig_prod_stat = px.bar(
        prod_stat, x="product", y="pct", color="order_status",
        color_discrete_map=STATUS_COLORS,
        barmode="stack"
    )
    apply_retro_theme_to_figure(fig_prod_stat, title="Status Mix by Product (%)", height=330)
    fig_prod_stat.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis_title="% of Product Orders",
        xaxis_title="Product"
    )
    st.plotly_chart(fig_prod_stat, use_container_width=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

with stat_p2:
    st.markdown("""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>🌐 CHANNEL_STATUS_MIX.DAT</span>
            <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
        </div>
        <div class="retro-window-body">
    """, unsafe_allow_html=True)
    if "channel" in df.columns:
        ch_stat = pd.crosstab(df["channel"], df["order_status"], normalize="index") * 100.0
        ch_stat = ch_stat.reset_index().melt(id_vars="channel", value_name="pct")
        fig_ch_stat = px.bar(
            ch_stat, x="channel", y="pct", color="order_status",
            color_discrete_map=STATUS_COLORS,
            barmode="stack"
        )
        apply_retro_theme_to_figure(fig_ch_stat, title="Status Mix by Channel (%)", height=330)
        fig_ch_stat.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis_title="% of Channel Orders",
            xaxis_title="Channel"
        )
        st.plotly_chart(fig_ch_stat, use_container_width=True)
    st.markdown("</div></div>", unsafe_allow_html=True)
