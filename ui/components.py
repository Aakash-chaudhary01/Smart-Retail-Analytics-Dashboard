"""
ui/components.py
================
Reusable UI components for the Retro Sales Intelligence Dashboard.
Framed window dialogs, pixel art KPI cards, retro badges, and headers.
"""

from __future__ import annotations
from typing import Optional
import streamlit as st
from utils import format_delta_arrow

def render_retro_header(title: str, subtitle: str = "", badge: str = "RETRO WEB v2.0") -> None:
    """Renders the top banner retro header with pixel badges."""
    badge_html = f'<span class="retro-badge badge-orange">{badge}</span>' if badge else ""
    st.markdown(
        f"""
        <div style="display:flex; justify-content:space-between; align-items:flex-end; margin-bottom: 0.8rem; border-bottom: 3px solid #222222; padding-bottom: 0.6rem;">
            <div>
                <h1 style="margin: 0; padding: 0; line-height: 1.1;">{title}</h1>
                <div style="font-size: 0.88rem; color: #555555; margin-top: 4px;">{subtitle}</div>
            </div>
            <div>
                {badge_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_retro_window_start(title: str, icon: str = "💾") -> str:
    """Returns HTML for starting a retro OS window container."""
    return f"""
    <div class="retro-window">
        <div class="retro-window-bar">
            <span>{icon} {title}</span>
            <div class="retro-window-controls">
                <span class="retro-window-btn btn-min"></span>
                <span class="retro-window-btn btn-max"></span>
                <span class="retro-window-btn btn-close"></span>
            </div>
        </div>
        <div class="retro-window-body">
    """

def render_retro_window_end() -> str:
    """Returns HTML for closing a retro OS window container."""
    return """
        </div>
    </div>
    """

def render_kpi_card(label: str, val: str, delta_val: Optional[float] = None, suffix: str = "%") -> str:
    """
    Renders a single retro pixel-styled KPI card.
    If delta_val is None, shows 'N/A' or neutral label as per rule:
    'If a metric isn't supported by existing logic, show N/A or hide it. Never fabricate values.'
    """
    if delta_val is not None:
        delta_str = format_delta_arrow(delta_val, suffix=suffix)
        css_class = "retro-kpi-delta-up" if delta_val > 0 else ("retro-kpi-delta-down" if delta_val < 0 else "retro-kpi-delta-neutral")
        delta_html = f'<div class="{css_class}">{delta_str} MoM</div>'
    else:
        delta_html = '<div class="retro-kpi-delta-neutral">-- MoM</div>'

    return f"""
    <div class="retro-kpi-card">
        <div class="retro-kpi-label">{label}</div>
        <div class="retro-kpi-value">{val}</div>
        {delta_html}
    </div>
    """

def render_notice(text: str, icon: str = "💡") -> None:
    """Renders a retro disclaimer/notice callout box."""
    st.markdown(
        f"""
        <div class="retro-callout">
            <span style="font-weight:700;">{icon} NOTICE:</span> {text}
        </div>
        """,
        unsafe_allow_html=True
    )

def render_status_badge(text: str, variant: str = "teal") -> str:
    """Returns HTML for a retro status badge pill."""
    variant_class = f"badge-{variant}" if variant in ["teal", "orange", "yellow", "navy"] else "badge-teal"
    return f'<span class="retro-badge {variant_class}">{text}</span>'
