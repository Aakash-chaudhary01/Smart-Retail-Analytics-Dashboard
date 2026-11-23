"""
pages/6_decision_engine.py
==========================
Product Decision Engine Page: BCG portfolio matrix, Health Score (0-100),
ABC inventory classification, and actionable prescriptive triggers in INR (₹).
"""

from __future__ import annotations
import streamlit as st
import pandas as pd
import plotly.express as px

from config import RECOMMENDATION_COLORS
from currency import format_inr, format_inr_compact
from ui.theme import apply_retro_theme_to_figure
from ui.components import render_kpi_card, render_retro_header, render_notice, render_status_badge

render_retro_header(
    title="Product Decision Engine",
    subtitle="Algorithmic lifecycle optimization, health scoring (0-100), and BCG matrix actions in INR (₹)",
    badge="DECISION (₹)"
)

render_notice(
    "Synthesizes 3-month growth, profit margins, fulfillment return penalties, and inventory stock "
    "to trigger 4 prescriptive actions: Increase Production, Discontinue, Review / Reprice, or Maintain.",
    icon="🧠"
)

product_decisions = st.session_state.get("product_decisions", pd.DataFrame())

if product_decisions.empty:
    st.info("ℹ️ No product decisions computed. Broaden sidebar filters.")
    st.stop()

# 1. Action Badges Row
rec_counts = product_decisions["recommendation"].value_counts()
badge_cols = st.columns(4)

with badge_cols[0]:
    st.markdown(render_kpi_card("Increase Production", str(rec_counts.get("Increase Production", 0))), unsafe_allow_html=True)
with badge_cols[1]:
    st.markdown(render_kpi_card("Discontinue", str(rec_counts.get("Discontinue", 0))), unsafe_allow_html=True)
with badge_cols[2]:
    st.markdown(render_kpi_card("Review / Reprice", str(rec_counts.get("Review / Reprice", 0))), unsafe_allow_html=True)
with badge_cols[3]:
    st.markdown(render_kpi_card("Maintain", str(rec_counts.get("Maintain", 0))), unsafe_allow_html=True)

# 2. BCG Matrix Scatter Plot
st.markdown("### 📊 BCG Growth-Share Portfolio Matrix")
st.markdown("""
<div class="retro-window">
    <div class="retro-window-bar">
        <span>🎯 BCG_PORTFOLIO_MATRIX.DAT</span>
        <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
    </div>
    <div class="retro-window-body">
""", unsafe_allow_html=True)

bcg_hover = product_decisions["net_revenue"].apply(lambda v: format_inr(v))
bcg_fig = px.scatter(
    product_decisions,
    x="rev_share_pct",
    y="growth_3m_pct",
    color="recommendation",
    size="net_revenue",
    text="product",
    color_discrete_map=RECOMMENDATION_COLORS,
    labels={"rev_share_pct": "Revenue Contribution Share (%)", "growth_3m_pct": "3-Month Growth (%)"},
)
bcg_fig.update_traces(
    customdata=bcg_hover,
    hovertemplate="Product: %{text}<br>Rev Share: %{x:.1f}%<br>3M Growth: %{y:.1f}%<br>Net Revenue: %{customdata}<extra></extra>",
    textposition="top center"
)
bcg_fig.add_hline(y=0, line_dash="dot", line_color="#888888")
bcg_fig.add_vline(x=product_decisions["rev_share_pct"].median(), line_dash="dot", line_color="#888888")
apply_retro_theme_to_figure(bcg_fig, title="BCG Growth-Share Matrix with Prescriptive Overlays", height=400)
st.plotly_chart(bcg_fig, use_container_width=True)
st.markdown("</div></div>", unsafe_allow_html=True)

# 3. Decision Table
st.markdown("### 📋 Prescriptive Product Recommendation Table (INR)")

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
    "net_revenue", "est_profit",
    "return_rate_pct", "rev_share_pct", "abc_class", "bcg_quadrant",
    "current_stock", "reorder_point", "reason"
]
table_df = product_decisions[display_cols].copy()
table_df["net_revenue"] = table_df["net_revenue"].apply(lambda v: format_inr(v))
table_df["est_profit"] = table_df["est_profit"].apply(lambda v: format_inr(v))
table_df = table_df.rename(columns={"net_revenue": "net_revenue (INR)", "est_profit": "est_profit (INR)"})

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
