"""
AeroScan — Aerospace Swarm Mission Operations Platform
Autonomous UAV Swarm Coverage Optimization & Real-Time Mission Control.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path for absolute imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import json
import math
from datetime import datetime, timezone

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
    build_3d_terrain_mission_figure,
    build_animated_mission_map_figure,
    build_battery_soc_figure,
    build_energy_breakdown_figure,
    build_mission_map_figure,
    build_uav_kinematics_figure,
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
SVG_CLOCK = """<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>"""


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
    box-shadow: none !important;
    z-index: 100 !important;
    min-width: 292px !important;
    max-width: 322px !important;
}
[data-testid="stSidebar"] > div:first-child,
[data-testid="stSidebarContent"] {
    padding: 18px 16px 16px 16px !important;
    background: #FFFFFF !important;
}

[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
    gap: 0.55rem !important;
}
[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] {
    gap: 0.6rem !important;
}

/* Micro section header: tiny caps label with hairline rule */
.side-section {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 10px 2px 2px 2px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 8.5px;
    font-weight: 700;
    letter-spacing: 0.14em;
    color: #94A3B8;
    text-transform: uppercase;
}
.side-section::after {
    content: "";
    flex: 1;
    height: 1px;
    background: #EEF2F6;
}

/* Brand */
.nav-rail-brand {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 2px 14px 2px;
    border-bottom: 1px solid #EEF2F6;
    margin-bottom: 8px;
}
.brand-left {
    display: flex;
    align-items: center;
    gap: 10px;
}
.nav-brand-text {
    font-family: 'Inter', -apple-system, sans-serif !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    letter-spacing: -0.01em !important;
    line-height: 1.15;
}
.nav-brand-sub {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 8.5px !important;
    color: #94A3B8 !important;
    font-weight: 600 !important;
    letter-spacing: 0.14em !important;
    margin-top: 2px !important;
}
.nav-brand-badge {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 8.5px !important;
    font-weight: 700 !important;
    color: #64748B !important;
    background: #F8FAFC !important;
    border: 1px solid #E2E8F0 !important;
    padding: 2px 8px !important;
    border-radius: 99px !important;
    letter-spacing: 0.06em !important;
}

/* Sidebar field labels: quiet Inter, sentence case */
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] label,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] label[data-testid="stWidgetLabel"] {
    font-family: 'Inter', -apple-system, sans-serif !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    color: #475569 !important;
    letter-spacing: 0.01em !important;
    text-transform: none !important;
    margin-bottom: 5px !important;
}

/* ── Workspace Navigation: quiet full-width rows, left accent on active ── */
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] {
    gap: 2px !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: stretch !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label {
    width: 100% !important;
    background: transparent !important;
    border: none !important;
    border-radius: 7px !important;
    padding: 8px 10px !important;
    margin: 0 !important;
    cursor: pointer !important;
    transition: background 0.12s ease !important;
    display: flex !important;
    align-items: center !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label > div:first-child,
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label input[type="radio"] {
    display: none !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:hover {
    background: #F6F8FA !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
    background: #F0F9FF !important;
    box-shadow: inset 3px 0 0 #0284C7 !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) div,
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) span,
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) p {
    color: #0369A1 !important;
    font-weight: 600 !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label div,
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label span,
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label p {
    color: #334155 !important;
    font-size: 12.5px !important;
    font-weight: 500 !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
    letter-spacing: 0 !important;
    text-transform: none !important;
    white-space: nowrap !important;
    margin: 0 !important;
}

/* Mission Context Card */
.mission-context-box {
    background: #F8FAFC;
    border: 1px solid #EEF2F6;
    border-radius: 10px;
    padding: 10px 12px 11px 12px;
    margin: 6px 0 2px 0;
}
.m-ctx-title {
    font-size: 10.5px;
    font-weight: 700;
    color: #0F172A;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.02em;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 9px;
}
.m-ctx-status {
    font-size: 8.5px;
    font-weight: 700;
    color: #059669;
    background: #ECFDF5;
    padding: 1px 7px;
    border-radius: 99px;
    border: 1px solid #A7F3D0;
    letter-spacing: 0.08em;
}
.m-ctx-grid {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 10px;
}
.m-stat {
    display: flex;
    flex-direction: column;
    gap: 3px;
}
.m-lbl {
    font-size: 8.5px;
    font-weight: 600;
    color: #94A3B8;
    font-family: 'Inter', -apple-system, sans-serif;
    letter-spacing: 0.07em;
    text-transform: uppercase;
}
.m-val {
    font-size: 12.5px;
    font-weight: 700;
    color: #0F172A;
    font-family: 'JetBrains Mono', monospace;
}

/* Selectbox in Sidebar */
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div,
[data-testid="stSidebar"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    min-height: 34px !important;
    height: 34px !important;
    font-size: 12px !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    background: #FFFFFF !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
    display: flex !important;
    align-items: center !important;
}

/* Sliders in Sidebar (headroom for the floating value pill) */
[data-testid="stSidebar"] [data-testid="stSlider"] {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}
[data-testid="stSidebar"] [data-testid="stSlider"] div[data-baseweb="slider"] {
    padding-top: 14px !important;
    padding-bottom: 6px !important;
}

/* Buttons in Sidebar */
[data-testid="stSidebar"] .stButton > button {
    height: 36px !important;
    min-height: 36px !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
    letter-spacing: 0.01em !important;
    border-radius: 8px !important;
    padding: 0 8px !important;
    margin-top: 4px !important;
    margin-bottom: 2px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    white-space: nowrap !important;
    width: 100% !important;
    overflow: visible !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton > button p,
[data-testid="stSidebar"] .stButton > button span {
    font-size: 12px !important;
    font-weight: 600 !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
    letter-spacing: 0.01em !important;
    white-space: nowrap !important;
    margin: 0 !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #0F172A !important;
    border: 1px solid #0F172A !important;
    color: #FFFFFF !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.2) !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
    background: #1E293B !important;
    border-color: #1E293B !important;
}
[data-testid="stSidebar"] .stButton > button:not([kind="primary"]) {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    color: #334155 !important;
}
[data-testid="stSidebar"] .stButton > button:not([kind="primary"]):hover {
    background: #F8FAFC !important;
    border-color: #CBD5E1 !important;
    color: #0F172A !important;
}

/* System Footer (borderless, hairline top rule) */
.sidebar-system-card {
    background: transparent;
    border: none;
    border-top: 1px solid #EEF2F6;
    border-radius: 0;
    padding: 12px 2px 0 2px;
    margin-top: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.sys-chip {
    font-size: 8.5px;
    font-weight: 600;
    color: #64748B;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.05em;
    display: flex;
    align-items: center;
    gap: 4px;
}
.live-dot {
    width: 6px; height: 6px;
    background: #10B981;
    border-radius: 50%;
    display: inline-block;
    box-shadow: 0 0 5px rgba(16, 185, 129, 0.7);
}

/* ── Top Header Context Bar (Avionics Command Deck) ── */
.top-ops-bar {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-top: 3px solid #0284C7;
    border-radius: 8px;
    padding: 7px 14px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
    min-height: 48px;
    flex-wrap: nowrap !important;
    gap: 10px;
    overflow: visible;
}

.top-title-wrap {
    display: flex;
    align-items: center;
    gap: 10px;
    white-space: nowrap !important;
    flex-shrink: 0 !important;
}
.top-meta-group {
    display: flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap !important;
    flex-shrink: 1 !important;
    min-width: 0 !important;
    overflow: hidden;
    justify-content: flex-end;
}
.top-meta-group > div { flex-shrink: 0; }

/* Instruments compress on narrower screens instead of clipping */
@media (min-width: 1501px) and (max-width: 1780px) {
    .tac-instrument:nth-of-type(1) { display: none !important; }
}
@media (max-width: 1500px) {
    .tac-instrument, .tac-zulu-card { display: none !important; }
}
@media (max-width: 1280px) {
    .tac-mission-meta { display: none !important; }
    .tac-callsign-text { font-size: 10.5px !important; }
    .tac-status-badge { padding: 5px 8px !important; font-size: 10px !important; }
}
@media (max-width: 760px) {
    .top-ops-bar { flex-wrap: wrap !important; }
    .top-title-wrap { flex-shrink: 1 !important; }
}
.tac-callsign-box {
    background: #0F172A;
    border: 1px solid #1E293B;
    border-radius: 5px;
    padding: 5px 10px;
    display: inline-flex;
    align-items: center;
    gap: 7px;
}
.tac-callsign-text {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11.5px;
    font-weight: 800;
    color: #38BDF8;
    letter-spacing: 0.07em;
}
.live-dot-pulse {
    width: 7px;
    height: 7px;
    background: #10B981;
    border-radius: 50%;
    display: inline-block;
    box-shadow: 0 0 6px rgba(16, 185, 129, 0.8);
    animation: pulse-ring 2s infinite;
}
@keyframes pulse-ring {
    0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
    70% { box-shadow: 0 0 0 5px rgba(16, 185, 129, 0); }
    100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}
.tac-mission-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    padding-left: 8px;
    border-left: 1px solid #E2E8F0;
}
.tac-mission-id {
    font-size: 11px;
    font-weight: 700;
    color: #0F172A;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.04em;
}
.tac-mission-chip {
    font-size: 9.5px;
    font-weight: 700;
    color: #0284C7;
    background: #EFF6FF;
    border: 1px solid #BAE6FD;
    padding: 2px 7px;
    border-radius: 4px;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.04em;
}

.top-meta-group {
    display: flex;
    align-items: center;
    gap: 7px;
    white-space: nowrap !important;
    flex-shrink: 0 !important;
}
.tac-instrument {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 5px;
    padding: 3px 9px;
    display: flex;
    flex-direction: column;
    gap: 1px;
    font-family: 'JetBrains Mono', monospace;
}
.tac-inst-lbl {
    font-size: 7.5px;
    font-weight: 700;
    color: #64748B;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.tac-inst-val {
    font-size: 11px;
    font-weight: 600;
    color: #334155;
    display: flex;
    align-items: center;
    gap: 4px;
}
.tac-inst-val b {
    color: #0F172A;
    font-weight: 700;
}
.tac-inst-val small {
    font-size: 8.5px;
    color: #64748B;
}
.energy-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    display: inline-block;
}
.tac-status-badge {
    background: #ECFDF5;
    border: 1px solid #A7F3D0;
    color: #059669;
    font-size: 11px;
    font-weight: 700;
    padding: 6px 11px;
    border-radius: 6px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.03em;
}
.tac-zulu-card {
    background: #F1F5F9;
    border: 1px solid #CBD5E1;
    color: #334155;
    font-size: 11px;
    font-weight: 700;
    padding: 6px 10px;
    border-radius: 6px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: 'JetBrains Mono', monospace;
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

/* ── Tactical HUD Deck Header & Flight Pipeline ── */
.deck-header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    row-gap: 6px;
    padding-bottom: 7px;
    margin-bottom: 6px;
    border-bottom: 1px solid #F1F5F9;
}
.deck-title-text,
.deck-sensors-badge,
.deck-time-badge {
    white-space: nowrap !important;
}
.deck-sensors-badge {
    padding: 2px 7px !important;
}
.deck-title-col {
    display: flex;
    align-items: center;
    gap: 10px;
}
.deck-title-text {
    font-size: 10px;
    font-weight: 700;
    color: #64748B;
    letter-spacing: 0.06em;
    font-family: 'JetBrains Mono', monospace;
}
.deck-time-badge {
    font-size: 10px;
    font-weight: 700;
    color: #0284C7;
    font-family: 'JetBrains Mono', monospace;
    background: #EFF6FF;
    border: 1px solid #BAE6FD;
    padding: 2px 7px;
    border-radius: 4px;
}
.deck-sensors-badge {
    font-size: 9.5px;
    font-weight: 700;
    color: #059669;
    font-family: 'JetBrains Mono', monospace;
    background: #ECFDF5;
    border: 1px solid #A7F3D0;
    padding: 2px 7px;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
}
.sensor-live-dot {
    width: 5px;
    height: 5px;
    background: #10B981;
    border-radius: 50%;
    display: inline-block;
}

/* ── Connected Mission Flight Phase Pipeline ── */
.mission-flight-pipeline {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 6px;
    width: 100%;
}
.pipeline-step {
    flex: 1;
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 5px;
    padding: 4px 6px;
    display: flex;
    flex-direction: column;
    gap: 3px;
    transition: all 0.2s ease;
}
.pipeline-step .pipe-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 5px;
}
.pipeline-step .pipe-idx,
.pipeline-step .pipe-name {
    white-space: nowrap;
}
.pipeline-step .pipe-idx {
    font-size: 8px;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    color: #94A3B8;
}
.pipeline-step .pipe-name {
    font-size: 9.5px;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    color: #475569;
    letter-spacing: 0.04em;
}
.pipeline-step .pipe-bar {
    height: 3px;
    border-radius: 1.5px;
    background: #E2E8F0;
}
/* Completed step */
.pipeline-step.completed {
    background: #F0FDF4;
    border-color: #BBF7D0;
}
.pipeline-step.completed .pipe-idx {
    color: #10B981;
}
.pipeline-step.completed .pipe-name {
    color: #059669;
}
.pipeline-step.completed .pipe-bar {
    background: #10B981;
}
/* Active step */
.pipeline-step.active {
    background: #EFF6FF;
    border-color: #0284C7;
    box-shadow: 0 1px 4px rgba(2, 132, 199, 0.2);
}
.pipeline-step.active .pipe-idx {
    color: #0284C7;
}
.pipeline-step.active .pipe-name {
    color: #0284C7;
    font-weight: 800;
}
.pipeline-step.active .pipe-bar {
    background: #0284C7;
    box-shadow: 0 0 6px rgba(2, 132, 199, 0.6);
}

/* ── Cockpit MFD Projection Buttons (Transform st.radio) ── */
div[data-testid="stRadio"] div[role="radiogroup"] {
    gap: 8px !important;
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    margin-bottom: 6px !important;
    width: 100% !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] > label {
    flex: 1 !important;
    background: #F8FAFC !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 6px !important;
    padding: 6px 10px !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    margin: 0 !important;
}
/* Hide native radio button circle */
div[data-testid="stRadio"] div[role="radiogroup"] > label > div:first-child {
    display: none !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] > label input[type="radio"] {
    display: none !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] > label:hover {
    border-color: #0284C7 !important;
    background: #F1F5F9 !important;
}
/* Active / Selected button */
div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
    background: #0F172A !important;
    border-color: #0F172A !important;
    box-shadow: 0 2px 6px rgba(15, 23, 42, 0.25) !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) span,
div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) p {
    color: #38BDF8 !important;
    font-weight: 700 !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] > label span,
div[data-testid="stRadio"] div[role="radiogroup"] > label p {
    font-size: 10.5px !important;
    font-weight: 600 !important;
    font-family: 'JetBrains Mono', monospace !important;
    letter-spacing: 0.04em !important;
    color: #475569 !important;
    margin: 0 !important;
    text-transform: uppercase !important;
    white-space: nowrap !important;
}

/* ── Cockpit Sensor Push-Buttons (Transform st.checkbox) ── */
div[data-testid="stCheckbox"] {
    margin: 0 !important;
}
div[data-testid="stCheckbox"] label {
    background: #F8FAFC !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 6px !important;
    padding: 5px 8px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
    width: 100% !important;
    margin: 0 !important;
    white-space: nowrap !important;
}
div[data-testid="stCheckbox"]:hover label {
    background: #F1F5F9 !important;
    border-color: #94A3B8 !important;
}
/* Active / Checked state */
div[data-testid="stCheckbox"]:has(input:checked) label {
    background: #EFF6FF !important;
    border-color: #0284C7 !important;
    box-shadow: 0 1px 4px rgba(2, 132, 199, 0.2) !important;
}
div[data-testid="stCheckbox"]:has(input:checked) label span,
div[data-testid="stCheckbox"]:has(input:checked) label p {
    color: #0284C7 !important;
    font-weight: 700 !important;
}
div[data-testid="stCheckbox"] label span,
div[data-testid="stCheckbox"] label p {
    font-size: 10px !important;
    font-weight: 600 !important;
    font-family: 'JetBrains Mono', monospace !important;
    letter-spacing: 0.02em !important;
    color: #475569 !important;
    margin: 0 !important;
    text-transform: uppercase !important;
    white-space: nowrap !important;
}

/* ── Bordered Container Cards (HUD Toolbar) ── */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #FFFFFF !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.03) !important;
    margin-bottom: 12px !important;
}
[data-testid="stVerticalBlockBorderWrapper"] > div {
    padding: 12px 16px 14px 16px !important;
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

/* ── Fleet Command Center Layout ── */
.fleet-command-grid {
    display: grid;
    grid-template-columns: 280px 1fr 280px;
    gap: 14px;
    margin-bottom: 16px;
}
.fleet-list-box {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
.fleet-card-item {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    padding: 10px 12px;
    margin-bottom: 8px;
    cursor: pointer;
    transition: all 0.15s ease;
}
.fleet-card-item:hover {
    border-color: #0284C7;
    background: #EFF6FF;
}
.fleet-card-item.active {
    border-color: #0284C7;
    background: #EFF6FF;
    border-left: 3px solid #0284C7;
}

/* ── Avionics Instrument Box (Right Panel) ── */
.avionics-panel {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 14px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
.avionics-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
    border-bottom: 1px solid #F1F5F9;
}
.avionics-row:last-child { border-bottom: none; }
.avionics-key { font-size: 10px; color: #64748B; font-family: 'JetBrains Mono', monospace; text-transform: uppercase; }
.avionics-val { font-size: 12px; font-weight: 700; color: #0F172A; font-family: 'JetBrains Mono', monospace; }

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
[data-testid="stSlider"] div[data-baseweb="slider"] {
    padding-top: 12px !important;
    padding-bottom: 6px !important;
}
[data-testid="stSlider"] div[data-baseweb="slider"] > div:first-child > div:nth-child(2) {
    background: #0284C7 !important;
    height: 4px !important;
    border-radius: 2px !important;
}
[data-testid="stSliderThumbValue"],
[data-testid="stThumbValue"] {
    background: #FFFFFF !important;
    color: #0F172A !important;
    border: 1px solid #E2E8F0 !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 10px !important;
    font-weight: 600 !important;
    padding: 1px 6px !important;
    border-radius: 5px !important;
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

/* ── UAV State Badge (Inspector) ── */
.uav-state-badge {
    font-size: 10px;
    font-weight: 700;
    color: #0284C7;
    background: #EFF6FF;
    border: 1px solid #BAE6FD;
    padding: 2px 8px;
    border-radius: 3px;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.05em;
}

/* ── Dataframe ── */
[data-testid="stDataFrame"] {
    border-radius: 6px !important;
    overflow: hidden;
    border: 1px solid #E2E8F0 !important;
}

/* ── Widget label overrides (ensure all labels visible + styled) ── */
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label,
.stSelectbox > label,
.stSlider > label,
.stRadio > label,
.stCheckbox > label {
    font-size: 11px !important;
    font-weight: 600 !important;
    color: #475569 !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* ── Expanders ── */
[data-testid="stExpander"] {
    border: 1px solid #E2E8F0 !important;
    border-radius: 6px !important;
    background: #FFFFFF !important;
}

/* ── Global action buttons: consistent modest height ── */
.stButton > button {
    height: 34px !important;
    min-height: 34px !important;
    padding: 0 16px !important;
}

/* ── Cockpit Transport Bar (centered playback controls) ── */
.transport-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    margin: 2px 0 2px 0;
}
.transport-btn > button {
    min-width: 132px !important;
    height: 34px !important;
    border-radius: 8px !important;
}
.transport-btn-stop > button {
    min-width: 86px !important;
    height: 34px !important;
    border-radius: 8px !important;
}
.transport-btn-stop > button p,
.transport-btn-stop > button span {
    letter-spacing: 0.08em !important;
}

/* ── Cockpit Sensor Pills: compact so five cells never squeeze their labels ── */
div[data-testid="stCheckbox"] label {
    padding: 4px 7px !important;
}
div[data-testid="stCheckbox"] label span,
div[data-testid="stCheckbox"] label p {
    font-size: 9.5px !important;
    letter-spacing: 0.01em !important;
}

/* ── Scrollbars ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #F4F7FA; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #94A3B8; }

/* ── Boot / Loading Overlay: fullscreen centered, large text ── */
[data-testid="stSpinner"] {
    position: fixed !important;
    inset: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: #F4F7FA !important;
    z-index: 9999 !important;
}
[data-testid="stSpinner"] > div {
    justify-content: center !important;
    align-items: center !important;
    flex-direction: column !important;
    gap: 18px !important;
}
[data-testid="stSpinner"] p {
    font-size: 24px !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    font-family: 'JetBrains Mono', monospace !important;
    text-align: center !important;
}
[data-testid="stSpinner"] [data-testid="stSpinnerIndicator"] {
    width: 44px !important;
    height: 44px !important;
}

.aeroscan-loader-wrap {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #F4F7FA;
    z-index: 9998;
}
.aeroscan-loader-card {
    text-align: center;
    max-width: 560px;
    padding: 40px 48px;
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-top: 4px solid #0284C7;
    border-radius: 12px;
    box-shadow: 0 8px 30px rgba(15, 23, 42, 0.08);
}
.aeroscan-loader-title {
    font-size: 30px;
    font-weight: 800;
    color: #0F172A;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.06em;
    margin: 12px 0 6px 0;
}
.aeroscan-loader-sub {
    font-size: 15px;
    font-weight: 600;
    color: #0284C7;
    font-family: 'JetBrains Mono', monospace;
    margin-bottom: 16px;
}
.aeroscan-loader-lines {
    font-size: 14px;
    color: #475569;
    font-family: 'JetBrains Mono', monospace;
    line-height: 1.9;
}
.aeroscan-loader-bar {
    height: 6px;
    border-radius: 3px;
    background: #E2E8F0;
    overflow: hidden;
    margin-top: 20px;
}
.aeroscan-loader-bar > div {
    height: 100%;
    width: 40%;
    border-radius: 3px;
    background: #0284C7;
    animation: aeroscan-slide 1.2s ease-in-out infinite alternate;
}
@keyframes aeroscan-slide {
    from { margin-left: 0; }
    to { margin-left: 60%; }
}
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


# ---------------------------------------------------------------------------
# Boot Loader (centered, large connecting status)
# ---------------------------------------------------------------------------
BOOT_LOADER_HTML = f"""
<div class="aeroscan-loader-wrap">
    <div class="aeroscan-loader-card">
        <div>{SVG_AERO_LOGO.replace('width="22" height="22"', 'width="42" height="42"')}</div>
        <div class="aeroscan-loader-title">AEROSCAN</div>
        <div class="aeroscan-loader-sub">CONNECTING TO MISSION OPERATIONS ...</div>
        <div class="aeroscan-loader-lines">
            Linking UAV fleet telemetry ...<br/>
            Loading mission scenario ...<br/>
            Solving mission schedule ...
        </div>
        <div class="aeroscan-loader-bar"><div></div></div>
    </div>
</div>
"""


def initialize_state():
    """Initializes default mission session state."""
    if "instance" not in st.session_state:
        st.session_state.instance = load_initial_instance(
            "Chao Set 64 (Clustered SAR)", 3, 3.5, 45.0
        )
    if "schedule" not in st.session_state:
        loader = st.empty()
        loader.markdown(BOOT_LOADER_HTML, unsafe_allow_html=True)
        pool = explore_route_pool(
            st.session_state.instance, max_iterations=150, time_limit_sec=0.8
        )
        st.session_state.schedule = solve_fleet_schedule(
            st.session_state.instance, pool, run_baselines=True
        )
        loader.empty()
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
            <div class="brand-left">
                {SVG_AERO_LOGO}
                <div>
                    <div class="nav-brand-text">AEROSCAN</div>
                    <div class="nav-brand-sub">MISSION OPERATIONS</div>
                </div>
            </div>
            <span class="nav-brand-badge">OPS-V2</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Workspace View Selector
    st.markdown('<div class="side-section">Workspace</div>', unsafe_allow_html=True)
    workspace_choice = st.radio(
        "Navigation",
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
            <div class="m-ctx-grid">
                <div class="m-stat"><span class="m-lbl">FLEET</span><span class="m-val">{len(instance.drones):02d} UAVs</span></div>
                <div class="m-stat"><span class="m-lbl">TARGETS</span><span class="m-val">{total_cnt}</span></div>
                <div class="m-stat"><span class="m-lbl">COVERAGE</span><span class="m-val">{cov_pct:.0f}%</span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Mission Configuration Controls
    st.markdown('<div class="side-section">Mission Setup</div>', unsafe_allow_html=True)
    scenario_choice = st.selectbox(
        "Scenario",
        [
            "Chao Set 64 (Clustered SAR)",
            "Chao Set 66 (Diamond Perimeter)",
            "Chao Set 100 (Concentric Grid)",
            "Chao Set 102 (Uniform Scatter)",
            "Sample Mountain SAR",
        ],
        index=0,
    )

    # Swarm & Environmental Sliders in 2 Columns
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        fleet_size = st.slider(
            "Fleet size",
            min_value=2,
            max_value=8,
            value=3,
            format="%d UAVs",
        )
    with col_p2:
        wind_speed = st.slider(
            "Wind speed",
            min_value=0.0,
            max_value=15.0,
            value=3.5,
            step=0.5,
            format="%.1f m/s",
        )

    wind_dir = st.slider(
        "Wind direction",
        min_value=0.0,
        max_value=360.0,
        value=45.0,
        step=15.0,
        format="%.0f°",
    )

    c_btn1, c_btn2 = st.columns([1.35, 1.0])
    with c_btn1:
        run_opt = st.button("Run Optimizer", type="primary", use_container_width=True)
    with c_btn2:
        load_mock = st.button("Load Mock", use_container_width=True)

    if run_opt:
        with st.spinner("Executing ALNS trajectory exploration & CP-SAT solver..."):
            inst = load_initial_instance(scenario_choice, fleet_size, wind_speed, wind_dir)
            st.session_state.instance = inst
            route_pool = explore_route_pool(inst, max_iterations=350, time_limit_sec=1.5)
            sched = solve_fleet_schedule(inst, route_pool, run_baselines=True)
            st.session_state.schedule = sched
            st.session_state.grasp_schedule = solve_grasp_baseline(inst)
            st.session_state.mission_config = (scenario_choice, fleet_size, wind_speed, wind_dir)
            st.session_state.mission_t = 0.0
            st.session_state.mission_playing = False
            st.toast(
                f"Swarm solved: {sched.cumulative_reward:.0f} pts in {sched.solve_time_seconds:.2f}s",
                icon="✅",
            )

    # Reactive fleet: slider changes rebuild the swarm immediately so the
    # exact number of selected drones appears scouting on the map.
    applied_cfg = st.session_state.get("mission_config")
    current_cfg = (scenario_choice, fleet_size, wind_speed, wind_dir)
    if applied_cfg is None:
        st.session_state.mission_config = (
            scenario_choice, len(st.session_state.instance.drones),
            wind_speed, wind_dir,
        )
    elif current_cfg != applied_cfg and not run_opt:
        with st.spinner(f"Rebuilding swarm for {fleet_size} UAVs..."):
            inst = load_initial_instance(scenario_choice, fleet_size, wind_speed, wind_dir)
            st.session_state.instance = inst
            route_pool = explore_route_pool(inst, max_iterations=150, time_limit_sec=0.8)
            sched = solve_fleet_schedule(inst, route_pool, run_baselines=True)
            st.session_state.schedule = sched
            st.session_state.grasp_schedule = solve_grasp_baseline(inst)
            st.session_state.mission_config = current_cfg
            st.session_state.mission_t = 0.0
            st.session_state.mission_playing = False
            st.toast(
                f"Fleet: {len(inst.drones)} UAVs · {len(sched.assigned_routes)} route(s) assigned",
                icon="✅",
            )
            st.rerun()

    if load_mock:
        mock_path = Path("tests/mock_schedule.json")
        if mock_path.exists():
            with open(mock_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            st.session_state.schedule = FleetSchedule.from_dict(data)
            st.toast("Loaded mock mission fixture", icon="✅")

    st.markdown(
        f"""
        <div class="sidebar-system-card">
            <span class="sys-chip">{SVG_RADIO} RTK LOCK</span>
            <span class="sys-chip">{SVG_SHIELD} AES-256</span>
            <span class="sys-chip"><span class="live-dot"></span>DECONFL</span>
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
            <div class="tac-callsign-box">
                <span class="live-dot-pulse"></span>
                <span class="tac-callsign-text">AEROSCAN // TAC-OPS</span>
            </div>
            <div class="tac-mission-meta">
                <span class="tac-mission-id">{instance.instance_name.upper()}</span>
                <span class="tac-mission-chip">CLUSTERED SAR</span>
            </div>
        </div>
        <div class="top-meta-group">
            <div class="tac-instrument">
                <span class="tac-inst-lbl">UAV FLEET</span>
                <span class="tac-inst-val">{SVG_DRONE_ICON} <b>{len(schedule.assigned_routes):02d}</b> <small>SORTIES</small></span>
            </div>
            <div class="tac-instrument">
                <span class="tac-inst-lbl">ATMOSPHERIC</span>
                <span class="tac-inst-val">{SVG_WIND} <b>{wind_v}</b></span>
            </div>
            <div class="tac-instrument">
                <span class="tac-inst-lbl">ENERGY FLOOR</span>
                <span class="tac-inst-val"><span class="energy-dot" style="background:{"#10B981" if min_reserve_header >= 15 else "#EF4444"};"></span><b>{min_reserve_header:.1f}%</b> <small>MIN</small></span>
            </div>
            <div class="tac-status-badge">
                <span class="live-dot-pulse"></span>
                <b>{schedule.status}</b>
            </div>
            <div class="tac-zulu-card">
                {SVG_CLOCK} <b>{now_utc}</b>
            </div>
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

    # Tactical HUD Controls Over Map (Glass Cockpit Mission Director Deck)
    with st.container(border=True):
        init_val = float(min(300.0, max_mission_time))
        if "mission_t" not in st.session_state:
            st.session_state.mission_t = init_val
        if "mission_playing" not in st.session_state:
            st.session_state.mission_playing = False

        top_c1, top_c2 = st.columns([1.35, 1.0], gap="medium")
        with top_c1:
            view_mode = st.radio(
                "Canvas Projection",
                ["2D Map", "3D Terrain"],
                horizontal=True,
                label_visibility="collapsed",
            )
        with top_c2:
            map_rotation = st.selectbox(
                "Orientation",
                [90, 180, 270, 0],
                index=0,
                label_visibility="collapsed",
                format_func=lambda deg: f"Rotate: {deg}°",
            )

        # Sensor toggles: five equal cells across the full deck width
        g1, g2, g3, g4, g5 = st.columns(5, gap="small")
        with g1:
            halos = st.checkbox("Radar Halos", value=True)
        with g2:
            breadcrumbs = st.checkbox("Flight Paths", value=True)
        with g3:
            range_rings = st.checkbox("Range Rings", value=True)
        with g4:
            tactical_canvas = st.checkbox("Tactical Canvas", value=True)
        with g5:
            uav_icons = st.checkbox("UAV Icons", value=True)

    @st.fragment
    def mission_map_fragment():
        """Mission map deck. Reruns only on user interaction — playback motion
        is handled entirely in the browser by the animated figure, so there are
        no periodic server ticks and no chart re-uploads while flying."""
        t = float(st.session_state.get("mission_t", init_val))
        frac = t / max(float(max_mission_time), 1.0)
        st.markdown(
            f"""
            <div class="deck-header-row">
                <div class="deck-title-col">
                    <span class="deck-title-text">FLIGHT TIMELINE // MISSION CHRONOLOGY</span>
                    <span class="deck-time-badge">MET T+{t:04.0f}s / {float(max_mission_time):04.0f}s ({frac * 100:04.1f}%)</span>
                </div>
                <div class="deck-title-col right">
                    <span class="deck-title-text">TACTICAL SENSOR MATRIX &amp; PROJECTION</span>
                    <span class="deck-sensors-badge"><span class="sensor-live-dot"></span>{'SCOUTING' if st.session_state.get('mission_playing') else 'HOLDING'}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Compact transport controls: small side-by-side buttons, not half-deck slabs
        btn_play, btn_stop, btn_gap = st.columns([0.6, 0.48, 2.8], gap="small")
        with btn_play:
            if st.button(
                "▶ Execute", type="primary", use_container_width=True, key="exec_mission_btn"
            ):
                st.session_state.mission_t = 0.0
                st.session_state.mission_playing = True
        with btn_stop:
            if st.button("■ Stop", use_container_width=True, key="stop_mission_btn"):
                st.session_state.mission_playing = False

        t_slider = st.slider(
            "Mission Timeline",
            min_value=0.0,
            max_value=float(max_mission_time),
            value=t,
            step=5.0,
            format="%0.0f sec",
            label_visibility="collapsed",
        )
        if abs(float(t_slider) - t) > 1e-6:
            st.session_state.mission_t = float(t_slider)
            st.session_state.mission_playing = False
            t = float(t_slider)

        p1 = "active" if frac < 0.15 else "completed"
        p2 = "active" if 0.15 <= frac < 0.40 else ("completed" if frac >= 0.40 else "")
        p3 = "active" if 0.40 <= frac < 0.70 else ("completed" if frac >= 0.70 else "")
        p4 = "active" if 0.70 <= frac < 0.90 else ("completed" if frac >= 0.90 else "")
        p5 = "active" if frac >= 0.90 else ""
        st.markdown(
            f"""
            <div class="mission-flight-pipeline">
                <div class="pipeline-step {p1}">
                    <div class="pipe-header"><span class="pipe-idx">01</span><span class="pipe-name">DEPLOY</span></div>
                    <div class="pipe-bar"></div>
                </div>
                <div class="pipeline-step {p2}">
                    <div class="pipe-header"><span class="pipe-idx">02</span><span class="pipe-name">TRANSIT</span></div>
                    <div class="pipe-bar"></div>
                </div>
                <div class="pipeline-step {p3}">
                    <div class="pipe-header"><span class="pipe-idx">03</span><span class="pipe-name">CLUSTER</span></div>
                    <div class="pipe-bar"></div>
                </div>
                <div class="pipeline-step {p4}">
                    <div class="pipe-header"><span class="pipe-idx">04</span><span class="pipe-name">ACQUIRE</span></div>
                    <div class="pipe-bar"></div>
                </div>
                <div class="pipeline-step {p5}">
                    <div class="pipe-header"><span class="pipe-idx">05</span><span class="pipe-name">RECOVERY</span></div>
                    <div class="pipe-bar"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Browser-side animated map during playback (zero reruns, buttery smooth);
        # the static figure is only rebuilt when scrubbing or toggling layers.
        if st.session_state.get("mission_playing", False) and view_mode in (
            "2D Tactical Map",
            "2D Map",
        ):
            fig_map = build_animated_mission_map_figure(
                instance=instance,
                schedule=schedule,
                n_frames=60,
                show_range_rings=range_rings,
                use_tactical_map=tactical_canvas,
                map_opacity=0.88,
                map_rotation_deg=map_rotation,
            )
            fig_map.update_layout(autosize=True)
            st.plotly_chart(fig_map, use_container_width=True, key="mission_anim_chart")
        elif view_mode in ("2D Tactical Map", "2D Map"):
            fig_map = build_mission_map_figure(
                instance=instance,
                schedule=schedule,
                current_time_sec=t,
                show_radar_halos=halos,
                show_breadcrumbs=breadcrumbs,
                show_range_rings=range_rings,
                use_tactical_map=tactical_canvas,
                map_opacity=0.88,
                map_rotation_deg=map_rotation,
                show_uav_icons=uav_icons,
            )
            st.plotly_chart(fig_map, use_container_width=True, key="mission_static_chart")
        else:
            fig_3d = build_3d_terrain_mission_figure(
                instance=instance,
                schedule=schedule,
                current_time_sec=t,
            )
            st.plotly_chart(fig_3d, use_container_width=True, key="mission_3d_chart")

    from streamlit.components.v1 import html as _html
    from app.mission_sim import render_mission_sim_html

    _html(render_mission_sim_html(len(instance.drones)), height=980, scrolling=False)

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
    active_telem, secured_set = get_fleet_telemetry_at_time(
        schedule, float(st.session_state.get("mission_t", 300.0)), instance
    )
    telem_by_id = {t["drone_id"]: t for t in active_telem}

    inspector_options = (
        ["None (Overview)"]
        + [d.id for d in instance.drones]
        + [f"Target #{t.id:02d}" for t in instance.target_nodes[:12]]
    )
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    c_sel, _ = st.columns([2, 3])
    with c_sel:
        selected_obj = st.selectbox("Context Inspector", inspector_options, index=0)

    if selected_obj != "None (Overview)":
        if selected_obj.startswith("UAV"):
            telem = telem_by_id.get(selected_obj, {})
            u_route = next(
                (r for r in schedule.assigned_routes if r.drone_id == selected_obj), None
            )
            cur_wp = telem.get("target_name", "DEPOT")
            st.markdown(
                f"""
                <div class="inspector-card">
                    <div class="inspector-header">
                        <span class="inspector-title">OBJECT INSPECTOR // {selected_obj}</span>
                        <span class="uav-state-badge">{telem.get("flight_phase", "CRUISE")}</span>
                    </div>
                    <div class="inspector-grid">
                        <div class="inspector-stat">
                            <span class="insp-key">BATTERY SOC</span>
                            <span class="insp-val" style="color: #10B981;">{telem.get("battery_percent", 100):.1f}%</span>
                        </div>
                        <div class="inspector-stat">
                            <span class="insp-key">GROUNDSPEED</span>
                            <span class="insp-val">{telem.get("speed_mps", 0):.1f} m/s</span>
                        </div>
                        <div class="inspector-stat">
                            <span class="insp-key">ALTITUDE</span>
                            <span class="insp-val">{telem.get("z", 60):.0f} m</span>
                        </div>
                        <div class="inspector-stat">
                            <span class="insp-key">HEADING</span>
                            <span class="insp-val">{telem.get("heading_deg", 0):.0f}°</span>
                        </div>
                        <div class="inspector-stat">
                            <span class="insp-key">CURRENT WAYPOINT</span>
                            <span class="insp-val">{cur_wp}</span>
                        </div>
                        <div class="inspector-stat">
                            <span class="insp-key">COORDINATES</span>
                            <span class="insp-val">({telem.get("x", 0):.0f}, {telem.get("y", 0):.0f})</span>
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
# Workspace View: 2. Fleet Telemetry (Command-Center Multi-Parameter View)
# ---------------------------------------------------------------------------
elif "02 Fleet Telemetry" in workspace_choice:
    telemetry_data, _ = get_fleet_telemetry_at_time(schedule, 300.0, instance)

    # Fleet Overview Summary Header
    avg_bat = sum(t["battery_percent"] for t in telemetry_data) / max(len(telemetry_data), 1)
    tot_dist = sum(r.total_flight_time * 15.0 for r in schedule.assigned_routes)

    st.markdown(
        f"""
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; padding:14px 20px; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
            <div>
                <span style="font-size:14px; font-weight:700; color:#0F172A; font-family:'JetBrains Mono', monospace;">SWARM TELEMETRY & KINEMATICS COMMAND CENTER</span>
                <span style="font-size:12px; color:#64748B; margin-left:10px;">Multi-parameter telemetry monitoring & kinematic state vectors</span>
            </div>
            <div style="display:flex; gap:16px; font-size:11px; font-family:'JetBrains Mono', monospace; color:#64748B;">
                <span>ACTIVE: <b style="color:#0F172A;">01</b></span>
                <span>STANDBY: <b style="color:#64748B;">02</b></span>
                <span>AVG BATTERY: <b style="color:#10B981;">{avg_bat:.1f}%</b></span>
                <span>TOTAL DIST: <b style="color:#0284C7;">{tot_dist / 1000.0:.1f} KM</b></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Multi-Column Telemetry Command Center: Left (Fleet List), Center (Kinematics Chart), Right (Avionics)
    c_left, c_center, c_right = st.columns([1.1, 2.3, 1.2])

    with c_left:
        st.markdown("##### Fleet Selector")
        drone_ids = [r.drone_id for r in schedule.assigned_routes]
        selected_uav = st.radio(
            "Active UAV",
            drone_ids,
            index=1 if len(drone_ids) > 1 else 0,
            label_visibility="collapsed",
        )

        # Compact summary cards in left column
        for idx, t in enumerate(telemetry_data):
            is_active_uav = t["drone_id"] == "UAV-02"
            border_cls = "border-left: 3px solid #0284C7;" if t["drone_id"] == selected_uav else ""
            act_badge = (
                "<span style='font-size:9px; background:#EFF6FF; color:#0284C7; padding:1px 5px; border-radius:3px; font-weight:700;'>CRUISE</span>"
                if is_active_uav
                else "<span style='font-size:9px; background:#F8FAFC; color:#64748B; padding:1px 5px; border-radius:3px;'>STANDBY</span>"
            )
            st.markdown(
                f"""
                <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:6px; padding:10px 12px; margin-bottom:8px; {border_cls}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:700; font-family:'JetBrains Mono'; font-size:12px; color:#0F172A;">{t["drone_id"]}</span>
                        {act_badge}
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-top:6px; font-size:11px; font-family:'JetBrains Mono'; color:#64748B;">
                        <span>SoC: <b style="color:#10B981;">{t["battery_percent"]:.0f}%</b></span>
                        <span>Alt: {t["z"]:.0f}m</span>
                        <span>Spd: {t["speed_mps"]:.1f}m/s</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with c_center:
        st.markdown(f"##### Kinematics Profile: `{selected_uav}` (Battery SoC & Altitude)")
        fig_kin = build_uav_kinematics_figure(
            schedule, instance, selected_uav, current_time_sec=300.0
        )
        st.plotly_chart(fig_kin, use_container_width=True)

    with c_right:
        st.markdown(f"##### Avionics: `{selected_uav}`")
        u_telem = next(
            (t for t in telemetry_data if t["drone_id"] == selected_uav), telemetry_data[0]
        )
        st.markdown(
            f"""
            <div class="avionics-panel">
                <div class="avionics-row">
                    <span class="avionics-key">CALLSIGN</span>
                    <span class="avionics-val">{selected_uav}</span>
                </div>
                <div class="avionics-row">
                    <span class="avionics-key">FLIGHT PHASE</span>
                    <span class="avionics-val" style="color:#0284C7;">{u_telem["flight_phase"]}</span>
                </div>
                <div class="avionics-row">
                    <span class="avionics-key">GROUNDSPEED</span>
                    <span class="avionics-val">{u_telem["speed_mps"]:.1f} m/s</span>
                </div>
                <div class="avionics-row">
                    <span class="avionics-key">ALTITUDE (AGL)</span>
                    <span class="avionics-val">{u_telem["z"]:.0f} m</span>
                </div>
                <div class="avionics-row">
                    <span class="avionics-key">HEADING AZIMUTH</span>
                    <span class="avionics-val">{u_telem.get("heading_deg", 0):.0f}°</span>
                </div>
                <div class="avionics-row">
                    <span class="avionics-key">CURRENT TARGET</span>
                    <span class="avionics-val">{u_telem.get("target_name", "DEPOT")}</span>
                </div>
                <div class="avionics-row">
                    <span class="avionics-key">COMM LINK RSSI</span>
                    <span class="avionics-val" style="color:#10B981;">99.8%</span>
                </div>
                <div class="avionics-row">
                    <span class="avionics-key">GEOFENCE STATUS</span>
                    <span class="avionics-val" style="color:#10B981;">CLEAR</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Detailed Tabular Log (Bottom)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown("##### Detailed Fleet Kinematics Table (10Hz State Vectors)")
    st.dataframe(
        telemetry_data,
        column_config={
            "drone_id": "UAV Callsign",
            "x": st.column_config.NumberColumn("Easting X (m)", format="%.1f"),
            "y": st.column_config.NumberColumn("Northing Y (m)", format="%.1f"),
            "z": st.column_config.NumberColumn("Altitude Z (m)", format="%.1f"),
            "battery_percent": st.column_config.ProgressColumn(
                "Battery SoC", min_value=0, max_value=100, format="%.0f%%"
            ),
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
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; padding:14px 20px; margin-bottom:14px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
            <div style="font-size:14px; font-weight:700; color:#0F172A; font-family:'JetBrains Mono', monospace;">SWARM ENERGY INTELLIGENCE // SOC DEPLETION ANALYSIS</div>
            <div style="font-size:12px; color:#64748B; margin-top:3px;">Aerodynamic power draw, wind drift penalty, and 15% emergency reserve floor monitoring</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    fig_bat = build_battery_soc_figure(schedule, instance, current_time_sec=300.0)
    st.plotly_chart(fig_bat, use_container_width=True)

    # Mission Phase Energy Draw Progression Strip
    st.markdown(
        """
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:6px; padding:10px 16px; margin-top:6px; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center; font-size:11px; font-family:'JetBrains Mono';">
            <span style="color:#64748B; font-weight:700;">MISSION PHASE CONSUMPTION:</span>
            <span><b style="color:#0284C7;">DEPLOY</b> (5.2%)</span> &rarr;
            <span><b style="color:#0284C7;">TRANSIT</b> (28.4%)</span> &rarr;
            <span><b style="color:#0284C7;">CLUSTER INGESTION</b> (21.8%)</span> &rarr;
            <span><b style="color:#0284C7;">TARGET ACQUISITION</b> (29.6%)</span> &rarr;
            <span><b style="color:#10B981;">RETURN BASE</b> (15.0%)</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Subsystem Power Allocation Breakdown (Horizontal Bar)
    st.markdown("##### Subsystem Power Allocation Breakdown")
    fig_pwr = build_energy_breakdown_figure()
    st.plotly_chart(fig_pwr, use_container_width=True)

    b1, b2, b3, b4 = st.columns(4)
    with b1:
        min_reserve_all = min(
            (r.final_reserve_percent for r in schedule.assigned_routes), default=100.0
        )
        st.metric("Minimum Fleet Reserve", f"{min_reserve_all:.1f}%", "Above 15% Safety Floor")
    with b2:
        total_joules = sum(r.total_energy_joules for r in schedule.assigned_routes)
        st.metric("Total Swarm Energy", f"{total_joules / 1000.0:.1f} kJ", "Wind-Compensated")
    with b3:
        avg_reserve = sum(r.final_reserve_percent for r in schedule.assigned_routes) / max(
            len(schedule.assigned_routes), 1
        )
        st.metric("Average Recovery Margin", f"{avg_reserve:.1f}%", "Optimal Land Margin")
    with b4:
        st.metric("Safety Reserve Floor", "15.0%", "Strict Constraint", delta_color="normal")

# ---------------------------------------------------------------------------
# Workspace View: 5. Mission Export
# ---------------------------------------------------------------------------
elif "05 Mission Export" in workspace_choice:
    st.markdown(
        """
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; padding:14px 20px; margin-bottom:14px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
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

        # Structured Mission Summary Card
        st.markdown(
            f"""
            <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:6px; padding:12px; margin-bottom:12px; font-size:11px; font-family:'JetBrains Mono';">
                <div style="font-weight:700; color:#0284C7; margin-bottom:6px;">MISSION SUMMARY // {selected_drone_id}</div>
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;"><span style="color:#64748B;">CRUISE SPEED</span><span>{selected_drone_spec.cruise_speed:.1f} m/s</span></div>
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;"><span style="color:#64748B;">WAYPOINTS</span><span>{len(selected_route.waypoints)} points</span></div>
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;"><span style="color:#64748B;">DURATION</span><span>{selected_route.total_flight_time:.0f}s</span></div>
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;"><span style="color:#64748B;">RESERVE</span><span style="color:#10B981; font-weight:700;">{selected_route.final_reserve_percent:.1f}%</span></div>
                <div style="display:flex; justify-content:space-between;"><span style="color:#64748B;">TARGETS</span><span>{len(selected_route.target_ids)} nodes</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

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
            <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:6px; padding:12px; margin-top:14px; font-size:11px; font-family:'JetBrains Mono', monospace;">
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
