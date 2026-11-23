"""
pages/2_categories_products.py
==============================
Category & Product Performance Page: Category Sales Breakdown, Donut Share,
Top/Bottom Product Rankings, Seasonality Matrix, and Discount Impact.
"""

from __future__ import annotations
import streamlit as st
import pandas as pd
import plotly.express as px

from config import CATEGORY_COLORS
from ui.theme import apply_retro_theme_to_figure, RETRO_COLORWAY
from ui.components import render_retro_header, render_notice

render_retro_header(
    title="Category & Product Analytics",
    subtitle="Category mix, product performance rankings, seasonality patterns, and pricing elasticity",
    badge="CATALOG READY"
)

df = st.session_state.get("df")
if df is None or df.empty:
    st.warning("⚠️ No data available. Adjust filters in the sidebar.")
    st.stop()

# 1. Top Section: Category Sales and Donut Share
c_top1, c_top2 = st.columns([1.2, 1.0])

cat_df = df.groupby("category").agg(
    net_revenue=("net_revenue", "sum"),
    est_profit=("est_profit", "sum"),
    units_sold=("quantity", "sum"),
    orders=("order_id", "count") if "order_id" in df.columns else ("net_revenue", "count")
).reset_index().sort_values("net_revenue", ascending=False)
cat_df["margin_pct"] = (cat_df["est_profit"] / cat_df["net_revenue"] * 100.0).round(1)

with c_top1:
    st.markdown("""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>📊 CATEGORY_SALES.DAT</span>
            <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
        </div>
        <div class="retro-window-body">
    """, unsafe_allow_html=True)
    fig_cat_bar = px.bar(
        cat_df, x="category", y="net_revenue",
        color="category",
        color_discrete_map=CATEGORY_COLORS,
        text_auto=".2s"
    )
    apply_retro_theme_to_figure(fig_cat_bar, title="Net Revenue by Category", height=320)
    fig_cat_bar.update_layout(showlegend=False, yaxis_title="Net Revenue ($)", xaxis_title="Category")
    st.plotly_chart(fig_cat_bar, use_container_width=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

with c_top2:
    st.markdown("""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>🍩 REVENUE_SHARE_DONUT.DAT</span>
            <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
        </div>
        <div class="retro-window-body">
    """, unsafe_allow_html=True)
    fig_donut = px.pie(
        cat_df, names="category", values="net_revenue",
        hole=0.45,
        color="category",
        color_discrete_map=CATEGORY_COLORS
    )
    fig_donut.update_traces(textposition="inside", textinfo="percent+label")
    apply_retro_theme_to_figure(fig_donut, title="Category Revenue Contribution", height=320)
    fig_donut.update_layout(showlegend=False)
    st.plotly_chart(fig_donut, use_container_width=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

# 2. Product Rankings
st.markdown("### 🏆 Product Performance Rankings")
p_col1, p_col2 = st.columns(2)

with p_col1:
    st.markdown("""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>📈 PRODUCT_NET_REVENUE.DAT</span>
            <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
        </div>
        <div class="retro-window-body">
    """, unsafe_allow_html=True)
    p_rev = df.groupby("product")["net_revenue"].sum().reset_index().sort_values("net_revenue", ascending=True)
    fig_p_rev = px.bar(
        p_rev, y="product", x="net_revenue", orientation="h",
        text_auto=".2s", color="net_revenue",
        color_continuous_scale="Purples"
    )
    apply_retro_theme_to_figure(fig_p_rev, title="Products Ranked by Net Revenue", height=320)
    fig_p_rev.update_layout(coloraxis_showscale=False, xaxis_title="Revenue ($)", yaxis_title="")
    st.plotly_chart(fig_p_rev, use_container_width=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

with p_col2:
    st.markdown("""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>💰 PRODUCT_EST_PROFIT.DAT</span>
            <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
        </div>
        <div class="retro-window-body">
    """, unsafe_allow_html=True)
    p_prof = df.groupby("product")["est_profit"].sum().reset_index().sort_values("est_profit", ascending=True)
    fig_p_prof = px.bar(
        p_prof, y="product", x="est_profit", orientation="h",
        text_auto=".2s", color="est_profit",
        color_continuous_scale="Teal"
    )
    apply_retro_theme_to_figure(fig_p_prof, title="Products Ranked by Estimated Profit", height=320)
    fig_p_prof.update_layout(coloraxis_showscale=False, xaxis_title="Estimated Profit ($)", yaxis_title="")
    st.plotly_chart(fig_p_prof, use_container_width=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

# 3. Category Seasonality Heatmap
st.markdown("### 🗓️ Category Seasonality Matrix")
st.markdown("""
<div class="retro-window">
    <div class="retro-window-bar">
        <span>🌡️ SEASONALITY_HEATMAP.DAT</span>
        <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
    </div>
    <div class="retro-window-body">
""", unsafe_allow_html=True)
pivot_heat = df.pivot_table(index="category", columns="year_month", values="net_revenue", aggfunc="sum", fill_value=0)
fig_heat = px.imshow(
    pivot_heat,
    labels=dict(x="Year-Month", y="Category", color="Revenue ($)"),
    color_continuous_scale="Burg",
    aspect="auto"
)
apply_retro_theme_to_figure(fig_heat, title="Monthly Revenue by Category", height=280)
st.plotly_chart(fig_heat, use_container_width=True)
st.markdown("</div></div>", unsafe_allow_html=True)

# 4. Regional Sales Discount vs Profit
if "channel" in df.columns and "discount_pct" in df.columns:
    reg_sales_df = df[df["channel"] == "Regional Sales"]
    if not reg_sales_df.empty:
        st.markdown("### 💸 Discount vs Profit Impact (Regional Sales Channel)")
        st.markdown("""
        <div class="retro-window">
            <div class="retro-window-bar">
                <span>🎯 DISCOUNT_ELASTICITY_SCATTER.DAT</span>
                <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
            </div>
            <div class="retro-window-body">
        """, unsafe_allow_html=True)
        fig_scatter = px.scatter(
            reg_sales_df,
            x="discount_pct",
            y="est_profit",
            color="product",
            size="quantity",
            hover_data=["order_id", "total_sales", "net_revenue"],
            labels={"discount_pct": "Discount Rate (0.0 - 1.0)", "est_profit": "Estimated Profit ($)"},
            color_discrete_sequence=RETRO_COLORWAY
        )
        fig_scatter.add_hline(y=0, line_dash="dash", line_color="#C0392B", annotation_text="Break-even Profit Line")
        apply_retro_theme_to_figure(fig_scatter, title="Discount Rate vs Profit Realization", height=350)
        st.plotly_chart(fig_scatter, use_container_width=True)
        st.markdown("</div></div>", unsafe_allow_html=True)
