"""
config.py
=========
Central configuration for the Retail Sales Dashboard.
Contains threshold configurations, column mappings, Gemini model definitions,
and color constants for charts and decision engine recommendations.
"""

from __future__ import annotations
import os
import logging
import sys
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load variables from .env file into environment
load_dotenv()

# ---------------------------------------------------------------------------
# AI Model Configuration (Google Gemini API)
# ---------------------------------------------------------------------------
# Default Gemini model name - configurable via environment variable GEMINI_MODEL
DEFAULT_GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
FALLBACK_GEMINI_MODEL: str = "gemini-3.5-flash-lite"
GEMINI_MAX_OUTPUT_TOKENS: int = 4096
GEMINI_TEMPERATURE: float = 0.2

# ---------------------------------------------------------------------------
# Product Decision Engine Thresholds (Config Dict & Defaults for Sliders)
# ---------------------------------------------------------------------------
DECISION_THRESHOLDS: Dict[str, Any] = {
    # INCREASE PRODUCTION Criteria
    "increase_growth_pct": 15.0,         # Minimum 3-month growth %
    "increase_margin_pct": 15.0,         # Minimum estimated profit margin %
    "increase_max_return_rate": 8.0,     # Maximum acceptable return rate %

    # DISCONTINUE Criteria
    "discontinue_growth_pct": -15.0,     # Negative growth threshold %
    "discontinue_margin_pct": 5.0,       # Margin below this triggers review/discontinue
    "discontinue_revenue_share": 2.0,    # Revenue share % below this triggers check
    "discontinue_loss_months": 3,        # Consecutive loss-making months
    "discontinue_return_rate": 20.0,     # Return rate above this triggers discontinue

    # REVIEW / REPRICE Criteria
    "review_max_margin_pct": 10.0,       # Good sales but margin below this -> reprice
    "review_high_return_rate": 15.0,     # High return rate threshold
    "review_high_replace_rate": 8.0,     # High replacement rate threshold
}

# ---------------------------------------------------------------------------
# Product Health Score Weights (0 to 100) - Must sum to 1.0
# ---------------------------------------------------------------------------
HEALTH_SCORE_WEIGHTS: Dict[str, float] = {
    "growth": 0.30,                      # 30% Growth trend
    "margin": 0.30,                      # 30% Profit margin
    "revenue_share": 0.20,               # 20% Revenue contribution
    "return_replacement_rate": 0.10,     # 10% Low return & replacement penalty
    "consistency": 0.10,                 # 10% Demand consistency (low CV)
}

# ---------------------------------------------------------------------------
# ABC Classification Cumulative Cutoffs
# ---------------------------------------------------------------------------
ABC_THRESHOLDS: Dict[str, float] = {
    "A": 0.70,  # Top 70% of revenue
    "B": 0.90,  # Next 20% (cumulative 70% - 90%)
    "C": 1.00,  # Bottom 10%
}

# ---------------------------------------------------------------------------
# Category & Product Metadata (Default Reference)
# ---------------------------------------------------------------------------
PRODUCT_CATEGORY_MAP: Dict[str, str] = {
    "Laptop": "Computers & Peripherals",
    "Monitor": "Computers & Peripherals",
    "Printer": "Computers & Peripherals",
    "Phone": "Mobiles & Tablets",
    "Tablet": "Mobiles & Tablets",
    "Chair": "Furniture",
    "Desk": "Furniture",
}

# Inventory baseline for default products (Stock, Reorder Point, Lead Time Days, Unit Cost)
DEFAULT_INVENTORY: Dict[str, Dict[str, Any]] = {
    "Laptop":  {"stock": 140, "reorder_point": 120, "lead_time_days": 18, "unit_cost": 650.0},
    "Monitor": {"stock": 210, "reorder_point": 150, "lead_time_days": 14, "unit_cost": 160.0},
    "Printer": {"stock": 85,  "reorder_point": 90,  "lead_time_days": 21, "unit_cost": 130.0},
    "Phone":   {"stock": 310, "reorder_point": 200, "lead_time_days": 10, "unit_cost": 420.0},
    "Tablet":  {"stock": 160, "reorder_point": 140, "lead_time_days": 12, "unit_cost": 280.0},
    "Chair":   {"stock": 95,  "reorder_point": 110, "lead_time_days": 25, "unit_cost": 120.0},
    "Desk":    {"stock": 60,  "reorder_point": 80,  "lead_time_days": 30, "unit_cost": 210.0},
}

# ---------------------------------------------------------------------------
# Status & Recommendation Color Palette
# ---------------------------------------------------------------------------
STATUS_COLORS: Dict[str, str] = {
    "Delivered": "#10B981",    # Emerald green
    "Returned":  "#EF4444",    # Crimson red
    "Replaced":  "#F59E0B",    # Amber
    "Cancelled": "#6B7280",    # Neutral grey
}

RECOMMENDATION_COLORS: Dict[str, str] = {
    "Increase Production": "#10B981",  # Vibrant green
    "Discontinue":         "#EF4444",  # Crimson red
    "Review / Reprice":    "#F59E0B",  # Amber / orange
    "Maintain":            "#64748B",  # Slate grey
}

CATEGORY_COLORS: Dict[str, str] = {
    "Computers & Peripherals": "#3B82F6",  # Blue
    "Mobiles & Tablets":       "#8B5CF6",  # Purple
    "Furniture":               "#EC4899",  # Rose pink
    "Other":                   "#94A3B8",  # Light slate
}

# Chart Theme
PLOTLY_TEMPLATE = "plotly_white"

# ---------------------------------------------------------------------------
# Column Aliases for Upload Auto-Detection
# ---------------------------------------------------------------------------
COLUMN_ALIASES: Dict[str, List[str]] = {
    "order_date": [
        "order_date", "date", "orderdate", "purchasedate", "purchase_date", 
        "transaction_date", "order_time", "created_at", "timestamp"
    ],
    "total_sales": [
        "total_sales", "sales", "revenue", "totalprice", "total_price", 
        "total amount", "total_amount", "amount", "gross_sales", "price_total"
    ],
    "quantity": [
        "quantity", "qty", "units", "items", "count", "num_items", "volume"
    ],
    "product": [
        "product", "product_name", "productname", "item", "item_name", "sku"
    ],
    "customer_id": [
        "customer_id", "customerid", "client_id", "cust_id", "user_id", "buyer_id"
    ],
    "category": [
        "category", "product_category", "productcategory", "dept", "department"
    ],
    "order_status": [
        "order_status", "status", "orderstatus", "delivery_status", "fulfillment_status"
    ],
    "region": [
        "region", "zone", "territory", "area", "market"
    ],
    "channel": [
        "channel", "sales_channel", "source", "platform", "store_type"
    ],
    "discount": [
        "discount", "discount_pct", "discount_percent", "discount_rate", "promo_pct"
    ],
    "profit": [
        "profit", "est_profit", "estimated_profit", "net_profit", "margin_val"
    ],
    "unit_price": [
        "unit_price", "price", "unitprice", "selling_price", "item_price"
    ],
    "order_id": [
        "order_id", "orderid", "id", "transaction_id", "invoice_no", "invoice_id"
    ]
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def get_logger(name: str = "retail_dashboard") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger

