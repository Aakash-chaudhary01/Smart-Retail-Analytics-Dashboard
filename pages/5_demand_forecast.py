"""
pages/5_demand_forecast.py
==========================
Statistical Demand & Revenue Forecasting Page: 3-month forward projections
via Holt-Winters Exponential Smoothing, 90% confidence bands, and MAPE backtesting in INR (₹).
"""

from __future__ import annotations
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from currency import format_inr, format_inr_compact, get_inr_ticks
from ui.theme import apply_retro_theme_to_figure, RETRO_COLORWAY
from ui.components import render_kpi_card, render_retro_header, render_notice

render_retro_header(
    title="Demand & Revenue Forecasting",
    subtitle="3-month predictive modeling via Holt-Winters exponential smoothing & confidence intervals in INR (₹)",
    badge="FORECAST (₹)"
)

forecast_results = st.session_state.get("forecast_results", {})
overall_fc = forecast_results.get("overall", {})

if not overall_fc:
    st.info("ℹ️ Insufficient time-series history for forecasting under the selected filters.")
    st.stop()

fc_df = overall_fc["forecast_df"]
hist_s = forecast_results.get("overall_history")

# 1. Metric Summary Cards
st.markdown("""
<div class="retro-window">
    <div class="retro-window-bar">
        <span>📈 FORECAST_MODEL_METRICS_INR.DAT</span>
        <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
    </div>
    <div class="retro-window-body">
""", unsafe_allow_html=True)

fc_c1, fc_c2, fc_c3 = st.columns(3)
with fc_c1:
    st.markdown(render_kpi_card("Model Architecture", overall_fc["model_name"]), unsafe_allow_html=True)
with fc_c2:
    mape_display = f"{overall_fc['mape']:.1f}%" if overall_fc['mape'] is not None else "N/A"
    st.markdown(render_kpi_card("Backtest Error (MAPE)", mape_display), unsafe_allow_html=True)
with fc_c3:
    st.markdown(render_kpi_card("Projected 3M Growth", f"{overall_fc['forecast_growth_pct']:+.1f}%"), unsafe_allow_html=True)

st.markdown("</div></div>", unsafe_allow_html=True)

# 2. Main Forecast Chart
st.markdown("### 🔮 3-Month Forward Net Revenue Projection (90% Confidence Interval)")
st.markdown("""
<div class="retro-window">
    <div class="retro-window-bar">
        <span>📊 EXPONENTIAL_SMOOTHING_PROJECTION.DAT</span>
        <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
    </div>
    <div class="retro-window-body">
""", unsafe_allow_html=True)

fig_fc = go.Figure()
# Historical Trace
if hist_s is not None and not hist_s.empty:
    hist_hover = [format_inr(v) for v in hist_s.values]
    fig_fc.add_trace(go.Scatter(
        x=hist_s.index, y=hist_s.values,
        name="Historical Net Revenue",
        line=dict(color=RETRO_COLORWAY[0], width=2.5),
        mode="lines+markers",
        customdata=hist_hover,
        hovertemplate="%{x|%Y-%m}<br>Actual Revenue: %{customdata}<extra></extra>"
    ))

# Upper Bound
fc_upper_hover = [format_inr(v) for v in fc_df["yhat_upper"]]
fig_fc.add_trace(go.Scatter(
    x=fc_df["ds"], y=fc_df["yhat_upper"],
    name="90% Upper Bound",
    line=dict(width=0),
    mode="lines",
    customdata=fc_upper_hover,
    hovertemplate="%{x|%Y-%m}<br>Upper: %{customdata}<extra></extra>",
    showlegend=False
))

# Lower Bound + Fill
fc_lower_hover = [format_inr(v) for v in fc_df["yhat_lower"]]
fig_fc.add_trace(go.Scatter(
    x=fc_df["ds"], y=fc_df["yhat_lower"],
    name="90% Confidence Band",
    fill="tonexty",
    fillcolor="rgba(24, 138, 141, 0.2)",
    line=dict(width=0),
    mode="lines",
    customdata=fc_lower_hover,
    hovertemplate="%{x|%Y-%m}<br>Lower: %{customdata}<extra></extra>"
))

# Forecast Projection Line
fc_yhat_hover = [format_inr(v) for v in fc_df["yhat"]]
fig_fc.add_trace(go.Scatter(
    x=fc_df["ds"], y=fc_df["yhat"],
    name="3-Month Projection",
    line=dict(color=RETRO_COLORWAY[2], width=3, dash="dash"),
    mode="lines+markers",
    customdata=fc_yhat_hover,
    hovertemplate="%{x|%Y-%m}<br>Projected Revenue: %{customdata}<extra></extra>"
))

apply_retro_theme_to_figure(fig_fc, title="Historical Sales & 3-Month Forward Projection (₹)", height=420)

max_fc = max(float(fc_df["yhat_upper"].max()), float(hist_s.max()) if hist_s is not None and not hist_s.empty else 0.0)
t_fc_vals, t_fc_text = get_inr_ticks(max_fc)

fig_fc.update_layout(
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    xaxis_title="Date",
    yaxis=dict(title="Revenue (₹)", tickmode="array", tickvals=t_fc_vals, ticktext=t_fc_text)
)
st.plotly_chart(fig_fc, use_container_width=True)
st.markdown("</div></div>", unsafe_allow_html=True)

# 3. Category Forecast Table
st.markdown("### 📦 Category Forecast Breakdown (INR)")
cat_fc_dict = forecast_results.get("categories", {})
cat_fc_rows = []
for cat, c_data in cat_fc_dict.items():
    f_df = c_data["forecast_df"]
    cat_fc_rows.append({
        "Category": cat,
        "Model": c_data["model_name"],
        "Confidence": c_data["confidence"],
        "Test MAPE": f"{c_data['mape']:.1f}%" if c_data['mape'] is not None else "N/A",
        "Month 1 Projected (INR)": format_inr(f_df['yhat'].iloc[0]),
        "Month 2 Projected (INR)": format_inr(f_df['yhat'].iloc[1]),
        "Month 3 Projected (INR)": format_inr(f_df['yhat'].iloc[2]),
        "Projected 3M Growth": f"{c_data['forecast_growth_pct']:+.1f}%"
    })

if cat_fc_rows:
    st.dataframe(pd.DataFrame(cat_fc_rows), use_container_width=True)
