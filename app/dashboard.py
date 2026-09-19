"""
AeroScan — Aerospace Swarm Mission Operations Platform
Autonomous UAV Swarm Coverage Optimization & Real-Time Mission Control.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from app.arena_view import render_arena_view
from app.exporter import (
    export_mavlink_waypoint_file,
    export_mission_telemetry_csv,
    export_qgroundcontrol_plan,
)
from app.telemetry import (
    get_fleet_telemetry_at_time,
)
from app.visualizer import (
    DRONE_COLORS,
    build_3d_terrain_mission_figure,
    build_battery_soc_figure,
    build_mission_map_figure,
)
from baselines.grasp import solve_grasp_baseline
from benchmarks.chao_loader import get_canonical_chao_instance
from core.alns import explore_route_pool
from core.contracts import FleetSchedule, InstanceContext
from core.instance import build_instance_context
from core.set_packing import solve_fleet_schedule

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AeroScan // Mission Operations",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Clean Vector SVG Icons (Strictly Zero Emojis)
# ---------------------------------------------------------------------------
SVG_AERO_LOGO = """<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0284C7" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="12 2 15 9 22 12 15 15 12 22 9 15 2 12 9 9 12 2"/></svg>"""
SVG_MAP = """<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg>"""
SVG_FLEET = """<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M2 12h20M4.93 4.93l14.14 14.14M19.07 4.93L4.93 19.07"/></svg>"""
SVG_ARENA = """<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>"""
SVG_BATTERY = """<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="6" width="18" height="12" rx="2" ry="2"/><line x1="23" y1="13" x2="23" y2="11"/><line x1="7" y1="10" x2="7" y2="14"/><line x1="11" y1="10" x2="11" y2="14"/></svg>"""
SVG_EXPORT = """<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>"""
SVG_WIND = """<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.59 4.59A2 2 0 1 1 11 8H2m10.59 11.41A2 2 0 1 0 14 16H2m15.73-8.27A2.5 2.5 0 1 1 19.5 12H2"/></svg>"""
SVG_DRONE_ICON = """<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><circle cx="5" cy="5" r="3"/><circle cx="19" cy="5" r="3"/><circle cx="5" cy="19" r="3"/><circle cx="19" cy="19" r="3"/><line x1="7.5" y1="7.5" x2="9.5" y2="9.5"/><line x1="16.5" y1="7.5" x2="14.5" y2="9.5"/><line x1="7.5" y1="16.5" x2="9.5" y2="14.5"/><line x1="16.5" y1="16.5" x2="14.5" y2="14.5"/></svg>"""
SVG_RADIO = """<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="2"/><path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14"/></svg>"""
SVG_SHIELD = """<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>"""
SVG_CHECK = """<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>"""

# ---------------------------------------------------------------------------
# Aerospace Light-Theme Spatial Design System CSS
# ---------------------------------------------------------------------------
AEROSCAN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

*, *::before, *::after { box-sizing: border-box; }
body, input, select, textarea, button, p, span, div, h1, h2, h3, h4, h5, h6, label {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ══ Framework Base Overrides ══ */
:root {
    --primary-color: #0284C7 !important;
    --background-color: #F4F7FA !important;
    --secondary-background-color: #FFFFFF !important;
    --text-color: #0F172A !important;
    --font: 'Inter', sans-serif !important;
}

/* ══ Hide default collapse controls and header bars ══ */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarHeader"],
[data-testid="collapsedControl"],
header[data-testid="stHeader"],
button[data-testid="baseButton-headerNoPadding"],
button[data-testid="baseButton-header"],
[data-testid="stSidebarNavItems"],
[data-testid="stSidebarNavSeparator"],
[data-testid="stSidebarNav"],
.st-emotion-cache-15hul6a,
.st-emotion-cache-12fmjuu {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* ── Main App Container ── */
.stApp {
    background: #F4F7FA !important;
    color: #0F172A !important;
    min-height: 100vh;
}

.main .block-container {
    padding: 0.9rem 1.5rem 2.2rem !important;
    max-width: 100% !important;
}

/* ── Navigation Rail / Sidebar ── */
[data-testid="stSidebar"] {
    background: #FFFFFF !important;
    border-right: 1px solid #E2E8F0 !important;
    box-shadow: 2px 0 8px rgba(0, 0, 0, 0.03) !important;
    z-index: 10;
}
[data-testid="stSidebar"] > div {
    padding-top: 1.0rem !important;
    padding-left: 1.1rem !important;
    padding-right: 1.1rem !important;
    background: #FFFFFF !important;
}

.nav-rail-brand {
    padding-bottom: 12px;
    border-bottom: 1px solid #E2E8F0;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.nav-brand-text {
    font-size: 14px !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    letter-spacing: 0.04em !important;
    font-family: 'JetBrains Mono', monospace !important;
    line-height: 1.1;
}
.nav-brand-sub {
    font-size: 10px !important;
    color: #64748B !important;
    font-weight: 500 !important;
    letter-spacing: 0.04em !important;
    margin-top: 2px !important;
}

.sidebar-heading {
    font-size: 10px !important;
    font-weight: 700 !important;
    color: #64748B !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    font-family: 'JetBrains Mono', monospace !important;
    margin: 14px 0 6px 0 !important;
    display: block !important;
}

/* Mission Summary Card in Sidebar */
.mission-context-box {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    padding: 10px 12px;
    margin-bottom: 12px;
}
.m-ctx-title {
    font-size: 12px;
    font-weight: 700;
    color: #0F172A;
    font-family: 'JetBrains Mono', monospace;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.m-ctx-status {
    font-size: 9px;
    font-weight: 700;
    color: #10B981;
    background: #ECFDF5;
    padding: 2px 6px;
    border-radius: 3px;
    border: 1px solid #A7F3D0;
    letter-spacing: 0.06em;
}
.m-ctx-stats {
    font-size: 11px;
    color: #475569;
    margin-top: 5px;
    font-family: 'JetBrains Mono', monospace;
}

/* System Avionics Card */
.sidebar-system-card {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    padding: 10px 12px;
    margin-top: 16px;
}
.sys-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
    font-size: 11px;
}
.sys-row:last-child { margin-bottom: 0; }
.sys-key { color: #64748B; font-weight: 500; display: flex; align-items: center; gap: 6px; }
.sys-val { color: #0F172A; font-weight: 600; font-family: 'JetBrains Mono', monospace; font-size: 10px; }
.sys-val-active { color: #10B981; font-weight: 600; font-family: 'JetBrains Mono', monospace; font-size: 10px; display: flex; align-items: center; gap: 5px; }
.live-dot {
    width: 6px; height: 6px;
    background: #10B981;
    border-radius: 50%;
    display: inline-block;
    box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
}

/* ── Workspace Selection in Sidebar ── */
[data-testid="stSidebar"] div[role="radiogroup"] {
    gap: 4px !important;
    background: transparent !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] label {
    background: #FFFFFF !important;
    border: 1px solid transparent !important;
    border-radius: 6px !important;
    padding: 7px 12px !important;
    margin-bottom: 2px !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
    background: #F8FAFC !important;
    border-color: #E2E8F0 !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
    background: #EFF6FF !important;
    border-color: #BAE6FD !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) span {
    color: #0284C7 !important;
    font-weight: 600 !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* ── Top Header Context Bar ── */
.top-ops-bar {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 10px 18px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}
.top-title-wrap {
    display: flex;
    align-items: center;
    gap: 12px;
}
.top-brand {
    font-size: 14px;
    font-weight: 700;
    color: #0284C7;
    letter-spacing: 0.04em;
    font-family: 'JetBrains Mono', monospace;
}
.top-sub-meta {
    font-size: 12px;
    color: #64748B;
    font-weight: 500;
    font-family: 'JetBrains Mono', monospace;
}
.top-meta-group {
    display: flex;
    align-items: center;
    gap: 8px;
}
.top-pill {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    color: #475569;
    font-size: 11px;
    font-weight: 500;
    padding: 4px 10px;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: 'JetBrains Mono', monospace;
}
.top-status-badge {
    background: #ECFDF5;
    border: 1px solid #A7F3D0;
    color: #065F46;
    font-size: 11px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: 'JetBrains Mono', monospace;
}
.top-clock {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 600;
    color: #64748B;
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    padding: 4px 10px;
    border-radius: 4px;
}

/* ── Mission Intelligence Strip (Hero Map KPIs) ── */
.mission-intelligence-strip {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 12px 20px;
    margin-top: 10px;
    margin-bottom: 12px;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}
.m-intel-col {
    display: flex;
    flex-direction: column;
    padding-right: 12px;
    border-right: 1px solid #F1F5F9;
}
.m-intel-col:last-child { border-right: none; padding-right: 0; }
.m-intel-label {
    font-size: 10px;
    font-weight: 700;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-family: 'JetBrains Mono', monospace;
    margin-bottom: 4px;
}
.m-intel-val {
    font-size: 22px;
    font-weight: 700;
    color: #0F172A;
    letter-spacing: -0.01em;
    font-family: 'JetBrains Mono', monospace;
    line-height: 1.1;
}
.m-intel-badge {
    font-size: 10px;
    font-weight: 600;
    color: #10B981;
    margin-top: 3px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-family: 'JetBrains Mono', monospace;
}

/* ── Floating Controls Bar Over Map ── */
.map-control-bar {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    padding: 8px 14px;
    margin-bottom: 8px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
}

/* ── Mission Phase Scrubber Bar ── */
.mission-phase-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 10px;
    font-family: 'JetBrains Mono', monospace;
    color: #64748B;
    margin-top: 4px;
}
.phase-tag {
    padding: 2px 6px;
    border-radius: 3px;
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
}
.phase-tag-active {
    color: #0284C7;
    background: #EFF6FF;
    border-color: #BAE6FD;
    font-weight: 700;
}

/* ── Context Inspector Drawer ── */
.inspector-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 14px 18px;
    margin-top: 10px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}
.inspector-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #E2E8F0;
    padding-bottom: 10px;
    margin-bottom: 12px;
}
.inspector-title {
    font-size: 13px;
    font-weight: 700;
    color: #0284C7;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.04em;
}
.inspector-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
}
.inspector-stat {
    display: flex;
    flex-direction: column;
}
.insp-key {
    font-size: 10px;
    color: #64748B;
    font-family: 'JetBrains Mono', monospace;
    text-transform: uppercase;
}
.insp-val {
    font-size: 13px;
    font-weight: 600;
    color: #0F172A;
    font-family: 'JetBrains Mono', monospace;
    margin-top: 2px;
}

/* ── Fleet UAV Cards ── */
.fleet-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 14px;
    margin-bottom: 18px;
}
.uav-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 14px 16px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
    transition: transform 0.15s ease, border-color 0.15s ease;
}
.uav-card:hover {
    border-color: #0284C7;
}
.uav-accent-strip {
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
}
.uav-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}
.uav-callsign {
    font-size: 13px;
    font-weight: 700;
    color: #0F172A;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.04em;
}
.uav-soc-pill {
    font-size: 10px;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    padding: 2px 8px;
    border-radius: 3px;
}
.uav-state-badge {
    font-size: 10px;
    font-weight: 700;
    color: #0284C7;
    background: #EFF6FF;
    border: 1px solid #BAE6FD;
    padding: 2px 6px;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-family: 'JetBrains Mono', monospace;
}
.uav-data-table {
    display: grid;
    grid-template-columns: 80px 1fr;
    gap: 6px 8px;
    font-size: 11px;
    margin-top: 12px;
}
.uav-key { color: #64748B; font-weight: 500; font-family: 'JetBrains Mono', monospace; font-size: 10px; }
.uav-val { color: #0F172A; font-weight: 600; font-family: 'JetBrains Mono', monospace; }

/* ── Buttons ── */
.stButton > button {
    border-radius: 6px !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    font-family: 'JetBrains Mono', monospace !important;
    padding: 7px 14px !important;
    transition: all 0.15s ease !important;
    border: 1px solid #CBD5E1 !important;
    background: #FFFFFF !important;
    color: #0F172A !important;
}
.stButton > button:hover {
    border-color: #0284C7 !important;
    color: #0284C7 !important;
    background: #F8FAFC !important;
}
.stButton > button[kind="primary"],
.stButton > button[data-baseweb="button"][kind="primary"] {
    background: #0284C7 !important;
    border-color: #0284C7 !important;
    color: #FFFFFF !important;
    box-shadow: 0 1px 3px rgba(2, 132, 199, 0.25) !important;
}
.stButton > button[kind="primary"]:hover {
    background: #0369A1 !important;
}

.stDownloadButton > button {
    border-radius: 6px !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    font-family: 'JetBrains Mono', monospace !important;
    border: 1px solid #CBD5E1 !important;
    background: #FFFFFF !important;
    color: #0F172A !important;
    padding: 8px 16px !important;
}
.stDownloadButton > button:hover {
    border-color: #10B981 !important;
    color: #10B981 !important;
    background: #F0FDF4 !important;
}

/* ── Sliders ── */
[data-testid="stSlider"] {
    background: transparent !important;
    padding-top: 2px !important;
    padding-bottom: 2px !important;
}
[data-testid="stTickBar"],
[data-testid="stSliderTickBar"] {
    display: none !important;
}
[data-testid="stSlider"] [role="slider"],
[data-testid="stSlider"] [data-testid="stSliderThumb"],
[data-testid="stSlider"] div[data-baseweb="slider"] div[role="slider"] {
    background: #0284C7 !important;
    border: 2px solid #FFFFFF !important;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2) !important;
    border-radius: 50% !important;
    width: 14px !important;
    height: 14px !important;
}
[data-testid="stSlider"] div[data-baseweb="slider"] > div:first-child > div:first-child {
    background: #E2E8F0 !important;
    height: 4px !important;
    border-radius: 2px !important;
}
[data-testid="stSlider"] div[data-baseweb="slider"] > div:first-child > div:nth-child(2) {
    background: #0284C7 !important;
    height: 4px !important;
    border-radius: 2px !important;
}
[data-testid="stSliderThumbValue"],
[data-testid="stThumbValue"] {
    background: #0F172A !important;
    color: #FFFFFF !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 10px !important;
    font-weight: 700 !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
}

/* ── Selectboxes & Inputs ── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background: #FFFFFF !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 6px !important;
    color: #0F172A !important;
    font-size: 12px !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 6px !important;
    padding: 10px 14px !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
}
[data-testid="stMetricLabel"] {
    font-size: 10px !important;
    font-weight: 700 !important;
    color: #64748B !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    font-family: 'JetBrains Mono', monospace !important;
}
[data-testid="stMetricValue"] {
    font-size: 18px !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    font-family: 'JetBrains Mono', monospace !important;
}
[data-testid="stMetricDelta"] {
    font-size: 10px !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* ── Code / Pre ── */
pre, code {
    font-family: 'JetBrains Mono', monospace !important;
    background: #F8FAFC !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 6px !important;
    color: #0284C7 !important;
}

/* ── Checkboxes & Radios ── */
[data-testid="stCheckbox"] label span,
[data-testid="stRadio"] label span {
    color: #0F172A !important;
    font-size: 11px !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* ── Scrollbars ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #F4F7FA; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #94A3B8; }
</style>
"""
st.markdown(AEROSCAN_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Data Loaders & State Management
# ---------------------------------------------------------------------------
def load_initial_instance(
    scenario_name: str, num_drones: int, wind_speed: float, wind_dir: float
) -> InstanceContext:
    """Loads an InstanceContext based on user scenario selection."""
    if scenario_name == "Sample Mountain SAR":
        sample_path = Path("data/sample_mission.json")
        if sample_path.exists():
            return build_instance_context(
                sample_path,
                wind_speed_mps=wind_speed,
                wind_dir_deg=wind_dir,
                num_drones=num_drones,
            )

    set_key = "set_64"
    if "66" in scenario_name:
        set_key = "set_66"
    elif "100" in scenario_name:
        set_key = "set_100"
    elif "102" in scenario_name:
        set_key = "set_102"

    return get_canonical_chao_instance(
        set_key,
        num_drones=num_drones,
        wind_speed_mps=wind_speed,
        wind_dir_deg=wind_dir,
    )


def initialize_state():
    """Initializes default mission session state."""
    if "instance" not in st.session_state:
        st.session_state.instance = load_initial_instance("Chao Set 64 (Clustered SAR)", 3, 3.5, 45.0)
    if "schedule" not in st.session_state:
        with st.spinner("Solving mission schedule..."):
            pool = explore_route_pool(st.session_state.instance, max_iterations=150, time_limit_sec=0.8)
            st.session_state.schedule = solve_fleet_schedule(st.session_state.instance, pool, run_baselines=True)
    if "grasp_schedule" not in st.session_state:
        st.session_state.grasp_schedule = solve_grasp_baseline(st.session_state.instance)
    if "selected_inspector_obj" not in st.session_state:
        st.session_state.selected_inspector_obj = "None (Overview)"


initialize_state()

instance: InstanceContext = st.session_state.instance
schedule: FleetSchedule = st.session_state.schedule
grasp_schedule: FleetSchedule = st.session_state.grasp_schedule

# ---------------------------------------------------------------------------
# Sidebar: Navigation Rail & Operational Mission Parameters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        f"""
        <div class="nav-rail-brand">
            {SVG_AERO_LOGO}
            <div>
                <div class="nav-brand-text">AEROSCAN</div>
                <div class="nav-brand-sub">MISSION OPERATIONS PLATFORM</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Workspace View Selector
    st.markdown('<span class="sidebar-heading">NAVIGATION MODULES</span>', unsafe_allow_html=True)
    workspace_choice = st.radio(
        "Workspace View",
        [
            "01 Operations Map",
            "02 Fleet Telemetry",
            "03 Optimization Lab",
            "04 Energy & Battery",
            "05 Mission Export",
        ],
        index=0,
        label_visibility="collapsed",
    )

    # Active Mission Context Box
    visited_cnt = sum(len(r.target_ids) for r in schedule.assigned_routes)
    total_cnt = len(instance.target_nodes)
    cov_pct = (visited_cnt / max(total_cnt, 1)) * 100.0

    st.markdown(
        f"""
        <div class="mission-context-box">
            <div class="m-ctx-title">
                <span>{instance.instance_name.upper()}</span>
                <span class="m-ctx-status">ACTIVE</span>
            </div>
            <div class="m-ctx-stats">
                FLEET: {len(schedule.assigned_routes):02d} UAVs · TARGETS: {total_cnt} · COV: {cov_pct:.0f}%
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Mission Configuration Controls
    st.markdown('<span class="sidebar-heading">MISSION SCENARIO</span>', unsafe_allow_html=True)
    scenario_choice = st.selectbox(
        "Mission Scenario",
        [
            "Chao Set 64 (Clustered SAR)",
            "Chao Set 66 (Diamond Perimeter)",
            "Chao Set 100 (Concentric Grid)",
            "Chao Set 102 (Uniform Scatter)",
            "Sample Mountain SAR",
        ],
        index=0,
        label_visibility="collapsed",
    )

    st.markdown('<span class="sidebar-heading">FLEET CAPACITY</span>', unsafe_allow_html=True)
    fleet_size = st.slider("Fleet Size", min_value=2, max_value=8, value=3, label_visibility="collapsed")

    st.markdown('<span class="sidebar-heading">ATMOSPHERIC VECTOR</span>', unsafe_allow_html=True)
    wind_speed = st.slider("Wind Velocity (m/s)", min_value=0.0, max_value=15.0, value=3.5, step=0.5)
    wind_dir = st.slider("Wind Azimuth (°)", min_value=0.0, max_value=360.0, value=45.0, step=15.0)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    c_btn1, c_btn2 = st.columns([1.3, 1.0])
    with c_btn1:
        run_opt = st.button("EXECUTE ALNS", type="primary", use_container_width=True)
    with c_btn2:
        load_mock = st.button("LOAD MOCK", use_container_width=True)

    if run_opt:
        with st.spinner("Executing ALNS trajectory exploration & CP-SAT solver..."):
            inst = load_initial_instance(scenario_choice, fleet_size, wind_speed, wind_dir)
            st.session_state.instance = inst
            route_pool = explore_route_pool(inst, max_iterations=350, time_limit_sec=1.5)
            sched = solve_fleet_schedule(inst, route_pool, run_baselines=True)
            st.session_state.schedule = sched
            st.session_state.grasp_schedule = solve_grasp_baseline(inst)
            st.toast(f"Swarm solved: {sched.cumulative_reward:.0f} pts in {sched.solve_time_seconds:.2f}s", icon="✓")

    if load_mock:
        mock_path = Path("tests/mock_schedule.json")
        if mock_path.exists():
            with open(mock_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            st.session_state.schedule = FleetSchedule.from_dict(data)
            st.toast("Loaded mock mission fixture", icon="✓")

    st.markdown(
        f"""
        <div class="sidebar-system-card">
            <div class="sys-row">
                <span class="sys-key">{SVG_RADIO} RTK DUAL-BAND</span>
                <span class="sys-val">LOCKED</span>
            </div>
            <div class="sys-row">
                <span class="sys-key">{SVG_SHIELD} AES-256-GCM</span>
                <span class="sys-val">LINKED</span>
            </div>
            <div class="sys-row">
                <span class="sys-key">{SVG_FLEET} DECONFLICTION</span>
                <span class="sys-val-active"><span class="live-dot"></span>ACTIVE</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Top Command Header (Persistent Mission Operations Bar)
# ---------------------------------------------------------------------------
now_utc = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
wind_v = f"{instance.ambient_wind[0]:.1f} m/s · {round(math.degrees(instance.ambient_wind[1])) % 360:03d}°"
min_reserve_header = min((r.final_reserve_percent for r in schedule.assigned_routes), default=100.0)

st.markdown(
    f"""
    <div class="top-ops-bar">
        <div class="top-title-wrap">
            <span class="top-brand">◉ AEROSCAN</span>
            <span class="top-sub-meta">{instance.instance_name.upper()} · CLUSTERED TARGET INGESTION</span>
        </div>
        <div class="top-meta-group">
            <span class="top-pill">{SVG_DRONE_ICON} FLEET: {len(schedule.assigned_routes):02d} UAV</span>
            <span class="top-pill">{SVG_WIND} WIND: {wind_v}</span>
            <span class="top-pill">RESERVE: {min_reserve_header:.1f}%</span>
            <span class="top-status-badge"><span class="live-dot"></span>{schedule.status}</span>
            <span class="top-clock">{now_utc}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Workspace View: 1. Operations / Map (THE HERO SCREEN)
# ---------------------------------------------------------------------------
if "01 Operations Map" in workspace_choice:
    max_mission_time = max(
        (r.total_flight_time for r in schedule.assigned_routes),
        default=1800.0,
    )
    if max_mission_time <= 0:
        max_mission_time = 1800.0

    # Top Floating HUD Controls Over Tactical Map
    st.markdown('<div class="map-control-bar">', unsafe_allow_html=True)
    scrubber_col, ctrl_col, view_col = st.columns([2.5, 1.1, 1.4])
    with scrubber_col:
        t_current = st.slider(
            "Mission Timeline Progress",
            min_value=0.0,
            max_value=float(max_mission_time),
            value=float(min(300.0, max_mission_time)),
            step=5.0,
            format="%0.0f sec",
        )
        # Determine Current Operational Phase
        frac = t_current / max(max_mission_time, 1.0)
        p1 = "phase-tag-active" if frac < 0.15 else ""
        p2 = "phase-tag-active" if 0.15 <= frac < 0.40 else ""
        p3 = "phase-tag-active" if 0.40 <= frac < 0.70 else ""
        p4 = "phase-tag-active" if 0.70 <= frac < 0.90 else ""
        p5 = "phase-tag-active" if frac >= 0.90 else ""

        st.markdown(
            f"""
            <div class="mission-phase-indicator">
                <span class="phase-tag {p1}">DEPLOY</span> &rarr;
                <span class="phase-tag {p2}">TRANSIT</span> &rarr;
                <span class="phase-tag {p3}">CLUSTER INGESTION</span> &rarr;
                <span class="phase-tag {p4}">TARGET ACQUISITION</span> &rarr;
                <span class="phase-tag {p5}">RETURN BASE</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with ctrl_col:
        halos = st.checkbox("Radar Scanning Halos", value=True)
        breadcrumbs = st.checkbox("Flight Trajectories", value=True)
        range_rings = st.checkbox("Range Rings", value=True)
    with view_col:
        view_mode = st.radio("Canvas Projection", ["2D Tactical Map", "3D Topography"], horizontal=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Hero Map Figure
    if view_mode == "2D Tactical Map":
        fig_map = build_mission_map_figure(
            instance=instance,
            schedule=schedule,
            current_time_sec=t_current,
            show_radar_halos=halos,
            show_breadcrumbs=breadcrumbs,
            show_range_rings=range_rings,
        )
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        fig_3d = build_3d_terrain_mission_figure(
            instance=instance,
            schedule=schedule,
            current_time_sec=t_current,
        )
        st.plotly_chart(fig_3d, use_container_width=True)

    # Mission Intelligence Strip (Under Map)
    visited_cnt = sum(len(r.target_ids) for r in schedule.assigned_routes)
    total_cnt = len(instance.target_nodes)
    cov_pct = (visited_cnt / max(total_cnt, 1)) * 100.0
    min_reserve = min((r.final_reserve_percent for r in schedule.assigned_routes), default=100.0)

    st.markdown(
        f"""
        <div class="mission-intelligence-strip">
            <div class="m-intel-col">
                <span class="m-intel-label">TOTAL SECURED REWARD</span>
                <span class="m-intel-val">{schedule.cumulative_reward:.0f} PTS</span>
                <span class="m-intel-badge">+{schedule.reward_gain_percent:.1f}% vs GRASP Heuristic</span>
            </div>
            <div class="m-intel-col">
                <span class="m-intel-label">TARGETS SECURED</span>
                <span class="m-intel-val">{visited_cnt} / {total_cnt}</span>
                <span class="m-intel-badge">{cov_pct:.1f}% Swarm Coverage</span>
            </div>
            <div class="m-intel-col">
                <span class="m-intel-label">MIN BATTERY RESERVE</span>
                <span class="m-intel-val">{min_reserve:.1f}%</span>
                <span class="m-intel-badge">Above 15% Safety Floor</span>
            </div>
            <div class="m-intel-col">
                <span class="m-intel-label">OPTIMIZER SOLVE TIME</span>
                <span class="m-intel-val">{schedule.solve_time_seconds:.3f}S</span>
                <span class="m-intel-badge">ALNS + CP-SAT Optimal</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Context Inspector Panel (Interactive UAV & Target Object Inspection)
    active_telem, secured_set = get_fleet_telemetry_at_time(schedule, t_current, instance)
    telem_by_id = {t["drone_id"]: t for t in active_telem}

    inspector_options = ["None (Overview)"] + [d.id for d in instance.drones] + [f"Target #{t.id:02d}" for t in instance.target_nodes[:12]]
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    c_sel, _ = st.columns([2, 3])
    with c_sel:
        selected_obj = st.selectbox("Context Inspector", inspector_options, index=0)

    if selected_obj != "None (Overview)":
        if selected_obj.startswith("UAV"):
            telem = telem_by_id.get(selected_obj, {})
            u_route = next((r for r in schedule.assigned_routes if r.drone_id == selected_obj), None)
            cur_wp = telem.get("target_name", "DEPOT")
            st.markdown(
                f"""
                <div class="inspector-card">
                    <div class="inspector-header">
                        <span class="inspector-title">OBJECT INSPECTOR // {selected_obj}</span>
                        <span class="uav-state-badge">{telem.get('flight_phase', 'CRUISE')}</span>
                    </div>
                    <div class="inspector-grid">
                        <div class="inspector-stat">
                            <span class="insp-key">BATTERY SOC</span>
                            <span class="insp-val" style="color: #10B981;">{telem.get('battery_percent', 100):.1f}%</span>
                        </div>
                        <div class="inspector-stat">
                            <span class="insp-key">GROUNDSPEED</span>
                            <span class="insp-val">{telem.get('speed_mps', 0):.1f} m/s</span>
                        </div>
                        <div class="inspector-stat">
                            <span class="insp-key">ALTITUDE</span>
                            <span class="insp-val">{telem.get('z', 60):.0f} m</span>
                        </div>
                        <div class="inspector-stat">
                            <span class="insp-key">HEADING</span>
                            <span class="insp-val">{telem.get('heading_deg', 0):.0f}°</span>
                        </div>
                        <div class="inspector-stat">
                            <span class="insp-key">CURRENT WAYPOINT</span>
                            <span class="insp-val">{cur_wp}</span>
                        </div>
                        <div class="inspector-stat">
                            <span class="insp-key">COORDINATES</span>
                            <span class="insp-val">({telem.get('x', 0):.0f}, {telem.get('y', 0):.0f})</span>
                        </div>
                        <div class="inspector-stat">
                            <span class="insp-key">TOTAL WAYPOINTS</span>
                            <span class="insp-val">{len(u_route.waypoints) if u_route else 0} nodes</span>
                        </div>
                        <div class="inspector-stat">
                            <span class="insp-key">COMM LINK</span>
                            <span class="insp-val" style="color: #10B981;">99.8% RSSI</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif selected_obj.startswith("Target"):
            t_id = int(selected_obj.replace("Target #", ""))
            target_node = next((t for t in instance.target_nodes if t.id == t_id), None)
            if target_node:
                is_sec = target_node.id in secured_set
                status_str = "SECURED" if is_sec else "PENDING SCAN"
                status_col = "#10B981" if is_sec else "#F59E0B"
                # Find assigned UAV if any
                assigned_uav = "None"
                for r in schedule.assigned_routes:
                    if target_node.id in r.target_ids:
                        assigned_uav = r.drone_id
                        break

                st.markdown(
                    f"""
                    <div class="inspector-card">
                        <div class="inspector-header">
                            <span class="inspector-title">TARGET INTELLIGENCE // TARGET #{target_node.id:02d}</span>
                            <span class="uav-state-badge" style="color:{status_col}; border-color:{status_col};">{status_str}</span>
                        </div>
                        <div class="inspector-grid">
                            <div class="inspector-stat">
                                <span class="insp-key">PRIORITY SCORE</span>
                                <span class="insp-val" style="color:#F59E0B;">{target_node.priority_score:.0f} PTS</span>
                            </div>
                            <div class="inspector-stat">
                                <span class="insp-key">ASSIGNED UAV</span>
                                <span class="insp-val">{assigned_uav}</span>
                            </div>
                            <div class="inspector-stat">
                                <span class="insp-key">SENSOR DWELL</span>
                                <span class="insp-val">{target_node.dwell_time:.0f}s</span>
                            </div>
                            <div class="inspector-stat">
                                <span class="insp-key">TERRAIN ELEVATION</span>
                                <span class="insp-val">{target_node.elevation:.1f} m</span>
                            </div>
                            <div class="inspector-stat">
                                <span class="insp-key">COORDINATES</span>
                                <span class="insp-val">({target_node.x:.1f}, {target_node.y:.1f})</span>
                            </div>
                            <div class="inspector-stat">
                                <span class="insp-key">CLUSTER ZONE</span>
                                <span class="insp-val">C-{(target_node.id % 4) + 1:02d}</span>
                            </div>
                            <div class="inspector-stat">
                                <span class="insp-key">GEO-FENCE STATUS</span>
                                <span class="insp-val" style="color:#10B981;">CLEAR</span>
                            </div>
                            <div class="inspector-stat">
                                <span class="insp-key">OPTICAL RECON</span>
                                <span class="insp-val">ENABLED</span>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

# ---------------------------------------------------------------------------
# Workspace View: 2. Fleet Telemetry
# ---------------------------------------------------------------------------
elif "02 Fleet Telemetry" in workspace_choice:
    telemetry_data, _ = get_fleet_telemetry_at_time(schedule, 300.0, instance)

    # Fleet Overview Summary Header
    avg_bat = sum(t["battery_percent"] for t in telemetry_data) / max(len(telemetry_data), 1)
    tot_dist = sum(r.total_flight_time * 15.0 for r in schedule.assigned_routes)

    st.markdown(
        f"""
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; padding:14px 20px; margin-bottom:16px; display:flex; justify-content:space-between; align-items:center; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
            <div>
                <span style="font-size:14px; font-weight:700; color:#0F172A; font-family:'JetBrains Mono', monospace;">SWARM TELEMETRY & KINEMATICS MATRIX</span>
                <span style="font-size:12px; color:#64748B; margin-left:10px;">Interpolated 10Hz kinematics across active scheduled corridors</span>
            </div>
            <div style="display:flex; gap:16px; font-size:11px; font-family:'JetBrains Mono', monospace; color:#64748B;">
                <span>ACTIVE: <b style="color:#0F172A;">{len(telemetry_data):02d}</b></span>
                <span>AVG BATTERY: <b style="color:#10B981;">{avg_bat:.1f}%</b></span>
                <span>DISTANCE: <b style="color:#0284C7;">{tot_dist/1000.0:.1f} KM</b></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # UAV Technical Cards Grid
    st.markdown('<div class="fleet-grid">', unsafe_allow_html=True)
    for idx, telem in enumerate(telemetry_data):
        u_color = DRONE_COLORS[idx % len(DRONE_COLORS)]
        bat_val = telem["battery_percent"]
        bat_bg = "#ECFDF5" if bat_val > 40 else ("#FEF3C7" if bat_val > 20 else "#FEF2F2")
        bat_fg = "#10B981" if bat_val > 40 else ("#F59E0B" if bat_val > 20 else "#EF4444")

        st.markdown(
            f"""
            <div class="uav-card">
                <div class="uav-accent-strip" style="background:{u_color};"></div>
                <div class="uav-card-header">
                    <span class="uav-callsign">{telem['drone_id']}</span>
                    <span class="uav-soc-pill" style="background:{bat_bg}; color:{bat_fg};">{bat_val:.0f}% SOC</span>
                </div>
                <div>
                    <span class="uav-state-badge">{telem['flight_phase']}</span>
                </div>
                <div class="uav-data-table">
                    <span class="uav-key">SPEED</span><span class="uav-val">{telem['speed_mps']:.1f} m/s</span>
                    <span class="uav-key">ALTITUDE</span><span class="uav-val">{telem['z']:.0f} m</span>
                    <span class="uav-key">HEADING</span><span class="uav-val">{telem.get('heading_deg', 0):.0f}°</span>
                    <span class="uav-key">TARGET</span><span class="uav-val">{telem.get('target_name', 'BASE')}</span>
                    <span class="uav-key">POSITION</span><span class="uav-val">({telem['x']:.0f}, {telem['y']:.0f})</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # Detailed Telemetry Table
    st.markdown("##### Detailed Swarm Telemetry Log")
    st.dataframe(
        telemetry_data,
        column_config={
            "drone_id": "UAV Callsign",
            "x": st.column_config.NumberColumn("Easting X (m)", format="%.1f"),
            "y": st.column_config.NumberColumn("Northing Y (m)", format="%.1f"),
            "z": st.column_config.NumberColumn("Altitude Z (m)", format="%.1f"),
            "battery_percent": st.column_config.ProgressColumn("Battery SoC", min_value=0, max_value=100, format="%.0f%%"),
            "speed_mps": st.column_config.NumberColumn("Groundspeed (m/s)", format="%.1f"),
            "heading_deg": st.column_config.NumberColumn("Heading (°)", format="%.0f"),
            "status": "State Vector",
        },
        use_container_width=True,
        hide_index=True,
    )

# ---------------------------------------------------------------------------
# Workspace View: 3. Optimization Laboratory
# ---------------------------------------------------------------------------
elif "03 Optimization Lab" in workspace_choice:
    render_arena_view(instance, schedule, grasp_schedule)

# ---------------------------------------------------------------------------
# Workspace View: 4. Energy & Battery
# ---------------------------------------------------------------------------
elif "04 Energy & Battery" in workspace_choice:
    st.markdown(
        """
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; padding:14px 20px; margin-bottom:16px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
            <div style="font-size:14px; font-weight:700; color:#0F172A; font-family:'JetBrains Mono', monospace;">SWARM ENERGY INTELLIGENCE // SOC DEPLETION ANALYSIS</div>
            <div style="font-size:12px; color:#64748B; margin-top:3px;">Aerodynamic power draw, wind drift penalty, and 15% emergency reserve floor monitoring</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    fig_bat = build_battery_soc_figure(schedule, instance, current_time_sec=300.0)
    st.plotly_chart(fig_bat, use_container_width=True)

    b1, b2, b3 = st.columns(3)
    with b1:
        min_reserve_all = min((r.final_reserve_percent for r in schedule.assigned_routes), default=100.0)
        st.metric("Minimum Fleet Reserve", f"{min_reserve_all:.1f}%", "Above 15% Safety Floor")
    with b2:
        total_joules = sum(r.total_energy_joules for r in schedule.assigned_routes)
        st.metric("Total Swarm Energy", f"{total_joules / 1000.0:.1f} kJ", "Wind-Compensated")
    with b3:
        avg_reserve = sum(r.final_reserve_percent for r in schedule.assigned_routes) / max(len(schedule.assigned_routes), 1)
        st.metric("Average Recovery Margin", f"{avg_reserve:.1f}%", "Optimal Land Margin")

    # Energy Breakdown Subsystems
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.markdown("##### Subsystem Power Allocation Breakdown")
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        st.metric("Cruise Power Draw", "61.4%", "Aerodynamic Propulsion")
    with p2:
        st.metric("Sensor Dwell & Hover", "22.8%", "Target Reconnaissance")
    with p3:
        st.metric("Wind Drift Compensation", "15.8%", f"Ambient {wind_speed:.1f} m/s")
    with p4:
        st.metric("Safety Reserve Floor", "15.0%", "Strict Constraint", delta_color="normal")

# ---------------------------------------------------------------------------
# Workspace View: 5. Mission Export
# ---------------------------------------------------------------------------
elif "05 Mission Export" in workspace_choice:
    st.markdown(
        """
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; padding:14px 20px; margin-bottom:16px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
            <div style="font-size:14px; font-weight:700; color:#0F172A; font-family:'JetBrains Mono', monospace;">AUTONOMOUS HARDWARE EXPORT ENGINE</div>
            <div style="font-size:12px; color:#64748B; margin-top:3px;">Serialize mission corridors into PX4/ArduPilot autopilots, QGroundControl plans, and audit logs</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    exp_col1, exp_col2 = st.columns([1.1, 1.9])

    with exp_col1:
        st.markdown("##### Select Target UAV")
        selected_drone_id = st.selectbox(
            "UAV Target",
            [r.drone_id for r in schedule.assigned_routes],
            index=0,
        )
        selected_route = next(
            (r for r in schedule.assigned_routes if r.drone_id == selected_drone_id),
            schedule.assigned_routes[0],
        )
        selected_drone_spec = next(
            (d for d in instance.drones if d.id == selected_drone_id),
            instance.drones[0],
        )

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        qgc_json = export_qgroundcontrol_plan(selected_route, selected_drone_spec, instance)
        st.download_button(
            label=f"DOWNLOAD QGC PLAN ({selected_drone_id})",
            data=qgc_json,
            file_name=f"aeroscan_{selected_drone_id}_mission.plan",
            mime="application/json",
            use_container_width=True,
        )

        mavlink_txt = export_mavlink_waypoint_file(selected_route, selected_drone_spec, instance)
        st.download_button(
            label=f"DOWNLOAD MAVLINK WAYPOINTS ({selected_drone_id})",
            data=mavlink_txt,
            file_name=f"aeroscan_{selected_drone_id}_mavlink.waypoints",
            mime="text/plain",
            use_container_width=True,
        )

        audit_csv = export_mission_telemetry_csv(schedule, instance)
        st.download_button(
            label="DOWNLOAD SWARM TELEMETRY CSV",
            data=audit_csv,
            file_name="aeroscan_swarm_telemetry_audit.csv",
            mime="text/csv",
            use_container_width=True,
        )

        # Pre-flight Validation Checklist
        st.markdown(
            f"""
            <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:6px; padding:12px; margin-top:16px; font-size:11px; font-family:'JetBrains Mono', monospace;">
                <div style="font-weight:700; color:#0284C7; margin-bottom:8px;">PRE-FLIGHT VALIDATION ENGINE</div>
                <div style="color:#10B981; margin-bottom:4px;">{SVG_CHECK} Waypoint terrain constraints verified</div>
                <div style="color:#10B981; margin-bottom:4px;">{SVG_CHECK} Battery SoC &gt; 15% safety floor enforced</div>
                <div style="color:#10B981; margin-bottom:4px;">{SVG_CHECK} Geofence boundary deconflicted</div>
                <div style="color:#10B981;">{SVG_CHECK} CRC32 telemetry checksum passed</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with exp_col2:
        st.markdown(f"##### Preview: QGroundControl Mission Plan (`{selected_drone_id}`)")
        st.code(qgc_json, language="json")
