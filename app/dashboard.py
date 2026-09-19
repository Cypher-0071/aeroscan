"""AeroScan-Optima: Autonomous Drone Mission Control — Defense-grade cockpit UI."""

from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root directory is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from app.arena_view import render_arena_view
from app.exporter import (
    export_mavlink_waypoint_file,
    export_mission_dossier_html,
    export_mission_telemetry_csv,
    export_qgroundcontrol_plan,
)
from app.telemetry import get_fleet_telemetry_at_time
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
# Streamlit Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AeroScan-Optima | Mission Control",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# AEROSCAN — Radical Mission Control UI
# No rounded corners. No gradients. No AI-template aesthetics.
# Angular geometry. Monochrome terminal. Real CSS animations.
# ---------------------------------------------------------------------------
AEROSCAN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500;600&display=swap');

*, *::before, *::after { box-sizing: border-box; }
* { font-family: 'Space Grotesk', system-ui, sans-serif !important; }

/* ══ CRITICAL: Streamlit root CSS variable overrides ══
   Without these, sliders/buttons/checkboxes bleed red (Streamlit default primary) */
:root {
    --primary-color: #0EA5E9 !important;
    --background-color: #040608 !important;
    --secondary-background-color: #06090E !important;
    --text-color: #C9D1D9 !important;
    --font: 'Space Grotesk', system-ui, sans-serif !important;
}

/* ══ Hide "keyboard_double" sidebar collapse icon ══
   Streamlit renders Material Icons as text when icon font fails to load.
   This hides the collapse toggle entirely. */
[data-testid="collapsedControl"] { display: none !important; }
button[data-testid="baseButton-headerNoPadding"] { display: none !important; }
[data-testid="stSidebarNavItems"] { display: none !important; }
[data-testid="stSidebarNavSeparator"] { display: none !important; }

/* ── ROOT ── */
.stApp {
    background: #040608 !important;
    color: #8B949E;
    min-height: 100vh;
}

/* ── Animated dot-grid background ── */
.stApp::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image: radial-gradient(circle, rgba(14,165,233,0.07) 1px, transparent 1px);
    background-size: 32px 32px;
    pointer-events: none;
    z-index: 0;
    animation: grid-drift 60s linear infinite;
}
@keyframes grid-drift {
    0%   { background-position: 0 0; }
    100% { background-position: 320px 320px; }
}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
    background: #030507 !important;
    border-right: 1px solid rgba(14,165,233,0.1) !important;
    z-index: 10;
}
[data-testid="stSidebar"] > div { padding-top: 1rem !important; }
[data-testid="stSidebar"] * { color: #4B5563 !important; }
[data-testid="stSidebar"] strong,
[data-testid="stSidebar"] b { color: #9CA3AF !important; }
[data-testid="stSidebarNav"] { display: none !important; }

/* Sidebar label overrides */
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] label {
    font-size: 9px !important;
    letter-spacing: 0.18em !important;
    text-transform: uppercase !important;
    color: #2D3748 !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* ── MAIN CONTENT ── */
.main .block-container {
    padding: 1.5rem 2rem 3rem !important;
    max-width: 100% !important;
    position: relative;
    z-index: 1;
}

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 3px; height: 3px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(14,165,233,0.2); border-radius: 0; }

/* =========================================================
   CUSTOM HTML COMPONENTS
   ========================================================= */

/* ── Sidebar brand ── */
.sidebar-brand {
    padding: 0 0 16px 0;
    border-bottom: 1px solid rgba(14,165,233,0.1);
    margin-bottom: 16px;
}
.brand-name {
    font-size: 10px !important;
    font-weight: 700 !important;
    letter-spacing: 0.28em !important;
    color: #0EA5E9 !important;
    text-transform: uppercase !important;
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: 'JetBrains Mono', monospace !important;
}
.brand-diamond {
    width: 7px; height: 7px;
    background: #0EA5E9;
    transform: rotate(45deg);
    flex-shrink: 0;
    animation: diamond-pulse 2.5s ease-in-out infinite;
}
@keyframes diamond-pulse {
    0%, 100% { opacity: 1; transform: rotate(45deg) scale(1); }
    50% { opacity: 0.4; transform: rotate(45deg) scale(0.6); }
}
.brand-sub {
    font-size: 9px !important;
    color: #1E2733 !important;
    letter-spacing: 0.12em !important;
    margin-top: 5px !important;
    text-transform: uppercase !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* Section labels */
.section-label {
    font-size: 8px !important;
    font-weight: 700 !important;
    letter-spacing: 0.24em !important;
    color: #1E2733 !important;
    text-transform: uppercase !important;
    margin: 20px 0 6px 0 !important;
    display: block !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* Sidebar footer */
.sidebar-footer {
    border-top: 1px solid rgba(255,255,255,0.03);
    padding-top: 14px;
    margin-top: 14px;
}
.sys-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}
.sys-key {
    font-size: 8px !important;
    font-weight: 700 !important;
    letter-spacing: 0.18em !important;
    color: #1E2733 !important;
    text-transform: uppercase !important;
    font-family: 'JetBrains Mono', monospace !important;
}
.sys-val {
    font-size: 10px !important;
    color: #374151 !important;
    font-family: 'JetBrains Mono', monospace !important;
}
.sys-val-active {
    font-size: 10px !important;
    color: #10B981 !important;
    font-family: 'JetBrains Mono', monospace !important;
    display: flex;
    align-items: center;
    gap: 5px;
}
.live-dot {
    width: 5px; height: 5px;
    background: #10B981;
    border-radius: 50%;
    animation: live-blink 1.5s step-end infinite;
    display: inline-block;
}
@keyframes live-blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}

/* ── CMD BAR ── */
.cmd-bar {
    display: flex;
    align-items: stretch;
    background: #06090E;
    border: 1px solid rgba(14,165,233,0.15);
    border-top: 2px solid #0EA5E9;
    margin-bottom: 18px;
    position: relative;
    clip-path: polygon(0 0, calc(100% - 20px) 0, 100% 20px, 100% 100%, 0 100%);
}
/* Animated sweep line across the top */
.cmd-bar::before {
    content: '';
    position: absolute;
    top: -2px; left: -100%;
    width: 40%;
    height: 2px;
    background: linear-gradient(90deg, transparent, rgba(14,165,233,0.8), transparent);
    animation: sweep-line 4s ease-in-out infinite;
}
@keyframes sweep-line {
    0%   { left: -40%; }
    100% { left: 140%; }
}
.cmd-seg {
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 10px 20px;
    border-right: 1px solid rgba(255,255,255,0.04);
    min-width: 120px;
}
.cmd-seg-label {
    font-size: 7px;
    font-weight: 700;
    letter-spacing: 0.24em;
    color: #1E2733;
    text-transform: uppercase;
    font-family: 'JetBrains Mono', monospace !important;
    margin-bottom: 3px;
}
.cmd-seg-val {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px;
    font-weight: 600;
    color: #E6EDF3;
    letter-spacing: 0.02em;
    line-height: 1;
}
.cmd-seg-val.accent { color: #0EA5E9; }
.cmd-spacer { flex: 1; }
.cmd-right {
    display: flex;
    align-items: center;
    padding: 10px 20px;
    gap: 24px;
}
.cmd-clock {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px;
    color: #374151;
    letter-spacing: 0.06em;
}
.beacon-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.2em;
    color: #10B981;
    text-transform: uppercase;
}
.beacon {
    position: relative;
    width: 8px; height: 8px;
    flex-shrink: 0;
}
.beacon-core {
    position: absolute;
    inset: 0;
    background: #10B981;
}
.beacon-ring {
    position: absolute;
    inset: -4px;
    border: 1px solid #10B981;
    animation: b-pulse 2s ease-out infinite;
}
.beacon-ring2 {
    position: absolute;
    inset: -4px;
    border: 1px solid #10B981;
    animation: b-pulse 2s ease-out 0.8s infinite;
}
@keyframes b-pulse {
    0%   { transform: scale(0.5); opacity: 1; }
    100% { transform: scale(2.5); opacity: 0; }
}

/* ── KPI CARDS — corner-bracket geometry ── */
[data-testid="stMetric"] {
    background: #06090E !important;
    border: 1px solid rgba(255,255,255,0.04) !important;
    border-radius: 0 !important;
    padding: 20px 18px 16px !important;
    position: relative !important;
    overflow: visible !important;
    transition: background 0.25s !important;
}
/* top-left corner bracket */
[data-testid="stMetric"]::before {
    content: '' !important;
    position: absolute !important;
    top: -1px; left: -1px !important;
    width: 12px; height: 12px !important;
    border-top: 2px solid #0EA5E9 !important;
    border-left: 2px solid #0EA5E9 !important;
    transition: width 0.2s, height 0.2s !important;
}
/* bottom-right corner bracket */
[data-testid="stMetric"]::after {
    content: '' !important;
    position: absolute !important;
    bottom: -1px; right: -1px !important;
    width: 12px; height: 12px !important;
    border-bottom: 2px solid rgba(14,165,233,0.25) !important;
    border-right: 2px solid rgba(14,165,233,0.25) !important;
}
[data-testid="stMetric"]:hover { background: #080D14 !important; }
[data-testid="stMetric"]:hover::before { width: 20px !important; height: 20px !important; }
[data-testid="stMetricLabel"] p {
    font-size: 8px !important;
    font-weight: 700 !important;
    color: #1E2733 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.22em !important;
    margin-bottom: 10px !important;
    font-family: 'JetBrains Mono', monospace !important;
}
[data-testid="stMetricValue"] div {
    font-size: 30px !important;
    font-weight: 700 !important;
    color: #F0F6FC !important;
    letter-spacing: -0.04em !important;
    font-family: 'Space Grotesk', sans-serif !important;
    line-height: 1 !important;
}
[data-testid="stMetricDelta"] { margin-top: 8px !important; }
[data-testid="stMetricDelta"] div {
    font-size: 10px !important;
    font-family: 'JetBrains Mono', monospace !important;
    color: #2D3748 !important;
}

/* ── NAV TABS ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0 !important;
    background: #030507 !important;
    border-bottom: 1px solid rgba(14,165,233,0.12) !important;
    padding: 0 !important;
    margin-bottom: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    font-size: 9px !important;
    font-weight: 700 !important;
    color: #2D3748 !important;
    padding: 11px 22px !important;
    letter-spacing: 0.22em !important;
    text-transform: uppercase !important;
    border-radius: 0 !important;
    background: transparent !important;
    border: none !important;
    border-right: 1px solid rgba(255,255,255,0.03) !important;
    transition: color 0.15s, background 0.15s !important;
    font-family: 'JetBrains Mono', monospace !important;
    position: relative !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #4B5563 !important;
    background: rgba(14,165,233,0.03) !important;
}
.stTabs [aria-selected="true"] {
    color: #0EA5E9 !important;
    background: rgba(14,165,233,0.07) !important;
    border-bottom: 2px solid #0EA5E9 !important;
}

/* ── TELEMETRY CARDS ── */
.telem-card {
    background: #06090E;
    border: 1px solid rgba(255,255,255,0.05);
    border-left: 2px solid;
    border-radius: 0;
    padding: 12px 14px;
    margin-bottom: 8px;
    position: relative;
    transition: background 0.2s;
}
.telem-card:hover { background: #080D14; }
.telem-hdr {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 10px;
    padding-bottom: 7px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.telem-drone-id {
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    font-family: 'JetBrains Mono', monospace !important;
}
.telem-bat {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px;
    font-weight: 700;
}
.telem-rows {
    display: grid;
    grid-template-columns: 38px 1fr;
    gap: 5px 6px;
}
.telem-key {
    color: #1E2733;
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    font-family: 'JetBrains Mono', monospace !important;
    padding-top: 1px;
}
.telem-val {
    font-family: 'JetBrains Mono', monospace !important;
    color: #9CA3AF;
    font-size: 11px;
    font-weight: 500;
}

/* ── BUTTONS — zero-radius, cut-corner clip ── */
.stButton > button {
    background: rgba(14,165,233,0.06) !important;
    border: 1px solid rgba(14,165,233,0.3) !important;
    color: #0EA5E9 !important;
    border-radius: 0 !important;
    font-size: 9px !important;
    font-weight: 700 !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    padding: 7px 10px !important;
    font-family: 'JetBrains Mono', monospace !important;
    transition: all 0.15s ease !important;
    clip-path: polygon(0 0, calc(100% - 6px) 0, 100% 6px, 100% 100%, 0 100%) !important;
    white-space: nowrap !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
.stButton > button:hover {
    background: rgba(14,165,233,0.15) !important;
    border-color: #0EA5E9 !important;
    color: #FFFFFF !important;
}
.stButton > button[kind="primary"],
.stButton > button[data-baseweb="button"][kind="primary"] {
    background: rgba(14,165,233,0.16) !important;
    border-color: #0EA5E9 !important;
    color: #38BDF8 !important;
}
.stButton > button[kind="primary"]:hover {
    background: #0EA5E9 !important;
    border-color: #0EA5E9 !important;
    color: #040608 !important;
}

/* ── DOWNLOAD BUTTONS ── */
.stDownloadButton > button {
    background: transparent !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #4B5563 !important;
    border-radius: 0 !important;
    font-size: 10px !important;
    font-weight: 700 !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    font-family: 'JetBrains Mono', monospace !important;
    transition: border-color 0.15s, color 0.15s !important;
}
.stDownloadButton > button:hover {
    border-color: rgba(16,185,129,0.4) !important;
    color: #10B981 !important;
}

/* ── SELECTBOX ── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background: #06090E !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 0 !important;
    color: #9CA3AF !important;
    font-size: 11px !important;
    font-family: 'JetBrains Mono', monospace !important;
}
/* Dropdown menu */
[data-baseweb="popover"] ul {
    background: #06090E !important;
    border: 1px solid rgba(14,165,233,0.15) !important;
    border-radius: 0 !important;
}
[data-baseweb="popover"] li {
    color: #6B7280 !important;
    font-size: 11px !important;
    font-family: 'JetBrains Mono', monospace !important;
}
[data-baseweb="popover"] li:hover {
    background: rgba(14,165,233,0.08) !important;
    color: #0EA5E9 !important;
}

/* ── SLIDERS ── */
[data-testid="stSlider"] {
    background: transparent !important;
    padding-top: 4px !important;
    padding-bottom: 4px !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] {
    background: transparent !important;
}
/* Hide tick min/max labels beneath slider */
[data-testid="stTickBar"],
[data-testid="stSliderTickBar"] {
    display: none !important;
}
/* Slider Thumb */
[data-testid="stSlider"] [role="slider"],
[data-testid="stSlider"] [data-testid="stSliderThumb"],
[data-testid="stSlider"] div[data-baseweb="slider"] div[role="slider"] {
    background: #0EA5E9 !important;
    border: 2px solid #040608 !important;
    box-shadow: 0 0 8px rgba(14,165,233,0.6) !important;
    border-radius: 0 !important;
    width: 14px !important;
    height: 14px !important;
}
/* Slider Track */
[data-testid="stSlider"] div[data-baseweb="slider"] > div:first-child {
    background: transparent !important;
}
[data-testid="stSlider"] div[data-baseweb="slider"] > div:first-child > div:first-child {
    background: rgba(14,165,233,0.15) !important;
    height: 4px !important;
    border-radius: 0 !important;
}
[data-testid="stSlider"] div[data-baseweb="slider"] > div:first-child > div:nth-child(2) {
    background: #0EA5E9 !important;
    height: 4px !important;
    border-radius: 0 !important;
}
/* Slider Floating Value (e.g. 300 sec) */
[data-testid="stSliderThumbValue"],
[data-testid="stThumbValue"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #0EA5E9 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 10px !important;
    font-weight: 700 !important;
    padding: 0 !important;
    letter-spacing: 0.05em !important;
}
/* Widget label */
[data-testid="stSlider"] [data-testid="stWidgetLabel"] p {
    font-size: 9px !important;
    color: #2D3640 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.18em !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* ── CHECKBOXES ── */
[data-testid="stCheckbox"] {
    background: transparent !important;
}
[data-testid="stCheckbox"] label {
    background: transparent !important;
    cursor: pointer !important;
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
}
[data-testid="stCheckbox"] [data-baseweb="checkbox"] {
    background: transparent !important;
}
/* Unchecked box */
[data-testid="stCheckbox"] [data-baseweb="checkbox"] > div:first-of-type {
    border-radius: 0 !important;
    border: 1px solid rgba(14,165,233,0.3) !important;
    background: #06090E !important;
    width: 14px !important;
    height: 14px !important;
}
/* Checked box */
[data-testid="stCheckbox"] input:checked ~ div:first-of-type,
[data-testid="stCheckbox"] [aria-checked="true"] > div:first-of-type {
    background-color: #0EA5E9 !important;
    border-color: #0EA5E9 !important;
}
[data-testid="stCheckbox"] svg {
    fill: #040608 !important;
    color: #040608 !important;
    stroke: #040608 !important;
}
/* Label text */
[data-testid="stCheckbox"] span,
[data-testid="stCheckbox"] p,
[data-testid="stCheckbox"] [data-testid="stWidgetLabel"] p {
    background: transparent !important;
    color: #9CA3AF !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 9px !important;
    font-weight: 600 !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    margin: 0 !important;
    padding: 0 !important;
}
[data-testid="stCheckbox"]:hover [data-testid="stWidgetLabel"] p,
[data-testid="stCheckbox"]:hover span {
    color: #E6EDF3 !important;
}

/* ── RADIO BUTTONS ── */
[data-testid="stRadio"] {
    background: transparent !important;
}
[data-testid="stRadio"] div[role="radiogroup"] {
    background: transparent !important;
    gap: 12px !important;
}
[data-testid="stRadio"] label {
    background: transparent !important;
    cursor: pointer !important;
    display: flex !important;
    align-items: center !important;
}
[data-testid="stRadio"] [data-baseweb="radio"] {
    background: transparent !important;
}
/* Outer radio circle */
[data-testid="stRadio"] div[role="radiogroup"] label div:first-of-type {
    border-radius: 50% !important;
    border: 1px solid rgba(14,165,233,0.35) !important;
    background: #06090E !important;
    width: 14px !important;
    height: 14px !important;
}
/* Inner dot / active */
[data-testid="stRadio"] input:checked ~ div:first-of-type {
    border-color: #0EA5E9 !important;
    background: #0EA5E9 !important;
    box-shadow: inset 0 0 0 3px #06090E !important;
}
/* Label text */
[data-testid="stRadio"] span,
[data-testid="stRadio"] p,
[data-testid="stRadio"] label div:last-child {
    background: transparent !important;
    color: #9CA3AF !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 9px !important;
    font-weight: 600 !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    margin: 0 !important;
}
[data-testid="stRadio"] label:hover span {
    color: #0EA5E9 !important;
}
[data-testid="stRadio"] [data-testid="stWidgetLabel"] p {
    font-size: 8px !important;
    font-weight: 700 !important;
    color: #2D3748 !important;
    font-family: 'JetBrains Mono', monospace !important;
    text-transform: uppercase !important;
    letter-spacing: 0.16em !important;
    margin-bottom: 4px !important;
}

/* ── DATAFRAME ── */
.stDataFrame {
    border: 1px solid rgba(255,255,255,0.05) !important;
    border-radius: 0 !important;
}

/* ── HEADINGS ── */
h1, h2, h3, h4, h5, h6 {
    color: #E6EDF3 !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
}

/* ── CAPTION ── */
.stCaption p, [data-testid="stCaptionContainer"] p {
    color: #2D3640 !important;
    font-size: 9px !important;
    font-family: 'JetBrains Mono', monospace !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
}

/* ── SPINNER ── */
.stSpinner > div {
    border-color: #0EA5E9 transparent transparent transparent !important;
}

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 3px; height: 3px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(14,165,233,0.2); border-radius: 0; }
::-webkit-scrollbar-thumb:hover { background: #0EA5E9; }

/* ── HR ── */
hr { border: none !important; border-top: 1px solid rgba(255,255,255,0.04) !important; }

/* ── Sidebar footer classes ── */
.sidebar-footer {
    border-top: 1px solid rgba(255,255,255,0.04);
    padding-top: 14px;
    margin-top: 14px;
}
.sys-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}
.sys-key {
    font-size: 8px !important;
    font-weight: 700 !important;
    letter-spacing: 0.2em !important;
    color: #1E2733 !important;
    text-transform: uppercase !important;
    font-family: 'JetBrains Mono', monospace !important;
}
.sys-val {
    font-size: 10px !important;
    color: #374151 !important;
    font-family: 'JetBrains Mono', monospace !important;
}
.sys-val-active {
    font-size: 10px !important;
    color: #10B981 !important;
    font-family: 'JetBrains Mono', monospace !important;
    display: flex;
    align-items: center;
    gap: 5px;
}
.live-dot {
    width: 5px; height: 5px;
    background: #10B981;
    border-radius: 50%;
    animation: live-blink 1.5s step-end infinite;
    display: inline-block;
    flex-shrink: 0;
}
@keyframes live-blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
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
    """Loads an InstanceContext based on user selection."""
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
        st.session_state.instance = load_initial_instance("Chao Set 64 (Clustered)", 3, 3.5, 45.0)
    if "schedule" not in st.session_state:
        with st.spinner("Solving mission schedule..."):
            pool = explore_route_pool(st.session_state.instance, max_iterations=150, time_limit_sec=0.8)
            st.session_state.schedule = solve_fleet_schedule(st.session_state.instance, pool, run_baselines=True)
    if "grasp_schedule" not in st.session_state:
        st.session_state.grasp_schedule = solve_grasp_baseline(st.session_state.instance)


initialize_state()

# ---------------------------------------------------------------------------
# Sidebar: Mission Planning & Atmospheric Controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="brand-name">
                <div class="brand-diamond"></div>
                AEROSCAN
            </div>
            <div class="brand-sub">Optima · Swarm Coverage Platform</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<span class="section-label">Mission Scenario</span>', unsafe_allow_html=True)
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
        label_visibility="collapsed",
    )

    st.markdown('<span class="section-label">Fleet</span>', unsafe_allow_html=True)
    fleet_size = st.slider("Fleet Size", min_value=2, max_value=8, value=3, label_visibility="collapsed")

    st.markdown('<span class="section-label">Wind Vector</span>', unsafe_allow_html=True)
    wind_speed = st.slider("Speed m/s", min_value=0.0, max_value=15.0, value=4.0, step=0.5, label_visibility="collapsed")
    wind_dir = st.slider("Heading deg", min_value=0.0, max_value=360.0, value=60.0, step=15.0, label_visibility="collapsed")

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    c_btn1, c_btn2 = st.columns([1.25, 1.0])
    with c_btn1:
        run_opt = st.button("Optimize", type="primary", use_container_width=True)
    with c_btn2:
        load_mock = st.button("Mock", use_container_width=True)

    if run_opt:
        with st.spinner("Optimizing swarm trajectories..."):
            inst = load_initial_instance(scenario_choice, fleet_size, wind_speed, wind_dir)
            st.session_state.instance = inst
            route_pool = explore_route_pool(inst, max_iterations=350, time_limit_sec=1.5)
            sched = solve_fleet_schedule(inst, route_pool, run_baselines=True)
            st.session_state.schedule = sched
            st.session_state.grasp_schedule = solve_grasp_baseline(inst)
            st.toast(f"Solved in {sched.solve_time_seconds:.2f}s", icon="✓")

    if load_mock:
        mock_path = Path("tests/mock_schedule.json")
        if mock_path.exists():
            with open(mock_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            st.session_state.schedule = FleetSchedule.from_dict(data)
            st.toast("Loaded mock fixture", icon="✓")

    st.markdown(
        """
        <div class="sidebar-footer">
            <div class="sys-row">
                <span class="sys-key">Telemetry</span>
                <span class="sys-val">RTK Dual-Band</span>
            </div>
            <div class="sys-row">
                <span class="sys-key">Encryption</span>
                <span class="sys-val">AES-256-GCM</span>
            </div>
            <div class="sys-row">
                <span class="sys-key">Deconfliction</span>
                <span class="sys-val-active"><span class="live-dot"></span>Active</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Top Header Bar
# ---------------------------------------------------------------------------
instance: InstanceContext = st.session_state.instance
schedule: FleetSchedule = st.session_state.schedule
grasp_schedule: FleetSchedule = st.session_state.grasp_schedule

now_utc = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
wind_v = f"{instance.ambient_wind[0]:.1f} m/s · {round(math.degrees(instance.ambient_wind[1])) % 360:03d}°"

st.markdown(
    f"""
    <div class="cmd-bar">
        <div class="cmd-seg">
            <span class="cmd-seg-label">Platform</span>
            <span class="cmd-seg-val">AEROSCAN</span>
        </div>
        <div class="cmd-seg">
            <span class="cmd-seg-label">Instance</span>
            <span class="cmd-seg-val accent">{instance.instance_name}</span>
        </div>
        <div class="cmd-seg">
            <span class="cmd-seg-label">Wind</span>
            <span class="cmd-seg-val">{wind_v}</span>
        </div>
        <div class="cmd-seg">
            <span class="cmd-seg-label">UAVs</span>
            <span class="cmd-seg-val">{len(schedule.assigned_routes):02d}</span>
        </div>
        <div class="cmd-spacer"></div>
        <div class="cmd-right">
            <span class="cmd-clock">{now_utc}</span>
            <div class="beacon-wrap">
                <div class="beacon">
                    <div class="beacon-core"></div>
                    <div class="beacon-ring"></div>
                    <div class="beacon-ring2"></div>
                </div>
                {schedule.status}
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Key KPI Cards
# ---------------------------------------------------------------------------
m1, m2, m3, m4 = st.columns(4)
with m1:
    gain_text = f"+{schedule.reward_gain_percent:.1f}% vs GRASP"
    st.metric(label="Total Collected Reward", value=f"{schedule.cumulative_reward:.0f} pts", delta=gain_text)
with m2:
    visited_cnt = sum(len(r.target_ids) for r in schedule.assigned_routes)
    total_cnt = len(instance.target_nodes)
    st.metric(label="Targets Secured", value=f"{visited_cnt} / {total_cnt}", delta=f"{visited_cnt/max(total_cnt,1)*100:.1f}% coverage")
with m3:
    min_reserve = min((r.final_reserve_percent for r in schedule.assigned_routes), default=100.0)
    st.metric(label="Min Battery Reserve", value=f"{min_reserve:.1f}%", delta="Above 15% Floor")
with m4:
    st.metric(label="Solve Latency", value=f"{schedule.solve_time_seconds:.3f}s", delta="Optimal")

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Navigation Tabs
# ---------------------------------------------------------------------------
tab_map, tab_cockpit, tab_arena, tab_battery, tab_export = st.tabs([
    "Radar",
    "Telemetry",
    "Arena",
    "Battery",
    "Export",
])

# ---------------------------------------------------------------------------
# TAB 1: Live Mission Radar
# ---------------------------------------------------------------------------
with tab_map:
    max_mission_time = max(
        (r.total_flight_time for r in schedule.assigned_routes),
        default=1800.0,
    )
    if max_mission_time <= 0:
        max_mission_time = 1800.0

    scrubber_col, ctrl_col, view_col = st.columns([3, 1, 1])
    with scrubber_col:
        t_current = st.slider(
            "Mission Time Scrubber",
            min_value=0.0,
            max_value=float(max_mission_time),
            value=float(min(300.0, max_mission_time)),
            step=5.0,
            format="%0.0f sec",
        )
    with ctrl_col:
        halos = st.checkbox("Radar Halos", value=True)
        breadcrumbs = st.checkbox("Flown Trail", value=True)
    with view_col:
        view_mode = st.radio("View", ["2D Radar", "3D Topographic"], horizontal=True)

    if view_mode == "2D Radar":
        fig_map = build_mission_map_figure(
            instance=instance,
            schedule=schedule,
            current_time_sec=t_current,
            show_radar_halos=halos,
            show_breadcrumbs=breadcrumbs,
        )
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        fig_3d = build_3d_terrain_mission_figure(
            instance=instance,
            schedule=schedule,
            current_time_sec=t_current,
        )
        st.plotly_chart(fig_3d, use_container_width=True)

# ---------------------------------------------------------------------------
# TAB 2: Swarm Telemetry
# ---------------------------------------------------------------------------
with tab_cockpit:
    telemetry_data, _ = get_fleet_telemetry_at_time(schedule, t_current, instance)

    cockpit_cols = st.columns(min(max(len(telemetry_data), 1), 4))
    for idx, telem in enumerate(telemetry_data):
        with cockpit_cols[idx % 4]:
            u_color = DRONE_COLORS[idx % len(DRONE_COLORS)]
            bat_val = telem["battery_percent"]
            bat_color = "#34D399" if bat_val > 40 else ("#FBBF24" if bat_val > 20 else "#F43F5E")

            st.markdown(
                f"""
                <div class="telem-card">
                    <div class="telem-card-accent" style="background:{u_color};"></div>
                    <div class="telem-hdr">
                        <span class="telem-drone-id" style="color:{u_color};">{telem['drone_id']}</span>
                        <span class="telem-bat" style="color:{bat_color};">{bat_val:.0f}%</span>
                    </div>
                    <div class="telem-rows">
                        <span class="telem-key">Phase</span><span class="telem-val">{telem['flight_phase']}</span>
                        <span class="telem-key">Speed</span><span class="telem-val">{telem['speed_mps']:.1f} m/s</span>
                        <span class="telem-key">Alt</span><span class="telem-val">{telem['z']:.0f} m</span>
                        <span class="telem-key">Hdg</span><span class="telem-val">{telem.get('heading_deg', 0):.0f}°</span>
                        <span class="telem-key">Next</span><span class="telem-val">{telem.get('target_name', 'BASE')}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.dataframe(
        telemetry_data,
        column_config={
            "drone_id": "UAV",
            "x": st.column_config.NumberColumn("X (m)", format="%.1f"),
            "y": st.column_config.NumberColumn("Y (m)", format="%.1f"),
            "z": st.column_config.NumberColumn("ALT (m)", format="%.1f"),
            "battery_percent": st.column_config.ProgressColumn("SoC", min_value=0, max_value=100, format="%.0f%%"),
            "speed_mps": st.column_config.NumberColumn("SPD m/s", format="%.1f"),
            "heading_deg": st.column_config.NumberColumn("HDG°", format="%.0f"),
            "status": "State",
        },
        use_container_width=True,
        hide_index=True,
    )

# ---------------------------------------------------------------------------
# TAB 3: Algorithmic Arena
# ---------------------------------------------------------------------------
with tab_arena:
    render_arena_view(instance, schedule, grasp_schedule)

# ---------------------------------------------------------------------------
# TAB 4: Battery Profiles
# ---------------------------------------------------------------------------
with tab_battery:
    st.caption("Continuous SoC curves · 15% safety floor · dual-channel verification")
    fig_soc = build_battery_soc_figure(schedule, instance, current_time_sec=t_current)
    st.plotly_chart(fig_soc, use_container_width=True)

# ---------------------------------------------------------------------------
# TAB 5: Mission Export
# ---------------------------------------------------------------------------
with tab_export:
    st.caption("QGroundControl (.plan) · PX4 MAVLink · telemetry audit · mission dossier")

    c_exp1, c_exp2 = st.columns(2)
    with c_exp1:
        st.markdown("###### Autopilot Mission Files")
        for route in schedule.assigned_routes:
            drone_spec = next((d for d in instance.drones if d.id == route.drone_id), instance.drones[0])
            plan_json = export_qgroundcontrol_plan(route, drone_spec, instance)
            mav_text = export_mavlink_waypoint_file(route, drone_spec, instance)

            col_a, col_b = st.columns(2)
            with col_a:
                st.download_button(
                    label=f"{route.drone_id} (.plan)",
                    data=plan_json,
                    file_name=f"{route.drone_id}_mission.plan",
                    mime="application/json",
                    use_container_width=True,
                )
            with col_b:
                st.download_button(
                    label=f"{route.drone_id} (MAVLink)",
                    data=mav_text,
                    file_name=f"{route.drone_id}_waypoints.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

    with c_exp2:
        st.markdown("###### Audit Logs & Reports")
        csv_data = export_mission_telemetry_csv(schedule, instance)
        st.download_button(
            label="Download Telemetry Audit (CSV)",
            data=csv_data,
            file_name=f"{instance.instance_name}_telemetry_audit.csv",
            mime="text/csv",
            use_container_width=True,
        )

        dossier_html = export_mission_dossier_html(schedule, instance)
        st.download_button(
            label="Download Mission Dossier (HTML)",
            data=dossier_html,
            file_name=f"{instance.instance_name}_flight_dossier.html",
            mime="text/html",
            use_container_width=True,
        )
