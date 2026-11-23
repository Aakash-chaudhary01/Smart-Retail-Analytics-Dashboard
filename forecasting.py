"""
forecasting.py
==============
Demand and revenue forecasting using Holt-Winters Exponential Smoothing /
statsmodels ARIMA (with Prophet support if available) and moving average fallback.
Evaluates accuracy via train-test split MAPE and generates 3-month forward projections.
"""

from __future__ import annotations
import warnings
from typing import Dict, Any, Optional, Tuple, List
import numpy as np
import pandas as pd
from config import get_logger

logger = get_logger("forecasting")
warnings.filterwarnings("ignore")

def _calculate_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Calculates Mean Absolute Percentage Error (MAPE), avoiding zero division."""
    y_true, y_pred = np.array(y_true, dtype=float), np.array(y_pred, dtype=float)
    non_zero = y_true > 0
    if not np.any(non_zero):
        return 0.0
    return float(np.mean(np.abs((y_true[non_zero] - y_pred[non_zero]) / y_true[non_zero])) * 100.0)

def forecast_series(
    series: pd.Series,
    horizon: int = 3,
    test_split: int = 3
) -> Dict[str, Any]:
    """
    Generates a 3-month forecast for a monthly sales series.
    Returns:
        dict with keys: 'forecast_df', 'mape', 'model_name', 'confidence', 'forecast_growth_pct'
    """
    series = series.astype(float).fillna(0.0)
    n = len(series)

    # Fallback for insufficient data
    if n < 4:
        last_val = series.iloc[-1] if n > 0 else 0.0
        future_idx = pd.date_range(
            start=series.index[-1] + pd.DateOffset(months=1) if n > 0 else pd.Timestamp.now(),
            periods=horizon,
            freq="MS"
        )
        forecast_df = pd.DataFrame({
            "ds": future_idx,
            "yhat": [last_val] * horizon,
            "yhat_lower": [max(0.0, last_val * 0.75)] * horizon,
            "yhat_upper": [last_val * 1.25] * horizon,
        })
        return {
            "forecast_df": forecast_df,
            "mape": None,
            "model_name": "Simple Fallback (Last Value)",
            "confidence": "Low",
            "forecast_growth_pct": 0.0
        }

    # Evaluate MAPE using train/test split if enough history
    mape_val = None
    if n >= test_split + 4:
        train_s = series.iloc[:-test_split]
        test_s = series.iloc[-test_split:]
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
            # Train simple Holt model
            model_eval = ExponentialSmoothing(
                train_s,
                trend="add",
                seasonal=None,
                initialization_method="estimated"
            ).fit()
            pred_eval = model_eval.forecast(test_split)
            mape_val = round(_calculate_mape(test_s.values, pred_eval.values), 1)
        except Exception:
            mape_val = round(_calculate_mape(test_s.values, np.full(len(test_s), train_s.mean())), 1)

    # Fit final model on full series
    model_name = "Holt-Winters Exponential Smoothing"
    confidence = "High" if (mape_val is not None and mape_val < 25.0 and n >= 12) else ("Medium" if n >= 6 else "Low")

    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        model = ExponentialSmoothing(
            series,
            trend="add",
            seasonal="add" if n >= 24 else None,
            seasonal_periods=12 if n >= 24 else None,
            initialization_method="estimated"
        ).fit()
        preds = model.forecast(horizon)
        std_err = float(series.std()) if n > 1 else 0.1 * float(series.mean())
        
        yhat = np.maximum(0.0, preds.values)
        yhat_lower = np.maximum(0.0, yhat - 1.645 * std_err)
        yhat_upper = yhat + 1.645 * std_err
    except Exception as exc:
        logger.info(f"ExponentialSmoothing fallback to 3-month moving average: {exc}")
        model_name = "Moving Average Trend"
        rolling_mean = series.tail(3).mean()
        yhat = np.full(horizon, max(0.0, rolling_mean))
        std_err = float(series.tail(3).std()) if len(series.tail(3)) > 1 else 0.1 * rolling_mean
        yhat_lower = np.maximum(0.0, yhat - 1.645 * std_err)
        yhat_upper = yhat + 1.645 * std_err
        confidence = "Low"

    # Future dates
    last_date = series.index[-1]
    future_dates = pd.date_range(start=last_date + pd.DateOffset(months=1), periods=horizon, freq="MS")

    forecast_df = pd.DataFrame({
        "ds": future_dates,
        "yhat": np.round(yhat, 2),
        "yhat_lower": np.round(yhat_lower, 2),
        "yhat_upper": np.round(yhat_upper, 2),
    })

    # Projected growth %: Next 3 months total vs Last 3 months total
    last_3m_sum = float(series.tail(horizon).sum())
    next_3m_sum = float(forecast_df["yhat"].sum())
    growth_pct = ((next_3m_sum - last_3m_sum) / last_3m_sum * 100.0) if last_3m_sum > 0 else 0.0

    return {
        "forecast_df": forecast_df,
        "mape": mape_val,
        "model_name": model_name,
        "confidence": confidence,
        "forecast_growth_pct": round(growth_pct, 1),
    }

def generate_all_forecasts(df: pd.DataFrame, horizon: int = 3) -> Dict[str, Any]:
    """
    Computes forecasts for:
    1. Overall Net Revenue
    2. Each Category
    3. Each Product
    """
    valid_df = df[df["order_status"] != "Cancelled"].copy()
    if valid_df.empty:
        return {}

    # Monthly series index
    valid_df["month_start"] = valid_df["order_date"].dt.to_period("M").dt.to_timestamp()

    # 1. Overall Forecast
    overall_ts = valid_df.groupby("month_start")["net_revenue"].sum()
    overall_forecast = forecast_series(overall_ts, horizon=horizon)

    # 2. Category Forecasts
    cat_forecasts = {}
    for cat, c_df in valid_df.groupby("category"):
        cat_ts = c_df.groupby("month_start")["net_revenue"].sum()
        cat_ts = overall_ts.index.to_series().map(cat_ts).fillna(0.0)
        cat_forecasts[cat] = forecast_series(cat_ts, horizon=horizon)

    # 3. Product Forecasts
    prod_forecasts = {}
    for prod, p_df in valid_df.groupby("product"):
        p_ts = p_df.groupby("month_start")["net_revenue"].sum()
        p_ts = overall_ts.index.to_series().map(p_ts).fillna(0.0)
        prod_forecasts[prod] = forecast_series(p_ts, horizon=horizon)

    return {
        "overall": overall_forecast,
        "categories": cat_forecasts,
        "products": prod_forecasts,
        "overall_history": overall_ts,
    }

