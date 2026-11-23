"""
pages/1_overview.py
===================
Overview Page: Executive KPI Scorecard, Monthly Net Revenue Trends,
and Channel & Regional Net Revenue Breakdown with Indian Rupee (₹) formatting.
"""

from __future__ import annotations
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

from currency import format_inr, format_inr_compact, get_inr_ticks
from utils import format_percentage, format_number
from ui.theme import apply_retro_theme_to_figure, RETRO_COLORWAY
from ui.components import render_kpi_card, render_retro_header, render_notice

# 1. Page Header
render_retro_header(
    title="Overview & Executive Scorecard",
    subtitle="High-level performance monitoring, MoM growth trajectory, and fulfillment health in INR (₹)",
    badge="INR (₹) READY"
)

render_notice(
    "Estimated profit reflects product unit costs from the inventory catalog converted to INR (₹). "
    "Walk-in POS transactions without persistent customer IDs are tracked in revenue metrics but excluded from customer lineage.",
    icon="💾"
)

# 2. Retrieve State
kpis = st.session_state.get("kpis", {})
monthly_df = st.session_state.get("monthly_df")
df = st.session_state.get("df")

if not kpis or df is None or df.empty:
    st.warning("⚠️ No data available. Adjust filters in the sidebar.")
    st.stop()

deltas = kpis.get("mom_deltas", {})

# 3. KPI Scorecards (Retro Window Frame)
st.markdown("""
<div class="retro-window">
    <div class="retro-window-bar">
        <span>💾 EXECUTIVE_SCORECARD_INR.EXE</span>
        <div class="retro-window-controls">
            <span class="retro-window-btn btn-min"></span>
            <span class="retro-window-btn btn-max"></span>
            <span class="retro-window-btn btn-close"></span>
        </div>
    </div>
    <div class="retro-window-body">
""", unsafe_allow_html=True)

# Row 1: Revenue & Profit
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(render_kpi_card("Net Revenue", format_inr_compact(kpis["net_revenue"]), deltas.get("net_revenue")), unsafe_allow_html=True)
with c2:
    st.markdown(render_kpi_card("Gross Billed Sales", format_inr_compact(kpis["gross_sales"]), deltas.get("gross_sales")), unsafe_allow_html=True)
with c3:
    st.markdown(render_kpi_card("Estimated Profit", format_inr_compact(kpis["est_profit"]), deltas.get("est_profit")), unsafe_allow_html=True)
with c4:
    st.markdown(render_kpi_card("Estimated Margin", format_percentage(kpis["est_margin_pct"]), None), unsafe_allow_html=True)

# Row 2: Volume & Customers
c5, c6, c7, c8 = st.columns(4)
with c5:
    st.markdown(render_kpi_card("Total Orders", format_number(kpis["total_orders"]), deltas.get("total_orders")), unsafe_allow_html=True)
with c6:
    st.markdown(render_kpi_card("Average Order Value (AOV)", format_inr(kpis["aov"]), None), unsafe_allow_html=True)
with c7:
    st.markdown(render_kpi_card("Unique Customers", format_number(kpis["unique_customers"]), deltas.get("unique_customers")), unsafe_allow_html=True)
with c8:
    st.markdown(render_kpi_card("Returning Customer %", format_percentage(kpis["returning_pct"]), None), unsafe_allow_html=True)

# Row 3: Fulfillment Health Rates
c9, c10, c11 = st.columns(3)
with c9:
    st.markdown(render_kpi_card("Return Rate", format_percentage(kpis["return_rate_pct"]), None), unsafe_allow_html=True)
with c10:
    st.markdown(render_kpi_card("Cancellation Rate", format_percentage(kpis["cancellation_rate_pct"]), None), unsafe_allow_html=True)
with c11:
    st.markdown(render_kpi_card("Replacement Rate", format_percentage(kpis["replacement_rate_pct"]), None), unsafe_allow_html=True)

st.markdown("</div></div>", unsafe_allow_html=True)

# 4. Charts Section
st.markdown("### 📊 Revenue Trajectory & Profitability Analysis")

col_chart1, col_chart2 = st.columns([1.35, 1.0])

with col_chart1:
    st.markdown("""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>📈 MONTHLY_TREND_CHART.DAT</span>
            <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
        </div>
        <div class="retro-window-body">
    """, unsafe_allow_html=True)
    if monthly_df is not None and not monthly_df.empty:
        # Pre-format hover text in INR
        hover_rev = [format_inr(v) for v in monthly_df["net_revenue"]]
        hover_ma = [format_inr(v) for v in monthly_df["net_revenue_ma3"]]

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Bar(
            x=monthly_df["year_month"],
            y=monthly_df["net_revenue"],
            name="Net Revenue",
            marker_color=RETRO_COLORWAY[0],
            opacity=0.9,
            customdata=hover_rev,
            hovertemplate="%{x}<br>Net Revenue: %{customdata}<extra></extra>"
        ))
        fig_trend.add_trace(go.Scatter(
            x=monthly_df["year_month"],
            y=monthly_df["net_revenue_ma3"],
            name="3-Month MA",
            line=dict(color=RETRO_COLORWAY[2], width=3, dash="solid"),
            mode="lines+markers",
            customdata=hover_ma,
            hovertemplate="%{x}<br>3M MA: %{customdata}<extra></extra>"
        ))
        apply_retro_theme_to_figure(fig_trend, title="Monthly Net Revenue & 3M Moving Average", height=350)
        
        # Apply custom Indian Lakh/Crore axis tickmarks
        max_y = float(monthly_df["net_revenue"].max())
        tickvals, ticktext = get_inr_ticks(max_y)
        fig_trend.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_title="Month",
            yaxis=dict(title="Revenue (₹)", tickmode="array", tickvals=tickvals, ticktext=ticktext)
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

with col_chart2:
    st.markdown("""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>⚖️ DUAL_AXIS_MARGINS.DAT</span>
            <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
        </div>
        <div class="retro-window-body">
    """, unsafe_allow_html=True)
    if monthly_df is not None and not monthly_df.empty:
        hover_rev = [format_inr(v) for v in monthly_df["net_revenue"]]
        hover_prof = [format_inr(v) for v in monthly_df["est_profit"]]

        fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
        fig_dual.add_trace(
            go.Scatter(
                x=monthly_df["year_month"], y=monthly_df["net_revenue"],
                name="Net Revenue", line=dict(color=RETRO_COLORWAY[0], width=2), mode="lines+markers",
                customdata=hover_rev,
                hovertemplate="%{x}<br>Net Revenue: %{customdata}<extra></extra>"
            ),
            secondary_y=False
        )
        fig_dual.add_trace(
            go.Scatter(
                x=monthly_df["year_month"], y=monthly_df["est_profit"],
                name="Estimated Profit", line=dict(color=RETRO_COLORWAY[1], width=2, dash="dash"), mode="lines+markers",
                customdata=hover_prof,
                hovertemplate="%{x}<br>Estimated Profit: %{customdata}<extra></extra>"
            ),
            secondary_y=True
        )
        apply_retro_theme_to_figure(fig_dual, title="Revenue vs Estimated Profit", height=350)
        
        max_rev = float(monthly_df["net_revenue"].max())
        max_prof = float(monthly_df["est_profit"].max())
        t_rev_vals, t_rev_text = get_inr_ticks(max_rev)
        t_prof_vals, t_prof_text = get_inr_ticks(max_prof)

        fig_dual.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_title="Month"
        )
        fig_dual.update_yaxes(title_text="Net Revenue (₹)", tickmode="array", tickvals=t_rev_vals, ticktext=t_rev_text, secondary_y=False)
        fig_dual.update_yaxes(title_text="Est. Profit (₹)", tickmode="array", tickvals=t_prof_vals, ticktext=t_prof_text, secondary_y=True)
        st.plotly_chart(fig_dual, use_container_width=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

# 5. Channel and Region breakdown
row2_1, row2_2 = st.columns(2)
with row2_1:
    st.markdown("""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>🌐 CHANNELS_NET_REVENUE.DAT</span>
            <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
        </div>
        <div class="retro-window-body">
    """, unsafe_allow_html=True)
    if "channel" in df.columns:
        ch_rev = df.groupby("channel")["net_revenue"].sum().reset_index().sort_values("net_revenue", ascending=False)
        ch_labels = ch_rev["net_revenue"].apply(lambda v: format_inr_compact(v, decimals=1))
        ch_hover = ch_rev["net_revenue"].apply(lambda v: format_inr(v))

        fig_ch = px.bar(
            ch_rev, x="channel", y="net_revenue", color="channel",
            color_discrete_sequence=RETRO_COLORWAY
        )
        fig_ch.update_traces(
            text=ch_labels,
            textposition="auto",
            customdata=ch_hover,
            hovertemplate="%{x}<br>Net Revenue: %{customdata}<extra></extra>"
        )
        apply_retro_theme_to_figure(fig_ch, title="Revenue by Channel", height=300)
        max_ch = float(ch_rev["net_revenue"].max())
        t_ch_vals, t_ch_text = get_inr_ticks(max_ch)
        fig_ch.update_layout(
            showlegend=False,
            yaxis=dict(title="Revenue (₹)", tickmode="array", tickvals=t_ch_vals, ticktext=t_ch_text),
            xaxis_title="Channel"
        )
        st.plotly_chart(fig_ch, use_container_width=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

with row2_2:
    st.markdown("""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>📍 REGIONAL_DISTRIBUTION.DAT</span>
            <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
        </div>
        <div class="retro-window-body">
    """, unsafe_allow_html=True)
    if "region" in df.columns:
        reg_rev = df.dropna(subset=["region"]).groupby("region")["net_revenue"].sum().reset_index().sort_values("net_revenue", ascending=False)
        reg_labels = reg_rev["net_revenue"].apply(lambda v: format_inr_compact(v, decimals=1))
        reg_hover = reg_rev["net_revenue"].apply(lambda v: format_inr(v))

        fig_reg = px.bar(
            reg_rev, x="region", y="net_revenue", color="region",
            color_discrete_sequence=RETRO_COLORWAY[2:] + RETRO_COLORWAY[:2]
        )
        fig_reg.update_traces(
            text=reg_labels,
            textposition="auto",
            customdata=reg_hover,
            hovertemplate="%{x}<br>Net Revenue: %{customdata}<extra></extra>"
        )
        apply_retro_theme_to_figure(fig_reg, title="Revenue by Region (Excl. Walk-in)", height=300)
        max_reg = float(reg_rev["net_revenue"].max())
        t_reg_vals, t_reg_text = get_inr_ticks(max_reg)
        fig_reg.update_layout(
            showlegend=False,
            yaxis=dict(title="Revenue (₹)", tickmode="array", tickvals=t_reg_vals, ticktext=t_reg_text),
            xaxis_title="Region"
        )
        st.plotly_chart(fig_reg, use_container_width=True)
    st.markdown("</div></div>", unsafe_allow_html=True)
