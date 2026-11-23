"""
generate_dataset.py
===================
Generates the baseline retail sales dataset according to exact specifications:
- 6,500 rows spanning Jan 2023 to Jun 2025 (30 months)
- 7 products across 3 categories
- 4 channels: Customer Purchase, Online Store, Regional Sales, Retail Store
- Accurate column structure, realistic seasonality, simulated vs reported statuses,
  and proper customer lineage (customer_order_number, frequency_segment, etc.).
Also outputs data/customer_summary.csv and data/inventory_summary.csv.
"""

from __future__ import annotations
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

from config import DEFAULT_INVENTORY, PRODUCT_CATEGORY_MAP

SEED = 42
np.random.seed(SEED)
random.seed(SEED)

def generate_retail_dataset(n_rows: int = 6500) -> pd.DataFrame:
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2025, 6, 30)
    total_days = (end_date - start_date).days

    channels = [
        ("Customer Purchase", "Customer_Purchase.xlsx", "CPH-", "Reported", 0.30),
        ("Online Store", "Online_Store.csv", "ONL-", "Simulated", 0.35),
        ("Regional Sales", "Regional_Sales.xlsx", "REG-", "Reported", 0.15),
        ("Retail Store", "Retail_Store_POS.csv", None, "Simulated", 0.20)
    ]

    products_info = [
        {"product": "Laptop", "category": "Computers & Peripherals", "base_price": 999.0, "unit_cost": 650.0, "weight": 0.22, "trend": 0.015},
        {"product": "Phone", "category": "Mobiles & Tablets", "base_price": 699.0, "unit_cost": 420.0, "weight": 0.25, "trend": 0.020},
        {"product": "Tablet", "category": "Mobiles & Tablets", "base_price": 449.0, "unit_cost": 280.0, "weight": 0.16, "trend": 0.008},
        {"product": "Monitor", "category": "Computers & Peripherals", "base_price": 279.0, "unit_cost": 160.0, "weight": 0.14, "trend": 0.010},
        {"product": "Desk", "category": "Furniture", "base_price": 349.0, "unit_cost": 210.0, "weight": 0.09, "trend": -0.010},
        {"product": "Chair", "category": "Furniture", "base_price": 199.0, "unit_cost": 120.0, "weight": 0.08, "trend": -0.005},
        {"product": "Printer", "category": "Computers & Peripherals", "base_price": 189.0, "unit_cost": 130.0, "weight": 0.06, "trend": -0.025},
    ]

    regions = ["North", "South", "East", "West", "Central"]
    store_locations = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego"]
    payment_methods = ["Credit Card", "Debit Card", "UPI / Digital Wallet", "Net Banking", "Cash"]
    referral_sources = ["Google Search", "Direct", "Social Media", "Email Newsletter", "Referral Link", "In-Store Walk-in"]
    times_of_day = ["Morning", "Afternoon", "Evening", "Night"]

    # Customer pool for non-walk-in channels
    customer_pools = {
        "CPH-": [f"CPH-{i:05d}" for i in range(1, 1100)],
        "ONL-": [f"ONL-{i:05d}" for i in range(1, 1400)],
        "REG-": [f"REG-{i:05d}" for i in range(1, 600)],
    }
    customer_names = {
        cid: f"Customer {cid.split('-')[1]}" for ctype, cids in customer_pools.items() for cid in cids
    }

    # Generate dates with mild month-end and holiday seasonality
    raw_dates = []
    for _ in range(n_rows):
        day_offset = random.randint(0, total_days)
        dt = start_date + timedelta(days=day_offset)
        # November/December seasonal boost
        if dt.month in (11, 12) and random.random() < 0.25:
            # re-sample slightly towards late year
            dt = dt.replace(day=min(dt.day, 28))
        raw_dates.append(dt)
    raw_dates.sort()

    rows = []
    prod_names = [p["product"] for p in products_info]
    prod_weights = [p["weight"] for p in products_info]

    channel_names = [c[0] for c in channels]
    channel_weights = [c[4] for c in channels]
    channel_meta = {c[0]: c for c in channels}

    for i in range(n_rows):
        order_id = f"ORD-{20230000 + i + 1}"
        order_date = raw_dates[i]
        
        # Pick channel
        ch_name = np.random.choice(channel_names, p=channel_weights)
        _, source_file, prefix, status_source, _ = channel_meta[ch_name]

        # Customer Assignment
        if prefix is not None:
            # Power law: some customers buy more than once, most buy once
            pool = customer_pools[prefix]
            if random.random() < 0.18:
                # repeat buyer candidate
                cid = random.choice(pool[:150])
            else:
                cid = random.choice(pool)
            cname = customer_names[cid]
            ctype = "Individual" if "REG" not in prefix else "Corporate / Wholesale"
        else:
            cid = None
            cname = "Walk-in Customer"
            ctype = "Walk-in"

        # Pick product
        p_obj = random.choices(products_info, weights=prod_weights, k=1)[0]
        prod = p_obj["product"]
        cat = p_obj["category"]

        # Quantity
        if ctype == "Corporate / Wholesale":
            qty = random.randint(2, 6)
        else:
            qty = np.random.choice([1, 2, 3, 4], p=[0.72, 0.20, 0.06, 0.02])

        unit_price = p_obj["base_price"]
        unit_cost = p_obj["unit_cost"]

        # Discount
        if ch_name == "Regional Sales":
            discount_pct = round(random.choice([0.05, 0.10, 0.15, 0.20, 0.25, 0.35]), 2)
        elif ch_name == "Online Store":
            discount_pct = round(random.choice([0.0, 0.0, 0.05, 0.10, 0.15]), 2)
        else:
            discount_pct = round(random.choice([0.0, 0.0, 0.0, 0.05]), 2)

        gross_sales = round(qty * unit_price * (1.0 - discount_pct), 2)

        # Order Status simulation
        # Realistic status distribution: Delivered ~82%, Returned ~7%, Replaced ~4%, Cancelled ~7%
        if prod == "Printer":
            # Higher return rate for demonstration of discontinue signal
            status_p = [0.72, 0.14, 0.06, 0.08]
        elif prod in ("Chair", "Desk"):
            status_p = [0.80, 0.09, 0.05, 0.06]
        else:
            status_p = [0.85, 0.06, 0.04, 0.05]

        order_status = np.random.choice(["Delivered", "Returned", "Replaced", "Cancelled"], p=status_p)
        source_status = order_status

        # Status flags
        is_deliv = 1 if order_status == "Delivered" else 0
        is_ret = 1 if order_status == "Returned" else 0
        is_rep = 1 if order_status == "Replaced" else 0
        is_canc = 1 if order_status == "Cancelled" else 0

        # Net Revenue calculation rule:
        # net_revenue = total_sales for Delivered and Replaced orders, 0 for Returned and Cancelled.
        if order_status in ("Delivered", "Replaced"):
            net_rev = gross_sales
            # est_profit = net_revenue - (unit_cost * qty)
            est_profit = round(net_rev - (unit_cost * qty), 2)
        else:
            net_rev = 0.0
            # For returns/cancellations, product didn't yield profit; shipping/restocking may cause mild loss
            est_profit = round(-0.05 * unit_cost * qty if is_ret else 0.0, 2)

        shipping_cost = round(random.uniform(5.0, 25.0), 2) if ch_name != "Retail Store" else 0.0
        pay_method = random.choice(payment_methods) if ch_name != "Retail Store" else "Cash"
        promo = "PROMO10" if discount_pct > 0.08 else "None"
        ref_source = random.choice(referral_sources) if ch_name != "Retail Store" else "In-Store Walk-in"
        reg = random.choice(regions) if ch_name != "Retail Store" else "East"
        store_loc = random.choice(store_locations) if ch_name == "Retail Store" else None
        store_id = f"STR-{random.randint(101, 108)}" if ch_name == "Retail Store" else None
        time_day = random.choice(times_of_day)
        delivery_dt = order_date + timedelta(days=random.randint(2, 6)) if order_status != "Cancelled" else None
        review_rating = random.choice([4, 5, 5, 4, 3, 2, 1]) if order_status == "Delivered" else (2 if is_ret else None)

        rows.append({
            "order_id": order_id,
            "order_date": order_date,
            "year": order_date.year,
            "quarter": f"Q{((order_date.month - 1) // 3) + 1}",
            "month_num": order_date.month,
            "month_name": order_date.strftime("%B"),
            "year_month": order_date.strftime("%Y-%m"),
            "day_of_week": order_date.strftime("%A"),
            "channel": ch_name,
            "source_file": source_file,
            "customer_id": cid,
            "customer_name": cname,
            "customer_type": ctype,
            "product": prod,
            "category": cat,
            "source_category": cat,
            "quantity": qty,
            "unit_price": unit_price,
            "discount_pct": discount_pct,
            "total_sales": gross_sales,
            "net_revenue": net_rev,
            "est_unit_cost": unit_cost,
            "est_profit": est_profit,
            "shipping_cost": shipping_cost,
            "payment_method": pay_method,
            "promotion_or_coupon": promo,
            "referral_source": ref_source,
            "region": reg,
            "store_location": store_loc,
            "store_id": store_id,
            "time_of_day": time_day,
            "delivery_date": delivery_dt,
            "review_rating": review_rating,
            "order_status": order_status,
            "source_status": source_status,
            "status_source": status_source,
            "is_delivered": is_deliv,
            "is_returned": is_ret,
            "is_replaced": is_rep,
            "is_cancelled": is_canc,
        })

    df = pd.DataFrame(rows)

    # Sort strictly by order_date
    df = df.sort_values("order_date").reset_index(drop=True)

    # Compute customer lineage for valid purchases (non-cancelled)
    # A "valid purchase" is any order that is not Cancelled.
    # A customer is "Returning" in a month if their first valid purchase was in an earlier month; otherwise "New".
    
    # 1. Track first valid purchase month per customer
    valid_orders = df[df["order_status"] != "Cancelled"]
    first_purchase_dates = (
        valid_orders.dropna(subset=["customer_id"])
        .groupby("customer_id")["order_date"]
        .min()
        .to_dict()
    )

    first_purchase_months = {
        cid: dt.strftime("%Y-%m") for cid, dt in first_purchase_dates.items()
    }

    # Count total valid orders per customer
    customer_valid_counts = (
        valid_orders.dropna(subset=["customer_id"])
        .groupby("customer_id")["order_id"]
        .count()
        .to_dict()
    )

    # Running order number and days_since_prev_order
    customer_order_num = []
    days_since_prev = []
    cust_prev_date = {}
    cust_running_count = {}

    for _, row in df.iterrows():
        cid = row["customer_id"]
        status = row["order_status"]
        odt = row["order_date"]

        if pd.isna(cid) or cid is None:
            customer_order_num.append(np.nan)
            days_since_prev.append(np.nan)
            continue

        if status == "Cancelled":
            # Cancelled does not advance valid order counter
            customer_order_num.append(np.nan)
            days_since_prev.append(np.nan)
        else:
            prev_cnt = cust_running_count.get(cid, 0) + 1
            cust_running_count[cid] = prev_cnt
            customer_order_num.append(prev_cnt)

            if cid in cust_prev_date:
                days = (odt - cust_prev_date[cid]).days
                days_since_prev.append(days)
            else:
                days_since_prev.append(np.nan)
            cust_prev_date[cid] = odt

    df["customer_order_number"] = customer_order_num
    df["days_since_prev_order"] = days_since_prev
    df["first_purchase_month"] = df["customer_id"].map(first_purchase_months)
    df["customer_total_orders"] = df["customer_id"].map(customer_valid_counts)

    # customer_type_in_month (New / Returning / Walk-in (unknown) / Cancelled (not counted))
    def determine_customer_type_in_month(r):
        if pd.isna(r["customer_id"]) or r["customer_id"] is None:
            return "Walk-in (unknown)"
        if r["order_status"] == "Cancelled":
            return "Cancelled (not counted)"
        first_m = r["first_purchase_month"]
        if pd.isna(first_m):
            return "New"
        current_m = r["year_month"]
        if current_m > first_m:
            return "Returning"
        else:
            return "New"

    df["customer_type_in_month"] = df.apply(determine_customer_type_in_month, axis=1)

    # customer_type_at_order
    def determine_type_at_order(r):
        if pd.isna(r["customer_id"]):
            return "Walk-in"
        num = r["customer_order_number"]
        if pd.isna(num):
            return "Cancelled"
        return "New" if num == 1 else "Returning"

    df["customer_type_at_order"] = df.apply(determine_type_at_order, axis=1)

    # frequency_segment (One-time buyer / Repeat buyer (2) / Loyal buyer (3+) / Not applicable)
    def determine_freq_segment(r):
        if pd.isna(r["customer_id"]):
            return "Not applicable"
        tot = r["customer_total_orders"]
        if pd.isna(tot) or tot <= 0:
            return "Not applicable"
        if tot == 1:
            return "One-time buyer"
        elif tot == 2:
            return "Repeat buyer (2)"
        else:
            return "Loyal buyer (3+)"

    df["frequency_segment"] = df.apply(determine_freq_segment, axis=1)

    return df

def generate_customer_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Generate customer-level aggregation table."""
    valid = df[df["customer_id"].notna() & (df["order_status"] != "Cancelled")].copy()
    
    summary = valid.groupby("customer_id").agg(
        customer_name=("customer_name", "first"),
        customer_type=("customer_type", "first"),
        channel=("channel", "first"),
        total_orders=("order_id", "nunique"),
        total_units=("quantity", "sum"),
        total_spend=("net_revenue", "sum"),
        first_order_date=("order_date", "min"),
        last_order_date=("order_date", "max"),
        avg_order_value=("net_revenue", "mean"),
        returned_orders=("is_returned", "sum"),
    ).reset_index()

    summary["repeat_customer"] = summary["total_orders"] > 1
    summary["frequency_segment"] = summary["total_orders"].apply(
        lambda x: "One-time buyer" if x == 1 else ("Repeat buyer (2)" if x == 2 else "Loyal buyer (3+)")
    )
    summary["total_spend"] = summary["total_spend"].round(2)
    summary["avg_order_value"] = summary["avg_order_value"].round(2)
    return summary

def generate_inventory_summary() -> pd.DataFrame:
    """Generate inventory and supply chain metadata."""
    rows = []
    for prod, meta in DEFAULT_INVENTORY.items():
        rows.append({
            "product": prod,
            "category": PRODUCT_CATEGORY_MAP.get(prod, "Other"),
            "current_stock": meta["stock"],
            "reorder_point": meta["reorder_point"],
            "lead_time_days": meta["lead_time_days"],
            "unit_cost": meta["unit_cost"],
            "stock_status": "Reorder Needed" if meta["stock"] <= meta["reorder_point"] else "Adequate",
            "stock_to_reorder_ratio": round(meta["stock"] / meta["reorder_point"], 2)
        })
    return pd.DataFrame(rows)

if __name__ == "__main__":
    out_dir = Path("data")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Generating retail sales combined dataset (6,500 rows)...")
    sales_df = generate_retail_dataset(6500)
    sales_file = out_dir / "retail_sales_combined.csv"
    sales_df.to_csv(sales_file, index=False)
    print(f"-> Saved: {sales_file} ({len(sales_df):,} rows)")

    print("Generating customer summary...")
    cust_df = generate_customer_summary(sales_df)
    cust_file = out_dir / "customer_summary.csv"
    cust_df.to_csv(cust_file, index=False)
    print(f"-> Saved: {cust_file} ({len(cust_df):,} customers)")

    print("Generating inventory summary...")
    inv_df = generate_inventory_summary()
    inv_file = out_dir / "inventory_summary.csv"
    inv_df.to_csv(inv_file, index=False)
    print(f"-> Saved: {inv_file} ({len(inv_df)} products)")
    print("Dataset generation complete!")

