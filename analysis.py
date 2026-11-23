"""
analysis.py
===========
Data pipeline, cleaning, feature engineering, and core metric computations
for the Retail Sales Dashboard.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd
import streamlit as st

from config import (
    DEFAULT_INVENTORY,
    PRODUCT_CATEGORY_MAP,
    get_logger,
)

logger = get_logger("analysis")

# ---------------------------------------------------------------------------
# Data Loading & Standard Cleaning Pipeline
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_default_data(filepath: str = "data/retail_sales_combined.csv") -> pd.DataFrame:
    """Load default combined retail sales CSV file."""
    df = pd.read_csv(filepath)
    df["order_date"] = pd.to_datetime(df["order_date"])
    if "delivery_date" in df.columns:
        df["delivery_date"] = pd.to_datetime(df["delivery_date"])
    return df

def clean_and_derive_features(
    raw_df: pd.DataFrame,
    default_status: Optional[str] = "Delivered"
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Cleans raw dataset, handles missing fields, computes derived metrics,
    and returns cleaned DataFrame alongside a Data Quality Report dict.
    """
    df = raw_df.copy()
    initial_rows = len(df)
    dropped_info: Dict[str, int] = {}

    # 1. Standardize column names (lowercase, stripped, underscored)
    df.columns = [str(c).strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]

    # 2. Check & drop exact duplicate rows
    dupes = df.duplicated().sum()
    if dupes > 0:
        df = df.drop_duplicates()
        dropped_info["duplicate_rows"] = int(dupes)

    # 3. Ensure order_date is parsed as datetime
    if "order_date" in df.columns:
        df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
        invalid_dates = df["order_date"].isna().sum()
        if invalid_dates > 0:
            df = df.dropna(subset=["order_date"])
            dropped_info["invalid_dates"] = int(invalid_dates)
    else:
        raise ValueError("Missing mandatory column: 'order_date'")

    # 4. Clean and validate quantity and sales
    if "quantity" in df.columns:
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(1)
        invalid_qty = (df["quantity"] <= 0).sum()
        if invalid_qty > 0:
            df = df[df["quantity"] > 0]
            dropped_info["non_positive_quantity"] = int(invalid_qty)
    else:
        df["quantity"] = 1

    if "total_sales" in df.columns:
        df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0.0)
        neg_sales = (df["total_sales"] < 0).sum()
        if neg_sales > 0:
            df = df[df["total_sales"] >= 0]
            dropped_info["negative_sales"] = int(neg_sales)
    else:
        raise ValueError("Missing mandatory column: 'total_sales'")

    # 5. Product & Category
    if "product" not in df.columns:
        raise ValueError("Missing mandatory column: 'product'")
    df["product"] = df["product"].astype(str).str.strip()

    if "category" not in df.columns:
        # Map using default dictionary or assign 'General'
        df["category"] = df["product"].map(PRODUCT_CATEGORY_MAP).fillna("Other")
    else:
        df["category"] = df["category"].fillna(df["product"].map(PRODUCT_CATEGORY_MAP)).fillna("Other")

    # 6. Order Status normalization
    if "order_status" not in df.columns:
        if default_status:
            df["order_status"] = default_status
        else:
            df["order_status"] = "Delivered"
    else:
        df["order_status"] = df["order_status"].astype(str).str.title().str.strip()
        # Map unknown statuses to closest standard
        status_map = {
            "Complete": "Delivered", "Completed": "Delivered", "Success": "Delivered",
            "Return": "Returned", "Refund": "Returned", "Refunded": "Returned",
            "Replace": "Replaced", "Exchange": "Replaced",
            "Cancel": "Cancelled", "Canceled": "Cancelled", "Void": "Cancelled"
        }
        df["order_status"] = df["order_status"].replace(status_map)
        valid_statuses = {"Delivered", "Returned", "Replaced", "Cancelled"}
        df["order_status"] = df["order_status"].apply(lambda s: s if s in valid_statuses else "Delivered")

    # Status binary indicator flags
    df["is_delivered"] = (df["order_status"] == "Delivered").astype(int)
    df["is_returned"] = (df["order_status"] == "Returned").astype(int)
    df["is_replaced"] = (df["order_status"] == "Replaced").astype(int)
    df["is_cancelled"] = (df["order_status"] == "Cancelled").astype(int)

    # 7. Net Revenue
    # net_revenue = total_sales for Delivered and Replaced orders, 0 for Returned and Cancelled.
    if "net_revenue" not in df.columns:
        df["net_revenue"] = np.where(
            df["order_status"].isin(["Delivered", "Replaced"]),
            df["total_sales"],
            0.0
        )
    else:
        df["net_revenue"] = pd.to_numeric(df["net_revenue"], errors="coerce").fillna(0.0)

    # 8. Unit Cost & Estimated Profit
    if "est_unit_cost" not in df.columns:
        if len(df) > 0:
            df["est_unit_cost"] = df["product"].apply(
                lambda p: float(DEFAULT_INVENTORY.get(p, {}).get("unit_cost", 50.0))
            )
        else:
            df["est_unit_cost"] = pd.Series(dtype=float)
    df["est_unit_cost"] = pd.to_numeric(df["est_unit_cost"], errors="coerce").fillna(50.0).astype(float)

    if "est_profit" not in df.columns:
        if len(df) > 0:
            # Profit = net_revenue - (unit_cost * quantity) for Delivered/Replaced; slight negative cost for return
            df["est_profit"] = np.where(
                df["order_status"].isin(["Delivered", "Replaced"]),
                df["net_revenue"] - (df["est_unit_cost"] * df["quantity"]),
                np.where(df["order_status"] == "Returned", -0.05 * df["est_unit_cost"] * df["quantity"], 0.0)
            )
        else:
            df["est_profit"] = pd.Series(dtype=float)
    df["est_profit"] = pd.to_numeric(df["est_profit"], errors="coerce").fillna(0.0).astype(float)

    # 9. Date Hierarchy
    df["year"] = df["order_date"].dt.year
    df["quarter"] = "Q" + df["order_date"].dt.quarter.astype(str)
    df["month_num"] = df["order_date"].dt.month
    df["month_name"] = df["order_date"].dt.strftime("%B")
    df["year_month"] = df["order_date"].dt.strftime("%Y-%m")
    df["day_of_week"] = df["order_date"].dt.strftime("%A")

    # 10. Outlier Flagging using Interquartile Range (IQR) on total_sales
    q25 = df["total_sales"].quantile(0.25)
    q75 = df["total_sales"].quantile(0.75)
    iqr = q75 - q25
    upper_bound = q75 + 3.0 * iqr
    df["is_sales_outlier"] = df["total_sales"] > upper_bound

    # 11. Customer Lineage & Frequency Segmentation (if customer_id is present)
    has_customer_id = "customer_id" in df.columns and df["customer_id"].notna().sum() > 0

    if has_customer_id:
        df["customer_id"] = df["customer_id"].astype(str).str.strip().replace(["nan", "None", ""], np.nan)
        df = df.sort_values("order_date").reset_index(drop=True)

        valid_mask = (df["order_status"] != "Cancelled") & df["customer_id"].notna()
        valid_orders = df[valid_mask]

        # First valid purchase month per customer
        first_dates = valid_orders.groupby("customer_id")["order_date"].min().to_dict()
        first_months = {cid: dt.strftime("%Y-%m") for cid, dt in first_dates.items()}
        df["first_purchase_month"] = df["customer_id"].map(first_months)

        # Total valid orders per customer
        order_counts = valid_orders.groupby("customer_id")["order_id"].nunique().to_dict() if "order_id" in df.columns else valid_orders.groupby("customer_id")["order_date"].count().to_dict()
        df["customer_total_orders"] = df["customer_id"].map(order_counts).fillna(0).astype(int)

        # customer_type_in_month:
        # A customer is "Returning" in a month if their first valid purchase was in an earlier month; otherwise "New".
        def calc_cust_type_month(r):
            if pd.isna(r["customer_id"]):
                return "Walk-in (unknown)"
            if r["order_status"] == "Cancelled":
                return "Cancelled (not counted)"
            f_month = r["first_purchase_month"]
            if pd.isna(f_month):
                return "New"
            return "Returning" if r["year_month"] > f_month else "New"

        df["customer_type_in_month"] = df.apply(calc_cust_type_month, axis=1)

        # Frequency segments
        def calc_freq_segment(total_ord: int, cid: Any) -> str:
            if pd.isna(cid):
                return "Not applicable"
            if total_ord <= 1:
                return "One-time buyer"
            elif total_ord == 2:
                return "Repeat buyer (2)"
            else:
                return "Loyal buyer (3+)"

        df["frequency_segment"] = [
            calc_freq_segment(tot, cid) for tot, cid in zip(df["customer_total_orders"], df["customer_id"])
        ]

        # Calculate days_since_prev_order if not already provided
        if "days_since_prev_order" not in df.columns:
            days_prev_list = []
            cust_last_seen = {}
            for _, r in df.iterrows():
                cid = r["customer_id"]
                dt = r["order_date"]
                stat = r["order_status"]
                if pd.isna(cid) or stat == "Cancelled":
                    days_prev_list.append(np.nan)
                else:
                    if cid in cust_last_seen:
                        days_prev_list.append(float((dt - cust_last_seen[cid]).days))
                    else:
                        days_prev_list.append(np.nan)
                    cust_last_seen[cid] = dt
            df["days_since_prev_order"] = days_prev_list
    else:
        df["customer_id"] = np.nan
        df["first_purchase_month"] = np.nan
        df["customer_total_orders"] = 0
        df["customer_type_in_month"] = "Walk-in (unknown)"
        df["frequency_segment"] = "Not applicable"
        df["days_since_prev_order"] = np.nan

    # Data Quality Report
    simulated_share = 0.0
    if "status_source" in df.columns:
        sim_count = (df["status_source"] == "Simulated").sum()
        simulated_share = round((sim_count / len(df)) * 100, 1)

    null_counts = df.isna().sum().to_dict()

    dq_report = {
        "initial_rows": initial_rows,
        "cleaned_rows": len(df),
        "dropped_info": dropped_info,
        "null_counts": {k: v for k, v in null_counts.items() if v > 0},
        "date_range": (
            df["order_date"].min().strftime("%Y-%m-%d") if not df.empty else "N/A",
            df["order_date"].max().strftime("%Y-%m-%d") if not df.empty else "N/A"
        ),
        "num_products": df["product"].nunique(),
        "num_categories": df["category"].nunique(),
        "num_customers": df["customer_id"].dropna().nunique() if has_customer_id else 0,
        "simulated_status_share": simulated_share,
        "has_customer_id": has_customer_id,
        "outlier_count": int(df["is_sales_outlier"].sum()),
    }

    return df, dq_report

# ---------------------------------------------------------------------------
# High-Level KPI Computations
# ---------------------------------------------------------------------------
def calculate_kpis(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate executive KPI summary metrics with month-over-month deltas."""
    if df.empty:
        return {
            "net_revenue": 0.0, "gross_sales": 0.0, "est_profit": 0.0,
            "est_margin_pct": 0.0, "total_orders": 0, "aov": 0.0,
            "unique_customers": 0, "returning_pct": 0.0,
            "return_rate_pct": 0.0, "cancellation_rate_pct": 0.0, "replacement_rate_pct": 0.0,
            "mom_deltas": {}
        }

    # High-level totals
    net_rev = float(df["net_revenue"].sum())
    gross_sales = float(df["total_sales"].sum())
    est_profit = float(df["est_profit"].sum())
    margin_pct = (est_profit / net_rev * 100.0) if net_rev > 0 else 0.0

    total_orders = len(df)
    valid_orders = df[df["order_status"] != "Cancelled"]
    n_valid = len(valid_orders)
    n_delivered_replaced = len(df[df["order_status"].isin(["Delivered", "Replaced"])])

    # AOV based on orders that generate net revenue
    aov = (net_rev / n_delivered_replaced) if n_delivered_replaced > 0 else 0.0

    # Customers
    valid_customers = valid_orders["customer_id"].dropna()
    unique_custs = valid_customers.nunique()

    # Returning customer %:
    # orders where customer_type_in_month == 'Returning' / total valid orders with customer_id
    cust_orders = valid_orders[valid_orders["customer_id"].notna()]
    if len(cust_orders) > 0:
        returning_orders = (cust_orders["customer_type_in_month"] == "Returning").sum()
        returning_pct = (returning_orders / len(cust_orders)) * 100.0
    else:
        returning_pct = 0.0

    # Rates:
    # Return rate = Returned / non-cancelled orders
    # Cancellation rate = Cancelled / all orders
    # Replacement rate = Replaced / non-cancelled orders
    n_returned = int(df["is_returned"].sum())
    n_cancelled = int(df["is_cancelled"].sum())
    n_replaced = int(df["is_replaced"].sum())

    return_rate_pct = (n_returned / n_valid * 100.0) if n_valid > 0 else 0.0
    cancellation_rate_pct = (n_cancelled / total_orders * 100.0) if total_orders > 0 else 0.0
    replacement_rate_pct = (n_replaced / n_valid * 100.0) if n_valid > 0 else 0.0

    # MoM Deltas: Compare latest month vs previous month
    months_sorted = sorted(df["year_month"].unique())
    mom_deltas: Dict[str, Optional[float]] = {}

    if len(months_sorted) >= 2:
        curr_m = months_sorted[-1]
        prev_m = months_sorted[-2]

        df_curr = df[df["year_month"] == curr_m]
        df_prev = df[df["year_month"] == prev_m]

        def pct_change(c: float, p: float) -> Optional[float]:
            return ((c - p) / p * 100.0) if p != 0 else None

        c_rev = df_curr["net_revenue"].sum()
        p_rev = df_prev["net_revenue"].sum()
        mom_deltas["net_revenue"] = pct_change(c_rev, p_rev)

        c_gross = df_curr["total_sales"].sum()
        p_gross = df_prev["total_sales"].sum()
        mom_deltas["gross_sales"] = pct_change(c_gross, p_gross)

        c_prof = df_curr["est_profit"].sum()
        p_prof = df_prev["est_profit"].sum()
        mom_deltas["est_profit"] = pct_change(c_prof, p_prof)

        c_orders = len(df_curr)
        p_orders = len(df_prev)
        mom_deltas["total_orders"] = pct_change(c_orders, p_orders)

        c_custs = df_curr["customer_id"].dropna().nunique()
        p_custs = df_prev["customer_id"].dropna().nunique()
        mom_deltas["unique_customers"] = pct_change(c_custs, p_custs)
    else:
        for k in ["net_revenue", "gross_sales", "est_profit", "total_orders", "unique_customers"]:
            mom_deltas[k] = None

    return {
        "net_revenue": net_rev,
        "gross_sales": gross_sales,
        "est_profit": est_profit,
        "est_margin_pct": margin_pct,
        "total_orders": total_orders,
        "aov": aov,
        "unique_customers": unique_custs,
        "returning_pct": returning_pct,
        "return_rate_pct": return_rate_pct,
        "cancellation_rate_pct": cancellation_rate_pct,
        "replacement_rate_pct": replacement_rate_pct,
        "mom_deltas": mom_deltas,
    }

# ---------------------------------------------------------------------------
# Monthly Aggregation Tables for Charts
# ---------------------------------------------------------------------------
def get_monthly_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate sales, profit, orders, and customer breakdown per year_month."""
    if df.empty:
        return pd.DataFrame()

    grp = df.groupby("year_month").agg(
        net_revenue=("net_revenue", "sum"),
        total_sales=("total_sales", "sum"),
        est_profit=("est_profit", "sum"),
        total_orders=("order_id", "count") if "order_id" in df.columns else ("total_sales", "count"),
        units_sold=("quantity", "sum"),
        delivered_orders=("is_delivered", "sum"),
        returned_orders=("is_returned", "sum"),
        replaced_orders=("is_replaced", "sum"),
        cancelled_orders=("is_cancelled", "sum"),
    ).reset_index()

    # 3-Month Moving Average of Net Revenue
    grp["net_revenue_ma3"] = grp["net_revenue"].rolling(window=3, min_periods=1).mean()
    grp["profit_margin_pct"] = np.where(
        grp["net_revenue"] > 0,
        (grp["est_profit"] / grp["net_revenue"]) * 100.0,
        0.0
    )

    # Customer counts per month
    valid_df = df[df["order_status"] != "Cancelled"]
    new_cust_counts = valid_df[valid_df["customer_type_in_month"] == "New"].groupby("year_month")["customer_id"].nunique().to_dict()
    ret_cust_counts = valid_df[valid_df["customer_type_in_month"] == "Returning"].groupby("year_month")["customer_id"].nunique().to_dict()

    grp["new_customers"] = grp["year_month"].map(new_cust_counts).fillna(0).astype(int)
    grp["returning_customers"] = grp["year_month"].map(ret_cust_counts).fillna(0).astype(int)
    grp["total_active_customers"] = grp["new_customers"] + grp["returning_customers"]

    grp["returning_customer_pct"] = np.where(
        grp["total_active_customers"] > 0,
        (grp["returning_customers"] / grp["total_active_customers"]) * 100.0,
        0.0
    )

    return grp.sort_values("year_month").reset_index(drop=True)
