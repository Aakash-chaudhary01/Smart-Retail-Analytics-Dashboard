"""
customers.py
============
Customer analytics engine: Cohort Retention Matrix, RFM Segmentation,
Customer Lifetime Value (CLV), and Buying Frequency behaviors.
"""

from __future__ import annotations
from typing import Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd
from datetime import datetime

from config import get_logger

logger = get_logger("customers")

def compute_customer_rfm(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes Recency, Frequency, and Monetary (RFM) metrics and classifies
    customers into behavioral segments (Champions, Loyal, At Risk, Lost, New).
    Excludes walk-in customers and cancelled transactions.
    """
    # Filter valid purchases with customer_id
    if "customer_id" not in df.columns or df.empty:
        return pd.DataFrame()
    valid_df = df[df["customer_id"].notna() & (df["order_status"] != "Cancelled")].copy()
    if valid_df.empty:
        return pd.DataFrame()

    snapshot_date = valid_df["order_date"].max() + pd.Timedelta(days=1)

    rfm = valid_df.groupby("customer_id").agg(
        customer_name=("customer_name", "first") if "customer_name" in valid_df.columns else ("customer_id", "first"),
        channel=("channel", "first") if "channel" in valid_df.columns else ("customer_id", lambda x: "Unknown"),
        last_order_date=("order_date", "max"),
        first_order_date=("order_date", "min"),
        frequency=("order_id", "nunique") if "order_id" in valid_df.columns else ("order_date", "count"),
        monetary=("net_revenue", "sum"),
        avg_order_value=("net_revenue", "mean"),
    ).reset_index()

    rfm["recency"] = (snapshot_date - rfm["last_order_date"]).dt.days
    rfm["monetary"] = rfm["monetary"].round(2)
    rfm["avg_order_value"] = rfm["avg_order_value"].round(2)

    # Rank & Score (Handle small counts safely)
    # Recency score: lower recency = higher score (5 = most recent)
    r_labels = [5, 4, 3, 2, 1]
    rfm["r_score"] = pd.qcut(rfm["recency"].rank(method="first"), q=5, labels=r_labels).astype(int)

    # Frequency score: most customers have 1 order
    def score_frequency(f: int) -> int:
        if f >= 4:
            return 5
        elif f == 3:
            return 4
        elif f == 2:
            return 3
        return 1

    rfm["f_score"] = rfm["frequency"].apply(score_frequency)

    # Monetary score
    m_labels = [1, 2, 3, 4, 5]
    rfm["m_score"] = pd.qcut(rfm["monetary"].rank(method="first"), q=5, labels=m_labels).astype(int)

    # Customer Segmentation Rules
    def assign_segment(row) -> str:
        r, f, m = row["r_score"], row["f_score"], row["m_score"]
        if f >= 4 and r >= 3:
            return "Champions"
        elif f >= 3 and r >= 2:
            return "Loyal Customers"
        elif f >= 3 and r < 2:
            return "At Risk"
        elif f <= 2 and r >= 4:
            return "Recent / New Buyers"
        elif f <= 2 and r <= 2 and m <= 2:
            return "Lost Customers"
        else:
            return "Potential Loyalists"

    rfm["segment"] = rfm.apply(assign_segment, axis=1)
    return rfm

def compute_cohort_retention(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Computes monthly cohort retention counts and percentage retention matrix.
    Row = Cohort Month (first valid purchase), Column = Months Since First Purchase (0, 1, 2, ...).
    """
    if "customer_id" not in df.columns or df.empty:
        return pd.DataFrame(), pd.DataFrame()
    valid = df[df["customer_id"].notna() & (df["order_status"] != "Cancelled")].copy()
    if valid.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Ensure first_purchase_month exists
    if "first_purchase_month" not in valid.columns or valid["first_purchase_month"].isna().all():
        first_dates = valid.groupby("customer_id")["order_date"].min().to_dict()
        valid["first_purchase_month"] = valid["customer_id"].map(
            lambda cid: first_dates[cid].strftime("%Y-%m")
        )

    valid["order_period"] = valid["order_date"].dt.to_period("M")
    valid["cohort_period"] = pd.to_datetime(valid["first_purchase_month"]).dt.to_period("M")

    # Cohort index (months elapsed)
    valid["cohort_index"] = (
        (valid["order_period"].dt.year - valid["cohort_period"].dt.year) * 12 +
        (valid["order_period"].dt.month - valid["cohort_period"].dt.month)
    )

    cohort_data = valid.groupby(["first_purchase_month", "cohort_index"])["customer_id"].nunique().reset_index()
    cohort_counts = cohort_data.pivot(index="first_purchase_month", columns="cohort_index", values="customer_id")

    # Cohort sizes (period 0)
    cohort_sizes = cohort_counts.iloc[:, 0]
    retention_pct = cohort_counts.divide(cohort_sizes, axis=0) * 100.0

    return cohort_counts, retention_pct.round(1)

def compute_customer_summary_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes overarching customer metrics: repeat purchase rate,
    average days between orders, and estimated Customer Lifetime Value (CLV).
    """
    empty_res = {
        "total_unique_customers": 0,
        "repeat_customers": 0,
        "repeat_purchase_rate": 0.0,
        "avg_days_between_orders": 0.0,
        "avg_clv": 0.0,
        "top_10_customers": pd.DataFrame(),
        "frequency_distribution": pd.DataFrame(),
    }
    if "customer_id" not in df.columns or df.empty:
        return empty_res
    valid = df[df["customer_id"].notna() & (df["order_status"] != "Cancelled")].copy()
    if valid.empty:
        return empty_res

    cust_summary = valid.groupby("customer_id").agg(
        customer_name=("customer_name", "first") if "customer_name" in valid.columns else ("customer_id", "first"),
        total_orders=("order_id", "nunique") if "order_id" in valid.columns else ("order_date", "count"),
        total_net_spend=("net_revenue", "sum"),
        first_purchase=("order_date", "min"),
        last_purchase=("order_date", "max"),
    ).reset_index()

    n_total = len(cust_summary)
    repeat_mask = cust_summary["total_orders"] > 1
    n_repeat = int(repeat_mask.sum())
    repeat_rate = (n_repeat / n_total * 100.0) if n_total > 0 else 0.0

    # Average days between orders for customers with 2+ orders
    if "days_since_prev_order" in valid.columns:
        days_between = valid["days_since_prev_order"].dropna()
        avg_days_between = float(days_between.mean()) if not days_between.empty else 0.0
    else:
        avg_days_between = 0.0

    # Average historical CLV
    avg_clv = float(cust_summary["total_net_spend"].mean()) if n_total > 0 else 0.0

    # Top 10 Customers
    top_10 = (
        cust_summary.sort_values("total_net_spend", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )
    top_10["total_net_spend"] = top_10["total_net_spend"].round(2)

    # Frequency distribution
    freq_dist = cust_summary["total_orders"].value_counts().sort_index().reset_index()
    freq_dist.columns = ["orders_count", "customer_count"]
    freq_dist["percentage"] = (freq_dist["customer_count"] / n_total * 100.0).round(1)

    return {
        "total_unique_customers": n_total,
        "repeat_customers": n_repeat,
        "repeat_purchase_rate": round(repeat_rate, 2),
        "avg_days_between_orders": round(avg_days_between, 1),
        "avg_clv": round(avg_clv, 2),
        "top_10_customers": top_10,
        "frequency_distribution": freq_dist,
    }
