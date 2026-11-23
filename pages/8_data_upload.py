"""
pages/8_data_upload.py
======================
Data Management & Quality Audit Page: Data hygiene metrics,
anomalies and outlier logs, raw dataset preview, and multi-format export center.
"""

from __future__ import annotations
import streamlit as st
import pandas as pd

from utils import format_number, to_csv_bytes, to_excel_bytes
from ui.components import render_kpi_card, render_retro_header, render_notice

render_retro_header(
    title="Data Architecture & Quality Audit",
    subtitle="Ingestion verification, anomaly detection logs, data health audit, and file exports",
    badge="AUDIT LOG"
)

df = st.session_state.get("df")
df_raw = st.session_state.get("df_raw")
dq_report = st.session_state.get("dq_report", {})
product_decisions = st.session_state.get("product_decisions", pd.DataFrame())
monthly_df = st.session_state.get("monthly_df", pd.DataFrame())
rfm_df = st.session_state.get("rfm_df", pd.DataFrame())

if df is None or df.empty:
    st.warning("⚠️ No data available.")
    st.stop()

# 1. Data Quality KPI Cards
st.markdown("""
<div class="retro-window">
    <div class="retro-window-bar">
        <span>🔍 DATA_INTEGRITY_AUDIT.DAT</span>
        <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
    </div>
    <div class="retro-window-body">
""", unsafe_allow_html=True)

dq_c1, dq_c2, dq_c3, dq_c4 = st.columns(4)
with dq_c1:
    st.markdown(render_kpi_card("Cleaned Rows", format_number(dq_report.get("cleaned_rows", 0))), unsafe_allow_html=True)
with dq_c2:
    st.markdown(render_kpi_card("Total Products", format_number(dq_report.get("num_products", 0))), unsafe_allow_html=True)
with dq_c3:
    st.markdown(render_kpi_card("Outlier Sales Flagged", format_number(dq_report.get("outlier_count", 0))), unsafe_allow_html=True)
with dq_c4:
    sim_share = dq_report.get("simulated_status_share", 0.0)
    st.markdown(render_kpi_card("Simulated Status Share", f"{sim_share:.1f}%"), unsafe_allow_html=True)

st.markdown("</div></div>", unsafe_allow_html=True)

# 2. Detailed Audit Report
st.markdown("### 📋 Data Cleaning & Transformation Log")
with st.expander("🔍 View Technical Audit Details", expanded=True):
    date_rng = dq_report.get("date_range", ("N/A", "N/A"))
    st.write(f"- **Active Date Span:** {date_rng[0]} to {date_rng[1]}")
    st.write(f"- **Dropped Rows & Fixes:** {dq_report.get('dropped_info', 'None')}")
    st.write(f"- **Missing Value Profile:** {dq_report.get('null_counts', 'None')}")
    st.write(f"- **Unique Trackable Customers:** {dq_report.get('num_customers', 'None')}")

# 3. Active Dataset Preview
st.markdown("### 🗃️ Active Dataset Preview (Top 25 Rows)")
st.dataframe(df.head(25), use_container_width=True)

# 4. Global Export Center
st.markdown("### 📥 Global Export Center")
exp_c1, exp_c2, exp_c3, exp_c4 = st.columns(4)

with exp_c1:
    st.download_button(
        "📄 Cleaned Data (CSV)",
        data=to_csv_bytes(df),
        file_name="cleaned_sales_data.csv",
        mime="text/csv"
    )
with exp_c2:
    st.download_button(
        "🧠 Product Decisions (CSV)",
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
        "📊 Multi-Tab Report (XLSX)",
        data=excel_payload,
        file_name="sales_intelligence_summary.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
with exp_c4:
    if not rfm_df.empty:
        st.download_button(
            "👥 Customer RFM (CSV)",
            data=to_csv_bytes(rfm_df),
            file_name="customer_rfm_segments.csv",
            mime="text/csv"
        )
