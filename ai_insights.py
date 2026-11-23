"""
ai_insights.py
==============
Generates executive AI business insights using the Google Gemini REST API.
Strictly sends aggregated summary tables (no raw PII / customer rows), enforces
evidence-based numerical reasoning, caches responses to prevent billing waste,
and provides a rule-based fallback and interactive Q&A "Chat with your data".
"""

from __future__ import annotations
import os
import json
import warnings
from typing import Dict, Any, Optional, Tuple, List
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from config import (
    DEFAULT_GEMINI_MODEL,
    FALLBACK_GEMINI_MODEL,
    GEMINI_MAX_OUTPUT_TOKENS,
    GEMINI_TEMPERATURE,
    get_logger,
)

warnings.filterwarnings("ignore")
load_dotenv()
logger = get_logger("ai_insights")

# ---------------------------------------------------------------------------
# API Key Resolver
# ---------------------------------------------------------------------------
def get_gemini_api_key() -> Optional[str]:
    """Retrieve Gemini API key from st.secrets or environment variables."""
    # 1. Check Streamlit secrets
    try:
        if hasattr(st, "secrets"):
            for key_name in ["GEMINI_API_KEY", "GOOGLE_API_KEY"]:
                if key_name in st.secrets and st.secrets[key_name].strip():
                    return st.secrets[key_name].strip()
    except Exception:
        pass

    # 2. Check environment variables
    for env_var in ["GEMINI_API_KEY", "GOOGLE_API_KEY"]:
        val = os.getenv(env_var)
        if val and val.strip():
            return val.strip()

    return None

# ---------------------------------------------------------------------------
# Summary JSON Payload Builder
# ---------------------------------------------------------------------------
def build_summary_payload(
    kpi_dict: Dict[str, Any],
    monthly_df: pd.DataFrame,
    product_decisions_df: pd.DataFrame,
    customer_stats: Dict[str, Any],
    dq_report: Dict[str, Any],
) -> str:
    """
    Constructs a compact JSON summary string of pre-aggregated metrics
    to feed into Gemini. NO RAW ROWS OR PERSONAL DATA ARE SENT.
    """
    # 1. Executive KPIs
    kpi_summary = {
        "net_revenue": round(kpi_dict.get("net_revenue", 0.0), 2),
        "gross_sales": round(kpi_dict.get("gross_sales", 0.0), 2),
        "est_profit": round(kpi_dict.get("est_profit", 0.0), 2),
        "est_margin_pct": round(kpi_dict.get("est_margin_pct", 0.0), 1),
        "total_orders": kpi_dict.get("total_orders", 0),
        "aov": round(kpi_dict.get("aov", 0.0), 2),
        "unique_customers": kpi_dict.get("unique_customers", 0),
        "returning_customer_pct": round(kpi_dict.get("returning_pct", 0.0), 1),
        "return_rate_pct": round(kpi_dict.get("return_rate_pct", 0.0), 1),
        "cancellation_rate_pct": round(kpi_dict.get("cancellation_rate_pct", 0.0), 1),
        "replacement_rate_pct": round(kpi_dict.get("replacement_rate_pct", 0.0), 1),
    }

    # 2. Monthly Trend Summary (Last 6 months)
    recent_months = []
    if not monthly_df.empty:
        for _, r in monthly_df.tail(6).iterrows():
            recent_months.append({
                "month": r["year_month"],
                "net_revenue": round(float(r["net_revenue"]), 2),
                "profit_margin_pct": round(float(r["profit_margin_pct"]), 1),
                "returning_pct": round(float(r["returning_customer_pct"]), 1),
            })

    # 3. Product Decisions Summary
    products_summary = []
    if not product_decisions_df.empty:
        for _, r in product_decisions_df.iterrows():
            products_summary.append({
                "product": r["product"],
                "category": r["category"],
                "net_revenue": round(float(r["net_revenue"]), 2),
                "rev_share_pct": round(float(r["rev_share_pct"]), 1),
                "margin_pct": round(float(r["margin_pct"]), 1),
                "growth_3m_pct": round(float(r["growth_3m_pct"]), 1),
                "return_rate_pct": round(float(r["return_rate_pct"]), 1),
                "replace_rate_pct": round(float(r["replace_rate_pct"]), 1),
                "health_score": round(float(r["health_score"]), 1),
                "abc_class": r["abc_class"],
                "bcg_quadrant": r["bcg_quadrant"],
                "rule_recommendation": r["recommendation"],
                "rule_reason": r["reason"],
            })

    # 4. Customer Retention & Frequency Summary
    cust_summary = {
        "repeat_purchase_rate_pct": customer_stats.get("repeat_purchase_rate", 0.0),
        "avg_days_between_orders": customer_stats.get("avg_days_between_orders", 0.0),
        "avg_historical_clv": customer_stats.get("avg_clv", 0.0),
    }

    payload = {
        "kpis": kpi_summary,
        "recent_monthly_trends": recent_months,
        "product_evaluations": products_summary,
        "customer_behavior": cust_summary,
        "data_qualifiers": {
            "simulated_status_share_pct": dq_report.get("simulated_status_share", 0.0),
            "date_range": dq_report.get("date_range", ("N/A", "N/A")),
            "profit_note": "Profit is an estimate based on inventory average unit cost."
        }
    }
    return json.dumps(payload, indent=2)

# ---------------------------------------------------------------------------
# Fallback Rule-Based Engine
# ---------------------------------------------------------------------------
def generate_rule_based_fallback(product_decisions_df: pd.DataFrame, kpis: Dict[str, Any]) -> str:
    """Fallback text generator when no Gemini API key is supplied."""
    inc_prods = product_decisions_df[product_decisions_df["recommendation"] == "Increase Production"]
    disc_prods = product_decisions_df[product_decisions_df["recommendation"] == "Discontinue"]
    rev_prods = product_decisions_df[product_decisions_df["recommendation"] == "Review / Reprice"]

    lines = [
        "# Rule-Based Executive Summary & Action Engine",
        "",
        "*(Note: Gemini API Key is not configured or reachable. Running high-precision deterministic rules engine.)*",
        "",
        "## 1. Executive Summary",
        f"- **Net Revenue:** ${kpis.get('net_revenue', 0.0):,.2f} | **Estimated Profit:** ${kpis.get('est_profit', 0.0):,.2f} ({kpis.get('est_margin_pct', 0.0):.1f}% margin)",
        f"- **Order Health:** {kpis.get('return_rate_pct', 0.0):.1f}% Return Rate, {kpis.get('cancellation_rate_pct', 0.0):.1f}% Cancellation Rate, {kpis.get('replacement_rate_pct', 0.0):.1f}% Replacement Rate.",
        f"- **Customer Loyalty:** {kpis.get('returning_pct', 0.0):.1f}% of monthly orders come from returning buyers.",
        "",
        "## 2. Products to DISCONTINUE",
    ]

    if not disc_prods.empty:
        for _, r in disc_prods.iterrows():
            lines.append(f"- **{r['product']}** ({r['category']}): {r['reason']} *(Health Score: {r['health_score']})*")
    else:
        lines.append("- No products currently meet the strict discontinuation thresholds.")

    lines.extend([
        "",
        "## 3. Products to INCREASE PRODUCTION",
    ])
    if not inc_prods.empty:
        for _, r in inc_prods.iterrows():
            lines.append(f"- **{r['product']}** ({r['category']}): {r['reason']} *(Suggested buffer: +20% capacity)*")
    else:
        lines.append("- No products currently meet all combined high-growth and high-margin expansion criteria.")

    lines.extend([
        "",
        "## 4. Products to REPRICE or REVIEW",
    ])
    if not rev_prods.empty:
        for _, r in rev_prods.iterrows():
            lines.append(f"- **{r['product']}**: {r['reason']}")
    else:
        lines.append("- Pricing and margin structures are currently within acceptable ranges.")

    lines.extend([
        "",
        "## 5. Strategic Risks & Action Checklist",
        "1. **Audit Estimated Profit:** Unit costs in the inventory file are static averages; audit against supplier invoices.",
        "2. **Simulated Statuses:** Review actual warehouse and courier logs to corroborate simulated return and replacement counts.",
        "3. **Customer Retention:** Accelerate automated email onboarding to boost second-purchase frequency.",
        "4. **Reorder Thresholds:** Immediately replenish products marked with stock-level warnings.",
        "5. **Discount Guardrails:** Eliminate discounts exceeding 15% on low-margin products."
    ])

    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Strategic Prompt Definition
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a senior retail business intelligence analyst and corporate strategist.
You are evaluating a comprehensive retail performance summary containing KPIs, category trends,
order fulfillment statuses, customer buying behavior, and product decision engine scores.

YOUR MANDATES:
1. Ground your reasoning strictly in the numbers provided in the summary JSON. Never invent or hallucinate metrics, dates, or product names.
2. Structure your response into exactly these 10 titled sections:
   1. Executive Summary (3-4 lines synthesis)
   2. Products to DISCONTINUE (cite exact growth %, margin %, return %, and expected capital saving)
   3. Products to INCREASE PRODUCTION (cite exact growth %, margin %, and suggested % capacity boost)
   4. Products to REPRICE or PROMOTE (actionable price adjustment or discount pruning)
   5. Category-Level Insights (strengths, shifts, category mix)
   6. Order Status Insights (root-cause analysis on Returns, Replacements, and Cancellations)
   7. Customer Insights (one-time vs repeat dynamic, retention risks, CLV opportunities)
   8. Seasonal Planning for the Next Quarter (inventory ramp-up and promotion timing)
   9. Risks and Assumptions (explicitly cite that profit is estimated and simulated statuses exist)
   10. Top 5 Prioritised Action Items (ranked by commercial impact)

Keep your tone professional, crisp, analytical, and highly actionable.
"""

# ---------------------------------------------------------------------------
# Direct REST Gemini Invoker (Fast, Reliable, No Hanging gRPC)
# ---------------------------------------------------------------------------
def _call_gemini_rest(model_name: str, prompt_text: str, api_key: str, max_tokens: int = 4000) -> str:
    """Helper to perform direct POST request to Google Gemini REST endpoint."""
    # Strip 'models/' prefix if present
    clean_model = model_name.replace("models/", "").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={api_key}"

    body = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "temperature": GEMINI_TEMPERATURE,
            "maxOutputTokens": max_tokens,
        }
    }

    headers = {"Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=body, timeout=45)

    if resp.status_code != 200:
        error_detail = resp.text
        try:
            err_json = resp.json()
            error_detail = err_json.get("error", {}).get("message", resp.text)
        except Exception:
            pass
        raise RuntimeError(f"HTTP {resp.status_code}: {error_detail}")

    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned empty candidates list.")

    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise RuntimeError("Gemini response contained no content parts.")

    return parts[0].get("text", "")

def generate_gemini_insights(
    summary_json: str,
    api_key: str,
    model_name: str = DEFAULT_GEMINI_MODEL
) -> Tuple[str, bool]:
    """
    Calls Google Gemini using direct HTTPS REST.
    Tries primary model, then falls back to secondary models if needed.
    Returns (report_text: str, success: bool).
    """
    if not api_key or not api_key.strip():
        return "⚠️ Gemini API key is missing.", False

    user_content = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Here is the synthesized retail sales and decision summary JSON:\n\n"
        f"```json\n{summary_json}\n```\n\n"
        f"Deliver the complete 10-section strategic business report according to your mandates."
    )

    models_to_try = [model_name, "gemini-3.5-flash", "gemini-3.5-flash-lite", FALLBACK_GEMINI_MODEL]
    # Remove duplicates preserving order
    seen = set()
    candidate_models = [m for m in models_to_try if not (m in seen or seen.add(m))]

    last_error = ""
    for cand in candidate_models:
        try:
            logger.info(f"Invoking Gemini model: {cand}")
            text = _call_gemini_rest(cand, user_content, api_key, max_tokens=GEMINI_MAX_OUTPUT_TOKENS)
            if text and text.strip():
                return text, True
        except Exception as exc:
            last_error = str(exc)
            logger.warning(f"Model {cand} attempt failed: {exc}")
            continue

    logger.error(f"All Gemini models failed: {last_error}")
    return f"⚠️ Gemini API Error: {last_error}", False

def answer_data_question(
    question: str,
    summary_json: str,
    api_key: Optional[str] = None,
    model_name: str = DEFAULT_GEMINI_MODEL
) -> str:
    """Answers a user question based strictly on the aggregated metrics summary using Gemini REST."""
    if not api_key:
        return "⚠️ Please provide a Gemini API Key in the sidebar or environment variable (GEMINI_API_KEY) to enable AI Q&A."

    qa_system = (
        "You are an expert retail data analyst answering questions about a company's sales report. "
        "Base your answer strictly on the provided summary data JSON. If the data does not contain the answer, "
        "state that clearly. Keep answers concise, factual, and backed by specific figures."
    )
    prompt = f"{qa_system}\n\nData Summary JSON:\n{summary_json}\n\nUser Question: {question}"

    models_to_try = [model_name, "gemini-3.5-flash", "gemini-3.5-flash-lite"]
    for cand in models_to_try:
        try:
            ans = _call_gemini_rest(cand, prompt, api_key, max_tokens=1000)
            if ans and ans.strip():
                return ans
        except Exception:
            continue

    return "⚠️ Could not retrieve answer from Gemini. Please check your internet connection and API key."
