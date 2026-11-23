"""
decision_engine.py
==================
Algorithmic Product Decision Engine:
Computes ABC classification, BCG quadrant matrix, stock-out risk,
composite Product Health Score (0-100), and automated action recommendations
(Increase Production, Discontinue, Review / Reprice, Maintain).
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from config import (
    ABC_THRESHOLDS,
    DECISION_THRESHOLDS,
    DEFAULT_INVENTORY,
    HEALTH_SCORE_WEIGHTS,
    get_logger,
)

logger = get_logger("decision_engine")

def evaluate_product_decisions(
    df: pd.DataFrame,
    thresholds: Optional[Dict[str, Any]] = None,
    product_forecasts: Optional[Dict[str, Any]] = None,
    inventory_data: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Evaluates every product in the dataset and generates metric summaries,
    classification (ABC, BCG), health score, and actionable business recommendations.
    """
    if df.empty:
        return pd.DataFrame()

    cfg = DECISION_THRESHOLDS.copy()
    if thresholds:
        cfg.update(thresholds)

    # Pre-aggregate by product
    total_company_rev = df["net_revenue"].sum()
    all_months = sorted(df["year_month"].unique())

    # Build inventory lookup
    inv_map = {}
    if inventory_data is not None and not inventory_data.empty:
        for _, row in inventory_data.iterrows():
            inv_map[row["product"]] = {
                "stock": row.get("current_stock", 0),
                "reorder_point": row.get("reorder_point", 0),
                "lead_time_days": row.get("lead_time_days", 14),
            }
    else:
        inv_map = DEFAULT_INVENTORY

    records = []
    
    for prod, p_df in df.groupby("product"):
        cat = p_df["category"].iloc[0] if "category" in p_df.columns else "General"
        units_sold = int(p_df["quantity"].sum())
        gross_sales = float(p_df["total_sales"].sum())
        net_rev = float(p_df["net_revenue"].sum())
        est_profit = float(p_df["est_profit"].sum())

        margin_pct = (est_profit / net_rev * 100.0) if net_rev > 0 else 0.0
        rev_share_pct = (net_rev / total_company_rev * 100.0) if total_company_rev > 0 else 0.0

        total_orders = len(p_df)
        valid_orders = p_df[p_df["order_status"] != "Cancelled"]
        n_valid = len(valid_orders)

        n_ret = int(p_df["is_returned"].sum())
        n_rep = int(p_df["is_replaced"].sum())
        n_canc = int(p_df["is_cancelled"].sum())

        return_rate_pct = (n_ret / n_valid * 100.0) if n_valid > 0 else 0.0
        replace_rate_pct = (n_rep / n_valid * 100.0) if n_valid > 0 else 0.0
        cancel_rate_pct = (n_canc / total_orders * 100.0) if total_orders > 0 else 0.0

        # Monthly time series for growth & volatility
        m_sales = p_df.groupby("year_month")["net_revenue"].sum()
        m_series = pd.Series(index=all_months, data=0.0)
        m_series.update(m_sales)

        # Volatility: Coefficient of Variation (std / mean)
        m_mean = m_series.mean()
        m_std = m_series.std()
        cv = (m_std / m_mean) if m_mean > 0 else 1.0

        # 3-Month Growth: Last 3 months vs Previous 3 months
        if len(all_months) >= 6:
            last_3 = m_series.iloc[-3:].sum()
            prev_3 = m_series.iloc[-6:-3].sum()
            growth_3m_pct = ((last_3 - prev_3) / prev_3 * 100.0) if prev_3 > 0 else 0.0
        elif len(all_months) >= 2:
            growth_3m_pct = ((m_series.iloc[-1] - m_series.iloc[-2]) / m_series.iloc[-2] * 100.0) if m_series.iloc[-2] > 0 else 0.0
        else:
            growth_3m_pct = 0.0

        # 6-Month Trend Slope (normalized by mean)
        if len(all_months) >= 6:
            y_vals = m_series.iloc[-6:].values
            x_vals = np.arange(len(y_vals))
            slope, _ = np.polyfit(x_vals, y_vals, 1)
            norm_slope = (slope / m_mean * 100.0) if m_mean > 0 else 0.0
        else:
            norm_slope = 0.0

        # Loss-making months check (last 3 months)
        m_profit = p_df.groupby("year_month")["est_profit"].sum()
        p_profit_series = pd.Series(index=all_months, data=0.0)
        p_profit_series.update(m_profit)
        recent_loss_months = int((p_profit_series.tail(3) < 0).sum())

        # Forecast Growth % if available
        fc_growth_pct = 0.0
        if product_forecasts and prod in product_forecasts:
            fc_growth_pct = product_forecasts[prod].get("forecast_growth_pct", 0.0)

        # Stock / Inventory Signals
        inv_info = inv_map.get(prod, {"stock": 100, "reorder_point": 80, "lead_time_days": 14})
        curr_stock = inv_info.get("stock", 0)
        reorder_point = inv_info.get("reorder_point", 0)
        lead_time = inv_info.get("lead_time_days", 14)
        is_low_stock = curr_stock <= reorder_point

        records.append({
            "product": prod,
            "category": cat,
            "units_sold": units_sold,
            "gross_sales": round(gross_sales, 2),
            "net_revenue": round(net_rev, 2),
            "est_profit": round(est_profit, 2),
            "margin_pct": round(margin_pct, 1),
            "rev_share_pct": round(rev_share_pct, 1),
            "return_rate_pct": round(return_rate_pct, 1),
            "replace_rate_pct": round(replace_rate_pct, 1),
            "cancel_rate_pct": round(cancel_rate_pct, 1),
            "growth_3m_pct": round(growth_3m_pct, 1),
            "trend_slope_pct": round(norm_slope, 1),
            "forecast_growth_pct": round(fc_growth_pct, 1),
            "volatility_cv": round(cv, 2),
            "recent_loss_months": recent_loss_months,
            "current_stock": curr_stock,
            "reorder_point": reorder_point,
            "lead_time_days": lead_time,
            "is_low_stock": is_low_stock,
        })

    result_df = pd.DataFrame(records)
    if result_df.empty:
        return result_df

    # 1. ABC Classification (Cumulative Revenue)
    result_df = result_df.sort_values("net_revenue", ascending=False).reset_index(drop=True)
    cum_share = result_df["net_revenue"].cumsum() / result_df["net_revenue"].sum()
    
    def assign_abc(cum_val: float) -> str:
        if cum_val <= ABC_THRESHOLDS["A"]:
            return "A"
        elif cum_val <= ABC_THRESHOLDS["B"]:
            return "B"
        return "C"

    result_df["abc_class"] = cum_share.apply(assign_abc)

    # 2. BCG Quadrant (Growth vs Revenue Share)
    median_share = result_df["rev_share_pct"].median()
    median_growth = 0.0  # benchmark is positive vs negative growth

    def assign_bcg(row) -> str:
        high_share = row["rev_share_pct"] >= median_share
        high_growth = row["growth_3m_pct"] >= median_growth
        if high_share and high_growth:
            return "Star"
        elif high_share and not high_growth:
            return "Cash Cow"
        elif not high_share and high_growth:
            return "Question Mark"
        return "Dog"

    result_df["bcg_quadrant"] = result_df.apply(assign_bcg, axis=1)

    # 3. Product Health Score (0 to 100)
    # Weights: growth 30%, margin 30%, revenue share 20%, return+replacement rate 10%, consistency 10%
    w = HEALTH_SCORE_WEIGHTS
    
    # Normalizations between 0 and 100
    # Growth normalized: -30% -> 0, +30% -> 100
    g_score = np.clip((result_df["growth_3m_pct"] + 30) / 60.0 * 100.0, 0, 100)
    # Margin normalized: 0% -> 0, 40% -> 100
    m_score = np.clip(result_df["margin_pct"] / 40.0 * 100.0, 0, 100)
    # Rev share normalized: relative to max product
    max_share = result_df["rev_share_pct"].max() or 1.0
    s_score = np.clip(result_df["rev_share_pct"] / max_share * 100.0, 0, 100)
    # Return + Replacement penalty: 0% -> 100, 30% -> 0
    ret_rep = result_df["return_rate_pct"] + result_df["replace_rate_pct"]
    r_score = np.clip((30.0 - ret_rep) / 30.0 * 100.0, 0, 100)
    # Consistency: low CV is good. CV 0 -> 100, CV 1.5 -> 0
    c_score = np.clip((1.5 - result_df["volatility_cv"]) / 1.5 * 100.0, 0, 100)

    health_score = (
        w["growth"] * g_score +
        w["margin"] * m_score +
        w["revenue_share"] * s_score +
        w["return_replacement_rate"] * r_score +
        w["consistency"] * c_score
    )
    result_df["health_score"] = health_score.round(1)

    # 4. Recommendation Rules Engine
    recommendations = []
    reasons = []
    confidences = []

    for _, row in result_df.iterrows():
        growth = row["growth_3m_pct"]
        margin = row["margin_pct"]
        fc_growth = row["forecast_growth_pct"]
        ret_rate = row["return_rate_pct"]
        rep_rate = row["replace_rate_pct"]
        rev_share = row["rev_share_pct"]
        loss_months = row["recent_loss_months"]
        is_low_stock = row["is_low_stock"]

        # RULE 1: INCREASE PRODUCTION
        # growth > 15% AND margin > 15% AND forecast trending up AND return rate low.
        if (
            growth >= cfg["increase_growth_pct"] and
            margin >= cfg["increase_margin_pct"] and
            fc_growth >= 0 and
            ret_rate <= cfg["increase_max_return_rate"]
        ):
            rec = "Increase Production"
            conf = "High" if (growth > 20 and margin > 25) else "Medium"
            stock_note = " ⚠️ Stock is below reorder point - urgent priority!" if is_low_stock else ""
            reason = (
                f"Strong revenue momentum (+{growth:.1f}% 3M growth), healthy margin ({margin:.1f}%), "
                f"upward forecast (+{fc_growth:.1f}%), and low returns ({ret_rate:.1f}%).{stock_note}"
            )

        # RULE 2: DISCONTINUE
        # (growth < -15% AND (margin < 5% OR revenue share < 1%)) OR loss-making for 3+ months OR very high return rate.
        elif (
            (growth <= cfg["discontinue_growth_pct"] and (margin < cfg["discontinue_margin_pct"] or rev_share < cfg["discontinue_revenue_share"])) or
            loss_months >= cfg["discontinue_loss_months"] or
            ret_rate >= cfg["discontinue_return_rate"]
        ):
            rec = "Discontinue"
            conf = "High" if (loss_months >= 3 or ret_rate >= 25 or growth < -20) else "Medium"
            triggers = []
            if growth <= cfg["discontinue_growth_pct"]:
                triggers.append(f"steep contraction ({growth:.1f}% growth)")
            if margin < cfg["discontinue_margin_pct"]:
                triggers.append(f"weak margin ({margin:.1f}%)")
            if rev_share < cfg["discontinue_revenue_share"]:
                triggers.append(f"negligible revenue share ({rev_share:.1f}%)")
            if loss_months >= cfg["discontinue_loss_months"]:
                triggers.append(f"consecutive losses ({loss_months} months)")
            if ret_rate >= cfg["discontinue_return_rate"]:
                triggers.append(f"critical return rate ({ret_rate:.1f}%)")
            reason = f"Severe underperformance triggered by: {', '.join(triggers)}."

        # RULE 3: REVIEW / REPRICE
        # good sales but low or negative margin, or high return/replacement rate
        elif (
            margin <= cfg["review_max_margin_pct"] or
            ret_rate >= cfg["review_high_return_rate"] or
            rep_rate >= cfg["review_high_replace_rate"]
        ):
            rec = "Review / Reprice"
            conf = "Medium"
            sub_reasons = []
            if margin <= cfg["review_max_margin_pct"]:
                sub_reasons.append(f"low margin ({margin:.1f}%) - suggest price hike or discount reduction")
            if ret_rate >= cfg["review_high_return_rate"]:
                sub_reasons.append(f"elevated return rate ({ret_rate:.1f}%) - check build quality")
            if rep_rate >= cfg["review_high_replace_rate"]:
                sub_reasons.append(f"high replacement requests ({rep_rate:.1f}%) - investigate packaging/shipping")
            reason = f"Operational review required due to: {'; '.join(sub_reasons)}."

        # RULE 4: MAINTAIN
        else:
            rec = "Maintain"
            conf = "Low" if len(all_months) < 6 else "Medium"
            reason = (
                f"Stable operational performance: {margin:.1f}% margin, {growth:+.1f}% growth, "
                f"and acceptable return rate ({ret_rate:.1f}%)."
            )

        recommendations.append(rec)
        reasons.append(reason)
        confidences.append(conf)

    result_df["recommendation"] = recommendations
    result_df["confidence"] = confidences
    result_df["reason"] = reasons

    return result_df

