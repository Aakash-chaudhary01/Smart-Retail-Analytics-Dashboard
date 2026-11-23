"""
pages/7_ai_insights.py
======================
AI Strategic Insights Page: Executive summary generation via Google Gemini
with rule-based fallback, PDF/TXT export, and interactive Q&A assistant.
"""

from __future__ import annotations
from datetime import datetime
import streamlit as st

from config import DEFAULT_GEMINI_MODEL
from utils import create_pdf_report
from ui.components import render_retro_header, render_notice, render_kpi_card
from ai_insights import (
    get_gemini_api_key,
    build_summary_payload,
    generate_gemini_insights,
    generate_rule_based_fallback,
    answer_data_question,
)

render_retro_header(
    title="AI Strategic Insights Engine",
    subtitle="Automated executive synthesis, audit reports, and interactive Q&A powered by Google Gemini",
    badge="GEMINI 2.5"
)

render_notice(
    "Operates exclusively on pre-aggregated numeric KPI tables. Raw customer records and PII are never sent to external LLMs.",
    icon="🤖"
)

kpis = st.session_state.get("kpis", {})
monthly_df = st.session_state.get("monthly_df")
product_decisions = st.session_state.get("product_decisions")
customer_stats = st.session_state.get("customer_stats", {})
dq_report = st.session_state.get("dq_report", {})
user_api_key = st.session_state.get("user_api_key", "")

api_key_to_use = user_api_key or get_gemini_api_key()

# 1. Build Payload
summary_json_payload = build_summary_payload(
    kpi_dict=kpis,
    monthly_df=monthly_df,
    product_decisions_df=product_decisions,
    customer_stats=customer_stats,
    dq_report=dq_report,
)

# 2. Controls & Status
col_btn, col_status = st.columns([1.2, 3.0])
with col_btn:
    generate_btn = st.button("🚀 Generate Strategic Report", type="primary")

with col_status:
    if api_key_to_use:
        st.success(f"Connected to Google Gemini (Model: `{DEFAULT_GEMINI_MODEL}`)")
    else:
        st.info("No Gemini API Key supplied. System will utilize deterministic rule-based synthesis.")

if "ai_report_cache" not in st.session_state:
    st.session_state["ai_report_cache"] = None

if generate_btn:
    with st.spinner("Synthesizing strategic insights..."):
        if api_key_to_use:
            report_out, success = generate_gemini_insights(
                summary_json=summary_json_payload,
                api_key=api_key_to_use,
                model_name=DEFAULT_GEMINI_MODEL
            )
            if not success:
                st.error("Encountered API issue; activating rule-based fallback below.")
                report_out = generate_rule_based_fallback(product_decisions, kpis)
        else:
            report_out = generate_rule_based_fallback(product_decisions, kpis)

        st.session_state["ai_report_cache"] = report_out

# 3. Report Output Display
current_report = st.session_state.get("ai_report_cache")
if current_report:
    st.markdown("""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>📄 EXECUTIVE_STRATEGIC_REPORT.TXT</span>
            <div class="retro-window-controls"><span class="retro-window-btn btn-min"></span><span class="retro-window-btn btn-max"></span><span class="retro-window-btn btn-close"></span></div>
        </div>
        <div class="retro-window-body">
    """, unsafe_allow_html=True)
    st.markdown(current_report)
    st.markdown("</div></div>", unsafe_allow_html=True)

    # Downloads
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

# 4. Interactive Q&A
st.markdown("---")
st.markdown("### 💬 Natural Language Data Q&A")
st.caption("Ask questions about product performance, return anomalies, or category trends.")

user_q = st.text_input("Enter your business query:")
if user_q:
    with st.spinner("Analyzing data tables..."):
        ans = answer_data_question(
            question=user_q,
            summary_json=summary_json_payload,
            api_key=api_key_to_use,
            model_name=DEFAULT_GEMINI_MODEL
        )
        st.markdown(f"""
        <div class="retro-callout">
            <strong>AI ANSWER:</strong><br>{ans}
        </div>
        """, unsafe_allow_html=True)
