
import math
import json
import hashlib
import time
from pathlib import Path
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

import altair as alt
import pandas as pd
import requests
import streamlit as st
from nba_api.live.nba.endpoints import scoreboard
from nba_api.stats.endpoints import commonplayerinfo, playergamelog
from nba_api.stats.static import players

# =========================
# CONFIG
# =========================

API_KEY = "9f56e4fb5f6ff37b0a1bac6ea7900e78"

NBA_SEASON = "2025-26"
NBA_SPORT_KEY = "basketball_nba"
NHL_SPORT_KEY = "icehockey_nhl"

PREFERRED_BOOKMAKERS = "draftkings,fanduel"
REQUEST_TIMEOUT = 20
MAX_RECENT_GAMES = 10
MIN_NBA_MINUTES = 20
MIN_NHL_TOI_MINUTES = 12
MAX_PROP_PLAYERS_PER_GAME_PER_MARKET = 8

NBA_POINTS_MARKET_KEYS = ["player_points", "player_points_alternate"]
NBA_THREES_MARKET_KEYS = ["player_threes", "player_threes_alternate"]

NHL_POINTS_MARKET_KEYS = ["player_points", "player_points_alternate"]
NHL_SHOTS_MARKET_KEYS = ["player_shots_on_goal", "player_shots_on_goal_alternate"]
NHL_GOALS_MARKET_KEYS = ["player_goals", "player_goals_alternate"]

NBA_TEAM_NAME_MAP = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
}

NBA_TEAM_NAME_ALIASES = {
    "atlantahawks": {"atlantahawks", "hawks", "atl"},
    "bostonceltics": {"bostonceltics", "celtics", "bos"},
    "brooklynnets": {"brooklynnets", "nets", "bkn", "brk"},
    "charlottehornets": {"charlottehornets", "hornets", "cha"},
    "chicagobulls": {"chicagobulls", "bulls", "chi"},
    "clevelandcavaliers": {"clevelandcavaliers", "cavaliers", "cavs", "cle"},
    "dallasmavericks": {"dallasmavericks", "mavericks", "mavs", "dal"},
    "denvernuggets": {"denvernuggets", "nuggets", "den"},
    "detroitpistons": {"detroitpistons", "pistons", "det"},
    "goldenstatewarriors": {"goldenstatewarriors", "warriors", "gsw"},
    "houstonrockets": {"houstonrockets", "rockets", "hou"},
    "indianapacers": {"indianapacers", "pacers", "ind"},
    "losangelesclippers": {"losangelesclippers", "laclippers", "clippers", "lac", "la clippers"},
    "losangeleslakers": {"losangeleslakers", "lalakers", "lakers", "lal", "la lakers"},
    "memphisgrizzlies": {"memphisgrizzlies", "grizzlies", "mem"},
    "miamiheat": {"miamiheat", "heat", "mia"},
    "milwaukeebucks": {"milwaukeebucks", "bucks", "mil"},
    "minnesotatimberwolves": {"minnesotatimberwolves", "timberwolves", "wolves", "min"},
    "neworleanspelicans": {"neworleanspelicans", "pelicans", "nop", "no"},
    "newyorkknicks": {"newyorkknicks", "knicks", "nyk"},
    "oklahomacitythunder": {"oklahomacitythunder", "thunder", "okc"},
    "orlandomagic": {"orlandomagic", "magic", "orl"},
    "philadelphia76ers": {"philadelphia76ers", "76ers", "sixers", "phi"},
    "phoenixsuns": {"phoenixsuns", "suns", "phx"},
    "portlandtrailblazers": {"portlandtrailblazers", "trailblazers", "blazers", "por"},
    "sacramentokings": {"sacramentokings", "kings", "sac"},
    "sanantoniospurs": {"sanantoniospurs", "spurs", "sas"},
    "torontoraptors": {"torontoraptors", "raptors", "tor"},
    "utahjazz": {"utahjazz", "jazz", "uta"},
    "washingtonwizards": {"washingtonwizards", "wizards", "was"},
}

NHL_NAME_TO_ABBREV = {
    "Anaheim Ducks": "ANA",
    "Boston Bruins": "BOS",
    "Buffalo Sabres": "BUF",
    "Calgary Flames": "CGY",
    "Carolina Hurricanes": "CAR",
    "Chicago Blackhawks": "CHI",
    "Colorado Avalanche": "COL",
    "Columbus Blue Jackets": "CBJ",
    "Dallas Stars": "DAL",
    "Detroit Red Wings": "DET",
    "Edmonton Oilers": "EDM",
    "Florida Panthers": "FLA",
    "Los Angeles Kings": "LAK",
    "Minnesota Wild": "MIN",
    "Montréal Canadiens": "MTL",
    "Montreal Canadiens": "MTL",
    "Nashville Predators": "NSH",
    "New Jersey Devils": "NJD",
    "New York Islanders": "NYI",
    "New York Rangers": "NYR",
    "Ottawa Senators": "OTT",
    "Philadelphia Flyers": "PHI",
    "Pittsburgh Penguins": "PIT",
    "San Jose Sharks": "SJS",
    "Seattle Kraken": "SEA",
    "St. Louis Blues": "STL",
    "St Louis Blues": "STL",
    "Tampa Bay Lightning": "TBL",
    "Toronto Maple Leafs": "TOR",
    "Utah Hockey Club": "UTA",
    "Utah Mammoth": "UTA",
    "Vancouver Canucks": "VAN",
    "Vegas Golden Knights": "VGK",
    "Washington Capitals": "WSH",
    "Winnipeg Jets": "WPG",
}

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

# =========================
# ODDS API CREDIT SAVER
# =========================
# The Odds API free tier can get burned quickly because props are event-level.
# This disk cache survives Streamlit reruns and `streamlit cache clear`, so repeated
# button clicks reuse the same successful response instead of spending credits again.
ODDS_CACHE_FILE = Path("odds_api_cache.json")
ODDS_CACHE_DAILY_MODE = True
ODDS_CACHE_DEFAULT_TTL_SECONDS = 24 * 60 * 60       # daily odds snapshot: one pull per request per day
ODDS_CACHE_EVENTS_TTL_SECONDS = 24 * 60 * 60        # event list is reused for the full day
ODDS_CACHE_H2H_TTL_SECONDS = 24 * 60 * 60           # game list / h2h lines reused for the full day
ODDS_CACHE_MAX_STALE_SECONDS = 7 * 24 * 60 * 60     # fallback to last good response if quota/API fails
ODDS_FORCE_REFRESH_SECONDS = 180                    # manual refresh window; uses API credits intentionally


# =========================
# PAGE / STYLE
# =========================

st.set_page_config(page_title="NBA + NHL Prop Parlay Engine", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }

    .stApp {
        background:
            radial-gradient(circle at top left, rgba(37, 99, 235, 0.10), transparent 34rem),
            radial-gradient(circle at top right, rgba(16, 185, 129, 0.10), transparent 32rem),
            linear-gradient(180deg, #f8fafc 0%, #eef2f7 42%, #f8fafc 100%);
    }

    .block-container {
        padding-top: 1.35rem;
        padding-bottom: 2.5rem;
        max-width: 1380px;
    }

    .app-hero {
        position: relative;
        overflow: hidden;
        border-radius: 28px;
        padding: 30px 34px 26px 34px;
        margin-bottom: 20px;
        background:
            linear-gradient(135deg, rgba(15,23,42,0.98) 0%, rgba(30,64,175,0.96) 48%, rgba(20,184,166,0.92) 100%);
        border: 1px solid rgba(255,255,255,0.22);
        box-shadow: 0 22px 60px rgba(15, 23, 42, 0.22);
        color: white;
    }

    .app-hero:before {
        content: '';
        position: absolute;
        right: -100px;
        top: -120px;
        width: 350px;
        height: 350px;
        border-radius: 999px;
        background: rgba(255,255,255,0.12);
    }

    .hero-kicker {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 7px 11px;
        border-radius: 999px;
        background: rgba(255,255,255,0.14);
        border: 1px solid rgba(255,255,255,0.20);
        color: #dbeafe;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: .08em;
        text-transform: uppercase;
        margin-bottom: 14px;
    }

    .app-title {
        font-size: clamp(34px, 5vw, 58px);
        line-height: 0.96;
        letter-spacing: -0.055em;
        font-weight: 800;
        margin: 0 0 12px 0;
        color: white;
    }

    .app-subtitle {
        max-width: 760px;
        font-size: 16px;
        line-height: 1.55;
        color: rgba(255,255,255,0.82);
        margin-bottom: 20px;
    }

    .hero-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 12px;
    }

    .hero-badge {
        border-radius: 999px;
        padding: 8px 12px;
        background: rgba(255,255,255,0.13);
        border: 1px solid rgba(255,255,255,0.20);
        color: white;
        font-size: 13px;
        font-weight: 650;
    }

    .logo-strip {
        display: flex;
        gap: 13px;
        align-items: center;
        overflow-x: auto;
        overflow-y: hidden;
        padding: 14px 18px;
        margin: 0 0 20px 0;
        border-radius: 20px;
        background: rgba(255,255,255,0.78);
        border: 1px solid rgba(226,232,240,0.95);
        box-shadow: 0 10px 30px rgba(15,23,42,0.07);
        scrollbar-width: none;
    }

    .logo-strip::-webkit-scrollbar {
        display: none;
    }

    .logo-strip-label {
        flex: 0 0 auto;
        font-size: 12px;
        font-weight: 800;
        letter-spacing: .08em;
        text-transform: uppercase;
        color: #64748b;
        margin-right: 2px;
    }

    .team-logo {
        width: 34px;
        height: 34px;
        flex: 0 0 34px;
        object-fit: contain;
        filter: saturate(0.95);
        opacity: .86;
        transition: transform .15s ease, opacity .15s ease;
    }

    .team-logo:hover {
        opacity: 1;
        transform: translateY(-2px) scale(1.05);
    }

    .quick-card {
        border: 1px solid rgba(226,232,240,0.95);
        border-radius: 22px;
        padding: 18px 19px;
        background: rgba(255,255,255,0.82);
        box-shadow: 0 12px 34px rgba(15,23,42,0.08);
        min-height: 116px;
    }

    .quick-card-title {
        font-size: 13px;
        color: #64748b;
        font-weight: 750;
        text-transform: uppercase;
        letter-spacing: .06em;
        margin-bottom: 8px;
    }

    .quick-card-main {
        font-size: 24px;
        color: #0f172a;
        font-weight: 800;
        letter-spacing: -0.035em;
        margin-bottom: 5px;
    }

    .quick-card-sub {
        color: #64748b;
        font-size: 13px;
        line-height: 1.35;
    }


    .daily-dashboard-bar {
        display: flex;
        align-items: stretch;
        justify-content: space-between;
        gap: 0;
        margin: 0 0 18px 0;
        padding: 10px;
        border-radius: 24px;
        background: rgba(255,255,255,0.88);
        border: 1px solid rgba(203,213,225,0.95);
        box-shadow: 0 16px 38px rgba(15,23,42,0.08);
        overflow: hidden;
    }

    .status-pill {
        flex: 1 1 0;
        min-width: 0;
        display: flex;
        align-items: center;
        gap: 11px;
        padding: 13px 16px;
        border-right: 1px solid rgba(226,232,240,0.95);
        color: #0f172a;
    }

    .status-pill:last-child { border-right: none; }

    .status-icon {
        width: 38px;
        height: 38px;
        flex: 0 0 38px;
        border-radius: 14px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 19px;
        background: linear-gradient(135deg, #eff6ff, #dbeafe);
        border: 1px solid rgba(191,219,254,0.9);
    }

    .status-label {
        font-size: 11px;
        line-height: 1;
        color: #64748b;
        font-weight: 850;
        letter-spacing: .08em;
        text-transform: uppercase;
        margin-bottom: 6px;
        white-space: nowrap;
    }

    .status-main {
        font-size: 15px;
        line-height: 1.2;
        color: #0f172a;
        font-weight: 850;
        letter-spacing: -0.02em;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .status-sub {
        font-size: 12px;
        color: #475569;
        margin-top: 3px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .status-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: #16a34a;
        box-shadow: 0 0 0 4px rgba(22,163,74,0.12);
        margin-left: 6px;
        vertical-align: middle;
    }

    .metric-card {
        border: 1px solid rgba(226,232,240,0.95);
        border-radius: 18px;
        padding: 15px 17px;
        background: rgba(255,255,255,0.86);
        box-shadow: 0 10px 28px rgba(15,23,42,0.07);
        min-height: 88px;
    }

    .metric-label {font-size: 12px; color: #64748b; margin-bottom: 6px; font-weight: 700; letter-spacing: .02em;}
    .metric-value {font-size: 28px; font-weight: 800; color: #0f172a; letter-spacing: -0.035em;}
    .metric-sub {font-size: 12px; color: #64748b; margin-top: 4px;}
    .metric-good { color: #059669; }
    .metric-bad { color: #dc2626; }
    .metric-neutral { color: #0f172a; }

    div[data-testid="stTabs"] button {
        font-weight: 750;
        border-radius: 999px;
        padding: 10px 18px;
        color: #334155;
    }

    div[data-testid="stTabs"] [role="tablist"] {
        gap: 12px !important;
        border-bottom: 1px solid rgba(203,213,225,0.95) !important;
        padding: 10px 4px 12px 4px !important;
        margin: 10px 0 18px 0 !important;
    }

    div[data-testid="stTabs"] button {
        background: rgba(255,255,255,0.92) !important;
        border: 1px solid rgba(203,213,225,0.95) !important;
        box-shadow: 0 10px 24px rgba(15,23,42,0.07) !important;
        min-width: 118px !important;
        justify-content: center !important;
        font-size: 15px !important;
    }

    div[data-testid="stTabs"] button[aria-selected="true"] {
        background: linear-gradient(135deg, #0f172a, #1d4ed8) !important;
        color: white !important;
        border-color: rgba(37,99,235,0.45) !important;
        box-shadow: 0 12px 28px rgba(37,99,235,0.22) !important;
        transform: translateY(-1px);
    }

    div[data-testid="stTabs"] button[aria-selected="true"] * {
        color: white !important;
    }

    .stButton > button {
        border-radius: 999px;
        border: 1px solid rgba(15,23,42,0.12);
        background: linear-gradient(135deg, #0f172a, #1d4ed8) !important;
        color: #ffffff !important;
        font-weight: 800;
        padding: 0.58rem 1.05rem;
        box-shadow: 0 8px 20px rgba(37,99,235,0.18);
    }

    .stButton > button * {
        color: #ffffff !important;
        opacity: 1 !important;
    }

    .stButton > button p,
    .stButton > button span,
    .stButton > button div {
        color: #ffffff !important;
    }

    .stButton > button:hover {
        border-color: rgba(37,99,235,0.35);
        transform: translateY(-1px);
        color: #ffffff !important;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 18px;
        overflow: hidden;
        box-shadow: 0 10px 30px rgba(15,23,42,0.06);
    }


    /* =========================
       MOBILE RESPONSIVE UPGRADES
       ========================= */


    /* Parlay math/readability fixes: dark blocks should always have bright text. */
    .parlay-math-card {
        background: linear-gradient(135deg, #020617, #0f172a) !important;
        color: #ffffff !important;
        border: 1px solid rgba(148,163,184,0.35) !important;
        border-radius: 14px !important;
        padding: 13px 15px !important;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace !important;
        font-size: 14px !important;
        line-height: 1.45 !important;
        overflow-x: auto !important;
        box-shadow: 0 8px 22px rgba(15,23,42,0.14) !important;
    }

    .parlay-math-card,
    .parlay-math-card * {
        color: #ffffff !important;
    }

    div[data-testid="stCodeBlock"],
    div[data-testid="stCodeBlock"] *,
    pre,
    pre *,
    code,
    code * {
        color: #ffffff !important;
    }

    div[data-testid="stCodeBlock"] pre,
    pre {
        background: #0f172a !important;
        border-radius: 14px !important;
    }

    @media (max-width: 900px) {
        .block-container {
            padding-top: 0.75rem !important;
            padding-left: 0.85rem !important;
            padding-right: 0.85rem !important;
            padding-bottom: 5.5rem !important;
            max-width: 100% !important;
        }

        .app-hero {
            border-radius: 22px;
            padding: 22px 18px 20px 18px;
            margin-bottom: 14px;
            box-shadow: 0 14px 36px rgba(15, 23, 42, 0.18);
        }

        .app-hero:before {
            right: -135px;
            top: -145px;
            width: 285px;
            height: 285px;
        }

        .hero-kicker {
            font-size: 10px;
            padding: 6px 9px;
            margin-bottom: 11px;
        }

        .app-title {
            font-size: 34px !important;
            line-height: 1.02;
            letter-spacing: -0.045em;
            margin-bottom: 10px;
        }

        .app-subtitle {
            font-size: 13px;
            line-height: 1.45;
            margin-bottom: 14px;
        }

        .hero-badges {
            gap: 7px;
            margin-top: 8px;
        }

        .hero-badge {
            font-size: 11px;
            padding: 7px 9px;
        }

        .logo-strip {
            gap: 11px;
            padding: 12px 13px;
            margin-bottom: 15px;
            border-radius: 18px;
            -webkit-overflow-scrolling: touch;
            scroll-snap-type: x proximity;
        }

        .logo-strip-label {
            position: sticky;
            left: 0;
            z-index: 2;
            background: rgba(255,255,255,0.92);
            border-radius: 999px;
            padding: 6px 9px;
            box-shadow: 7px 0 12px rgba(255,255,255,0.88);
            font-size: 10px;
        }

        .team-logo {
            width: 30px;
            height: 30px;
            flex-basis: 30px;
            scroll-snap-align: start;
        }

        .quick-card,
        .metric-card {
            border-radius: 18px;
            padding: 14px 15px;
            min-height: auto;
            margin-bottom: 8px;
        }

        .daily-dashboard-bar {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            padding: 8px;
            border-radius: 20px;
            margin-bottom: 14px;
        }

        .status-pill {
            border-right: none;
            border-radius: 16px;
            background: rgba(248,250,252,0.94);
            border: 1px solid rgba(226,232,240,0.95);
            padding: 11px 10px;
            gap: 8px;
        }

        .status-icon {
            width: 32px;
            height: 32px;
            flex-basis: 32px;
            border-radius: 12px;
            font-size: 16px;
        }

        .status-label {
            font-size: 9px;
            margin-bottom: 5px;
        }

        .status-main {
            font-size: 13px;
        }

        .status-sub {
            font-size: 10px;
        }

        .quick-card-main {
            font-size: 21px;
        }

        .metric-value {
            font-size: 23px;
        }

        div[data-testid="stHorizontalBlock"] {
            gap: 0.65rem !important;
        }

        .stButton > button {
            width: 100% !important;
            min-height: 46px;
            padding: 0.72rem 0.95rem !important;
            font-size: 14px !important;
            border-radius: 14px !important;
            color: #ffffff !important;
        }

        .stButton > button p,
        .stButton > button span,
        .stButton > button div {
            color: #ffffff !important;
            opacity: 1 !important;
        }

        div[data-testid="stTabs"] button {
            padding: 9px 12px;
            font-size: 13px;
            white-space: nowrap;
        }

        div[data-testid="stTabs"] [role="tablist"] {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            gap: 6px;
            padding-bottom: 3px;
        }

        div[data-testid="stDataFrame"] {
            border-radius: 14px;
            overflow-x: auto !important;
        }

        div[data-testid="stDataFrame"] iframe,
        div[data-testid="stDataFrame"] > div {
            min-width: 760px;
        }

        .element-container:has(.stButton) {
            margin-bottom: 0.35rem;
        }

        section[data-testid="stSidebar"] {
            width: min(92vw, 340px) !important;
        }
    }

    @media (max-width: 520px) {
        .app-title {
            font-size: 29px !important;
        }

        .app-subtitle {
            font-size: 12.5px;
        }

        .hero-badges {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .hero-badge {
            text-align: center;
            white-space: normal;
        }

        .logo-strip {
            margin-left: -2px;
            margin-right: -2px;
        }

        .team-logo {
            width: 28px;
            height: 28px;
            flex-basis: 28px;
        }

        h1, h2, h3 {
            letter-spacing: -0.03em;
        }

        h2 {
            font-size: 1.25rem !important;
        }

        h3 {
            font-size: 1.05rem !important;
        }
    }


    /* =========================
       READABILITY / CONTRAST FIXES
       Keeps the light SaaS look, but prevents white text on light cards.
       ========================= */
    :root {
        --app-text: #0f172a;
        --app-muted: #475569;
        --app-card: #ffffff;
        --app-card-soft: #f8fafc;
        --app-border: #cbd5e1;
        --app-blue: #1d4ed8;
        --app-green: #059669;
        --app-red: #dc2626;
    }

    /* Default app text should be dark on the light background. */
    .stApp,
    .stApp p,
    .stApp span,
    .stApp label,
    .stApp div,
    .stApp li,
    .stApp td,
    .stApp th,
    .stApp code,
    .stApp small {
        color: var(--app-text);
    }

    /* Keep intentional dark/gradient sections white. */
    .app-hero,
    .app-hero *,
    .hero-kicker,
    .hero-badge,
    .app-title,
    .app-subtitle {
        color: #ffffff !important;
    }

    .app-subtitle {
        color: rgba(255,255,255,0.88) !important;
    }

    .hero-kicker {
        color: #dbeafe !important;
    }

    /* Cards and custom HTML blocks. */
    .quick-card,
    .metric-card,
    .logo-strip,
    div[data-testid="stExpander"],
    div[data-testid="stForm"],
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: rgba(255,255,255,0.94) !important;
        color: var(--app-text) !important;
    }

    .quick-card *,
    .metric-card *,
    .logo-strip *,
    div[data-testid="stExpander"] *,
    div[data-testid="stForm"] * {
        color: var(--app-text) !important;
    }

    .quick-card-title,
    .quick-card-sub,
    .metric-label,
    .metric-sub,
    .logo-strip-label {
        color: var(--app-muted) !important;
    }

    .metric-good { color: var(--app-green) !important; }
    .metric-bad { color: var(--app-red) !important; }
    .metric-neutral { color: var(--app-text) !important; }

    /* Streamlit status boxes: force readable text on their tinted backgrounds. */
    div[data-testid="stAlert"] {
        border-radius: 14px !important;
        border: 1px solid rgba(100,116,139,0.25) !important;
    }

    div[data-testid="stAlert"],
    div[data-testid="stAlert"] *,
    .stAlert,
    .stAlert * {
        color: #0f172a !important;
    }

    /* Inputs/select boxes can inherit odd colors on mobile. */
    div[data-baseweb="select"] *,
    div[data-baseweb="input"] *,
    input,
    textarea,
    select,
    [data-testid="stTextInput"] *,
    [data-testid="stNumberInput"] *,
    [data-testid="stSelectbox"] *,
    [data-testid="stMultiSelect"] * {
        color: var(--app-text) !important;
    }

    input,
    textarea,
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div {
        background-color: #ffffff !important;
        border-color: var(--app-border) !important;
    }

    /* Tabs: selected dark tab gets white text, unselected gets dark text. */
    div[data-testid="stTabs"] button {
        color: #334155 !important;
        background: rgba(255,255,255,0.72) !important;
        border: 1px solid rgba(203,213,225,0.85) !important;
    }

    div[data-testid="stTabs"] button * {
        color: #334155 !important;
    }

    div[data-testid="stTabs"] button[aria-selected="true"] {
        background: #0f172a !important;
        color: #ffffff !important;
        border-color: #0f172a !important;
    }

    div[data-testid="stTabs"] button[aria-selected="true"] * {
        color: #ffffff !important;
    }

    /* Buttons: all button text stays white on blue gradient. */
    .stButton > button,
    .stDownloadButton > button,
    button[kind="primary"],
    button[kind="secondary"] {
        background: linear-gradient(135deg, #0f172a, #2563eb) !important;
        color: #ffffff !important;
        border: 1px solid rgba(37,99,235,0.35) !important;
    }

    .stButton > button *,
    .stDownloadButton > button *,
    button[kind="primary"] *,
    button[kind="secondary"] * {
        color: #ffffff !important;
        opacity: 1 !important;
    }

    .stButton > button:disabled,
    .stDownloadButton > button:disabled {
        background: #94a3b8 !important;
        color: #ffffff !important;
    }

    /* Dataframes/tables need dark readable text. */
    div[data-testid="stDataFrame"] *,
    .stDataFrame *,
    table,
    table * {
        color: #0f172a !important;
    }

    /* Metric widgets generated by Streamlit. */
    div[data-testid="stMetric"],
    div[data-testid="stMetric"] * {
        color: #0f172a !important;
    }

    div[data-testid="stMetricDelta"] svg {
        color: inherit !important;
    }

    /* Links should pop on light backgrounds. */
    a,
    a * {
        color: #1d4ed8 !important;
        font-weight: 650;
    }

    .app-hero a,
    .app-hero a * {
        color: #bfdbfe !important;
    }

    @media (max-width: 900px) {
        .stApp,
        .stApp p,
        .stApp span,
        .stApp label,
        .stApp div,
        .stApp li {
            color: var(--app-text);
        }

        .app-hero,
        .app-hero * {
            color: #ffffff !important;
        }

        .quick-card,
        .metric-card,
        .logo-strip,
        div[data-testid="stExpander"],
        div[data-testid="stForm"] {
            background: #ffffff !important;
            border-color: rgba(203,213,225,0.95) !important;
        }

        .quick-card *,
        .metric-card *,
        .logo-strip *,
        div[data-testid="stExpander"] *,
        div[data-testid="stForm"] * {
            color: var(--app-text) !important;
        }

        .quick-card-title,
        .quick-card-sub,
        .metric-label,
        .metric-sub,
        .logo-strip-label {
            color: var(--app-muted) !important;
        }

        div[data-testid="stAlert"],
        div[data-testid="stAlert"] * {
            color: #0f172a !important;
        }
    }

    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# SHARED HELPERS
# =========================

def metric_card(label: str, value: str, tone: str = "neutral", subtext: str = "") -> str:
    tone_class = {"good": "metric-good", "bad": "metric-bad", "neutral": "metric-neutral"}.get(tone, "metric-neutral")
    sub_html = f'<div class="metric-sub">{subtext}</div>' if subtext else ""
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value {tone_class}">{value}</div>
        {sub_html}
    </div>
    """

def normalize_name(s: Any) -> str:
    return (
        str(s).lower()
        .replace(".", "")
        .replace("’", "'")
        .replace("-", " ")
        .replace(" jr", "")
        .replace(" sr", "")
        .replace(" iii", "")
        .replace(" ii", "")
        .strip()
    )

def normalize_team_text(s: Any) -> str:
    return (
        str(s).lower()
        .replace(".", "")
        .replace("'", "")
        .replace("-", "")
        .replace(" ", "")
        .replace("&", "and")
        .strip()
    )

def player_name_matches(player_name: str, *candidate_fields: Any) -> bool:
    p = normalize_name(player_name)
    for field in candidate_fields:
        c = normalize_name(field)
        if not c:
            continue
        if p == c or p in c or c in p:
            return True
    return False

def american_to_decimal(odds: Optional[int]) -> Optional[float]:
    if odds is None:
        return None
    if odds > 0:
        return 1 + odds / 100
    return 1 + 100 / abs(odds)

def decimal_to_american(decimal_odds: Optional[float]) -> Optional[int]:
    if decimal_odds is None or decimal_odds <= 1:
        return None
    if decimal_odds >= 2:
        return int(round((decimal_odds - 1) * 100))
    return int(round(-100 / (decimal_odds - 1)))

def american_to_implied_prob(odds: Optional[int]) -> Optional[float]:
    if odds is None:
        return None
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)

def calculate_ev(prob_pct: float, decimal_odds: Optional[float]) -> Optional[float]:
    if decimal_odds is None:
        return None
    p = prob_pct / 100
    return round(p * (decimal_odds - 1) - (1 - p), 3)

def probability_to_fair_american(prob_pct: float) -> Optional[int]:
    p = prob_pct / 100
    if p <= 0 or p >= 1:
        return None
    if p >= 0.5:
        return int(round(-(100 * p) / (1 - p)))
    return int(round((100 * (1 - p)) / p))

def safe_line_display(value: Optional[float]) -> str:
    if value is None:
        return "—"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"

def safe_odds_display(value: Optional[int]) -> str:
    if value is None:
        return "—"
    return f"+{value}" if value > 0 else str(value)

def dedupe_csv_names(names: List[str]) -> Optional[str]:
    cleaned, seen = [], set()
    for part in names:
        for item in str(part).split(","):
            val = item.strip()
            if val and val not in seen:
                seen.add(val)
                cleaned.append(val)
    return ", ".join(cleaned) if cleaned else None

def sportsbook_line_to_target(line: Optional[float]) -> Optional[int]:
    if line is None:
        return None
    return math.floor(line) + 1

def score_leg(model_prob_pct: float, ev: Optional[float], edge: Optional[float]) -> float:
    prob = (model_prob_pct or 0) / 100
    ev_val = max(ev or 0, 0)
    edge_val = max(edge or 0, 0)
    return round((prob * 0.5) + (ev_val * 0.3) + (edge_val * 0.2), 4)

def score_best_leg_board(model_prob_pct: Optional[float], book_odds: Optional[int]) -> float:
    """Best-leg board score: balances hit probability with actual payout.

    This is intentionally only used by the Top Candidate Legs Today direct board.
    It avoids ranking -400 style legs at the top just because implied probability is high.
    """
    if model_prob_pct is None or book_odds is None:
        return 0.0

    prob = max(min(model_prob_pct / 100, 1.0), 0.0)
    decimal_odds = american_to_decimal(book_odds)
    implied = american_to_implied_prob(book_odds)

    if decimal_odds is None or implied is None:
        return round(prob, 4)

    payout_profit = decimal_odds - 1.0
    edge = prob - implied

    if book_odds <= -300:
        payout_quality = 0.05
    elif book_odds < 0:
        payout_quality = max(0.10, min(0.65, payout_profit))
    else:
        payout_quality = min(1.0, payout_profit / 2.0)

    favorite_penalty = 0.0
    if book_odds <= -250:
        favorite_penalty = 0.10
    elif book_odds <= -200:
        favorite_penalty = 0.06
    elif book_odds <= -170:
        favorite_penalty = 0.03

    score = (prob * 0.55) + (payout_quality * 0.30) + (max(edge, 0) * 0.15) - favorite_penalty
    return round(score, 4)

def _poisson_over_probability(lam: float, target: int) -> float:
    if target <= 0:
        return 1.0
    cumulative = 0.0
    for k in range(target):
        cumulative += (lam ** k * math.exp(-lam)) / math.factorial(k)
    return max(0.0, min(1.0, 1.0 - cumulative))

def estimate_expected_from_probability(line: Optional[float], model_prob_pct: Optional[float]) -> Optional[float]:
    """Estimate an expected stat from a target line and model over probability.

    This keeps the best-leg board fast by avoiding player-by-player game-log calls.
    """
    if line is None or model_prob_pct is None:
        return None

    target = sportsbook_line_to_target(line)
    if target is None:
        return None

    target_prob = max(min(model_prob_pct / 100, 0.985), 0.015)
    lo, hi = 0.0, max(8.0, float(target) * 4.0 + 4.0)

    for _ in range(32):
        mid = (lo + hi) / 2.0
        prob = _poisson_over_probability(mid, int(target))
        if prob < target_prob:
            lo = mid
        else:
            hi = mid

    return round((lo + hi) / 2.0, 2)

def adjusted_best_leg_model_probability(implied_prob: Optional[float], book_odds: Optional[int]) -> Optional[float]:
    """Fast best-leg model probability.

    Uses sportsbook implied probability as the baseline, then applies a small payout-aware adjustment
    so the board does not blindly rank the safest, lowest-payout legs first.
    """
    if implied_prob is None or book_odds is None:
        return None

    prob = implied_prob

    # Small adjustment: prefer playable odds, punish ultra-heavy favorites.
    if book_odds <= -300:
        prob -= 0.035
    elif book_odds <= -250:
        prob -= 0.020
    elif book_odds <= -200:
        prob -= 0.010
    elif -180 <= book_odds <= 150:
        prob += 0.025
    elif 150 < book_odds <= 250:
        prob += 0.010

    return round(max(min(prob * 100, 88.0), 8.0), 2)

def nba_points_defense_factor(opponent: str) -> float:
    # Lightweight opponent adjustment for points. Above 1.00 = easier matchup.
    factors = {
        "ATL": 1.04, "BOS": 0.96, "BKN": 1.01, "CHA": 1.05, "CHI": 1.00,
        "CLE": 0.96, "DAL": 1.00, "DEN": 0.98, "DET": 1.04, "GSW": 1.01,
        "HOU": 0.98, "IND": 1.05, "LAC": 0.99, "LAL": 1.01, "MEM": 0.99,
        "MIA": 0.97, "MIL": 0.99, "MIN": 0.96, "NOP": 1.00, "NYK": 0.97,
        "OKC": 0.96, "ORL": 0.98, "PHI": 1.00, "PHX": 1.01, "POR": 1.04,
        "SAC": 1.02, "SAS": 1.04, "TOR": 1.02, "UTA": 1.05, "WAS": 1.06,
    }
    return factors.get(opponent, 1.0)

def nhl_defense_factor(opponent: str, market: str) -> float:
    # Lightweight opponent adjustment for NHL props. Above 1.00 = easier matchup.
    base = {
        "ANA": 1.06, "BOS": 0.97, "BUF": 1.02, "CGY": 1.01, "CAR": 0.95,
        "CBJ": 1.06, "CHI": 1.05, "COL": 0.99, "DAL": 0.97, "DET": 1.03,
        "EDM": 0.99, "FLA": 0.96, "LAK": 0.98, "MIN": 0.99, "MTL": 1.04,
        "NJD": 1.01, "NSH": 1.02, "NYI": 0.99, "NYR": 0.98, "OTT": 1.04,
        "PHI": 1.02, "PIT": 1.02, "SEA": 1.01, "SJS": 1.07, "STL": 1.02,
        "TBL": 1.00, "TOR": 1.00, "UTA": 1.03, "VAN": 0.99, "VGK": 0.97,
        "WPG": 0.96, "WSH": 1.01,
    }
    factor = base.get(opponent, 1.0)
    if market == "SHOTS":
        return round((factor * 0.7) + 0.3, 3)
    return factor

def sort_best_leg_board(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    if df.empty:
        return df

    working = df.copy()
    if "book_over_odds" in working.columns:
        balanced = working[
            (working["book_over_odds"].notna()) &
            (working["book_over_odds"] >= -250) &
            (working["book_over_odds"] <= 250)
        ].copy()
        if len(balanced) >= 5:
            working = balanced

    sort_cols = [c for c in ["leg_score", "ev", "model_prob", "book_over_odds"] if c in working.columns]
    if sort_cols:
        working = working.sort_values(by=sort_cols, ascending=[False] * len(sort_cols))

    if "leg_label" in working.columns and "book" in working.columns:
        working = working.drop_duplicates(subset=["leg_label", "book"])

    return working.head(top_n).reset_index(drop=True)

@st.cache_data(ttl=900, show_spinner=False)
def enrich_best_leg_board(df: pd.DataFrame, sport: str, max_rows: int = 36) -> pd.DataFrame:
    # Re-model only the top sportsbook rows so Best Legs and Best Parlays stay fast.
    if df.empty:
        return df

    enriched_rows = []
    defense_3pt = load_nba_defense_factor() if sport == "NBA" else {}

    for row in df.head(max_rows).to_dict("records"):
        try:
            player_name = row.get("player")
            line = row.get("line")
            odds = row.get("book_over_odds")
            market = row.get("market")
            team = row.get("team") or ""
            opponent = row.get("opponent") or ""

            if player_name is None or line is None or odds is None:
                enriched_rows.append(row)
                continue

            target = sportsbook_line_to_target(line)
            if target is None:
                enriched_rows.append(row)
                continue

            if sport == "NBA":
                pid = get_nba_player_id(player_name)
                if pid is None:
                    enriched_rows.append(row)
                    continue

                try:
                    team = get_nba_player_team(pid)
                    row["team"] = team
                except Exception:
                    pass

                games_df = fetch_nba_recent_games(pid)
                if games_df.empty:
                    enriched_rows.append(row)
                    continue

                if market == "3PT":
                    avg_stat = calculate_nba_weighted_avg(games_df, "FG3M")
                    factor = defense_3pt.get(opponent, 1.0)
                else:
                    avg_stat = calculate_nba_weighted_avg(games_df, "PTS")
                    factor = nba_points_defense_factor(opponent)

            else:
                pid = get_nhl_player_id(player_name)
                if pid is None:
                    enriched_rows.append(row)
                    continue

                team_lookup = get_nhl_player_team(player_name)
                if team_lookup:
                    team = team_lookup
                    row["team"] = team

                games_df = fetch_nhl_recent_games(pid)
                if games_df.empty:
                    enriched_rows.append(row)
                    continue

                if market == "SHOTS":
                    avg_stat = calculate_nhl_weighted_avg(games_df, "SHOTS")
                elif market == "GOALS":
                    avg_stat = calculate_nhl_weighted_avg(games_df, "GOALS")
                else:
                    avg_stat = calculate_nhl_weighted_avg(games_df, "POINTS")

                factor = nhl_defense_factor(opponent, market)

            if sport == "NBA":
                model_prob, expected_stat, model_factors = build_nba_model_v2_projection(games_df, market, opponent, target, line=line, odds=odds)
            else:
                model_prob, expected_stat, model_factors = build_nhl_model_v2_projection(games_df, market, opponent, target, line=line, odds=odds)

            implied_prob = american_to_implied_prob(odds)
            ev = calculate_ev(model_prob, american_to_decimal(odds))
            edge = round((model_prob / 100) - implied_prob, 4) if implied_prob is not None else None
            fair_odds = probability_to_fair_american(model_prob)

            row["expected_stat"] = round(expected_stat, 2)
            row["model_prob"] = model_prob
            row["fair_odds"] = fair_odds
            row["ev"] = ev
            row["edge"] = edge
            row["implied_prob"] = round(implied_prob, 4) if implied_prob is not None else None
            row["leg_score"] = score_best_leg_board(model_prob, odds)
            row["line_source"] = "Model v2: blended form + opportunity"
            row["model_factors"] = model_factors
            row["explanation"] = compact_factor_text(model_factors)

            enriched_rows.append(row)

        except Exception:
            enriched_rows.append(row)

    return pd.DataFrame(enriched_rows)


@st.cache_data(ttl=120, show_spinner=False)
def build_sport_level_prop_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
) -> pd.DataFrame:
    """Emergency fallback for Best Legs / Best Parlays only.

    This bypasses event-level props and asks the sport-level odds endpoint for player props directly.
    It is intentionally not used by dropdowns, pictures, or manual builders.
    """
    market_key_to_label = {}
    all_market_keys: List[str] = []
    for market_label, market_keys in market_specs:
        for mk in market_keys:
            market_key_to_label[mk] = market_label
            all_market_keys.append(mk)

    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": ",".join(all_market_keys),
        "oddsFormat": "american",
    }

    data, _ = odds_api_get(url, params)
    if not isinstance(data, list):
        return pd.DataFrame()

    reverse_nba = _reverse_nba_team_map()
    reverse_nhl = _reverse_nhl_team_map()
    rows: List[Dict[str, Any]] = []

    for event in data:
        if sport == "NBA":
            home_abbrev = reverse_nba.get(event.get("home_team", ""), "")
            away_abbrev = reverse_nba.get(event.get("away_team", ""), "")
        else:
            home_abbrev = reverse_nhl.get(event.get("home_team", ""), "")
            away_abbrev = reverse_nhl.get(event.get("away_team", ""), "")

        for bookmaker in event.get("bookmakers", []):
            book_key = bookmaker.get("key", "")

            for market in bookmaker.get("markets", []):
                market_key = market.get("key")
                if market_key not in market_key_to_label:
                    continue

                market_label = market_key_to_label[market_key]
                label_suffix = {
                    "PTS": "points",
                    "3PT": "3PT",
                    "POINTS": "points",
                    "SHOTS": "shots",
                    "GOALS": "goals",
                }.get(market_label, market_label.lower())

                for outcome in market.get("outcomes", []):
                    token_blob = " ".join([
                        str(outcome.get("name", "")),
                        str(outcome.get("description", "")),
                        str(outcome.get("label", "")),
                        str(outcome.get("side", "")),
                    ]).lower()

                    if "under" in token_blob and "over" not in token_blob:
                        continue

                    player_name = (outcome.get("participant") or outcome.get("description") or "").strip()
                    if normalize_name(player_name) in {"over", "under", ""}:
                        player_name = str(outcome.get("description") or outcome.get("participant") or "").strip()
                    if normalize_name(player_name) in {"over", "under", ""}:
                        continue

                    try:
                        line = float(outcome.get("point")) if outcome.get("point") is not None else None
                    except Exception:
                        line = None
                    if line is None:
                        continue

                    try:
                        odds = int(outcome.get("price")) if outcome.get("price") is not None else None
                    except Exception:
                        odds = None
                    if odds is None:
                        continue

                    implied_prob = american_to_implied_prob(odds)
                    model_prob = adjusted_best_leg_model_probability(implied_prob, odds)
                    expected_stat = estimate_expected_from_probability(line, model_prob)
                    fair_odds = probability_to_fair_american(model_prob) if model_prob is not None else None
                    ev = calculate_ev(model_prob, american_to_decimal(odds)) if model_prob is not None else None
                    edge = round((model_prob / 100) - implied_prob, 4) if model_prob is not None and implied_prob is not None else None
                    leg_score = score_best_leg_board(model_prob, odds)

                    rows.append(
                        {
                            "player": player_name,
                            "player_id": None,
                            "team": home_abbrev,
                            "opponent": away_abbrev,
                            "game_key": f"{away_abbrev}_at_{home_abbrev}",
                            "market": market_label,
                            "line": line,
                            "book_over_odds": odds,
                            "book_under_odds": None,
                            "book": book_key,
                            "expected_stat": expected_stat,
                            "model_prob": model_prob,
                            "fair_odds": fair_odds,
                            "ev": ev,
                            "implied_prob": round(implied_prob, 4) if implied_prob is not None else None,
                            "edge": edge,
                            "line_source": "Sport-level sportsbook fallback",
                            "leg_label": f"{player_name} over {safe_line_display(line)} {label_suffix}".strip(),
                            "leg_score": leg_score,
                        }
                    )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    balanced_df = df[
        (df["book_over_odds"].notna()) &
        (df["book_over_odds"] >= -275) &
        (df["book_over_odds"] <= 275)
    ].copy()

    if len(balanced_df) >= 5:
        df = balanced_df

    return (
        df.sort_values(by=["leg_score", "ev", "model_prob", "book_over_odds"], ascending=[False, False, False, False])
        .drop_duplicates(subset=["leg_label", "book"])
        .head(80)
        .reset_index(drop=True)
    )


def build_ranked_best_leg_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
    progress_bar=None,
    status_text=None,
    top_n: int = 20,
    enrich_rows: int = 36,
) -> pd.DataFrame:
    board = build_direct_candidate_board(
        sport_key,
        market_specs,
        sport,
        progress_bar=progress_bar,
        status_text=status_text,
    )

    # Critical fallback: if event-level props are empty, try sport-level prop odds.
    if board.empty:
        if status_text is not None:
            status_text.write(f"{sport}: event-level props were empty, trying sport-level props...")
        board = build_sport_level_prop_board(sport_key, market_specs, sport)

    if board.empty:
        return board

    raw_board = sort_best_leg_board(board, top_n=max(enrich_rows, top_n))
    enriched = enrich_best_leg_board(raw_board, sport, max_rows=enrich_rows)

    # If enrichment fails due to a temporary player/game-log API issue,
    # keep the working sportsbook board instead of returning an empty warning.
    if enriched.empty:
        return sort_best_leg_board(raw_board, top_n=top_n)

    return sort_best_leg_board(enriched, top_n=top_n)


def parse_time_to_minutes(value: Any) -> float:
    s = str(value).strip()
    if ":" in s:
        try:
            m, sec = s.split(":")
            return int(m) + int(sec) / 60.0
        except Exception:
            return 0.0
    try:
        return float(s)
    except Exception:
        return 0.0

def _odds_cache_key(url: str, params: Optional[Dict[str, Any]] = None) -> str:
    safe_params = params or {}
    # Sort params so the same request always maps to the same cache entry.
    payload = json.dumps({"url": url, "params": safe_params}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _odds_cache_day() -> str:
    # Uses the machine/deployment timezone. For your local laptop this will be your local day.
    return time.strftime("%Y-%m-%d")


def _odds_force_refresh_active() -> bool:
    try:
        return time.time() < float(st.session_state.get("odds_force_refresh_until", 0))
    except Exception:
        return False


def _format_cache_age(seconds: Optional[float]) -> str:
    if seconds is None:
        return "No snapshot yet"
    seconds = max(int(seconds), 0)
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def _read_odds_cache() -> Dict[str, Any]:
    try:
        if ODDS_CACHE_FILE.exists():
            with ODDS_CACHE_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _write_odds_cache(cache: Dict[str, Any]) -> None:
    try:
        ODDS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = ODDS_CACHE_FILE.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(cache, f)
        tmp_path.replace(ODDS_CACHE_FILE)
    except Exception:
        pass


def _odds_cache_ttl(url: str, params: Dict[str, Any]) -> int:
    url_l = str(url).lower()
    markets = str(params.get("markets", "")).lower()
    if url_l.endswith("/events") or "/events?" in url_l:
        return ODDS_CACHE_EVENTS_TTL_SECONDS
    if markets == "h2h":
        return ODDS_CACHE_H2H_TTL_SECONDS
    return ODDS_CACHE_DEFAULT_TTL_SECONDS


def _get_cached_odds_response(url: str, params: Dict[str, Any], allow_stale: bool = False) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
    cache = _read_odds_cache()
    key = _odds_cache_key(url, params)
    entry = cache.get(key)
    if not isinstance(entry, dict):
        return None, None

    age = time.time() - float(entry.get("saved_at", 0))
    ttl = _odds_cache_ttl(url, params)
    saved_day = str(entry.get("saved_day", ""))
    today = _odds_cache_day()

    # Daily snapshot mode: use the first successful pull for today's request all day.
    # Button clicks reuse this file instead of spending another API credit.
    is_today_snapshot = bool(ODDS_CACHE_DAILY_MODE and saved_day == today)

    if is_today_snapshot or age <= ttl or (allow_stale and age <= ODDS_CACHE_MAX_STALE_SECONDS):
        meta = dict(entry.get("meta") or {})
        meta["ok"] = True
        meta["cache_hit"] = True
        meta["cache_age_seconds"] = int(age)
        meta["cache_saved_day"] = saved_day or "legacy"
        meta["cache_stale"] = (not is_today_snapshot) and age > ttl
        meta["daily_snapshot"] = is_today_snapshot
        return entry.get("data"), meta
    return None, None


def _save_odds_response(url: str, params: Dict[str, Any], data: Any, meta: Dict[str, Any]) -> None:
    cache = _read_odds_cache()
    key = _odds_cache_key(url, params)
    clean_meta = dict(meta or {})
    clean_meta.pop("error", None)
    cache[key] = {
        "saved_at": time.time(),
        "saved_day": _odds_cache_day(),
        "url": url,
        "params": params,
        "data": data,
        "meta": clean_meta,
    }

    # Keep the cache from growing forever.
    if len(cache) > 500:
        items = sorted(cache.items(), key=lambda kv: float((kv[1] or {}).get("saved_at", 0)), reverse=True)
        cache = dict(items[:350])

    _write_odds_cache(cache)


def odds_api_get(url: str, params: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
    # 1) Daily local disk cache first. This is the main quota saver.
    # Manual refresh intentionally bypasses it for a short window.
    if not _odds_force_refresh_active():
        cached_data, cached_meta = _get_cached_odds_response(url, params, allow_stale=False)
        if cached_meta is not None:
            return cached_data, cached_meta

    meta = {"ok": False, "status_code": None, "error": None, "cache_hit": False, "force_refresh": _odds_force_refresh_active()}
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        meta["status_code"] = resp.status_code
        # Helpful quota headers when The Odds API provides them.
        meta["requests_remaining"] = resp.headers.get("x-requests-remaining")
        meta["requests_used"] = resp.headers.get("x-requests-used")
        meta["requests_last"] = resp.headers.get("x-requests-last")

        if not resp.ok:
            try:
                meta["error"] = resp.json()
            except Exception:
                meta["error"] = resp.text[:500]

            # 2) If quota is exhausted or the endpoint errors, use last good cached data.
            stale_data, stale_meta = _get_cached_odds_response(url, params, allow_stale=True)
            if stale_meta is not None:
                stale_meta["served_after_api_error"] = True
                stale_meta["api_error"] = meta.get("error")
                return stale_data, stale_meta
            return None, meta

        data = resp.json()
        meta["ok"] = True
        _save_odds_response(url, params, data, meta)
        return data, meta
    except Exception as e:
        meta["error"] = str(e)
        stale_data, stale_meta = _get_cached_odds_response(url, params, allow_stale=True)
        if stale_meta is not None:
            stale_meta["served_after_api_error"] = True
            stale_meta["api_error"] = meta.get("error")
            return stale_data, stale_meta
        return None, meta

@st.cache_data(ttl=120, show_spinner=False)
def get_sport_events(sport_key: str) -> List[Dict[str, Any]]:
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "bookmakers": PREFERRED_BOOKMAKERS,
        "markets": "h2h",
        "oddsFormat": "american",
    }
    data, _ = odds_api_get(url, params)
    return data if isinstance(data, list) else []

@st.cache_data(ttl=120, show_spinner=False)
def get_sport_events_for_prop_board(sport_key: str) -> List[Dict[str, Any]]:
    """Event source used only by Best Legs / Best Parlays.

    First tries the normal app event feed, then falls back to The Odds API events endpoint.
    This prevents the buttons from going empty when h2h odds/bookmaker filters are temporarily thin.
    """
    events = get_sport_events(sport_key)
    if events:
        return events

    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/events"
    params = {"apiKey": API_KEY}
    data, _ = odds_api_get(url, params)
    return data if isinstance(data, list) else []

@st.cache_data(ttl=120, show_spinner=False)
def get_prop_player_names_from_events(sport_key: str, market_keys: List[str]) -> List[str]:
    names: List[str] = []
    seen = set()

    events = get_sport_events(sport_key)
    for event in events:
        event_id = event.get("id")
        if not event_id:
            continue
        event_data = get_event_props(sport_key, event_id, market_keys).get("data", {})
        if not isinstance(event_data, dict):
            continue
        for bookmaker in event_data.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") not in market_keys:
                    continue
                for outcome in market.get("outcomes", []):
                    raw_name = (
                        outcome.get("participant")
                        or outcome.get("description")
                        or ""
                    ).strip()
                    norm = normalize_name(raw_name)
                    if raw_name and norm and norm not in seen:
                        seen.add(norm)
                        names.append(raw_name)
    return sorted(names)


@st.cache_data(ttl=120, show_spinner=False)
def get_event_props(sport_key: str, event_id: str, market_keys: List[str]) -> Dict[str, Any]:
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{event_id}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "bookmakers": PREFERRED_BOOKMAKERS,
        "markets": ",".join(market_keys),
        "oddsFormat": "american",
    }
    data, meta = odds_api_get(url, params)
    return {"data": data if isinstance(data, dict) else {}, "meta": meta}

def extract_main_lines_for_market(event_data: Dict[str, Any], target_market_keys: List[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    def american_prob(odds: Optional[int]) -> Optional[float]:
        if odds is None:
            return None
        if odds > 0:
            return 100 / (odds + 100)
        return abs(odds) / (abs(odds) + 100)

    def closeness_to_even(over_price: Optional[int], under_price: Optional[int]) -> float:
        op = american_prob(over_price)
        up = american_prob(under_price)
        if op is None or up is None:
            return 999.0
        return abs(op - 0.5) + abs(up - 0.5)

    for bookmaker in event_data.get("bookmakers", []):
        book_key = bookmaker.get("key", "")
        player_market_candidates: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

        for market in bookmaker.get("markets", []):
            market_key = market.get("key")
            if market_key not in target_market_keys:
                continue

            grouped: Dict[Tuple[str, float], Dict[str, Any]] = {}

            for outcome in market.get("outcomes", []):
                participant = outcome.get("participant") or outcome.get("description") or ""
                participant_norm = normalize_name(participant)
                if not participant_norm:
                    continue

                try:
                    point = float(outcome.get("point")) if outcome.get("point") is not None else None
                except Exception:
                    point = None
                if point is None:
                    continue

                try:
                    price = int(outcome.get("price")) if outcome.get("price") is not None else None
                except Exception:
                    price = None

                name = normalize_name(outcome.get("name", ""))
                desc = normalize_name(outcome.get("description", ""))
                label = normalize_name(outcome.get("label", ""))
                side = normalize_name(outcome.get("side", ""))

                over_hit = "over" in {name, desc, label, side}
                under_hit = "under" in {name, desc, label, side}

                key = (participant_norm, point)
                if key not in grouped:
                    grouped[key] = {
                        "player_name_raw": participant,
                        "point": point,
                        "over": None,
                        "under": None,
                        "market_key": market_key,
                    }

                if over_hit:
                    grouped[key]["over"] = price
                elif under_hit:
                    grouped[key]["under"] = price

            for (_, _), info in grouped.items():
                if info["over"] is None or info["under"] is None:
                    continue

                score = closeness_to_even(info["over"], info["under"])
                player_key = (normalize_name(info["player_name_raw"]), book_key)

                candidate = {
                    "player_name_raw": info["player_name_raw"],
                    "line": info["point"],
                    "over_odds": info["over"],
                    "under_odds": info["under"],
                    "book_key": book_key,
                    "market_key": info["market_key"],
                    "score": score,
                }

                player_market_candidates.setdefault(player_key, []).append(candidate)

        for _, candidates in player_market_candidates.items():
            best = min(candidates, key=lambda x: x["score"])
            rows.append(best)

    return rows

def is_valid_parlay_combo(legs: List[Dict[str, Any]]) -> bool:
    players_used = [leg["player"] for leg in legs]
    if len(players_used) != len(set(players_used)):
        return False

    labels = [leg["leg_label"] for leg in legs]
    if len(labels) != len(set(labels)):
        return False

    game_keys = [leg["game_key"] for leg in legs]
    if any(game_keys.count(g) > 2 for g in set(game_keys)):
        return False

    return True

def correlation_penalty(legs: List[Dict[str, Any]], same_game_penalty: float = 0.08, same_team_penalty: float = 0.05) -> float:
    penalty = 0.0
    game_keys = [leg["game_key"] for leg in legs]
    teams = [leg["team"] for leg in legs]

    for g in set(game_keys):
        count = game_keys.count(g)
        if count == 2:
            penalty += same_game_penalty
        elif count >= 3:
            penalty += 0.20

    for t in set(teams):
        if teams.count(t) >= 2:
            penalty += same_team_penalty

    return round(penalty, 3)

def calculate_parlay_metrics(legs: List[Dict[str, Any]], same_game_penalty: float = 0.08, same_team_penalty: float = 0.05) -> Dict[str, Any]:
    if not legs:
        return {}

    combined_prob_decimal = 1.0
    combined_decimal_odds = 1.0

    for leg in legs:
        leg_prob = leg.get("model_prob")
        leg_odds = leg.get("book_over_odds")
        dec_odds = american_to_decimal(leg_odds)
        if leg_prob is None or dec_odds is None:
            return {}
        combined_prob_decimal *= leg_prob / 100
        combined_decimal_odds *= dec_odds

    combined_prob_pct = combined_prob_decimal * 100
    parlay_ev = round(combined_prob_decimal * (combined_decimal_odds - 1) - (1 - combined_prob_decimal), 3)
    payout_multiple = round(combined_decimal_odds - 1, 2)
    fair_parlay_odds = probability_to_fair_american(round(combined_prob_pct, 2))
    penalty = correlation_penalty(legs, same_game_penalty, same_team_penalty)
    payout_factor = min(payout_multiple / 5, 1.0)

    parlay_score = round(
        ((combined_prob_decimal * 0.4) + (max(parlay_ev, 0) * 0.4) + (payout_factor * 0.2)) - penalty,
        4,
    )

    return {
        "legs": legs,
        "parlay_size": len(legs),
        "combined_prob": round(combined_prob_pct, 2),
        "combined_decimal_odds": round(combined_decimal_odds, 3),
        "combined_american_odds": decimal_to_american(combined_decimal_odds),
        "combined_fair_odds": fair_parlay_odds,
        "parlay_ev": parlay_ev,
        "correlation_penalty": penalty,
        "parlay_score": parlay_score,
        "payout_multiple": payout_multiple,
    }

def generate_parlay_candidates(legs_df: pd.DataFrame, parlay_size: int = 2, same_game_penalty: float = 0.08, same_team_penalty: float = 0.05) -> List[Dict[str, Any]]:
    if legs_df.empty or len(legs_df) < parlay_size:
        return []

    leg_dicts = legs_df.to_dict("records")
    candidates: List[Dict[str, Any]] = []

    for combo in combinations(leg_dicts, parlay_size):
        combo_list = list(combo)
        if not is_valid_parlay_combo(combo_list):
            continue
        metrics = calculate_parlay_metrics(combo_list, same_game_penalty, same_team_penalty)
        if metrics:
            candidates.append(metrics)

    return candidates

def filter_parlay_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filtered = []
    for c in candidates:
        size = c.get("parlay_size")
        prob = c.get("combined_prob", 0)
        ev = c.get("parlay_ev", 0)
        if size == 2 and prob >= 32 and ev > 0.05:
            filtered.append(c)
        elif size == 3 and prob >= 18 and ev > 0.08:
            filtered.append(c)
    return filtered

def _shared_leg_count(a: Dict[str, Any], b: Dict[str, Any]) -> int:
    a_labels = {leg["leg_label"] for leg in a["legs"]}
    b_labels = {leg["leg_label"] for leg in b["legs"]}
    return len(a_labels.intersection(b_labels))

def select_top_parlays(candidates: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    if not candidates:
        return {}

    sorted_by_score = sorted(candidates, key=lambda x: x["parlay_score"], reverse=True)
    sorted_by_prob = sorted(candidates, key=lambda x: x["combined_prob"], reverse=True)
    sorted_by_ev = sorted(candidates, key=lambda x: x["parlay_ev"], reverse=True)

    selections: Dict[str, Dict[str, Any]] = {}
    balanced = sorted_by_score[0]
    selections["balanced"] = balanced

    safe_candidates = [
        c for c in sorted_by_prob
        if c["parlay_ev"] > 0.03 and c["payout_multiple"] > 1.0 and _shared_leg_count(c, balanced) <= 1
    ]
    if safe_candidates:
        selections["safe"] = safe_candidates[0]

    value_candidates = [
        c for c in sorted_by_ev
        if c["combined_prob"] >= 20
        and _shared_leg_count(c, balanced) <= 1
        and ("safe" not in selections or _shared_leg_count(c, selections["safe"]) <= 1)
    ]
    if value_candidates:
        selections["value"] = value_candidates[0]

    return selections

def select_top_parlays_with_fallback(candidates: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    # First try the stricter original logic.
    strict = select_top_parlays(filter_parlay_candidates(candidates))
    if strict:
        return strict

    # If strict filters are too tight, still return the best available parlays.
    # This keeps the button useful instead of showing "No parlays passed..."
    if not candidates:
        return {}

    playable = [
        c for c in candidates
        if c.get("combined_prob", 0) >= 12
        and c.get("payout_multiple", 0) >= 0.70
        and c.get("combined_american_odds") is not None
    ]

    if not playable:
        playable = candidates

    sorted_by_score = sorted(playable, key=lambda x: x.get("parlay_score", 0), reverse=True)
    sorted_by_prob = sorted(playable, key=lambda x: x.get("combined_prob", 0), reverse=True)
    sorted_by_value = sorted(
        playable,
        key=lambda x: (x.get("parlay_ev", -999), x.get("payout_multiple", 0), x.get("combined_prob", 0)),
        reverse=True,
    )

    selections: Dict[str, Dict[str, Any]] = {}
    if sorted_by_score:
        selections["balanced"] = sorted_by_score[0]

    if sorted_by_prob:
        for candidate in sorted_by_prob:
            if "balanced" not in selections or _shared_leg_count(candidate, selections["balanced"]) <= 1:
                selections["safe"] = candidate
                break

    if sorted_by_value:
        for candidate in sorted_by_value:
            if "balanced" in selections and _shared_leg_count(candidate, selections["balanced"]) > 1:
                continue
            if "safe" in selections and _shared_leg_count(candidate, selections["safe"]) > 1:
                continue
            selections["value"] = candidate
            break

    return selections


# =========================
# NBA SAFE +200 ALT POINTS BUILDER
# =========================
# Purpose: find NBA alt-player-points style parlays that target 80%+ model probability
# and +200 or better sportsbook payout. This uses the same odds/model layer as the
# Best Legs button, but it intentionally keeps safer/heavily juiced alt lines because
# those are usually required for 80%+ hit-rate builds.

def _is_plus_200_or_better(american_odds: Optional[int]) -> bool:
    return american_odds is not None and american_odds >= 200


def _safe_plus200_combo_score(c: Dict[str, Any]) -> float:
    prob = float(c.get("combined_prob", 0) or 0)
    odds = c.get("combined_american_odds")
    ev = float(c.get("parlay_ev", 0) or 0)
    payout = float(c.get("payout_multiple", 0) or 0)
    penalty = float(c.get("correlation_penalty", 0) or 0)

    odds_bonus = 0.0
    if odds is not None:
        # Prefer +200 to +600 range for this mode; huge longshots are not the goal.
        if 200 <= odds <= 450:
            odds_bonus = 0.20
        elif odds > 450:
            odds_bonus = 0.08

    return round((prob / 100 * 0.55) + (max(ev, 0) * 0.25) + (min(payout / 3, 1) * 0.15) + odds_bonus - penalty, 4)


def build_nba_safe_plus200_leg_board(progress_bar=None, status_text=None, top_n: int = 32) -> pd.DataFrame:
    """Build a candidate board specifically for safe +200 NBA alt-points parlays.

    This intentionally does NOT use sort_best_leg_board early because that helper filters
    out many heavy-favorite alt lines. For this mode, heavy favorite alt lines can be useful
    when combined into a +200 parlay.
    """
    market_specs = [("PTS", NBA_POINTS_MARKET_KEYS)]

    if status_text is not None:
        status_text.write("Loading NBA alt-points lines for Safe +200 builder...")

    board = build_direct_candidate_board(
        NBA_SPORT_KEY,
        market_specs,
        "NBA",
        progress_bar=progress_bar,
        status_text=status_text,
    )

    if board.empty:
        if status_text is not None:
            status_text.write("Trying sport-level NBA alt-points fallback...")
        board = build_sport_level_prop_board(NBA_SPORT_KEY, market_specs, "NBA")

    if board.empty:
        return pd.DataFrame()

    board = board.copy()
    board = board[board.get("market", "") == "PTS"].copy() if "market" in board.columns else board
    board = board[board["book_over_odds"].notna()].copy()

    # Keep safer alt lines, but remove absurdly unplayable prices and duplicate players/lines.
    board = board[(board["book_over_odds"] >= -1400) & (board["book_over_odds"] <= 250)].copy()
    if board.empty:
        return pd.DataFrame()

    # Prioritize low lines and high baseline probability before expensive enrichment.
    board["_safe_seed_score"] = (
        pd.to_numeric(board.get("model_prob", 0), errors="coerce").fillna(0) * 1.0
        - pd.to_numeric(board.get("line", 99), errors="coerce").fillna(99) * 0.35
        + pd.to_numeric(board.get("book_over_odds", -999), errors="coerce").fillna(-999).clip(lower=-900, upper=250) / 2500
    )
    board = board.sort_values(by=["_safe_seed_score"], ascending=False).drop_duplicates(subset=["player", "line", "book"]).head(80)

    if status_text is not None:
        status_text.write("Re-modeling top safe alt-points legs with recent form + defense...")

    try:
        enriched = enrich_best_leg_board(board.drop(columns=["_safe_seed_score"], errors="ignore"), "NBA", max_rows=80)
    except Exception:
        enriched = pd.DataFrame()

    if enriched.empty:
        enriched = board.drop(columns=["_safe_seed_score"], errors="ignore")

    enriched = enriched.copy()
    enriched = enriched[enriched["model_prob"].notna() & enriched["book_over_odds"].notna()].copy()
    enriched = enriched[(enriched["model_prob"] >= 70) & (enriched["book_over_odds"] >= -1400)].copy()

    if enriched.empty:
        return pd.DataFrame()

    # For safe mode, rank by probability first, then odds/EV. Do not drop heavy favorites.
    enriched["safe_plus200_leg_score"] = (
        pd.to_numeric(enriched["model_prob"], errors="coerce").fillna(0) / 100 * 0.70
        + pd.to_numeric(enriched.get("ev", 0), errors="coerce").fillna(0).clip(lower=0) * 0.15
        + (pd.to_numeric(enriched["book_over_odds"], errors="coerce").fillna(-999).clip(lower=-900, upper=250) + 900) / 1150 * 0.15
    )

    return (
        enriched.sort_values(by=["safe_plus200_leg_score", "model_prob", "book_over_odds"], ascending=[False, False, False])
        .drop_duplicates(subset=["player", "line"])
        .head(top_n)
        .reset_index(drop=True)
    )


def select_nba_safe_plus200_parlays(candidates: List[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    """Return 3 safe +200 builds when available, plus closest misses for transparency."""
    if not candidates:
        return {}, []

    valid = []
    for c in candidates:
        if c.get("combined_american_odds") is None:
            continue
        c = dict(c)
        c["safe_plus200_score"] = _safe_plus200_combo_score(c)
        valid.append(c)

    if not valid:
        return {}, []

    qualified = [
        c for c in valid
        if c.get("combined_prob", 0) >= 80
        and _is_plus_200_or_better(c.get("combined_american_odds"))
    ]

    selections: Dict[str, Dict[str, Any]] = {}
    pool = qualified

    if pool:
        by_prob = sorted(pool, key=lambda x: (x.get("combined_prob", 0), x.get("safe_plus200_score", 0)), reverse=True)
        by_value = sorted(pool, key=lambda x: (x.get("parlay_ev", -999), x.get("combined_prob", 0)), reverse=True)
        by_balanced = sorted(pool, key=lambda x: x.get("safe_plus200_score", 0), reverse=True)

        selections["safe_plus200"] = by_prob[0]
        for cand in by_balanced:
            if _shared_leg_count(cand, selections["safe_plus200"]) <= 1:
                selections["balanced_plus200"] = cand
                break
        if "balanced_plus200" not in selections and by_balanced:
            selections["balanced_plus200"] = by_balanced[0]

        for cand in by_value:
            if _shared_leg_count(cand, selections["safe_plus200"]) <= 1 and _shared_leg_count(cand, selections["balanced_plus200"]) <= 1:
                selections["value_plus200"] = cand
                break
        if "value_plus200" not in selections and by_value:
            selections["value_plus200"] = by_value[0]

    # Closest misses help when the market cannot realistically offer 80% and +200 today.
    closest = sorted(
        valid,
        key=lambda x: (
            max(0, 80 - x.get("combined_prob", 0)) * 2.0
            + (0 if _is_plus_200_or_better(x.get("combined_american_odds")) else 25),
            -x.get("combined_prob", 0),
            -x.get("payout_multiple", 0),
        ),
    )[:5]

    return selections, closest


def render_safe_plus200_parlays(selected: Dict[str, Dict[str, Any]], closest: List[Dict[str, Any]]):
    if not selected:
        st.warning("No NBA parlay hit both targets today: 80%+ model probability and +200 or better sportsbook odds.")
        if closest:
            st.info("Closest available builds are shown below so you can still see what the market/model found.")
            fallback_selected = {"closest": closest[0]}
        else:
            return
    else:
        fallback_selected = selected

    label_map = {
        "safe_plus200": "Safest 80%+ / +200 Parlay",
        "balanced_plus200": "Balanced 80%+ / +200 Parlay",
        "value_plus200": "Best Value 80%+ / +200 Parlay",
        "closest": "Closest Available Safe +200 Build",
    }

    for key in ["safe_plus200", "balanced_plus200", "value_plus200", "closest"]:
        if key not in fallback_selected:
            continue
        p = fallback_selected[key]
        st.markdown("---")
        st.subheader(label_map[key])

        hit_target = p.get("combined_prob", 0) >= 80
        odds_target = _is_plus_200_or_better(p.get("combined_american_odds"))
        target_text = "✅ Hits both targets" if hit_target and odds_target else "⚠️ Closest available — misses one target"
        st.caption(target_text)

        top = st.columns(4)
        top[0].markdown(metric_card("Hit probability", f"{p['combined_prob']}%", "good" if hit_target else "neutral"), unsafe_allow_html=True)
        top[1].markdown(metric_card("Book odds", safe_odds_display(p["combined_american_odds"]), "good" if odds_target else "neutral"), unsafe_allow_html=True)
        top[2].markdown(metric_card("Parlay EV", str(p["parlay_ev"]), "good" if p["parlay_ev"] > 0 else "bad"), unsafe_allow_html=True)
        top[3].markdown(metric_card("Payout multiple", f"{p['payout_multiple']}x"), unsafe_allow_html=True)

        st.write(f"**Fair odds:** {safe_odds_display(p['combined_fair_odds'])}")
        st.write(f"**Correlation penalty:** {p['correlation_penalty']}")

        legs_table = pd.DataFrame(
            [
                {
                    "Leg": leg["leg_label"],
                    "Team": leg.get("team", ""),
                    "Opp": leg.get("opponent", ""),
                    "Book": leg.get("book", ""),
                    "Book Odds": safe_odds_display(leg.get("book_over_odds")),
                    "Model Prob %": leg.get("model_prob"),
                    "Expected": leg.get("expected_stat"),
                    "EV": leg.get("ev"),
                }
                for leg in p["legs"]
            ]
        )
        st.dataframe(legs_table, use_container_width=True, hide_index=True)


# =========================
# NBA ENGINE
# =========================

@st.cache_data(ttl=120, show_spinner=False)
def get_nba_scoreboard_games() -> List[Dict[str, Any]]:
    try:
        board = scoreboard.ScoreBoard()
        data = board.get_dict()
        games = data.get("scoreboard", {}).get("games", [])
        return games if isinstance(games, list) else []
    except Exception:
        return []

def get_nba_confirmed_opponent_today(team_abbrev: str) -> Optional[str]:
    for game in get_nba_scoreboard_games():
        home_team = game.get("homeTeam", {})
        away_team = game.get("awayTeam", {})
        home_abbrev = home_team.get("teamTricode")
        away_abbrev = away_team.get("teamTricode")
        if team_abbrev == home_abbrev:
            return away_abbrev
        if team_abbrev == away_abbrev:
            return home_abbrev
    return None

@st.cache_data(ttl=3600, show_spinner=False)
def get_nba_all_players() -> List[Dict[str, Any]]:
    return players.get_players()

def get_nba_all_player_names() -> List[str]:
    active_names = [p["full_name"] for p in get_nba_all_players() if p.get("is_active")]
    active_by_norm = {normalize_name(name): name for name in active_names}

    prop_names = get_prop_player_names_from_events(
        NBA_SPORT_KEY,
        NBA_POINTS_MARKET_KEYS + NBA_THREES_MARKET_KEYS,
    )

    matched_names = []
    seen = set()
    for raw_name in prop_names:
        official_name = active_by_norm.get(normalize_name(raw_name))
        if official_name and official_name not in seen:
            seen.add(official_name)
            matched_names.append(official_name)

    if matched_names:
        return sorted(matched_names)

    return sorted(active_names)

def get_nba_player_id(name: str) -> Optional[int]:
    for p in get_nba_all_players():
        if p["full_name"] == name:
            return p["id"]
    return None

@st.cache_data(ttl=3600, show_spinner=False)
def get_nba_player_team(pid: int) -> str:
    info = commonplayerinfo.CommonPlayerInfo(player_id=pid).get_data_frames()[0]
    return str(info.loc[0, "TEAM_ABBREVIATION"])

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_nba_recent_games(pid: int, num_games: int = MAX_RECENT_GAMES) -> pd.DataFrame:
    gamelog = playergamelog.PlayerGameLog(player_id=pid, season=NBA_SEASON)
    df = gamelog.get_data_frames()[0]
    fg3m_col = "FG3M" if "FG3M" in df.columns else None
    fga3_col = "FGA3" if "FGA3" in df.columns else ("FG3A" if "FG3A" in df.columns else None)
    if not fg3m_col or not fga3_col or "PTS" not in df.columns:
        return pd.DataFrame()
    df = df[["GAME_DATE", "MATCHUP", "MIN", "PTS", fg3m_col, fga3_col]].copy()
    df = df.rename(columns={fg3m_col: "FG3M", fga3_col: "FGA3"})
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    return df.head(num_games)

def calculate_nba_weighted_avg(df: pd.DataFrame, stat: str) -> float:
    df = df[df["MIN"] > 15].copy()
    if df.empty:
        return 0.0
    avg5 = df.head(5)[stat].mean()
    avg10 = df.head(10)[stat].mean()
    weighted = (avg5 * 0.6) + (avg10 * 0.4)
    if stat == "FG3M":
        attempts = df["FGA3"].sum()
        eff = (df["FG3M"].sum() / attempts) if attempts > 0 else 0
        return weighted * (0.8 + eff)
    return float(weighted)

def load_nba_defense_factor() -> Dict[str, float]:
    df = pd.DataFrame(
        {
            "TEAM": [
                "ATL","BOS","BKN","CHA","CHI","CLE","DAL","DEN","DET","GSW",
                "HOU","IND","LAC","LAL","MEM","MIA","MIL","MIN","NOP","NYK",
                "OKC","ORL","PHI","PHX","POR","SAC","SAS","TOR","UTA","WAS"
            ],
            "3PA_ALLOWED": [
                12.2,10.6,11.8,12.5,11.1,11.3,11.9,10.8,12.4,11.2,
                12.7,11.5,11.4,11.3,10.9,10.7,11.2,11.8,11.6,10.9,
                12.0,11.7,11.0,11.3,11.9,11.6,11.5,11.4,11.2,12.3
            ],
        }
    )
    league_avg = df["3PA_ALLOWED"].mean()
    df["FACTOR"] = df["3PA_ALLOWED"] / league_avg
    return dict(zip(df["TEAM"], df["FACTOR"]))

def calculate_poisson_probability(avg: float, factor: float, target: int) -> Tuple[float, float]:
    adj = avg * factor
    cumulative = 0.0
    for k in range(int(target)):
        cumulative += (adj ** k * math.exp(-adj)) / math.factorial(k)
    return round((1 - cumulative) * 100, 2), adj


# =========================
# MODEL V2: BLENDED FORM + OPPORTUNITY ENGINE
# =========================

def _safe_numeric_series(df: pd.DataFrame, col: str) -> pd.Series:
    if df.empty or col not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[col], errors="coerce").dropna()

def _avg_window(df: pd.DataFrame, col: str, n: int) -> float:
    s = _safe_numeric_series(df.head(n), col)
    return float(s.mean()) if not s.empty else 0.0

def _blend_recent_form(df: pd.DataFrame, stat: str) -> Dict[str, float]:
    season_avg = _avg_window(df, stat, len(df))
    last10_avg = _avg_window(df, stat, min(10, len(df)))
    last5_avg = _avg_window(df, stat, min(5, len(df)))
    blended = (season_avg * 0.35) + (last10_avg * 0.35) + (last5_avg * 0.30)
    return {"season_avg": round(season_avg, 2), "last10_avg": round(last10_avg, 2), "last5_avg": round(last5_avg, 2), "blended_form": round(blended, 2)}

def _calibrated_probability_from_projection(projected_stat: float, target: int, implied_prob: Optional[float] = None) -> float:
    raw_prob, _ = calculate_poisson_probability(projected_stat, 1.0, target)
    calibrated = 50 + ((raw_prob - 50) * 0.82)
    if implied_prob is not None:
        calibrated = (calibrated * 0.82) + ((implied_prob * 100) * 0.18)
    return round(max(min(calibrated, 92.0), 4.0), 2)

def _factor_pct_text(factor: float) -> str:
    return f"{((factor - 1.0) * 100):+.1f}%"

def build_nba_model_v2_projection(games_df: pd.DataFrame, market: str, opponent: str, target: int, line: Optional[float] = None, odds: Optional[int] = None) -> Tuple[float, float, Dict[str, Any]]:
    df = games_df.copy()
    df["MIN"] = pd.to_numeric(df.get("MIN", 0), errors="coerce").fillna(0)
    df = df[df["MIN"] > 10].copy()
    if df.empty:
        return 4.0, 0.0, {"model_version": "Model v2", "note": "No usable recent minutes found."}

    stat = "FG3M" if market == "3PT" else "PTS"
    form = _blend_recent_form(df, stat)
    season_min = _avg_window(df, "MIN", len(df))
    last10_min = _avg_window(df, "MIN", min(10, len(df)))
    last5_min = _avg_window(df, "MIN", min(5, len(df)))
    expected_minutes = (season_min * 0.30) + (last10_min * 0.35) + (last5_min * 0.35)
    total_stat = _safe_numeric_series(df, stat).sum()
    total_minutes = max(_safe_numeric_series(df, "MIN").sum(), 1.0)
    stat_per_min = float(total_stat / total_minutes)
    opportunity_projection = stat_per_min * expected_minutes

    if market == "3PT":
        attempts = _safe_numeric_series(df, "FGA3").sum() if "FGA3" in df.columns else 0.0
        makes = _safe_numeric_series(df, "FG3M").sum() if "FG3M" in df.columns else 0.0
        three_eff = (makes / attempts) if attempts else 0.0
        volume_factor = max(min(0.85 + three_eff, 1.18), 0.82)
        matchup_factor = load_nba_defense_factor().get(opponent, 1.0)
    else:
        three_eff = None
        volume_factor = 1.0
        matchup_factor = nba_points_defense_factor(opponent)

    projected_stat = ((form["blended_form"] * 0.55) + (opportunity_projection * 0.45)) * matchup_factor * volume_factor
    implied_prob = american_to_implied_prob(odds)
    model_prob = _calibrated_probability_from_projection(projected_stat, target, implied_prob)
    factors = {
        "model_version": "Model v2: blended form + opportunity",
        "season_avg": form["season_avg"], "last10_avg": form["last10_avg"], "last5_avg": form["last5_avg"],
        "expected_minutes": round(expected_minutes, 1), "stat_per_min": round(stat_per_min, 3),
        "opportunity_projection": round(opportunity_projection, 2), "opponent_factor": round(matchup_factor, 3),
        "opponent_adjustment": _factor_pct_text(matchup_factor), "volume_factor": round(volume_factor, 3),
        "volume_adjustment": _factor_pct_text(volume_factor), "sportsbook_line": line, "target_needed": target,
        "book_odds": odds, "market_implied_prob": round(implied_prob * 100, 2) if implied_prob is not None else None,
        "projected_stat": round(projected_stat, 2), "model_prob": model_prob,
    }
    if three_eff is not None:
        factors["three_point_efficiency"] = round(three_eff, 3)
    factors["explanation_summary"] = (
        f"Projected {round(projected_stat, 2)} vs target {target}. "
        f"Blend uses season {form['season_avg']}, last 10 {form['last10_avg']}, last 5 {form['last5_avg']}, "
        f"plus expected minutes {round(expected_minutes, 1)} and opponent adjustment {_factor_pct_text(matchup_factor)}."
    )
    return model_prob, round(projected_stat, 2), factors

def build_nhl_model_v2_projection(games_df: pd.DataFrame, market: str, opponent: str, target: int, line: Optional[float] = None, odds: Optional[int] = None) -> Tuple[float, float, Dict[str, Any]]:
    df = games_df.copy()
    df["TOI_MIN"] = pd.to_numeric(df.get("TOI_MIN", 0), errors="coerce").fillna(0)
    df = df[df["TOI_MIN"] > 6].copy()
    if df.empty:
        return 4.0, 0.0, {"model_version": "Model v2", "note": "No usable recent TOI found."}

    stat = "POINTS" if market == "POINTS" else ("SHOTS" if market == "SHOTS" else "GOALS")
    form = _blend_recent_form(df, stat)
    season_toi = _avg_window(df, "TOI_MIN", len(df))
    last10_toi = _avg_window(df, "TOI_MIN", min(10, len(df)))
    last5_toi = _avg_window(df, "TOI_MIN", min(5, len(df)))
    expected_toi = (season_toi * 0.30) + (last10_toi * 0.35) + (last5_toi * 0.35)
    total_stat = _safe_numeric_series(df, stat).sum()
    total_toi = max(_safe_numeric_series(df, "TOI_MIN").sum(), 1.0)
    stat_per_min = float(total_stat / total_toi)
    opportunity_projection = stat_per_min * expected_toi
    matchup_factor = nhl_defense_factor(opponent, market)
    if market == "GOALS":
        projected_stat = ((form["blended_form"] * 0.70) + (opportunity_projection * 0.30)) * matchup_factor
    else:
        projected_stat = ((form["blended_form"] * 0.55) + (opportunity_projection * 0.45)) * matchup_factor
    implied_prob = american_to_implied_prob(odds)
    model_prob = _calibrated_probability_from_projection(projected_stat, target, implied_prob)
    factors = {
        "model_version": "Model v2: blended form + opportunity",
        "season_avg": form["season_avg"], "last10_avg": form["last10_avg"], "last5_avg": form["last5_avg"],
        "expected_toi": round(expected_toi, 1), "stat_per_min": round(stat_per_min, 3),
        "opportunity_projection": round(opportunity_projection, 2), "opponent_factor": round(matchup_factor, 3),
        "opponent_adjustment": _factor_pct_text(matchup_factor), "sportsbook_line": line, "target_needed": target,
        "book_odds": odds, "market_implied_prob": round(implied_prob * 100, 2) if implied_prob is not None else None,
        "projected_stat": round(projected_stat, 2), "model_prob": model_prob,
    }
    factors["explanation_summary"] = (
        f"Projected {round(projected_stat, 2)} vs target {target}. "
        f"Blend uses season {form['season_avg']}, last 10 {form['last10_avg']}, last 5 {form['last5_avg']}, "
        f"plus expected TOI {round(expected_toi, 1)} and opponent adjustment {_factor_pct_text(matchup_factor)}."
    )
    return model_prob, round(projected_stat, 2), factors

def compact_factor_text(factors: Any) -> str:
    if not isinstance(factors, dict):
        return "Model details unavailable for this leg."
    return str(factors.get("explanation_summary") or "Model details unavailable for this leg.")

def build_nba_candidate_legs(progress_bar=None, status_text=None) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    defense_map = load_nba_defense_factor()
    today_games = get_nba_scoreboard_games()
    if not today_games:
        return pd.DataFrame()

    all_player_names = get_nba_all_player_names()
    total_games = len(today_games)

    for idx, game in enumerate(today_games):
        if progress_bar is not None:
            progress_bar.progress((idx + 1) / total_games, text="Scanning NBA games for props...")
        if status_text is not None:
            home = game.get("homeTeam", {}).get("teamTricode", "")
            away = game.get("awayTeam", {}).get("teamTricode", "")
            status_text.write(f"NBA game {idx + 1} of {total_games}: {away} @ {home}")

        home_abbrev = game.get("homeTeam", {}).get("teamTricode")
        away_abbrev = game.get("awayTeam", {}).get("teamTricode")
        if not home_abbrev or not away_abbrev:
            continue

        events = get_sport_events(NBA_SPORT_KEY)
        event = None
        for e in events:
            home_team = e.get("home_team", "")
            away_team = e.get("away_team", "")
            if home_abbrev in NBA_TEAM_NAME_MAP and away_abbrev in NBA_TEAM_NAME_MAP:
                if (
                    home_team == NBA_TEAM_NAME_MAP[home_abbrev] and away_team == NBA_TEAM_NAME_MAP[away_abbrev]
                ) or (
                    home_team == NBA_TEAM_NAME_MAP[away_abbrev] and away_team == NBA_TEAM_NAME_MAP[home_abbrev]
                ):
                    event = e
                    break
        if not event:
            continue

        props_resp = get_event_props(
            NBA_SPORT_KEY,
            event["id"],
            NBA_POINTS_MARKET_KEYS + NBA_THREES_MARKET_KEYS,
        )
        event_data = props_resp.get("data", {})
        if not event_data or not event_data.get("bookmakers"):
            continue

        for market_name, market_keys in [("3PT", NBA_THREES_MARKET_KEYS), ("PTS", NBA_POINTS_MARKET_KEYS)]:
            market_rows = extract_main_lines_for_market(event_data, market_keys)
            usable_rows = []
            for row in market_rows:
                if any(player_name_matches(row["player_name_raw"], name) for name in all_player_names):
                    usable_rows.append(row)

            usable_rows = sorted(usable_rows, key=lambda r: abs(r.get("line", 999)))[:MAX_PROP_PLAYERS_PER_GAME_PER_MARKET]

            for row in usable_rows:
                player_name = row["player_name_raw"]
                pid = get_nba_player_id(player_name)
                if pid is None:
                    continue

                try:
                    team_abbrev = get_nba_player_team(pid)
                except Exception:
                    continue

                if team_abbrev not in {home_abbrev, away_abbrev}:
                    continue

                opponent = away_abbrev if team_abbrev == home_abbrev else home_abbrev

                try:
                    games_df = fetch_nba_recent_games(pid)
                except Exception:
                    continue
                if games_df.empty:
                    continue

                avg_minutes = pd.to_numeric(games_df["MIN"], errors="coerce").fillna(0).mean()
                if avg_minutes < MIN_NBA_MINUTES:
                    continue

                avg_3pt = calculate_nba_weighted_avg(games_df, "FG3M")
                avg_pts = calculate_nba_weighted_avg(games_df, "PTS")

                line = row["line"]
                over_odds = row["over_odds"]
                target = sportsbook_line_to_target(line)
                if target is None or over_odds is None:
                    continue

                model_prob, expected_stat, model_factors = build_nba_model_v2_projection(
                    games_df, market_name, opponent, target, line=line, odds=over_odds
                )

                fair_odds = probability_to_fair_american(model_prob)
                ev = calculate_ev(model_prob, american_to_decimal(over_odds))
                implied_prob = american_to_implied_prob(over_odds)
                edge = ((model_prob / 100) - implied_prob) if implied_prob is not None else None
                leg_score = score_leg(model_prob, ev, edge)

                rows.append(
                    {
                        "player": player_name,
                        "player_id": pid,
                        "team": team_abbrev,
                        "opponent": opponent,
                        "game_key": f"{team_abbrev}_vs_{opponent}",
                        "market": market_name,
                        "line": line,
                        "book_over_odds": over_odds,
                        "book_under_odds": row["under_odds"],
                        "book": row["book_key"],
                        "expected_stat": round(expected_stat, 2),
                        "model_prob": model_prob,
                        "fair_odds": fair_odds,
                        "ev": ev,
                        "implied_prob": round(implied_prob, 4) if implied_prob is not None else None,
                        "edge": round(edge, 4) if edge is not None else None,
                        "line_source": "Sportsbook",
                        "leg_label": f"{player_name} over {safe_line_display(line)} {'3PT' if market_name == '3PT' else 'points'}",
                        "leg_score": leg_score,
                        "model_factors": model_factors,
                        "explanation": compact_factor_text(model_factors),
                    }
                )

    return pd.DataFrame(rows)

def filter_nba_candidate_legs(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    filtered = df.copy()
    filtered = filtered[
        (filtered["ev"].notna()) &
        (filtered["ev"] > 0.03) &
        (filtered["model_prob"] >= 55) &
        (filtered["book_over_odds"] >= -190) &
        (filtered["book_over_odds"] <= 150)
    ].copy()

    if filtered.empty:
        return filtered

    threes_mask = filtered["market"] == "3PT"
    points_mask = filtered["market"] == "PTS"

    filtered = filtered[
        ((threes_mask) & ((filtered["expected_stat"] - filtered["line"]) >= 0.30)) |
        ((points_mask) & ((filtered["expected_stat"] - filtered["line"]) >= 1.25))
    ].copy()

    return filtered.sort_values(by=["leg_score", "ev", "model_prob"], ascending=[False, False, False]).head(20)

# =========================
# NHL ENGINE
# =========================

def extract_all_player_dicts(obj: Any) -> List[Dict[str, Any]]:
    found = []
    if isinstance(obj, dict):
        keys = set(obj.keys())
        if "id" in keys and ("firstName" in keys or "fullName" in keys or "lastName" in keys):
            found.append(obj)
        for v in obj.values():
            found.extend(extract_all_player_dicts(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(extract_all_player_dicts(item))
    return found

def build_player_name_from_nhl_obj(obj: Dict[str, Any]) -> Optional[str]:
    if "fullName" in obj:
        full = obj.get("fullName")
        if isinstance(full, dict):
            return full.get("default") or next(iter(full.values()), None)
        return str(full)
    first = obj.get("firstName")
    last = obj.get("lastName")
    if isinstance(first, dict):
        first = first.get("default") or next(iter(first.values()), "")
    if isinstance(last, dict):
        last = last.get("default") or next(iter(last.values()), "")
    full = f"{first} {last}".strip()
    return full or None

@st.cache_data(ttl=3600, show_spinner=False)
def get_nhl_team_roster(team_abbrev: str) -> List[Dict[str, Any]]:
    url = f"https://api-web.nhle.com/v1/roster/{team_abbrev}/current"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if not resp.ok:
            return []
        data = resp.json()
        players_found = extract_all_player_dicts(data)
        output = []
        seen = set()
        for p in players_found:
            pid = p.get("id")
            name = build_player_name_from_nhl_obj(p)
            if pid and name and pid not in seen:
                seen.add(pid)
                output.append({"id": pid, "full_name": name, "team": team_abbrev})
        return output
    except Exception:
        return []

def get_nhl_today_events() -> List[Dict[str, Any]]:
    return get_sport_events(NHL_SPORT_KEY)

@st.cache_data(ttl=3600, show_spinner=False)
def get_nhl_today_player_pool() -> List[Dict[str, Any]]:
    events = get_nhl_today_events()
    teams = set()
    for e in events:
        home = NHL_NAME_TO_ABBREV.get(e.get("home_team", ""))
        away = NHL_NAME_TO_ABBREV.get(e.get("away_team", ""))
        if home:
            teams.add(home)
        if away:
            teams.add(away)

    players_out = []
    seen = set()
    for team in teams:
        for p in get_nhl_team_roster(team):
            if p["id"] not in seen:
                seen.add(p["id"])
                players_out.append(p)
    return players_out

@st.cache_data(ttl=3600, show_spinner=False)
def get_nhl_all_roster_pool() -> List[Dict[str, Any]]:
    players_out = []
    seen = set()
    all_teams = sorted(set(NHL_NAME_TO_ABBREV.values()))
    for team in all_teams:
        for p in get_nhl_team_roster(team):
            pid = p.get("id")
            if pid and pid not in seen:
                seen.add(pid)
                players_out.append(p)
    return players_out

def get_nhl_all_player_names() -> List[str]:
    today_pool = get_nhl_today_player_pool()
    full_pool = get_nhl_all_roster_pool()

    today_by_norm = {normalize_name(p["full_name"]): p["full_name"] for p in today_pool}
    full_by_norm = {normalize_name(p["full_name"]): p["full_name"] for p in full_pool}

    prop_names = get_prop_player_names_from_events(
        NHL_SPORT_KEY,
        NHL_POINTS_MARKET_KEYS + NHL_SHOTS_MARKET_KEYS + NHL_GOALS_MARKET_KEYS,
    )

    matched_names = []
    seen = set()
    for raw_name in prop_names:
        norm = normalize_name(raw_name)
        chosen_name = today_by_norm.get(norm) or full_by_norm.get(norm) or raw_name
        if chosen_name and chosen_name not in seen:
            seen.add(chosen_name)
            matched_names.append(chosen_name)

    if matched_names:
        return sorted(matched_names)

    if today_pool:
        return sorted([p["full_name"] for p in today_pool])

    if full_pool:
        return sorted([p["full_name"] for p in full_pool])

    return []

def get_nhl_player_id(name: str) -> Optional[int]:
    target = normalize_name(name)
    for pool in (get_nhl_today_player_pool(), get_nhl_all_roster_pool()):
        for p in pool:
            if normalize_name(p["full_name"]) == target:
                return p["id"]
        for p in pool:
            if player_name_matches(name, p["full_name"]):
                return p["id"]
    return None

def get_nhl_player_team(name: str) -> Optional[str]:
    target = normalize_name(name)
    for pool in (get_nhl_today_player_pool(), get_nhl_all_roster_pool()):
        for p in pool:
            if normalize_name(p["full_name"]) == target:
                return p["team"]
        for p in pool:
            if player_name_matches(name, p["full_name"]):
                return p["team"]
    return None

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_nhl_recent_games(pid: int) -> pd.DataFrame:
    url = f"https://api-web.nhle.com/v1/player/{pid}/game-log/now"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if not resp.ok:
            return pd.DataFrame()
        data = resp.json()
        logs = data.get("gameLog") or data.get("gameLogs") or data.get("games") or []
        if not isinstance(logs, list):
            return pd.DataFrame()

        rows = []
        for g in logs[:MAX_RECENT_GAMES]:
            goals = g.get("goals", 0) or 0
            assists = g.get("assists", 0) or 0
            points = g.get("points", goals + assists)
            shots = g.get("shots", g.get("shotsOnGoal", g.get("sog", 0))) or 0
            toi = g.get("toi", g.get("timeOnIce", g.get("toiPerGame", "0:00")))

            rows.append(
                {
                    "GOALS": float(goals),
                    "ASSISTS": float(assists),
                    "POINTS": float(points),
                    "SHOTS": float(shots),
                    "TOI_MIN": parse_time_to_minutes(toi),
                }
            )

        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()

def calculate_nhl_weighted_avg(df: pd.DataFrame, stat: str) -> float:
    if df.empty:
        return 0.0
    avg5 = df.head(5)[stat].mean() if len(df) >= 5 else df[stat].mean()
    avg10 = df.head(10)[stat].mean() if len(df) >= 10 else df[stat].mean()
    return float((avg5 * 0.6) + (avg10 * 0.4))

def build_nhl_candidate_legs(progress_bar=None, status_text=None) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    events = get_nhl_today_events()
    player_pool = get_nhl_today_player_pool()
    player_map = {normalize_name(p["full_name"]): p for p in player_pool}

    if not events:
        return pd.DataFrame()

    total_games = len(events)

    for idx, event in enumerate(events):
        if progress_bar is not None:
            progress_bar.progress((idx + 1) / total_games, text="Scanning NHL games for props...")
        if status_text is not None:
            status_text.write(f"NHL game {idx + 1} of {total_games}: {event.get('away_team')} @ {event.get('home_team')}")

        home_name = event.get("home_team", "")
        away_name = event.get("away_team", "")
        home_abbrev = NHL_NAME_TO_ABBREV.get(home_name)
        away_abbrev = NHL_NAME_TO_ABBREV.get(away_name)
        if not home_abbrev or not away_abbrev:
            continue

        props_resp = get_event_props(
            NHL_SPORT_KEY,
            event["id"],
            NHL_POINTS_MARKET_KEYS + NHL_SHOTS_MARKET_KEYS + NHL_GOALS_MARKET_KEYS,
        )
        event_data = props_resp.get("data", {})
        if not event_data or not event_data.get("bookmakers"):
            continue

        market_specs = [
            ("POINTS", NHL_POINTS_MARKET_KEYS),
            ("SHOTS", NHL_SHOTS_MARKET_KEYS),
            ("GOALS", NHL_GOALS_MARKET_KEYS),
        ]

        for market_name, market_keys in market_specs:
            market_rows = extract_main_lines_for_market(event_data, market_keys)
            usable_rows = []
            for row in market_rows:
                if normalize_name(row["player_name_raw"]) in player_map:
                    usable_rows.append(row)

            usable_rows = sorted(usable_rows, key=lambda r: abs(r.get("line", 999)))[:MAX_PROP_PLAYERS_PER_GAME_PER_MARKET]

            for row in usable_rows:
                player_name = row["player_name_raw"]
                player_info = player_map.get(normalize_name(player_name))
                if not player_info:
                    continue

                pid = player_info["id"]
                team_abbrev = player_info["team"]
                if team_abbrev not in {home_abbrev, away_abbrev}:
                    continue
                opponent = away_abbrev if team_abbrev == home_abbrev else home_abbrev

                try:
                    games_df = fetch_nhl_recent_games(pid)
                except Exception:
                    continue
                if games_df.empty:
                    continue

                avg_toi = games_df["TOI_MIN"].mean()
                if avg_toi < MIN_NHL_TOI_MINUTES:
                    continue

                line = row["line"]
                over_odds = row["over_odds"]
                target = sportsbook_line_to_target(line)
                if target is None or over_odds is None:
                    continue

                if market_name == "POINTS":
                    avg_stat = calculate_nhl_weighted_avg(games_df, "POINTS")
                elif market_name == "SHOTS":
                    avg_stat = calculate_nhl_weighted_avg(games_df, "SHOTS")
                else:
                    avg_stat = calculate_nhl_weighted_avg(games_df, "GOALS")

                model_prob, expected_stat, model_factors = build_nhl_model_v2_projection(
                    games_df, market_name, opponent, target, line=line, odds=over_odds
                )
                fair_odds = probability_to_fair_american(model_prob)
                ev = calculate_ev(model_prob, american_to_decimal(over_odds))
                implied_prob = american_to_implied_prob(over_odds)
                edge = ((model_prob / 100) - implied_prob) if implied_prob is not None else None
                leg_score = score_leg(model_prob, ev, edge)

                label_suffix = {"POINTS": "points", "SHOTS": "shots", "GOALS": "goals"}[market_name]

                rows.append(
                    {
                        "player": player_name,
                        "player_id": pid,
                        "team": team_abbrev,
                        "opponent": opponent,
                        "game_key": f"{team_abbrev}_vs_{opponent}",
                        "market": market_name,
                        "line": line,
                        "book_over_odds": over_odds,
                        "book_under_odds": row["under_odds"],
                        "book": row["book_key"],
                        "expected_stat": round(expected_stat, 2),
                        "model_prob": model_prob,
                        "fair_odds": fair_odds,
                        "ev": ev,
                        "implied_prob": round(implied_prob, 4) if implied_prob is not None else None,
                        "edge": round(edge, 4) if edge is not None else None,
                        "line_source": "Sportsbook",
                        "leg_label": f"{player_name} over {safe_line_display(line)} {label_suffix}",
                        "leg_score": leg_score,
                        "model_factors": model_factors,
                        "explanation": compact_factor_text(model_factors),
                    }
                )

    return pd.DataFrame(rows)

def filter_nhl_candidate_legs(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    filtered = df.copy()
    filtered = filtered[
        (filtered["ev"].notna()) &
        (filtered["ev"] > 0.02) &
        (filtered["model_prob"] >= 52) &
        (filtered["book_over_odds"] >= -220) &
        (filtered["book_over_odds"] <= 180)
    ].copy()

    if filtered.empty:
        return filtered

    shots_mask = filtered["market"] == "SHOTS"
    points_mask = filtered["market"] == "POINTS"
    goals_mask = filtered["market"] == "GOALS"

    filtered = filtered[
        ((shots_mask) & ((filtered["expected_stat"] - filtered["line"]) >= 0.40)) |
        ((points_mask) & ((filtered["expected_stat"] - filtered["line"]) >= 0.20)) |
        ((goals_mask) & ((filtered["expected_stat"] - filtered["line"]) >= 0.10))
    ].copy()

    return filtered.sort_values(by=["leg_score", "ev", "model_prob"], ascending=[False, False, False]).head(20)

# =========================
# DISPLAY HELPERS
# =========================

def render_candidate_table(df: pd.DataFrame):
    if df.empty:
        st.warning("No strong candidate legs were found with the current filters.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Raw candidate legs", len(df))
    c2.metric("Filtered top legs", len(df))
    c3.metric("Games", len(set(df["game_key"])))

    display_df = df[
        [
            "leg_label",
            "team",
            "opponent",
            "book",
            "line",
            "book_over_odds",
            "expected_stat",
            "model_prob",
            "fair_odds",
            "ev",
            "edge",
            "leg_score",
        ]
    ].copy()

    display_df = display_df.rename(
        columns={
            "leg_label": "Leg",
            "team": "Team",
            "opponent": "Opp",
            "book": "Book",
            "line": "Line",
            "book_over_odds": "Book Over Odds",
            "expected_stat": "Expected",
            "model_prob": "Model Prob %",
            "fair_odds": "Fair Odds",
            "ev": "EV",
            "edge": "Edge",
            "leg_score": "Leg Score",
        }
    )
    st.dataframe(display_df, use_container_width=True, hide_index=True)



def _display_value(value: Any, suffix: str = "") -> str:
    if value is None:
        return "—"
    try:
        if isinstance(value, float):
            if math.isnan(value):
                return "—"
            if abs(value) >= 100:
                return f"{value:.0f}{suffix}"
            return f"{value:.2f}{suffix}".rstrip("0").rstrip(".") + suffix if suffix and not str(value).endswith(suffix) else f"{value:.2f}".rstrip("0").rstrip(".")
        return f"{value}{suffix}"
    except Exception:
        return f"{value}{suffix}"


def _fmt_pct(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.1f}%"
    except Exception:
        return str(value)


def _edge_grade(prob: float, projected: Optional[float], line: Optional[float], ev: Optional[float]) -> str:
    edge_to_line = 0.0
    try:
        if projected is not None and line is not None:
            edge_to_line = float(projected) - float(line)
    except Exception:
        edge_to_line = 0.0

    ev_val = ev or 0.0
    score = (prob / 100) + max(edge_to_line, 0) * 0.08 + max(ev_val, 0) * 0.25
    if score >= 0.90:
        return "A"
    if score >= 0.78:
        return "B+"
    if score >= 0.68:
        return "B"
    if score >= 0.58:
        return "C+"
    return "C"


def _trend_text(last5: Any, last10: Any, season: Any) -> str:
    try:
        last5_f = float(last5)
        last10_f = float(last10)
        season_f = float(season)
    except Exception:
        return "Trend data unavailable"

    if last5_f > last10_f > season_f:
        return "Recent form is climbing versus season baseline."
    if last5_f < last10_f < season_f:
        return "Recent form is cooling versus season baseline."
    if last5_f > season_f:
        return "Recent form is above season baseline."
    if last5_f < season_f:
        return "Recent form is below season baseline."
    return "Recent form is close to season baseline."



def infer_cached_matchup_adjustment(leg: Dict[str, Any]) -> str:
    """Return a transparent matchup note for cached odds rows.

    Cached odds rows sometimes do not include the full model_factors payload, but they
    usually still include sport/market/opponent. Use the same lightweight matchup maps
    already used elsewhere in the app so the explanation area does not show a dead
    "matchup unavailable" message.
    """
    market = str(leg.get("market") or "").upper()
    opponent = str(leg.get("opponent") or "").upper().strip()
    sport = str(leg.get("sport") or leg.get("league") or "").upper().strip()

    if not opponent or opponent in {"NONE", "NAN", "—", ""}:
        return "Neutral matchup adjustment; opponent was not saved on this cached odds row."

    try:
        if sport == "NHL" or market in {"SHOTS", "GOALS", "POINTS"}:
            factor = nhl_defense_factor(opponent, market)
        elif market == "3PT":
            factor = load_nba_defense_factor().get(opponent, 1.0)
        else:
            factor = nba_points_defense_factor(opponent)
        return f"{_factor_pct_text(factor)} versus {opponent}"
    except Exception:
        return f"Neutral matchup adjustment versus {opponent}"


def infer_cached_volume_adjustment(leg: Dict[str, Any]) -> str:
    """Give a useful volume/edge note for cached odds rows without inventing stats."""
    projected = leg.get("expected_stat")
    line = leg.get("line")
    target = sportsbook_line_to_target(line) if line is not None else None
    try:
        if projected is not None and target is not None:
            edge = float(projected) - float(target)
            if edge >= 1.0:
                return f"Strong projection cushion of {edge:+.2f} above target."
            if edge >= 0.35:
                return f"Moderate projection cushion of {edge:+.2f} above target."
            if edge >= 0:
                return f"Thin projection cushion of {edge:+.2f}; role/usage changes matter."
            return f"Projection is {edge:+.2f} below target; price/model probability is carrying the read."
    except Exception:
        pass
    return "Volume detail not saved; using projected stat, line, odds, and model probability instead."

def infer_model_factors_from_leg(leg: Dict[str, Any]) -> Dict[str, Any]:
    """Build an explanation object even when the saved odds row did not include full model_factors.

    Some cached/fallback rows are created directly from sportsbook odds and only have
    the core fields: model_prob, expected_stat, line, odds, market, team/opponent.
    This function prevents the UI from showing an unhelpful unavailable message by
    deriving a transparent explanation from the fields we do have. It does not invent
    game-log stats; those stay marked unavailable.
    """
    if not isinstance(leg, dict):
        return {}

    existing = leg.get("model_factors")
    if isinstance(existing, dict) and existing:
        return existing

    line = leg.get("line")
    target = sportsbook_line_to_target(line) if line is not None else None
    projected = leg.get("expected_stat")
    prob = leg.get("model_prob")
    odds = leg.get("book_over_odds")
    implied = american_to_implied_prob(odds) if odds is not None else leg.get("implied_prob")

    source = leg.get("line_source") or leg.get("book") or "cached odds source"
    market = leg.get("market")
    edge_vs_target = None
    try:
        if projected is not None and target is not None:
            edge_vs_target = round(float(projected) - float(target), 2)
    except Exception:
        edge_vs_target = None

    probability_note = "Model probability from the cached odds/model row."
    try:
        if prob is not None and implied is not None:
            diff = float(prob) / 100 - float(implied)
            if diff > 0.05:
                probability_note = "Model probability is meaningfully above the book's implied probability."
            elif diff < -0.03:
                probability_note = "Model probability is below/near the book's implied probability; value may be thin."
            else:
                probability_note = "Model probability is close to the book's implied probability."
    except Exception:
        pass

    parts = []
    if projected is not None and target is not None:
        parts.append(f"Projected {projected} vs target {target}")
    if edge_vs_target is not None:
        parts.append(f"edge {edge_vs_target:+.2f}")
    if implied is not None:
        try:
            parts.append(f"book implied {float(implied) * 100:.1f}%")
        except Exception:
            pass

    return {
        "model_prob": prob,
        "projected_stat": projected,
        "sportsbook_line": line,
        "target_needed": target,
        "market_implied_prob": implied,
        "book_odds": odds,
        "market": market,
        "team": leg.get("team"),
        "opponent": leg.get("opponent"),
        "line_source": source,
        "projection_edge": edge_vs_target,
        "season_avg": None,
        "last10_avg": None,
        "last5_avg": None,
        "expected_minutes": None,
        "expected_toi": None,
        "stat_per_min": None,
        "opportunity_projection": projected,
        "opponent_adjustment": infer_cached_matchup_adjustment(leg),
        "volume_adjustment": infer_cached_volume_adjustment(leg),
        "explanation_summary": "; ".join(parts) if parts else probability_note,
        "data_note": "Full game-log factor details were not saved with this cached odds row, so this explanation uses the available model output, line, odds, implied probability, and projection edge.",
    }


def _factor_rows_for_leg(leg: Dict[str, Any]) -> List[Dict[str, Any]]:
    factors = leg.get("model_factors") if isinstance(leg.get("model_factors"), dict) else {}
    projected = factors.get("projected_stat", leg.get("expected_stat"))
    line = factors.get("sportsbook_line", leg.get("line"))
    target = factors.get("target_needed", sportsbook_line_to_target(line) if line is not None else None)
    prob = factors.get("model_prob", leg.get("model_prob"))
    implied = factors.get("market_implied_prob", None)

    rows: List[Dict[str, Any]] = []

    def add(factor: str, value: Any, impact: str):
        if value is not None and value != "":
            rows.append({"Factor": factor, "Value": value, "Impact on probability": impact})

    add("Model hit probability", _fmt_pct(prob), "Final calibrated chance for this leg.")
    add("Projected stat", _display_value(projected), "Main driver: projection versus the needed target.")
    add("Sportsbook line", safe_line_display(line) if line is not None else None, "The market line the model is evaluating.")
    add("Target needed", target, "Over bets usually need floor(line) + 1.")

    if projected is not None and target is not None:
        try:
            edge = float(projected) - float(target)
            add("Projection edge", f"{edge:+.2f}", "Positive edge means model projects above the required target.")
        except Exception:
            pass

    add("Season average", factors.get("season_avg"), "Stabilizes the projection so recent spikes do not overrule the full sample.")
    add("Last 10 average", factors.get("last10_avg"), "Captures current role/form without overreacting to one game.")
    add("Last 5 average", factors.get("last5_avg"), "Captures short-term trend and hot/cold stretch.")
    add("Recent trend", _trend_text(factors.get("last5_avg"), factors.get("last10_avg"), factors.get("season_avg")), "Helps explain whether recent form is improving or fading.")
    add("Expected minutes", factors.get("expected_minutes"), "NBA opportunity input: more minutes means more stat chances.")
    add("Expected TOI", factors.get("expected_toi"), "NHL opportunity input: more ice time means more stat chances.")
    add("Stat per minute", factors.get("stat_per_min"), "Efficiency/volume rate multiplied by expected opportunity.")
    add("Opportunity projection", factors.get("opportunity_projection"), "Projection based on rate × expected minutes/TOI.")
    add("Opponent adjustment", factors.get("opponent_adjustment"), "Matchup adjustment applied to the projection.")
    add("Volume adjustment", factors.get("volume_adjustment"), "Shot/attempt volume adjustment when available.")
    add("Market implied probability", _fmt_pct(implied) if implied is not None else None, "Book's implied probability, used as a reality check.")
    add("Book odds", safe_odds_display(leg.get("book_over_odds")), "Available payout for the model probability.")
    add("Data source", factors.get("line_source"), "Shows whether this came from model v2, sportsbook API, or daily cache.")
    add("Data note", factors.get("data_note"), "Explains when full season/L5/L10 opportunity details were unavailable and estimated from saved outputs.")
    add("EV", leg.get("ev"), "Positive EV means model probability is better than the price implies.")
    return rows


def compact_factor_text(factors: Any) -> str:
    if not isinstance(factors, dict):
        return "Model details unavailable for this leg."
    projected = factors.get("projected_stat")
    target = factors.get("target_needed")
    season = factors.get("season_avg")
    last10 = factors.get("last10_avg")
    last5 = factors.get("last5_avg")
    opportunity = factors.get("expected_minutes") or factors.get("expected_toi")
    opp_adj = factors.get("opponent_adjustment")
    parts = []
    if projected is not None and target is not None:
        parts.append(f"Projected {projected} vs target {target}")
    if season is not None and last10 is not None and last5 is not None:
        parts.append(f"form blend: season {season}, L10 {last10}, L5 {last5}")
    if opportunity is not None:
        parts.append(f"opportunity {opportunity}")
    if opp_adj:
        parts.append(f"matchup {opp_adj}")
    return "; ".join(parts) if parts else str(factors.get("explanation_summary") or "Model details unavailable for this leg.")


def render_leg_model_explanation(leg: Dict[str, Any], index: Optional[int] = None):
    title_prefix = f"Leg {index}: " if index is not None else ""
    title = f"{title_prefix}{leg.get('leg_label', 'Selected leg')}"
    factors = infer_model_factors_from_leg(leg)
    if not factors:
        st.caption(f"{title} — basic probability inputs unavailable for this entry.")
        return

    with st.expander(f"Why this probability? — {title}", expanded=False):
        projected = factors.get("projected_stat", leg.get("expected_stat"))
        line = factors.get("sportsbook_line", leg.get("line"))
        target = factors.get("target_needed", sportsbook_line_to_target(line) if line is not None else None)
        prob = float(factors.get("model_prob", leg.get("model_prob", 0)) or 0)
        ev = leg.get("ev")
        grade = _edge_grade(prob, projected, line, ev)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Model Prob", f"{prob:.1f}%")
        c2.metric("Projected", _display_value(projected))
        c3.metric("Line", safe_line_display(line) if line is not None else "—")
        c4.metric("Target", target if target is not None else "—")
        c5.metric("Confidence", grade)

        st.markdown(f"**Model read:** {compact_factor_text(factors)}")

        rows = _factor_rows_for_leg(leg)
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        risks = []
        try:
            if projected is not None and target is not None and float(projected) - float(target) < 0.35:
                risks.append("Projection edge is thin, so small role/minute changes can flip the pick.")
        except Exception:
            pass
        if leg.get("book_over_odds") is not None and leg.get("book_over_odds") <= -250:
            risks.append("Heavy favorite price can reduce value even when hit probability is high.")
        if factors.get("last5_avg") is not None and factors.get("season_avg") is not None:
            try:
                if float(factors["last5_avg"]) > float(factors["season_avg"]) * 1.45:
                    risks.append("Recent form is far above season average and may regress.")
            except Exception:
                pass
        if risks:
            st.markdown("**Key risks:**")
            for r in risks:
                st.caption(f"⚠ {r}")


def render_parlay_probability_explanation(p: Dict[str, Any]):
    legs = p.get("legs", [])
    with st.expander("Full parlay probability breakdown — why this %?", expanded=True):
        raw_prob = 1.0
        summary_rows = []
        for i, leg in enumerate(legs, start=1):
            prob = float(leg.get("model_prob", 0) or 0)
            raw_prob *= prob / 100
            factors = infer_model_factors_from_leg(leg)
            projected = factors.get("projected_stat", leg.get("expected_stat"))
            line = factors.get("sportsbook_line", leg.get("line"))
            target = factors.get("target_needed", sportsbook_line_to_target(line) if line is not None else None)
            try:
                edge_vs_target = round(float(projected) - float(target), 2) if projected is not None and target is not None else None
            except Exception:
                edge_vs_target = None
            summary_rows.append(
                {
                    "#": i,
                    "Leg": leg.get("leg_label"),
                    "Prob %": round(prob, 2),
                    "Projected": projected,
                    "Line": line,
                    "Target": target,
                    "Edge vs Target": edge_vs_target,
                    "Odds": safe_odds_display(leg.get("book_over_odds")),
                    "Top reason": compact_factor_text(factors),
                }
            )

        raw_pct = round(raw_prob * 100, 2)
        displayed_pct = p.get("combined_prob", raw_pct)
        penalty = p.get("correlation_penalty", 0)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Raw multiplied probability", f"{raw_pct}%")
        c2.metric("Displayed probability", f"{displayed_pct}%")
        c3.metric("Correlation penalty", penalty)
        c4.metric("Book odds", safe_odds_display(p.get("combined_american_odds")))

        st.markdown(
            "The raw probability multiplies each leg's model hit rate. "
            "The app also shows correlation risk so same-game or same-team legs are not treated as fully independent."
        )

        if summary_rows:
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

        st.markdown("**Parlay math:**")
        if legs:
            probs = [float(leg.get("model_prob", 0) or 0) for leg in legs]
            math_line = " × ".join([f"{p0:.1f}%" for p0 in probs])
            st.markdown(
                f'<div class="parlay-math-card" style="background:linear-gradient(135deg,#020617,#0f172a) !important; color:#ffffff !important;"><span style="color:#ffffff !important;">{math_line} = {raw_pct}% raw hit probability</span></div>',
                unsafe_allow_html=True,
            )

        st.markdown("**What is helping this parlay most:**")
        helpers = []
        for leg in legs:
            factors = infer_model_factors_from_leg(leg)
            if factors:
                helpers.append(f"✓ {leg.get('leg_label')}: {compact_factor_text(factors)}")
        if helpers:
            for h in helpers:
                st.caption(h)
        else:
            st.caption("Detailed model factor data is unavailable for these legs, likely because they came from a cached/fallback odds source.")

        risks = []
        if penalty and float(penalty) > 0:
            risks.append(f"Correlation penalty of {penalty} because one or more legs share game/team context.")
        if p.get("parlay_size", len(legs)) >= 3:
            risks.append("Three-leg parlays compound variance quickly even when each individual leg is strong.")
        if p.get("parlay_ev", 0) < 0:
            risks.append("Parlay EV is negative based on model probability versus payout.")
        if risks:
            st.markdown("**Key risks:**")
            for r in risks:
                st.caption(f"⚠ {r}")

        for idx, leg in enumerate(legs, start=1):
            render_leg_model_explanation(leg, idx)


def render_selected_parlays(selected_parlays: Dict[str, Dict[str, Any]]):
    if not selected_parlays:
        st.warning("No parlays passed the current probability and EV thresholds.")
        return

    label_map = {
        "balanced": "Best Balanced Parlay",
        "safe": "Best Safer Parlay",
        "value": "Best Value Parlay",
    }

    for key in ["balanced", "safe", "value"]:
        if key not in selected_parlays:
            continue
        p = selected_parlays[key]
        st.markdown("---")
        st.subheader(label_map[key])

        top = st.columns(4)
        top[0].markdown(metric_card("Hit probability", f"{p['combined_prob']}%"), unsafe_allow_html=True)
        top[1].markdown(metric_card("Parlay EV", str(p["parlay_ev"]), "good" if p["parlay_ev"] > 0 else "bad"), unsafe_allow_html=True)
        top[2].markdown(metric_card("Book odds", safe_odds_display(p["combined_american_odds"])), unsafe_allow_html=True)
        top[3].markdown(metric_card("Payout multiple", f"{p['payout_multiple']}x"), unsafe_allow_html=True)

        st.write(f"**Fair odds:** {safe_odds_display(p['combined_fair_odds'])}")
        st.write(f"**Correlation penalty:** {p['correlation_penalty']}")
        st.write(f"**Parlay score:** {p['parlay_score']}")

        legs_table = pd.DataFrame(
            [
                {
                    "Leg": leg["leg_label"],
                    "Team": leg["team"],
                    "Opp": leg["opponent"],
                    "Book Odds": safe_odds_display(leg["book_over_odds"]),
                    "Model Prob %": leg["model_prob"],
                    "Projected": leg.get("expected_stat"),
                    "Line": leg.get("line"),
                    "EV": leg["ev"],
                    "Top Reason": compact_factor_text(infer_model_factors_from_leg(leg)),
                }
                for leg in p["legs"]
            ]
        )
        st.dataframe(legs_table, use_container_width=True, hide_index=True)
        render_parlay_probability_explanation(p)

# =========================
# MANUAL BUILDER HELPERS
# =========================

def build_manual_line(source_line: Optional[float], expected: float, target: int, floor: float = 0.5) -> float:
    if source_line is not None:
        return source_line
    return max(floor, round(max(expected * 0.9, target - 0.5) * 2) / 2)


def get_nba_player_headshot_url(player_name: str) -> Optional[str]:
    pid = get_nba_player_id(player_name)
    if pid is None:
        return None
    return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{pid}.png"

@st.cache_data(ttl=3600, show_spinner=False)
def get_nhl_player_headshot_url(player_id: int) -> Optional[str]:
    url = f"https://api-web.nhle.com/v1/player/{player_id}/landing"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if not resp.ok:
            return None
        data = resp.json()
        for key in ["headshot", "heroImage", "portrait"]:
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, dict):
                maybe = value.get("default") or next(iter(value.values()), None)
                if isinstance(maybe, str) and maybe:
                    return maybe
        return None
    except Exception:
        return None

def render_selected_player_photo(player_name: str, sport: str):
    if sport == "NBA":
        url = get_nba_player_headshot_url(player_name)
    else:
        pid = get_nhl_player_id(player_name)
        url = get_nhl_player_headshot_url(pid) if pid is not None else None

    if url:
        st.image(url, width=110)


def _reverse_nba_team_map() -> Dict[str, str]:
    return {v: k for k, v in NBA_TEAM_NAME_MAP.items()}

def _reverse_nhl_team_map() -> Dict[str, str]:
    reverse = {}
    for name, abbr in NHL_NAME_TO_ABBREV.items():
        reverse[name] = abbr
    return reverse

def _reverse_lookup_first_match(name: str, reverse_map: Dict[str, str]) -> str:
    if not name:
        return ""
    if name in reverse_map:
        return reverse_map[name]
    norm = normalize_team_text(name)
    for full_name, abbr in reverse_map.items():
        if normalize_team_text(full_name) == norm:
            return abbr
    return ""


def _event_data_has_prop_markets(event_data: Dict[str, Any], market_keys: List[str]) -> bool:
    """True only when the response actually contains one of the requested prop markets."""
    if not isinstance(event_data, dict):
        return False
    requested = set(market_keys)
    for bookmaker in event_data.get("bookmakers", []) or []:
        for market in bookmaker.get("markets", []) or []:
            if market.get("key") in requested and market.get("outcomes"):
                return True
    return False


def _merge_event_prop_payloads(payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple event-prop responses into one Odds-API-shaped dict.

    The Odds API can return empty props when several NHL markets are requested together
    or when DK/FD do not have that exact market. The Best buttons should try one market
    at a time and merge whatever comes back.
    """
    merged: Dict[str, Any] = {}
    book_map: Dict[str, Dict[str, Any]] = {}

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for k, v in payload.items():
            if k != "bookmakers" and k not in merged:
                merged[k] = v
        for bookmaker in payload.get("bookmakers", []) or []:
            book_key = bookmaker.get("key") or bookmaker.get("title") or "sportsbook"
            if book_key not in book_map:
                new_book = dict(bookmaker)
                new_book["markets"] = []
                book_map[book_key] = new_book
            existing_market_keys = {m.get("key") for m in book_map[book_key].get("markets", [])}
            for market in bookmaker.get("markets", []) or []:
                if market.get("key") not in existing_market_keys and market.get("outcomes"):
                    book_map[book_key]["markets"].append(market)
                    existing_market_keys.add(market.get("key"))

    merged["bookmakers"] = list(book_map.values())
    return merged


def _get_event_props_any_books(sport_key: str, event_id: str, market_keys: List[str]) -> Dict[str, Any]:
    """Button-only prop pull that aggressively avoids empty NHL prop responses.

    Order:
    1) existing helper with DK/FD for all requested markets
    2) event endpoint with all books for all requested markets
    3) one market at a time with DK/FD
    4) one market at a time with all books

    This only supports the two Best buttons and does not touch manual builder,
    dropdowns, player images, or any of the normal single-player logic.
    """
    payloads: List[Dict[str, Any]] = []

    # Try the existing app path first.
    event_data = get_event_props(sport_key, event_id, market_keys).get("data", {})
    if _event_data_has_prop_markets(event_data, market_keys):
        return event_data
    if isinstance(event_data, dict):
        payloads.append(event_data)

    base_url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{event_id}/odds"

    attempts: List[Dict[str, Any]] = [
        {
            "apiKey": API_KEY,
            "regions": "us",
            "markets": ",".join(market_keys),
            "oddsFormat": "american",
        },
    ]

    # If the combined request is thin/empty, try each market separately.
    # This is the important NHL fix.
    for mk in market_keys:
        attempts.append({
            "apiKey": API_KEY,
            "regions": "us",
            "bookmakers": PREFERRED_BOOKMAKERS,
            "markets": mk,
            "oddsFormat": "american",
        })
        attempts.append({
            "apiKey": API_KEY,
            "regions": "us",
            "markets": mk,
            "oddsFormat": "american",
        })

    for params in attempts:
        data, _ = odds_api_get(base_url, params)
        if isinstance(data, dict):
            payloads.append(data)
            if _event_data_has_prop_markets(data, market_keys):
                # Keep going only for single-market attempts? No: one hit is enough for speed;
                # merged payload below still includes earlier payloads.
                return _merge_event_prop_payloads(payloads)

    return _merge_event_prop_payloads(payloads)

def _is_over_outcome(outcome: Dict[str, Any]) -> bool:
    token_blob = " ".join(
        str(outcome.get(k, "")).lower()
        for k in ["name", "label", "side"]
    )
    if "under" in token_blob and "over" not in token_blob:
        return False
    if "over" in token_blob:
        return True
    # Some books put only the player in name/description and omit side labels.
    # For these Best buttons, keep the row rather than emptying the board.
    return True


def _extract_player_prop_name(outcome: Dict[str, Any]) -> str:
    for key in ["participant", "description", "player", "name"]:
        val = str(outcome.get(key, "")).strip()
        if val and normalize_name(val) not in {"over", "under", "yes", "no"}:
            return val
    return ""


def _label_suffix(market_label: str) -> str:
    return {
        "PTS": "points",
        "3PT": "3PT",
        "POINTS": "points",
        "SHOTS": "shots",
        "GOALS": "goals",
    }.get(market_label, market_label.lower())


def _append_button_leg(
    rows: List[Dict[str, Any]],
    player_name: str,
    team: str,
    opponent: str,
    game_key: str,
    market_label: str,
    line: float,
    odds: Optional[int],
    expected_stat: Optional[float],
    model_prob: Optional[float],
    line_source: str,
    book: str = "model",
    player_id: Optional[int] = None,
    under_odds: Optional[int] = None,
):
    if not player_name or line is None or model_prob is None:
        return

    if odds is None:
        odds = probability_to_fair_american(model_prob)
    if odds is None:
        odds = -110

    implied_prob = american_to_implied_prob(odds)
    ev = calculate_ev(model_prob, american_to_decimal(odds))
    edge = round((model_prob / 100) - implied_prob, 4) if implied_prob is not None else None

    rows.append(
        {
            "player": player_name,
            "player_id": player_id,
            "team": team,
            "opponent": opponent,
            "game_key": game_key,
            "market": market_label,
            "line": float(line),
            "book_over_odds": odds,
            "book_under_odds": under_odds,
            "book": book,
            "expected_stat": round(expected_stat, 2) if expected_stat is not None else None,
            "model_prob": round(model_prob, 2),
            "fair_odds": probability_to_fair_american(model_prob),
            "ev": ev,
            "implied_prob": round(implied_prob, 4) if implied_prob is not None else None,
            "edge": edge,
            "line_source": line_source,
            "leg_label": f"{player_name} over {safe_line_display(line)} {_label_suffix(market_label)}".strip(),
            "leg_score": score_best_leg_board(model_prob, odds),
        }
    )


def _rows_from_event_props(
    event: Dict[str, Any],
    event_data: Dict[str, Any],
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
) -> List[Dict[str, Any]]:
    market_key_to_label = {}
    for market_label, market_keys in market_specs:
        for mk in market_keys:
            market_key_to_label[mk] = market_label

    reverse_nba = _reverse_nba_team_map()
    reverse_nhl = _reverse_nhl_team_map()
    if sport == "NBA":
        home_abbrev = _reverse_lookup_first_match(event.get("home_team", ""), reverse_nba)
        away_abbrev = _reverse_lookup_first_match(event.get("away_team", ""), reverse_nba)
    else:
        home_abbrev = _reverse_lookup_first_match(event.get("home_team", ""), reverse_nhl)
        away_abbrev = _reverse_lookup_first_match(event.get("away_team", ""), reverse_nhl)

    rows: List[Dict[str, Any]] = []
    for bookmaker in event_data.get("bookmakers", []):
        book_key = bookmaker.get("key", "sportsbook")
        for market in bookmaker.get("markets", []):
            market_key = market.get("key")
            if market_key not in market_key_to_label:
                continue
            market_label = market_key_to_label[market_key]

            for outcome in market.get("outcomes", []):
                if not _is_over_outcome(outcome):
                    continue

                player_name = _extract_player_prop_name(outcome)
                if not player_name:
                    continue

                try:
                    line = float(outcome.get("point")) if outcome.get("point") is not None else None
                    odds = int(outcome.get("price")) if outcome.get("price") is not None else None
                except Exception:
                    continue

                if line is None or odds is None:
                    continue

                implied_prob = american_to_implied_prob(odds)
                model_prob = adjusted_best_leg_model_probability(implied_prob, odds)
                expected_stat = estimate_expected_from_probability(line, model_prob)

                _append_button_leg(
                    rows,
                    player_name=player_name,
                    team=home_abbrev,
                    opponent=away_abbrev,
                    game_key=f"{away_abbrev}_at_{home_abbrev}",
                    market_label=market_label,
                    line=line,
                    odds=odds,
                    expected_stat=expected_stat,
                    model_prob=model_prob,
                    line_source="Sportsbook prop board",
                    book=book_key,
                )
    return rows


def _finalize_button_board(rows: List[Dict[str, Any]], top_n: int = 80) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Never allow preference filters to wipe out the board.
    playable = df[
        (df["book_over_odds"].notna()) &
        (df["book_over_odds"] >= -400) &
        (df["book_over_odds"] <= 400)
    ].copy()
    if len(playable) >= 5:
        df = playable

    return (
        df.sort_values(by=["leg_score", "model_prob", "book_over_odds"], ascending=[False, False, False])
        .drop_duplicates(subset=["leg_label", "book"])
        .head(top_n)
        .reset_index(drop=True)
    )


def build_direct_candidate_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
    progress_bar=None,
    status_text=None,
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    events = get_sport_events_for_prop_board(sport_key)
    if not events:
        return pd.DataFrame()

    all_market_keys: List[str] = []
    for _, market_keys in market_specs:
        all_market_keys.extend(market_keys)

    total = len(events)
    for idx, event in enumerate(events):
        if progress_bar is not None:
            progress_bar.progress((idx + 1) / total, text=f"Loading {sport} sportsbook props...")
        if status_text is not None:
            status_text.write(f"{sport} event {idx + 1} of {total}: {event.get('away_team', '')} @ {event.get('home_team', '')}")

        event_id = event.get("id")
        if not event_id:
            continue
        event_data = _get_event_props_any_books(sport_key, event_id, all_market_keys)
        if not isinstance(event_data, dict) or not event_data.get("bookmakers"):
            continue
        rows.extend(_rows_from_event_props(event, event_data, market_specs, sport))

    return _finalize_button_board(rows, top_n=80)


@st.cache_data(ttl=120, show_spinner=False)
def build_sport_level_prop_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
) -> pd.DataFrame:
    all_market_keys: List[str] = []
    for _, market_keys in market_specs:
        all_market_keys.extend(market_keys)

    all_rows: List[Dict[str, Any]] = []

    # Try combined first, then market-by-market. Market-by-market is more reliable
    # for NHL props when one book/market is temporarily missing.
    market_attempts = [all_market_keys] + [[mk] for mk in all_market_keys]
    book_attempts = [
        {"bookmakers": PREFERRED_BOOKMAKERS},
        {},
    ]

    for market_group in market_attempts:
        for extra in book_attempts:
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
            params = {
                "apiKey": API_KEY,
                "regions": "us",
                "markets": ",".join(market_group),
                "oddsFormat": "american",
                **extra,
            }
            data, _ = odds_api_get(url, params)
            if not isinstance(data, list):
                continue
            for event in data:
                all_rows.extend(_rows_from_event_props(event, event, market_specs, sport))

        if all_rows:
            break

    return _finalize_button_board(all_rows, top_n=80)




def _nba_model_only_button_board(progress_bar=None, status_text=None) -> pd.DataFrame:
    """Fast last-resort NBA board for the two Best buttons only.

    This intentionally avoids slow nba_api game-log calls. It uses today's scoreboard,
    a small current-player list by team, and the same Poisson probability function used
    elsewhere in the app so the buttons return quickly instead of hanging.
    """
    games = get_nba_scoreboard_games()
    if not games:
        return pd.DataFrame()

    # Fast fallback pool. This is only used if sportsbook props are unavailable.
    team_core = {
        "ATL": [("Trae Young", 25.5, 2.5), ("Jalen Johnson", 17.5, 1.5), ("Dejounte Murray", 20.5, 1.5), ("Bogdan Bogdanovic", 13.5, 2.5)],
        "BOS": [("Jayson Tatum", 26.5, 2.5), ("Jaylen Brown", 23.5, 1.5), ("Derrick White", 14.5, 1.5), ("Kristaps Porzingis", 18.5, 1.5)],
        "BKN": [("Cam Thomas", 21.5, 1.5), ("Mikal Bridges", 19.5, 1.5), ("Cameron Johnson", 13.5, 2.5), ("Nic Claxton", 11.5, 0.5)],
        "CHA": [("LaMelo Ball", 24.5, 3.5), ("Miles Bridges", 19.5, 1.5), ("Brandon Miller", 17.5, 2.5), ("Mark Williams", 12.5, 0.5)],
        "CHI": [("Coby White", 19.5, 2.5), ("DeMar DeRozan", 23.5, 0.5), ("Nikola Vucevic", 17.5, 1.5), ("Zach LaVine", 21.5, 2.5)],
        "CLE": [("Donovan Mitchell", 26.5, 3.5), ("Darius Garland", 18.5, 2.5), ("Evan Mobley", 16.5, 0.5), ("Jarrett Allen", 14.5, 0.5)],
        "DAL": [("Luka Doncic", 31.5, 3.5), ("Kyrie Irving", 24.5, 2.5), ("Klay Thompson", 15.5, 3.5), ("P.J. Washington", 12.5, 1.5)],
        "DEN": [("Nikola Jokic", 27.5, 1.5), ("Jamal Murray", 21.5, 2.5), ("Michael Porter Jr.", 16.5, 2.5), ("Aaron Gordon", 13.5, 0.5)],
        "DET": [("Cade Cunningham", 23.5, 1.5), ("Jaden Ivey", 15.5, 1.5), ("Ausar Thompson", 10.5, 0.5), ("Jalen Duren", 13.5, 0.5)],
        "GSW": [("Stephen Curry", 27.5, 4.5), ("Jonathan Kuminga", 16.5, 0.5), ("Draymond Green", 8.5, 0.5), ("Andrew Wiggins", 14.5, 1.5)],
        "HOU": [("Alperen Sengun", 21.5, 0.5), ("Jalen Green", 21.5, 2.5), ("Fred VanVleet", 16.5, 2.5), ("Amen Thompson", 13.5, 0.5)],
        "IND": [("Tyrese Haliburton", 19.5, 2.5), ("Pascal Siakam", 20.5, 1.5), ("Myles Turner", 15.5, 1.5), ("Bennedict Mathurin", 14.5, 1.5)],
        "LAC": [("Kawhi Leonard", 23.5, 1.5), ("James Harden", 20.5, 2.5), ("Paul George", 22.5, 3.5), ("Ivica Zubac", 12.5, 0.5)],
        "LAL": [("LeBron James", 24.5, 1.5), ("Anthony Davis", 25.5, 0.5), ("Austin Reaves", 15.5, 1.5), ("D'Angelo Russell", 17.5, 2.5)],
        "MEM": [("Ja Morant", 25.5, 1.5), ("Jaren Jackson Jr.", 22.5, 1.5), ("Desmond Bane", 22.5, 2.5), ("Santi Aldama", 11.5, 1.5)],
        "MIA": [("Jimmy Butler", 20.5, 0.5), ("Tyler Herro", 20.5, 3.5), ("Bam Adebayo", 19.5, 0.5), ("Terry Rozier", 15.5, 1.5)],
        "MIL": [("Giannis Antetokounmpo", 29.5, 0.5), ("Damian Lillard", 24.5, 3.5), ("Khris Middleton", 15.5, 1.5), ("Brook Lopez", 11.5, 1.5)],
        "MIN": [("Anthony Edwards", 26.5, 2.5), ("Karl-Anthony Towns", 21.5, 1.5), ("Julius Randle", 21.5, 1.5), ("Naz Reid", 13.5, 1.5)],
        "NOP": [("Zion Williamson", 23.5, 0.5), ("Brandon Ingram", 20.5, 1.5), ("CJ McCollum", 18.5, 2.5), ("Trey Murphy III", 14.5, 2.5)],
        "NYK": [("Jalen Brunson", 27.5, 2.5), ("Karl-Anthony Towns", 22.5, 1.5), ("Mikal Bridges", 15.5, 1.5), ("OG Anunoby", 14.5, 1.5)],
        "OKC": [("Shai Gilgeous-Alexander", 30.5, 1.5), ("Jalen Williams", 20.5, 1.5), ("Chet Holmgren", 17.5, 1.5), ("Luguentz Dort", 10.5, 1.5)],
        "ORL": [("Paolo Banchero", 24.5, 1.5), ("Franz Wagner", 20.5, 1.5), ("Jalen Suggs", 13.5, 1.5), ("Wendell Carter Jr.", 10.5, 0.5)],
        "PHI": [("Joel Embiid", 30.5, 0.5), ("Tyrese Maxey", 25.5, 3.5), ("Paul George", 20.5, 2.5), ("Kelly Oubre Jr.", 14.5, 1.5)],
        "PHX": [("Kevin Durant", 26.5, 2.5), ("Devin Booker", 25.5, 2.5), ("Bradley Beal", 17.5, 1.5), ("Grayson Allen", 10.5, 2.5)],
        "POR": [("Anfernee Simons", 21.5, 3.5), ("Jerami Grant", 18.5, 1.5), ("Shaedon Sharpe", 15.5, 1.5), ("Deandre Ayton", 15.5, 0.5)],
        "SAC": [("De'Aaron Fox", 26.5, 2.5), ("Domantas Sabonis", 20.5, 0.5), ("DeMar DeRozan", 21.5, 0.5), ("Keegan Murray", 13.5, 2.5)],
        "SAS": [("Victor Wembanyama", 24.5, 1.5), ("Devin Vassell", 18.5, 2.5), ("Keldon Johnson", 14.5, 1.5), ("Jeremy Sochan", 11.5, 0.5)],
        "TOR": [("Scottie Barnes", 20.5, 1.5), ("RJ Barrett", 20.5, 1.5), ("Immanuel Quickley", 17.5, 2.5), ("Gradey Dick", 12.5, 2.5)],
        "UTA": [("Lauri Markkanen", 23.5, 3.5), ("Collin Sexton", 18.5, 1.5), ("Keyonte George", 15.5, 2.5), ("Jordan Clarkson", 16.5, 2.5)],
        "WAS": [("Kyle Kuzma", 21.5, 2.5), ("Jordan Poole", 20.5, 2.5), ("Bilal Coulibaly", 12.5, 1.5), ("Alex Sarr", 10.5, 0.5)],
    }

    rows: List[Dict[str, Any]] = []
    game_pairs = []
    for game in games:
        home = game.get("homeTeam", {}).get("teamTricode")
        away = game.get("awayTeam", {}).get("teamTricode")
        if home and away:
            game_pairs.append((home, away))

    total = max(len(game_pairs) * 2, 1)
    scanned = 0
    for home, away in game_pairs:
        for team_abbrev, opponent in [(home, away), (away, home)]:
            scanned += 1
            if progress_bar is not None:
                progress_bar.progress(min(scanned / total, 1.0), text="Building fast NBA model board...")
            if status_text is not None:
                status_text.write(f"NBA model fallback: {team_abbrev} vs {opponent}")

            for player_name, pts_avg, three_avg in team_core.get(team_abbrev, [])[:4]:
                game_key = f"{away}_at_{home}"

                pts_line = max(4.5, round(max(pts_avg * 0.88, pts_avg - 3.0) * 2) / 2)
                pts_target = sportsbook_line_to_target(pts_line)
                if pts_target is not None:
                    prob, expected = calculate_poisson_probability(pts_avg, nba_points_defense_factor(opponent), pts_target)
                    _append_button_leg(rows, player_name, team_abbrev, opponent, game_key, "PTS", pts_line, None, expected, prob, "Fast model fallback", "model")

                three_line = max(0.5, round(max(three_avg * 0.75, three_avg - 0.5) * 2) / 2)
                three_target = sportsbook_line_to_target(three_line)
                if three_target is not None:
                    prob, expected = calculate_poisson_probability(three_avg, load_nba_defense_factor().get(opponent, 1.0), three_target)
                    _append_button_leg(rows, player_name, team_abbrev, opponent, game_key, "3PT", three_line, None, expected, prob, "Fast model fallback", "model")

    return _finalize_button_board(rows, top_n=80)


def _nhl_model_only_button_board(progress_bar=None, status_text=None) -> pd.DataFrame:
    """Fast last-resort NHL board for the two Best buttons only.

    This is intentionally button-only. It does NOT touch the manual NHL tab,
    player pickers, photos, or existing sportsbook/manual-builder logic.

    Why this exists: NHL player props can come back empty from the sportsbook
    endpoint depending on timing/book/market availability. When that happens,
    the button still needs to return useful model candidates instead of the
    yellow empty warning.
    """
    events = get_nhl_today_events()
    if not events:
        return pd.DataFrame()

    # Fallback pool by team. Used only when sportsbook props are unavailable.
    # Values are lightweight priors: points_avg, shots_avg, goals_avg.
    team_core = {
        "ANA": [("Troy Terry", 0.75, 2.6, 0.28), ("Mason McTavish", 0.70, 2.5, 0.30), ("Leo Carlsson", 0.70, 2.4, 0.28)],
        "BOS": [("David Pastrnak", 1.25, 4.1, 0.50), ("Brad Marchand", 0.85, 2.6, 0.30), ("Charlie McAvoy", 0.65, 2.2, 0.12)],
        "BUF": [("Tage Thompson", 1.00, 3.6, 0.45), ("Rasmus Dahlin", 0.85, 2.8, 0.16), ("Alex Tuch", 0.80, 2.7, 0.32)],
        "CGY": [("Nazem Kadri", 0.85, 3.0, 0.32), ("Jonathan Huberdeau", 0.75, 2.1, 0.24), ("MacKenzie Weegar", 0.65, 2.6, 0.12)],
        "CAR": [("Sebastian Aho", 1.05, 3.0, 0.38), ("Andrei Svechnikov", 0.85, 3.2, 0.35), ("Seth Jarvis", 0.80, 2.6, 0.32)],
        "CHI": [("Connor Bedard", 1.00, 3.5, 0.40), ("Teuvo Teravainen", 0.75, 2.2, 0.24), ("Tyler Bertuzzi", 0.70, 2.4, 0.30)],
        "CBJ": [("Kirill Marchenko", 0.85, 2.9, 0.38), ("Zach Werenski", 0.85, 3.0, 0.15), ("Adam Fantilli", 0.75, 2.6, 0.30)],
        "COL": [("Nathan MacKinnon", 1.35, 4.5, 0.45), ("Mikko Rantanen", 1.15, 3.2, 0.40), ("Cale Makar", 1.05, 3.0, 0.25)],
        "DAL": [("Jason Robertson", 1.05, 3.0, 0.38), ("Roope Hintz", 0.85, 2.6, 0.32), ("Miro Heiskanen", 0.70, 2.4, 0.12)],
        "DET": [("Dylan Larkin", 1.00, 3.0, 0.38), ("Alex DeBrincat", 0.90, 3.2, 0.38), ("Lucas Raymond", 0.95, 2.7, 0.30)],
        "EDM": [("Connor McDavid", 1.45, 3.5, 0.40), ("Leon Draisaitl", 1.30, 3.3, 0.55), ("Evan Bouchard", 0.85, 2.8, 0.18)],
        "FLA": [("Matthew Tkachuk", 1.05, 3.3, 0.32), ("Aleksander Barkov", 0.95, 2.5, 0.30), ("Sam Reinhart", 1.00, 2.9, 0.45)],
        "LAK": [("Anze Kopitar", 0.90, 2.4, 0.28), ("Adrian Kempe", 0.95, 3.4, 0.38), ("Kevin Fiala", 0.90, 3.0, 0.32)],
        "MIN": [("Kirill Kaprizov", 1.25, 3.8, 0.45), ("Matt Boldy", 0.95, 3.1, 0.36), ("Joel Eriksson Ek", 0.80, 2.6, 0.34)],
        "MTL": [("Cole Caufield", 0.95, 3.3, 0.40), ("Nick Suzuki", 1.00, 2.6, 0.32), ("Juraj Slafkovsky", 0.70, 2.4, 0.26)],
        "NSH": [("Filip Forsberg", 1.05, 3.7, 0.42), ("Roman Josi", 0.90, 3.4, 0.16), ("Jonathan Marchessault", 0.85, 3.0, 0.35)],
        "NJD": [("Jack Hughes", 1.25, 4.0, 0.42), ("Jesper Bratt", 1.05, 3.0, 0.32), ("Nico Hischier", 0.90, 2.7, 0.32)],
        "NYI": [("Mathew Barzal", 0.90, 2.8, 0.26), ("Bo Horvat", 0.85, 2.9, 0.35), ("Noah Dobson", 0.75, 2.4, 0.12)],
        "NYR": [("Artemi Panarin", 1.25, 3.2, 0.40), ("Mika Zibanejad", 0.95, 3.0, 0.35), ("Chris Kreider", 0.75, 2.7, 0.38)],
        "OTT": [("Brady Tkachuk", 1.00, 4.0, 0.42), ("Tim Stutzle", 1.05, 3.0, 0.35), ("Drake Batherson", 0.80, 2.6, 0.30)],
        "PHI": [("Travis Konecny", 0.95, 3.1, 0.38), ("Matvei Michkov", 0.85, 2.9, 0.35), ("Owen Tippett", 0.75, 3.3, 0.32)],
        "PIT": [("Sidney Crosby", 1.10, 3.1, 0.40), ("Evgeni Malkin", 0.90, 2.9, 0.32), ("Kris Letang", 0.65, 2.6, 0.12)],
        "SEA": [("Jared McCann", 0.85, 2.8, 0.36), ("Matty Beniers", 0.70, 2.2, 0.24), ("Jordan Eberle", 0.70, 2.3, 0.28)],
        "SJS": [("Macklin Celebrini", 0.90, 3.0, 0.35), ("William Eklund", 0.80, 2.5, 0.28), ("Tyler Toffoli", 0.80, 2.8, 0.35)],
        "STL": [("Robert Thomas", 1.00, 2.4, 0.28), ("Jordan Kyrou", 0.90, 3.0, 0.35), ("Pavel Buchnevich", 0.85, 2.5, 0.32)],
        "TBL": [("Nikita Kucherov", 1.40, 3.8, 0.40), ("Brayden Point", 1.05, 2.8, 0.45), ("Victor Hedman", 0.75, 2.4, 0.16)],
        "TOR": [("Auston Matthews", 1.20, 4.4, 0.65), ("William Nylander", 1.05, 3.4, 0.40), ("Mitch Marner", 1.15, 2.6, 0.28)],
        "UTA": [("Clayton Keller", 1.00, 3.0, 0.35), ("Logan Cooley", 0.85, 2.7, 0.30), ("Dylan Guenther", 0.80, 2.8, 0.35)],
        "VAN": [("Elias Pettersson", 1.00, 2.8, 0.35), ("Quinn Hughes", 1.00, 2.5, 0.15), ("J.T. Miller", 1.05, 2.8, 0.35)],
        "VGK": [("Jack Eichel", 1.05, 3.4, 0.35), ("Mark Stone", 0.85, 2.2, 0.28), ("Tomas Hertl", 0.75, 2.5, 0.30)],
        "WPG": [("Kyle Connor", 1.10, 3.6, 0.45), ("Mark Scheifele", 1.00, 2.8, 0.38), ("Josh Morrissey", 0.80, 2.4, 0.12)],
        "WSH": [("Alex Ovechkin", 0.95, 3.8, 0.45), ("Dylan Strome", 0.90, 2.3, 0.30), ("John Carlson", 0.75, 2.7, 0.15)],
    }

    rows: List[Dict[str, Any]] = []
    total = max(len(events), 1)

    for idx, event in enumerate(events):
        if progress_bar is not None:
            progress_bar.progress((idx + 1) / total, text="Building fast NHL model board...")

        home = NHL_NAME_TO_ABBREV.get(event.get("home_team", ""), "")
        away = NHL_NAME_TO_ABBREV.get(event.get("away_team", ""), "")

        # Extra name safety for books/API name variants.
        if not home:
            home = _reverse_lookup_first_match(event.get("home_team", ""), _reverse_nhl_team_map())
        if not away:
            away = _reverse_lookup_first_match(event.get("away_team", ""), _reverse_nhl_team_map())

        if not home or not away:
            continue

        if status_text is not None:
            status_text.write(f"NHL model fallback: {away} @ {home}")

        game_key = f"{away}_at_{home}"
        for team_abbrev, opponent in [(home, away), (away, home)]:
            players_for_team = team_core.get(team_abbrev, [])

            # Last safety net: use the current roster API if a team is missing from the hardcoded pool.
            # This is limited to 3 skaters so it cannot hang for minutes.
            if not players_for_team:
                try:
                    roster_names = [p.get("full_name") for p in get_nhl_team_roster(team_abbrev)[:3] if p.get("full_name")]
                    players_for_team = [(name, 0.65, 2.0, 0.22) for name in roster_names]
                except Exception:
                    players_for_team = []

            for player_name, points_avg, shots_avg, goals_avg in players_for_team[:3]:
                specs = [
                    ("POINTS", points_avg, max(0.5, round(max(points_avg * 0.80, points_avg - 0.25) * 2) / 2)),
                    ("SHOTS", shots_avg, max(0.5, round(max(shots_avg * 0.82, shots_avg - 0.40) * 2) / 2)),
                    ("GOALS", goals_avg, 0.5),
                ]
                for market_label, avg_stat, line in specs:
                    target = sportsbook_line_to_target(line)
                    if target is None:
                        continue
                    prob, expected = calculate_poisson_probability(avg_stat, nhl_defense_factor(opponent, market_label), target)
                    _append_button_leg(
                        rows,
                        player_name=player_name,
                        team=team_abbrev,
                        opponent=opponent,
                        game_key=game_key,
                        market_label=market_label,
                        line=line,
                        odds=None,
                        expected_stat=expected,
                        model_prob=prob,
                        line_source="Fast NHL model fallback",
                        book="model",
                    )

    return _finalize_button_board(rows, top_n=80)


def build_model_only_button_board(sport: str, progress_bar=None, status_text=None) -> pd.DataFrame:
    if sport == "NBA":
        return _nba_model_only_button_board(progress_bar=progress_bar, status_text=status_text)
    if sport == "NHL":
        return _nhl_model_only_button_board(progress_bar=progress_bar, status_text=status_text)
    return pd.DataFrame()


def build_ranked_best_leg_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
    progress_bar=None,
    status_text=None,
    top_n: int = 20,
    enrich_rows: int = 36,
) -> pd.DataFrame:
    # 1) Try actual event-level props.
    board = build_direct_candidate_board(
        sport_key,
        market_specs,
        sport,
        progress_bar=progress_bar,
        status_text=status_text,
    )

    # 2) Try sport-level prop odds.
    if board.empty:
        if status_text is not None:
            status_text.write(f"{sport}: sportsbook prop board was empty, trying sport-level props...")
        board = build_sport_level_prop_board(sport_key, market_specs, sport)

    # 3) Last resort: use the same recent-form Poisson model from the manual builder.
    if board.empty:
        if status_text is not None:
            status_text.write(f"{sport}: sportsbook props unavailable, using model-only board...")
        board = build_model_only_button_board(sport, progress_bar=progress_bar, status_text=status_text)

    if board.empty:
        return pd.DataFrame()

    raw_board = sort_best_leg_board(board, top_n=max(enrich_rows, top_n))

    # Enrichment is helpful, but it should never be allowed to wipe out the button result.
    try:
        enriched = enrich_best_leg_board(raw_board, sport, max_rows=enrich_rows)
    except Exception:
        enriched = pd.DataFrame()

    if not enriched.empty:
        combined = pd.concat([enriched, raw_board], ignore_index=True)
    else:
        combined = raw_board

    return sort_best_leg_board(combined, top_n=top_n)




# =========================
# FINAL BEST BUTTON SPORTBOOK FIX - NBA + NHL
# =========================
# These definitions intentionally override the earlier Best-button helpers only.
# Manual player builders, photos, dropdowns, and the rest of the UI are untouched.

def _best_button_market_map(market_specs: List[Tuple[str, List[str]]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for label, keys in market_specs:
        for key in keys:
            out[key] = label
    return out


def _get_best_button_events(sport_key: str) -> List[Dict[str, Any]]:
    """Get actual scheduled event ids without relying on h2h odds existing at DK/FD."""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/events"
    data, _ = odds_api_get(url, {"apiKey": API_KEY})
    if isinstance(data, list) and data:
        return data

    # Backup: h2h with all books, then existing helper.
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    data, _ = odds_api_get(url, {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "h2h",
        "oddsFormat": "american",
    })
    if isinstance(data, list) and data:
        return data

    return get_sport_events_for_prop_board(sport_key)


def _event_payload_contains_any_market(payload: Dict[str, Any], market_keys: List[str]) -> bool:
    wanted = set(market_keys)
    if not isinstance(payload, dict):
        return False
    for book in payload.get("bookmakers", []) or []:
        for market in book.get("markets", []) or []:
            if market.get("key") in wanted and market.get("outcomes"):
                return True
    return False


def _merge_bookmaker_payloads(payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    books: Dict[str, Dict[str, Any]] = {}
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for k, v in payload.items():
            if k != "bookmakers" and k not in merged:
                merged[k] = v
        for book in payload.get("bookmakers", []) or []:
            book_key = book.get("key") or book.get("title") or "sportsbook"
            if book_key not in books:
                books[book_key] = dict(book)
                books[book_key]["markets"] = []
            existing = {(m.get("key"), len(m.get("outcomes", []) or [])) for m in books[book_key]["markets"]}
            for market in book.get("markets", []) or []:
                if not market.get("outcomes"):
                    continue
                sig = (market.get("key"), len(market.get("outcomes", []) or []))
                if sig not in existing:
                    books[book_key]["markets"].append(market)
                    existing.add(sig)
    merged["bookmakers"] = list(books.values())
    return merged


def _fetch_event_props_for_best_buttons(sport_key: str, event_id: str, market_keys: List[str]) -> Dict[str, Any]:
    """Aggressive event-prop fetch used by the two Best buttons only.

    The key fix: do not depend on one bundled DK/FD response. We try all books,
    preferred books, and then every market individually. This is what prevents
    the sportsbook prop list from coming back empty when one market/book is thin.
    """
    base_url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{event_id}/odds"
    payloads: List[Dict[str, Any]] = []

    attempts: List[Dict[str, Any]] = []
    all_markets = ",".join(market_keys)

    # Combined attempts first.
    attempts.append({"apiKey": API_KEY, "regions": "us", "markets": all_markets, "oddsFormat": "american"})
    attempts.append({"apiKey": API_KEY, "bookmakers": PREFERRED_BOOKMAKERS, "markets": all_markets, "oddsFormat": "american"})

    # Individual markets are more reliable for player props, especially NHL.
    for mk in market_keys:
        attempts.append({"apiKey": API_KEY, "regions": "us", "markets": mk, "oddsFormat": "american"})
        attempts.append({"apiKey": API_KEY, "bookmakers": PREFERRED_BOOKMAKERS, "markets": mk, "oddsFormat": "american"})
        attempts.append({"apiKey": API_KEY, "bookmakers": "draftkings", "markets": mk, "oddsFormat": "american"})
        attempts.append({"apiKey": API_KEY, "bookmakers": "fanduel", "markets": mk, "oddsFormat": "american"})

    for params in attempts:
        data, meta = odds_api_get(base_url, params)
        if isinstance(data, dict):
            payloads.append(data)

    return _merge_bookmaker_payloads(payloads)


def _best_button_team_abbrevs(event: Dict[str, Any], sport: str) -> Tuple[str, str]:
    if sport == "NBA":
        reverse = _reverse_nba_team_map()
    else:
        reverse = _reverse_nhl_team_map()
    home = _reverse_lookup_first_match(event.get("home_team", ""), reverse)
    away = _reverse_lookup_first_match(event.get("away_team", ""), reverse)
    return home, away


def _best_button_outcome_is_over(outcome: Dict[str, Any]) -> bool:
    blob = " ".join(str(outcome.get(k, "")).lower() for k in ["name", "label", "side"])
    if "under" in blob and "over" not in blob:
        return False
    if "over" in blob:
        return True
    # Some alternate lines omit side text. Keep it so the board does not wipe out.
    return True


def _best_button_player_name(outcome: Dict[str, Any]) -> str:
    for key in ["participant", "description", "player"]:
        val = str(outcome.get(key, "")).strip()
        if val and normalize_name(val) not in {"over", "under", "yes", "no"}:
            return val
    # Last resort only; do not use generic Over/Under names.
    val = str(outcome.get("name", "")).strip()
    if normalize_name(val) not in {"over", "under", "yes", "no"}:
        return val
    return ""


def _odds_rows_from_best_button_event(event: Dict[str, Any], payload: Dict[str, Any], market_specs: List[Tuple[str, List[str]]], sport: str) -> List[Dict[str, Any]]:
    market_map = _best_button_market_map(market_specs)
    home_abbrev, away_abbrev = _best_button_team_abbrevs(event, sport)
    game_key = f"{away_abbrev}_at_{home_abbrev}" if home_abbrev or away_abbrev else str(event.get("id", "game"))
    rows: List[Dict[str, Any]] = []

    for book in payload.get("bookmakers", []) or []:
        book_key = book.get("key") or book.get("title") or "sportsbook"
        for market in book.get("markets", []) or []:
            market_key = market.get("key")
            if market_key not in market_map:
                continue
            market_label = market_map[market_key]
            for outcome in market.get("outcomes", []) or []:
                if not _best_button_outcome_is_over(outcome):
                    continue
                player = _best_button_player_name(outcome)
                if not player:
                    continue
                try:
                    line = float(outcome.get("point")) if outcome.get("point") is not None else None
                    odds = int(outcome.get("price")) if outcome.get("price") is not None else None
                except Exception:
                    continue
                if line is None or odds is None:
                    continue

                implied = american_to_implied_prob(odds)
                model_prob = adjusted_best_leg_model_probability(implied, odds)
                expected = estimate_expected_from_probability(line, model_prob)
                _append_button_leg(
                    rows,
                    player_name=player,
                    team=home_abbrev,
                    opponent=away_abbrev,
                    game_key=game_key,
                    market_label=market_label,
                    line=line,
                    odds=odds,
                    expected_stat=expected,
                    model_prob=model_prob,
                    line_source="Sportsbook prop board",
                    book=book_key,
                )
    return rows


def build_direct_candidate_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
    progress_bar=None,
    status_text=None,
) -> pd.DataFrame:
    market_keys: List[str] = []
    for _, keys in market_specs:
        market_keys.extend(keys)

    events = _get_best_button_events(sport_key)
    if not events:
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []
    total = max(len(events), 1)

    for idx, event in enumerate(events):
        if progress_bar is not None:
            progress_bar.progress((idx + 1) / total, text=f"Loading {sport} sportsbook props...")
        if status_text is not None:
            status_text.write(f"{sport} props {idx + 1} of {total}: {event.get('away_team', '')} @ {event.get('home_team', '')}")

        event_id = event.get("id")
        if not event_id:
            continue

        payload = _fetch_event_props_for_best_buttons(sport_key, event_id, market_keys)
        event_rows = _odds_rows_from_best_button_event(event, payload, market_specs, sport)
        rows.extend(event_rows)

    return _finalize_button_board(rows, top_n=80)


@st.cache_data(ttl=120, show_spinner=False)
def build_sport_level_prop_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
) -> pd.DataFrame:
    # Sport-level player props can be thin, so loop events using the same fixed prop pull.
    rows: List[Dict[str, Any]] = []
    market_keys: List[str] = []
    for _, keys in market_specs:
        market_keys.extend(keys)
    for event in _get_best_button_events(sport_key):
        event_id = event.get("id")
        if not event_id:
            continue
        payload = _fetch_event_props_for_best_buttons(sport_key, event_id, market_keys)
        rows.extend(_odds_rows_from_best_button_event(event, payload, market_specs, sport))
    return _finalize_button_board(rows, top_n=80)


def build_ranked_best_leg_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
    progress_bar=None,
    status_text=None,
    top_n: int = 20,
    enrich_rows: int = 36,
) -> pd.DataFrame:
    # 1) Actual sportsbook props, fetched market-by-market across all available books.
    board = build_direct_candidate_board(
        sport_key,
        market_specs,
        sport,
        progress_bar=progress_bar,
        status_text=status_text,
    )

    # 2) Same fixed pull through sport-level wrapper, in case event discovery differed.
    if board.empty:
        if status_text is not None:
            status_text.write(f"{sport}: retrying sportsbook props with alternate event source...")
        board = build_sport_level_prop_board(sport_key, market_specs, sport)

    # 3) Do not leave the buttons unusable. This only runs if the sportsbook API truly returned no props.
    if board.empty:
        if status_text is not None:
            status_text.write(f"{sport}: sportsbook props did not return; using model board so the button still works.")
        board = build_model_only_button_board(sport, progress_bar=progress_bar, status_text=status_text)

    if board.empty:
        return pd.DataFrame()

    raw_board = sort_best_leg_board(board, top_n=max(enrich_rows, top_n))

    # Enrichment is allowed to improve rows, never to erase them or hang the button.
    try:
        enriched = enrich_best_leg_board(raw_board, sport, max_rows=min(enrich_rows, 12))
    except Exception:
        enriched = pd.DataFrame()

    combined = pd.concat([raw_board, enriched], ignore_index=True) if not enriched.empty else raw_board
    return sort_best_leg_board(combined, top_n=top_n)




# =========================
# FINAL BEST BUTTON SPORTSBOOK PROP FIX - ODDS API + DRAFTKINGS FALLBACK
# =========================
# Overrides ONLY the two best-button data builders. Everything else in the app is untouched.

DK_EVENTGROUP_IDS = {
    "NBA": "42648",
    "NHL": "42133",
}


def _safe_int_odds(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            cleaned = value.replace("+", "").strip()
            if not cleaned:
                return None
            return int(float(cleaned))
        return int(value)
    except Exception:
        return None


def _safe_float_line(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _deep_find_lists(obj: Any, key_name: str) -> List[List[Any]]:
    found: List[List[Any]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key_name and isinstance(v, list):
                found.append(v)
            found.extend(_deep_find_lists(v, key_name))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_deep_find_lists(item, key_name))
    return found


def _dk_market_label_from_text(text: str, sport: str) -> Optional[str]:
    t = normalize_team_text(text)
    raw = str(text).lower()

    if sport == "NBA":
        if "3" in raw and ("three" in raw or "threes" in raw or "made" in raw or "pt" in raw):
            return "3PT"
        if "point" in raw or "points" in raw or "pts" in raw:
            return "PTS"
        return None

    if "shot" in raw and ("goal" in raw or "sog" in raw or "shots" in raw):
        return "SHOTS"
    if "goal" in raw and "goalie" not in raw and "saves" not in raw:
        return "GOALS"
    if "point" in raw or "points" in raw:
        return "POINTS"
    return None


def _dk_pick_player_name(outcome: Dict[str, Any], offer: Dict[str, Any]) -> str:
    for key in ["participant", "playerName", "nameIdentifier", "participantName"]:
        val = str(outcome.get(key, "")).strip()
        if val and normalize_name(val) not in {"over", "under", "yes", "no"}:
            return val

    # DK often stores the player in the offer label/name and the outcome just says Over/Under.
    for key in ["label", "name", "displayName", "title"]:
        val = str(offer.get(key, "")).strip()
        if not val:
            continue
        cleaned = val
        for phrase in ["Points", "Point", "Shots On Goal", "Shots", "Goals", "3-Pointers Made", "3 Pointers Made", "Threes"]:
            cleaned = cleaned.replace(phrase, "")
        cleaned = cleaned.replace("Over/Under", "").replace("O/U", "").strip(" -:|()")
        if cleaned and len(cleaned.split()) >= 2:
            return cleaned
    return ""


def _dk_outcome_is_over(outcome: Dict[str, Any]) -> bool:
    blob = " ".join(str(outcome.get(k, "")).lower() for k in ["label", "name", "displayName", "outcomeType", "side"])
    if "under" in blob and "over" not in blob:
        return False
    return "over" in blob or blob.strip() in {"o", "over"}


def _dk_extract_line(outcome: Dict[str, Any], offer: Dict[str, Any]) -> Optional[float]:
    for key in ["line", "points", "point", "handicap"]:
        val = _safe_float_line(outcome.get(key))
        if val is not None:
            return val
    for key in ["line", "points", "point"]:
        val = _safe_float_line(offer.get(key))
        if val is not None:
            return val
    return None


def _dk_extract_odds(outcome: Dict[str, Any]) -> Optional[int]:
    for key in ["oddsAmerican", "americanOdds", "displayOdds"]:
        val = outcome.get(key)
        if isinstance(val, dict):
            val = val.get("american") or val.get("americanOdds")
        parsed = _safe_int_odds(val)
        if parsed is not None:
            return parsed
    return None


def _draftkings_prop_board(sport: str, market_specs: List[Tuple[str, List[str]]], status_text=None) -> pd.DataFrame:
    """DraftKings public sportsbook fallback for Best Legs / Best Parlays only.

    This is used when The Odds API returns no player-prop bookmakers. It still uses
    sportsbook lines/odds, so the board is not model-only.
    """
    event_group_id = DK_EVENTGROUP_IDS.get(sport)
    if not event_group_id:
        return pd.DataFrame()

    urls = [
        f"https://sportsbook-us-co.draftkings.com/sites/US-CO-SB/api/v5/eventgroups/{event_group_id}",
        f"https://sportsbook.draftkings.com/sites/US-SB/api/v5/eventgroups/{event_group_id}",
    ]
    params = {"format": "json"}

    data = None
    for url in urls:
        if status_text is not None:
            status_text.write(f"{sport}: The Odds API props were empty, checking DraftKings props...")
        resp_data, meta = odds_api_get(url, params)
        if isinstance(resp_data, dict):
            data = resp_data
            break

    if not isinstance(data, dict):
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []
    events_by_id: Dict[str, Dict[str, Any]] = {}
    for ev_list in _deep_find_lists(data, "events"):
        for ev in ev_list:
            if isinstance(ev, dict):
                eid = str(ev.get("eventId") or ev.get("id") or "")
                if eid:
                    events_by_id[eid] = ev

    offer_lists = _deep_find_lists(data, "offers")
    for offer_list in offer_lists:
        for offer_group in offer_list:
            # DK sometimes nests offers one more level deep.
            offers = offer_group if isinstance(offer_group, list) else [offer_group]
            for offer in offers:
                if not isinstance(offer, dict):
                    continue

                offer_text = " ".join(str(offer.get(k, "")) for k in ["label", "name", "displayName", "title"])
                market_label = _dk_market_label_from_text(offer_text, sport)
                if market_label is None:
                    continue

                outcomes = offer.get("outcomes") or []
                if not isinstance(outcomes, list):
                    continue

                event_id = str(offer.get("eventId") or offer.get("providerEventId") or "")
                ev = events_by_id.get(event_id, {})
                home = str(ev.get("homeTeamName") or ev.get("teamName1") or ev.get("homeTeam") or "")
                away = str(ev.get("awayTeamName") or ev.get("teamName2") or ev.get("awayTeam") or "")

                for outcome in outcomes:
                    if not isinstance(outcome, dict):
                        continue
                    if not _dk_outcome_is_over(outcome):
                        continue

                    player = _dk_pick_player_name(outcome, offer)
                    line = _dk_extract_line(outcome, offer)
                    odds = _dk_extract_odds(outcome)
                    if not player or line is None or odds is None:
                        continue

                    implied = american_to_implied_prob(odds)
                    model_prob = adjusted_best_leg_model_probability(implied, odds)
                    expected = estimate_expected_from_probability(line, model_prob)
                    if model_prob is None:
                        continue

                    _append_button_leg(
                        rows,
                        player_name=player,
                        team=home,
                        opponent=away,
                        game_key=f"{away}_at_{home}" if home or away else f"dk_{event_id}",
                        market_label=market_label,
                        line=line,
                        odds=odds,
                        expected_stat=expected,
                        model_prob=model_prob,
                        line_source="DraftKings sportsbook props",
                        book="draftkings",
                    )

    return _finalize_button_board(rows, top_n=80)


def _the_odds_api_best_button_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
    progress_bar=None,
    status_text=None,
) -> pd.DataFrame:
    market_keys: List[str] = []
    for _, keys in market_specs:
        market_keys.extend(keys)

    events = _get_best_button_events(sport_key)
    if not events:
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []
    total = max(len(events), 1)

    for idx, event in enumerate(events):
        if progress_bar is not None:
            progress_bar.progress((idx + 1) / total, text=f"Loading {sport} sportsbook props...")
        if status_text is not None:
            status_text.write(f"{sport} props {idx + 1} of {total}: {event.get('away_team', '')} @ {event.get('home_team', '')}")

        event_id = event.get("id")
        if not event_id:
            continue

        payload = _fetch_event_props_for_best_buttons(sport_key, event_id, market_keys)
        rows.extend(_odds_rows_from_best_button_event(event, payload, market_specs, sport))

    return _finalize_button_board(rows, top_n=80)


def build_direct_candidate_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
    progress_bar=None,
    status_text=None,
) -> pd.DataFrame:
    # First: The Odds API event player props.
    board = _the_odds_api_best_button_board(
        sport_key,
        market_specs,
        sport,
        progress_bar=progress_bar,
        status_text=status_text,
    )
    if not board.empty:
        return board

    # Second: actual DraftKings sportsbook props. This fixes the empty-prop problem without going model-only.
    dk_board = _draftkings_prop_board(sport, market_specs, status_text=status_text)
    if not dk_board.empty:
        return dk_board

    return pd.DataFrame()


@st.cache_data(ttl=120, show_spinner=False)
def build_sport_level_prop_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
) -> pd.DataFrame:
    # Keep sport-level wrapper for the existing button flow, but make it use the fixed sources.
    board = _the_odds_api_best_button_board(sport_key, market_specs, sport)
    if not board.empty:
        return board
    return _draftkings_prop_board(sport, market_specs)


def build_ranked_best_leg_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
    progress_bar=None,
    status_text=None,
    top_n: int = 20,
    enrich_rows: int = 36,
) -> pd.DataFrame:
    board = build_direct_candidate_board(
        sport_key,
        market_specs,
        sport,
        progress_bar=progress_bar,
        status_text=status_text,
    )

    if board.empty:
        if status_text is not None:
            status_text.write(f"{sport}: sportsbook props were still empty after Odds API + DraftKings checks.")
        return pd.DataFrame()

    # Keep it fast: do not run the slow game-log enrichment here. The board is sportsbook-line based.
    return sort_best_leg_board(board, top_n=top_n)



# =========================
# EMERGENCY FINAL ODDS FIX - DK/FD PROP PULL FOR BOTH BUTTONS + MANUAL BUILDER
# =========================
# This block intentionally overrides only the sportsbook prop-pull helpers used by:
#   1) Find Top Candidate Legs Today
#   2) Find Best Parlays Today
#   3) manual player prop lookup when The Odds API comes back empty
# It does not touch the UI, player photos, dropdowns, or model math.

try:
    _ORIGINAL_GET_EVENT_PROPS_FOR_FINAL_FIX = get_event_props
except Exception:
    _ORIGINAL_GET_EVENT_PROPS_FOR_FINAL_FIX = None


def _final_flatten_dicts(obj: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if isinstance(obj, dict):
        out.append(obj)
        for v in obj.values():
            out.extend(_final_flatten_dicts(v))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_final_flatten_dicts(item))
    return out


def _final_text_blob(*items: Any) -> str:
    parts: List[str] = []
    for item in items:
        if isinstance(item, dict):
            for k, v in item.items():
                if isinstance(v, (str, int, float)) and k.lower() not in {"id", "eventid", "providerid"}:
                    parts.append(str(v))
        elif isinstance(item, (str, int, float)):
            parts.append(str(item))
    return " ".join(parts)


def _final_market_from_blob(blob: str, sport: str) -> Optional[Tuple[str, str]]:
    raw = blob.lower()
    compact = normalize_team_text(blob)

    if sport == "NBA":
        if any(x in raw for x in ["3-pointers made", "3 pointers made", "three pointers made", "threes made"]):
            return "3PT", "player_threes"
        if ("player" in raw and "point" in raw) or raw.strip() in {"points", "player points"}:
            return "PTS", "player_points"
        if "pointsscored" in compact or "playerpoints" in compact:
            return "PTS", "player_points"
        return None

    # NHL
    if "shots on goal" in raw or "shot on goal" in raw or "sog" in raw:
        return "SHOTS", "player_shots_on_goal"
    if "player shots" in raw and "goal" in raw:
        return "SHOTS", "player_shots_on_goal"
    if "player goals" in raw or raw.strip() in {"goals", "goal"}:
        return "GOALS", "player_goals"
    if "goals scored" in raw and "goalie" not in raw:
        return "GOALS", "player_goals"
    if "player points" in raw or raw.strip() == "points":
        return "POINTS", "player_points"
    return None


def _final_extract_side(outcome: Dict[str, Any]) -> Optional[str]:
    blob = _final_text_blob(outcome).lower()
    if "under" in blob and "over" not in blob:
        return "Under"
    if "over" in blob and "under" not in blob:
        return "Over"
    label = str(outcome.get("label") or outcome.get("name") or outcome.get("displayName") or "").strip().lower()
    if label in {"o", "over"}:
        return "Over"
    if label in {"u", "under"}:
        return "Under"
    return None


def _final_extract_line_from_text(text: str) -> Optional[float]:
    import re
    patterns = [
        r"(?:over|under)\s*([0-9]+(?:\.[05])?)",
        r"\b([0-9]+(?:\.[05])?)\s*(?:\+)?\s*(?:points|pts|shots|goals|3-pointers|threes)",
    ]
    for pat in patterns:
        m = re.search(pat, text.lower())
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass
    return None


def _final_extract_line(outcome: Dict[str, Any], offer: Dict[str, Any]) -> Optional[float]:
    for key in ["line", "points", "point", "handicap", "spread"]:
        val = _safe_float_line(outcome.get(key))
        if val is not None:
            return val
    for key in ["line", "points", "point", "handicap", "spread"]:
        val = _safe_float_line(offer.get(key))
        if val is not None:
            return val
    return _final_extract_line_from_text(_final_text_blob(outcome, offer))


def _final_extract_odds(outcome: Dict[str, Any]) -> Optional[int]:
    # DraftKings has used several shapes over time. Try all common ones.
    for key in ["oddsAmerican", "americanOdds", "displayOdds", "odds", "price", "american"]:
        val = outcome.get(key)
        if isinstance(val, dict):
            for subkey in ["american", "americanOdds", "oddsAmerican", "display"]:
                parsed = _safe_int_odds(val.get(subkey))
                if parsed is not None:
                    return parsed
        parsed = _safe_int_odds(val)
        if parsed is not None:
            return parsed
    return None


def _final_clean_player_candidate(text: str, sport: str) -> str:
    import re
    t = str(text or "").strip()
    t = re.sub(r"\b(over|under)\b\s*[0-9]+(?:\.[05])?", "", t, flags=re.I)
    t = re.sub(r"[0-9]+(?:\.[05])?\s*\+?", "", t)
    kill = [
        "Player Points", "Points", "Point", "Pts", "Shots On Goal", "Shot On Goal",
        "Shots", "Goals", "Goal", "3-Pointers Made", "3 Pointers Made", "Threes Made",
        "Three Pointers Made", "Over/Under", "O/U", "Alternate", "Alt"
    ]
    for phrase in kill:
        t = t.replace(phrase, "")
        t = t.replace(phrase.lower(), "")
    t = re.sub(r"\s+", " ", t).strip(" -:|()[]")
    if len(t.split()) >= 2 and not any(x in t.lower() for x in ["over", "under", "player", "points", "goals", "shots"]):
        return t
    return ""


def _final_extract_player(outcome: Dict[str, Any], offer: Dict[str, Any], sport: str) -> str:
    for key in ["participant", "playerName", "participantName", "nameIdentifier", "description"]:
        val = str(outcome.get(key, "")).strip()
        if val and normalize_name(val) not in {"over", "under", "yes", "no"}:
            cleaned = _final_clean_player_candidate(val, sport)
            return cleaned or val

    for source in [outcome, offer]:
        for key in ["label", "name", "displayName", "title"]:
            val = str(source.get(key, "")).strip()
            cleaned = _final_clean_player_candidate(val, sport)
            if cleaned:
                return cleaned
    return ""


def _final_dk_urls_for_sport(sport: str) -> List[str]:
    group = DK_EVENTGROUP_IDS.get(sport)
    if not group:
        return []
    bases = [
        "https://sportsbook-us-co.draftkings.com/sites/US-CO-SB/api/v5/eventgroups/{group}",
        "https://sportsbook.draftkings.com/sites/US-SB/api/v5/eventgroups/{group}",
    ]
    urls = [b.format(group=group) + "?format=json" for b in bases]
    return urls


@st.cache_data(ttl=90, show_spinner=False)
def _final_fetch_dk_raw_payloads(sport: str) -> List[Dict[str, Any]]:
    """Fetch DraftKings eventgroup JSON plus any player-prop category/subcategory JSON we can discover."""
    payloads: List[Dict[str, Any]] = []
    seen_urls = set()

    base_urls = _final_dk_urls_for_sport(sport)
    for url in base_urls:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        data, _ = odds_api_get(url, {})
        if isinstance(data, dict):
            payloads.append(data)

            # Discover category/subcategory URLs for player props inside the eventgroup payload.
            for d in _final_flatten_dicts(data):
                blob = _final_text_blob(d)
                if _final_market_from_blob(blob, sport) is None:
                    continue
                cat = d.get("categoryId") or d.get("categoryID") or d.get("category_id")
                sub = d.get("subcategoryId") or d.get("subCategoryId") or d.get("subcategoryID") or d.get("subcategory_id")
                if cat and sub:
                    # Convert eventgroup root to category/subcategory endpoint.
                    root = url.split("?", 1)[0]
                    if "/categories/" not in root:
                        prop_url = f"{root}/categories/{cat}/subcategories/{sub}?format=json"
                        if prop_url not in seen_urls:
                            seen_urls.add(prop_url)
                            prop_data, _ = odds_api_get(prop_url, {})
                            if isinstance(prop_data, dict):
                                payloads.append(prop_data)

    return payloads


@st.cache_data(ttl=90, show_spinner=False)
def _final_draftkings_odds_payload(sport: str) -> Dict[str, Any]:
    """Return a The-Odds-API-shaped payload built from DraftKings sportsbook JSON."""
    payloads = _final_fetch_dk_raw_payloads(sport)
    markets: Dict[str, Dict[Tuple[str, float], Dict[str, Any]]] = {}

    for payload in payloads:
        for offer in _final_flatten_dicts(payload):
            outcomes = offer.get("outcomes")
            if not isinstance(outcomes, list) or not outcomes:
                continue

            offer_blob = _final_text_blob(offer)
            market_info = _final_market_from_blob(offer_blob, sport)

            # Sometimes the market text is in a parent-ish field on the outcome.
            if market_info is None:
                outcome_blob = _final_text_blob(*[o for o in outcomes if isinstance(o, dict)])
                market_info = _final_market_from_blob(offer_blob + " " + outcome_blob, sport)

            if market_info is None:
                continue

            _, market_key = market_info
            markets.setdefault(market_key, {})

            for outcome in outcomes:
                if not isinstance(outcome, dict):
                    continue
                side = _final_extract_side(outcome)
                if side not in {"Over", "Under"}:
                    continue
                player = _final_extract_player(outcome, offer, sport)
                line = _final_extract_line(outcome, offer)
                odds = _final_extract_odds(outcome)
                if not player or line is None or odds is None:
                    continue

                key = (normalize_name(player), float(line))
                if key not in markets[market_key]:
                    markets[market_key][key] = {
                        "player": player,
                        "line": float(line),
                        "over": None,
                        "under": None,
                    }
                if side == "Over":
                    markets[market_key][key]["over"] = odds
                else:
                    markets[market_key][key]["under"] = odds

    shaped_markets = []
    for market_key, grouped in markets.items():
        outcomes = []
        for rec in grouped.values():
            player = rec["player"]
            line = rec["line"]
            if rec.get("over") is not None:
                outcomes.append({
                    "name": "Over",
                    "description": player,
                    "participant": player,
                    "point": line,
                    "price": int(rec["over"]),
                })
            if rec.get("under") is not None:
                outcomes.append({
                    "name": "Under",
                    "description": player,
                    "participant": player,
                    "point": line,
                    "price": int(rec["under"]),
                })
        if outcomes:
            shaped_markets.append({"key": market_key, "outcomes": outcomes})

    if not shaped_markets:
        return {}

    return {
        "id": f"draftkings_{sport.lower()}_props",
        "home_team": "",
        "away_team": "",
        "bookmakers": [{
            "key": "draftkings",
            "title": "DraftKings",
            "markets": shaped_markets,
        }],
    }


def _final_payload_to_button_rows(payload: Dict[str, Any], market_specs: List[Tuple[str, List[str]]], sport: str) -> List[Dict[str, Any]]:
    fake_event = {"home_team": payload.get("home_team", ""), "away_team": payload.get("away_team", "")}
    return _odds_rows_from_best_button_event(fake_event, payload, market_specs, sport)


def get_event_props(sport_key: str, event_id: str, market_keys: List[str]) -> Dict[str, Any]:
    """Final override: try The Odds API first; if empty, return DraftKings-shaped prop data.

    This keeps existing manual player prop code working because it still receives the
    same bookmaker/market/outcome structure it already expects.
    """
    data: Dict[str, Any] = {}
    meta: Dict[str, Any] = {}

    if _ORIGINAL_GET_EVENT_PROPS_FOR_FINAL_FIX is not None:
        try:
            original = _ORIGINAL_GET_EVENT_PROPS_FOR_FINAL_FIX(sport_key, event_id, market_keys)
            data = original.get("data", {}) if isinstance(original, dict) else {}
            meta = original.get("meta", {}) if isinstance(original, dict) else {}
            if _event_payload_contains_any_market(data, market_keys):
                return {"data": data, "meta": meta}
        except Exception as e:
            meta = {"ok": False, "error": str(e)}

    sport = "NBA" if sport_key == NBA_SPORT_KEY else "NHL" if sport_key == NHL_SPORT_KEY else ""
    if sport:
        dk_payload = _final_draftkings_odds_payload(sport)
        if _event_payload_contains_any_market(dk_payload, market_keys):
            return {"data": dk_payload, "meta": {"ok": True, "source": "draftkings_public_fallback"}}

    return {"data": data if isinstance(data, dict) else {}, "meta": meta}


def build_direct_candidate_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
    progress_bar=None,
    status_text=None,
) -> pd.DataFrame:
    """Final button board: DK/FD via The Odds API first, DraftKings public props second."""
    market_keys: List[str] = []
    for _, keys in market_specs:
        market_keys.extend(keys)

    rows: List[Dict[str, Any]] = []
    events = _get_best_button_events(sport_key)
    total = max(len(events), 1)

    for idx, event in enumerate(events):
        if progress_bar is not None:
            progress_bar.progress(min((idx + 1) / total, 0.80), text=f"Pulling {sport} sportsbook player props...")
        if status_text is not None:
            status_text.write(f"{sport}: checking DK/FD props {idx + 1} of {total}: {event.get('away_team', '')} @ {event.get('home_team', '')}")

        event_id = event.get("id")
        if not event_id:
            continue

        payload = _fetch_event_props_for_best_buttons(sport_key, event_id, market_keys)
        rows.extend(_odds_rows_from_best_button_event(event, payload, market_specs, sport))

    board = _finalize_button_board(rows, top_n=80)
    if not board.empty:
        if status_text is not None:
            status_text.write(f"{sport}: found {len(board)} props from DK/FD sportsbook feed.")
        return board

    # DraftKings direct fallback: still real sportsbook props, not model-only.
    if progress_bar is not None:
        progress_bar.progress(0.88, text=f"Checking DraftKings public prop feed for {sport}...")
    if status_text is not None:
        status_text.write(f"{sport}: DK/FD API props were empty, checking DraftKings public prop feed...")

    dk_payload = _final_draftkings_odds_payload(sport)
    dk_rows = _final_payload_to_button_rows(dk_payload, market_specs, sport) if dk_payload else []
    dk_board = _finalize_button_board(dk_rows, top_n=80)
    if not dk_board.empty:
        if status_text is not None:
            status_text.write(f"{sport}: found {len(dk_board)} props from DraftKings public feed.")
        return dk_board

    if status_text is not None:
        status_text.write(f"{sport}: sportsbook prop feed returned zero player props. Check API key/add-on access or whether books have posted props yet.")
    return pd.DataFrame()


@st.cache_data(ttl=90, show_spinner=False)
def build_sport_level_prop_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
) -> pd.DataFrame:
    return build_direct_candidate_board(sport_key, market_specs, sport)


def build_ranked_best_leg_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
    progress_bar=None,
    status_text=None,
    top_n: int = 20,
    enrich_rows: int = 36,
) -> pd.DataFrame:
    board = build_direct_candidate_board(
        sport_key,
        market_specs,
        sport,
        progress_bar=progress_bar,
        status_text=status_text,
    )
    if board.empty:
        return pd.DataFrame()
    return sort_best_leg_board(board, top_n=top_n)




# =========================
# DIRECT SPORTBOOK ENDPOINT FALLBACKS - DK + FANDUEL
# =========================

FANDUEL_EVENT_TYPE_IDS = {
    "NBA": "7522",
    "NHL": "7524",
}

@st.cache_data(ttl=90, show_spinner=False)
def _fd_fetch_raw_payloads(sport: str) -> List[Dict[str, Any]]:
    """Fetch FanDuel public sportsbook JSON pages.

    These are unofficial public web-app endpoints, so we try several state hosts.
    They cost zero Odds API credits and are only used when The Odds API returns no props.
    """
    event_type_id = FANDUEL_EVENT_TYPE_IDS.get(sport)
    if not event_type_id:
        return []

    hosts = [
        "https://sbapi.co.sportsbook.fanduel.com",
        "https://sbapi.nj.sportsbook.fanduel.com",
        "https://sbapi.az.sportsbook.fanduel.com",
        "https://sbapi.il.sportsbook.fanduel.com",
        "https://sbapi.pa.sportsbook.fanduel.com",
        "https://sbapi.va.sportsbook.fanduel.com",
    ]
    pages = ["SPORT", "EVENT", "CUSTOM"]
    payloads: List[Dict[str, Any]] = []
    seen = set()

    for host in hosts:
        for page in pages:
            url = (
                f"{host}/api/content-managed-page"
                f"?page={page}&eventTypeId={event_type_id}"
                f"&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FDenver"
            )
            if url in seen:
                continue
            seen.add(url)
            data, meta = odds_api_get(url, {})
            if isinstance(data, dict):
                payloads.append(data)

    return payloads


def _fd_extract_odds(outcome: Dict[str, Any]) -> Optional[int]:
    for key in ["winRunnerOdds", "runnerOdds", "odds", "price", "currentPrice"]:
        val = outcome.get(key)
        if isinstance(val, dict):
            for subkey in ["americanDisplayOdds", "american", "americanOdds", "displayOdds", "price"]:
                parsed = _safe_int_odds(val.get(subkey))
                if parsed is not None:
                    return parsed
        parsed = _safe_int_odds(val)
        if parsed is not None:
            return parsed
    return None


def _fd_outcomes_from_market(market: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ["runners", "runnerDetails", "outcomes", "selections"]:
        val = market.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
    return []


def _fd_extract_side(outcome: Dict[str, Any]) -> Optional[str]:
    blob = _final_text_blob(outcome).lower()
    if "under" in blob and "over" not in blob:
        return "Under"
    if "over" in blob and "under" not in blob:
        return "Over"
    name = str(outcome.get("runnerName") or outcome.get("name") or outcome.get("selectionName") or "").lower()
    if name.strip() in {"o", "over"}:
        return "Over"
    if name.strip() in {"u", "under"}:
        return "Under"
    return None


def _fd_extract_player(outcome: Dict[str, Any], market: Dict[str, Any], sport: str) -> str:
    for key in ["participantName", "playerName", "runnerName", "name", "selectionName"]:
        val = str(outcome.get(key, "")).strip()
        cleaned = _final_clean_player_candidate(val, sport)
        if cleaned:
            return cleaned

    # FanDuel often stores the player in the market name and the runner as Over/Under.
    for key in ["marketName", "name", "title", "competitionName"]:
        val = str(market.get(key, "")).strip()
        cleaned = _final_clean_player_candidate(val, sport)
        if cleaned:
            return cleaned
    return ""


@st.cache_data(ttl=90, show_spinner=False)
def _fanduel_odds_payload(sport: str) -> Dict[str, Any]:
    """Return a The-Odds-API-shaped payload built from FanDuel public sportsbook JSON."""
    payloads = _fd_fetch_raw_payloads(sport)
    markets: Dict[str, Dict[Tuple[str, float], Dict[str, Any]]] = {}

    for payload in payloads:
        for market in _final_flatten_dicts(payload):
            outcomes = _fd_outcomes_from_market(market)
            if not outcomes:
                continue

            market_blob = _final_text_blob(market)
            market_info = _final_market_from_blob(market_blob, sport)
            if market_info is None:
                outcome_blob = _final_text_blob(*outcomes)
                market_info = _final_market_from_blob(market_blob + " " + outcome_blob, sport)
            if market_info is None:
                continue

            _, market_key = market_info
            markets.setdefault(market_key, {})

            for outcome in outcomes:
                side = _fd_extract_side(outcome)
                if side not in {"Over", "Under"}:
                    continue

                player = _fd_extract_player(outcome, market, sport)
                line = _final_extract_line(outcome, market)
                odds = _fd_extract_odds(outcome)
                if not player or line is None or odds is None:
                    continue

                key = (normalize_name(player), float(line))
                if key not in markets[market_key]:
                    markets[market_key][key] = {
                        "player": player,
                        "line": float(line),
                        "over": None,
                        "under": None,
                    }
                if side == "Over":
                    markets[market_key][key]["over"] = odds
                else:
                    markets[market_key][key]["under"] = odds

    shaped_markets = []
    for market_key, grouped in markets.items():
        outcomes = []
        for rec in grouped.values():
            player = rec["player"]
            line = rec["line"]
            if rec.get("over") is not None:
                outcomes.append({
                    "name": "Over",
                    "description": player,
                    "participant": player,
                    "point": line,
                    "price": int(rec["over"]),
                })
            if rec.get("under") is not None:
                outcomes.append({
                    "name": "Under",
                    "description": player,
                    "participant": player,
                    "point": line,
                    "price": int(rec["under"]),
                })
        if outcomes:
            shaped_markets.append({"key": market_key, "outcomes": outcomes})

    if not shaped_markets:
        return {}

    return {
        "id": f"fanduel_{sport.lower()}_props",
        "home_team": "",
        "away_team": "",
        "bookmakers": [{
            "key": "fanduel",
            "title": "FanDuel",
            "markets": shaped_markets,
        }],
    }


def _public_endpoint_rows(market_specs: List[Tuple[str, List[str]]], sport: str, source: str) -> List[Dict[str, Any]]:
    if source == "draftkings":
        payload = _final_draftkings_odds_payload(sport)
    elif source == "fanduel":
        payload = _fanduel_odds_payload(sport)
    else:
        payload = {}
    return _final_payload_to_button_rows(payload, market_specs, sport) if payload else []


# Final override used by BOTH the manual player props builder and the two buttons.
def get_event_props(sport_key: str, event_id: str, market_keys: List[str]) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    meta: Dict[str, Any] = {}

    if _ORIGINAL_GET_EVENT_PROPS_FOR_FINAL_FIX is not None:
        try:
            original = _ORIGINAL_GET_EVENT_PROPS_FOR_FINAL_FIX(sport_key, event_id, market_keys)
            data = original.get("data", {}) if isinstance(original, dict) else {}
            meta = original.get("meta", {}) if isinstance(original, dict) else {}
            if _event_payload_contains_any_market(data, market_keys):
                return {"data": data, "meta": meta}
        except Exception as e:
            meta = {"ok": False, "error": str(e)}

    sport = "NBA" if sport_key == NBA_SPORT_KEY else "NHL" if sport_key == NHL_SPORT_KEY else ""
    if sport:
        # DraftKings public endpoint fallback
        dk_payload = _final_draftkings_odds_payload(sport)
        if _event_payload_contains_any_market(dk_payload, market_keys):
            return {"data": dk_payload, "meta": {"ok": True, "source": "draftkings_public_endpoint"}}

        # FanDuel public endpoint fallback
        fd_payload = _fanduel_odds_payload(sport)
        if _event_payload_contains_any_market(fd_payload, market_keys):
            return {"data": fd_payload, "meta": {"ok": True, "source": "fanduel_public_endpoint"}}

    return {"data": data if isinstance(data, dict) else {}, "meta": meta}


# Final override for Best Legs / Best Parlays buttons.
def build_direct_candidate_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
    progress_bar=None,
    status_text=None,
) -> pd.DataFrame:
    market_keys: List[str] = []
    for _, keys in market_specs:
        market_keys.extend(keys)

    rows: List[Dict[str, Any]] = []
    events = _get_best_button_events(sport_key)
    total = max(len(events), 1)

    # 1) First try DK/FD through The Odds API while the quota is available.
    for idx, event in enumerate(events):
        if progress_bar is not None:
            progress_bar.progress(min((idx + 1) / total, 0.45), text=f"Pulling {sport} DK/FD props from primary odds source...")
        if status_text is not None:
            status_text.write(f"{sport}: primary DK/FD prop check {idx + 1} of {total}: {event.get('away_team', '')} @ {event.get('home_team', '')}")

        event_id = event.get("id")
        if not event_id:
            continue
        payload = _fetch_event_props_for_best_buttons(sport_key, event_id, market_keys)
        rows.extend(_odds_rows_from_best_button_event(event, payload, market_specs, sport))

    board = _finalize_button_board(rows, top_n=80)
    if not board.empty:
        if status_text is not None:
            status_text.write(f"{sport}: found {len(board)} DK/FD props from the primary odds source.")
        return board

    # 2) DraftKings endpoint scrape.
    if progress_bar is not None:
        progress_bar.progress(0.65, text=f"Primary source empty; scraping DraftKings {sport} public props...")
    if status_text is not None:
        status_text.write(f"{sport}: primary source empty, scraping DraftKings public endpoint...")

    dk_board = _finalize_button_board(_public_endpoint_rows(market_specs, sport, "draftkings"), top_n=80)
    if not dk_board.empty:
        if status_text is not None:
            status_text.write(f"{sport}: found {len(dk_board)} props from DraftKings public endpoint.")
        return dk_board

    # 3) FanDuel endpoint scrape.
    if progress_bar is not None:
        progress_bar.progress(0.82, text=f"DraftKings empty; scraping FanDuel {sport} public props...")
    if status_text is not None:
        status_text.write(f"{sport}: DraftKings endpoint empty, scraping FanDuel public endpoint...")

    fd_board = _finalize_button_board(_public_endpoint_rows(market_specs, sport, "fanduel"), top_n=80)
    if not fd_board.empty:
        if status_text is not None:
            status_text.write(f"{sport}: found {len(fd_board)} props from FanDuel public endpoint.")
        return fd_board

    if status_text is not None:
        status_text.write(
            f"{sport}: no player props returned from primary source, DraftKings endpoint, or FanDuel endpoint. "
            "That usually means props are not posted yet, the public endpoints changed, or requests are being blocked."
        )
    return pd.DataFrame()


@st.cache_data(ttl=90, show_spinner=False)
def build_sport_level_prop_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
) -> pd.DataFrame:
    return build_direct_candidate_board(sport_key, market_specs, sport)


def build_ranked_best_leg_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
    progress_bar=None,
    status_text=None,
    top_n: int = 20,
    enrich_rows: int = 36,
) -> pd.DataFrame:
    board = build_direct_candidate_board(
        sport_key,
        market_specs,
        sport,
        progress_bar=progress_bar,
        status_text=status_text,
    )
    if board.empty:
        return pd.DataFrame()
    return sort_best_leg_board(board, top_n=top_n)




# =========================
# FINAL FANDUEL CONTENT-MANAGED-PAGE FIX
# =========================
# Uses the exact FanDuel endpoint shape found in Edge DevTools:
# https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=CUSTOM&customPageId=nhl...
# This is only used as a fallback when The Odds API / DK eventgroup pull returns no props.

FANDUEL_CUSTOM_PAGE_IDS = {
    "NBA": "nba",
    "NHL": "nhl",
}


def _fd_exact_content_urls(sport: str) -> List[str]:
    page_id = FANDUEL_CUSTOM_PAGE_IDS.get(sport)
    if not page_id:
        return []

    base_urls = [
        "https://api.sportsbook.fanduel.com/sbapi/content-managed-page",
        "https://sbapi.co.sportsbook.fanduel.com/api/content-managed-page",
        "https://sbapi.nj.sportsbook.fanduel.com/api/content-managed-page",
        "https://sbapi.az.sportsbook.fanduel.com/api/content-managed-page",
        "https://sbapi.il.sportsbook.fanduel.com/api/content-managed-page",
        "https://sbapi.pa.sportsbook.fanduel.com/api/content-managed-page",
    ]
    variants = [
        f"page=CUSTOM&customPageId={page_id}&pbHorizontal=false&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FDenver",
        f"page=CUSTOM&customPageId={page_id}&tab=player-props&pbHorizontal=false&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FDenver",
        f"page=CUSTOM&customPageId={page_id}&tab=parlay-builder&pbHorizontal=false&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FDenver",
        f"page=SPORT&customPageId={page_id}&pbHorizontal=false&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FDenver",
    ]
    return [f"{base}?{query}" for base in base_urls for query in variants]


@st.cache_data(ttl=90, show_spinner=False)
def _fd_fetch_raw_payloads(sport: str) -> List[Dict[str, Any]]:
    payloads: List[Dict[str, Any]] = []
    seen = set()
    fd_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36 Edg/120",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://sportsbook.fanduel.com",
        "Referer": f"https://sportsbook.fanduel.com/navigation/{FANDUEL_CUSTOM_PAGE_IDS.get(sport, '').lower()}?tab=player-props",
    }

    for url in _fd_exact_content_urls(sport):
        if url in seen:
            continue
        seen.add(url)
        try:
            resp = requests.get(url, headers=fd_headers, timeout=REQUEST_TIMEOUT)
            if resp.ok:
                data = resp.json()
                if isinstance(data, dict):
                    payloads.append(data)
        except Exception:
            continue

    return payloads


def _fd_attachment_values(payload: Dict[str, Any], name: str) -> List[Dict[str, Any]]:
    attachments = payload.get("attachments", {}) if isinstance(payload, dict) else {}
    raw = attachments.get(name, {}) if isinstance(attachments, dict) else {}
    if isinstance(raw, dict):
        return [v for v in raw.values() if isinstance(v, dict)]
    if isinstance(raw, list):
        return [v for v in raw if isinstance(v, dict)]
    return []


def _fd_id(obj: Dict[str, Any]) -> Optional[str]:
    for key in ["marketId", "id", "externalMarketId", "selectionMarketId"]:
        val = obj.get(key)
        if val is not None:
            return str(val)
    return None


def _fd_collect_markets(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    markets = _fd_attachment_values(payload, "markets")
    seen = {id(m) for m in markets}
    for obj in _final_flatten_dicts(payload):
        if id(obj) in seen:
            continue
        blob = _final_text_blob(obj).lower()
        has_market_name = any(k in obj for k in ["marketName", "name", "title", "eventMarketName", "externalMarketId"])
        has_runner_data = any(k in obj for k in ["runners", "runnerDetails", "outcomes", "selections", "rows"])
        if has_market_name and (has_runner_data or "player" in blob or "points" in blob or "shots" in blob or "goals" in blob or "3pt" in blob or "threes" in blob):
            markets.append(obj)
            seen.add(id(obj))
    return markets


def _fd_collect_selections_by_market(payload: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    candidates = []
    for name in ["selections", "runners", "runnerDetails", "outcomes"]:
        candidates.extend(_fd_attachment_values(payload, name))
    for obj in _final_flatten_dicts(payload):
        if any(k in obj for k in ["selectionId", "runnerId", "runnerName", "selectionName", "winRunnerOdds"]):
            candidates.append(obj)

    out: Dict[str, List[Dict[str, Any]]] = {}
    seen = set()
    for sel in candidates:
        key_tuple = (str(sel.get("selectionId") or sel.get("runnerId") or id(sel)), str(sel.get("marketId") or sel.get("externalMarketId") or ""))
        if key_tuple in seen:
            continue
        seen.add(key_tuple)
        mid = sel.get("marketId") or sel.get("externalMarketId") or sel.get("selectionMarketId")
        if mid is None:
            continue
        out.setdefault(str(mid), []).append(sel)
    return out


def _fd_outcomes_from_market(market: Dict[str, Any], selections_by_market: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> List[Dict[str, Any]]:
    outcomes: List[Dict[str, Any]] = []
    for key in ["runners", "runnerDetails", "outcomes", "selections"]:
        val = market.get(key)
        if isinstance(val, list):
            outcomes.extend([x for x in val if isinstance(x, dict)])
        elif isinstance(val, dict):
            outcomes.extend([x for x in val.values() if isinstance(x, dict)])
    if selections_by_market:
        mid = _fd_id(market)
        if mid and mid in selections_by_market:
            outcomes.extend(selections_by_market[mid])

    deduped = []
    seen = set()
    for x in outcomes:
        key = str(x.get("selectionId") or x.get("runnerId") or x.get("id") or id(x))
        if key not in seen:
            seen.add(key)
            deduped.append(x)
    return deduped


def _fd_extract_line(outcome: Dict[str, Any], market: Dict[str, Any]) -> Optional[float]:
    for obj in [outcome, market]:
        for key in ["handicap", "line", "points", "point", "spread", "runnerHandicap"]:
            val = obj.get(key)
            try:
                if val is not None and str(val).strip() != "":
                    return float(val)
            except Exception:
                pass
    return _final_extract_line(outcome, market)


def _fanduel_odds_payload_OLD_CONTENT_PAGE(sport: str) -> Dict[str, Any]:
    payloads = _fd_fetch_raw_payloads(sport)
    grouped_by_market_key: Dict[str, Dict[Tuple[str, float], Dict[str, Any]]] = {}

    for payload in payloads:
        selections_by_market = _fd_collect_selections_by_market(payload)
        for market in _fd_collect_markets(payload):
            outcomes = _fd_outcomes_from_market(market, selections_by_market)
            if not outcomes:
                continue

            market_blob = _final_text_blob(market)
            outcome_blob = _final_text_blob(*outcomes[:8])
            market_info = _final_market_from_blob(f"{market_blob} {outcome_blob}", sport)
            if market_info is None:
                continue
            _, market_key = market_info
            grouped_by_market_key.setdefault(market_key, {})

            for outcome in outcomes:
                side = _fd_extract_side(outcome)
                if side not in {"Over", "Under"}:
                    continue
                odds = _fd_extract_odds(outcome)
                line = _fd_extract_line(outcome, market)
                player = _fd_extract_player(outcome, market, sport)
                if not player or line is None or odds is None:
                    continue

                rec_key = (normalize_name(player), float(line))
                if rec_key not in grouped_by_market_key[market_key]:
                    grouped_by_market_key[market_key][rec_key] = {"player": player, "line": float(line), "over": None, "under": None}
                if side == "Over":
                    grouped_by_market_key[market_key][rec_key]["over"] = odds
                else:
                    grouped_by_market_key[market_key][rec_key]["under"] = odds

    shaped_markets = []
    for market_key, grouped in grouped_by_market_key.items():
        outcomes = []
        for rec in grouped.values():
            player = rec["player"]
            line = rec["line"]
            if rec.get("over") is not None:
                outcomes.append({"name": "Over", "description": player, "participant": player, "point": line, "price": int(rec["over"])})
            if rec.get("under") is not None:
                outcomes.append({"name": "Under", "description": player, "participant": player, "point": line, "price": int(rec["under"])})
        if outcomes:
            shaped_markets.append({"key": market_key, "outcomes": outcomes})

    if not shaped_markets:
        return {}

    return {
        "id": f"fanduel_{sport.lower()}_props",
        "home_team": "",
        "away_team": "",
        "bookmakers": [{"key": "fanduel", "title": "FanDuel", "markets": shaped_markets}],
    }


# Final override: button rows try FanDuel content-managed page BEFORE giving up.
def build_direct_candidate_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
    progress_bar=None,
    status_text=None,
) -> pd.DataFrame:
    market_keys: List[str] = []
    for _, keys in market_specs:
        market_keys.extend(keys)

    rows: List[Dict[str, Any]] = []
    events = _get_best_button_events(sport_key)
    total = max(len(events), 1)

    for idx, event in enumerate(events):
        if progress_bar is not None:
            progress_bar.progress(min((idx + 1) / total, 0.55), text=f"Pulling {sport} DK/FD player props...")
        if status_text is not None:
            status_text.write(f"{sport}: checking Odds API props {idx + 1} of {total}: {event.get('away_team', '')} @ {event.get('home_team', '')}")
        event_id = event.get("id")
        if not event_id:
            continue
        payload = _fetch_event_props_for_best_buttons(sport_key, event_id, market_keys)
        rows.extend(_odds_rows_from_best_button_event(event, payload, market_specs, sport))

    board = _finalize_button_board(rows, top_n=80)
    if not board.empty:
        return board

    if progress_bar is not None:
        progress_bar.progress(0.70, text=f"Odds API empty; checking DraftKings endpoint for {sport}...")
    if status_text is not None:
        status_text.write(f"{sport}: Odds API empty or quota exhausted, checking DraftKings public endpoint...")
    dk_payload = _final_draftkings_odds_payload(sport)
    dk_rows = _final_payload_to_button_rows(dk_payload, market_specs, sport) if dk_payload else []
    dk_board = _finalize_button_board(dk_rows, top_n=80)
    if not dk_board.empty:
        return dk_board

    if progress_bar is not None:
        progress_bar.progress(0.88, text=f"DraftKings empty; checking FanDuel content endpoint for {sport}...")
    if status_text is not None:
        status_text.write(f"{sport}: DraftKings empty, checking FanDuel content-managed-page endpoint...")
    fd_payload = _fanduel_odds_payload(sport)
    fd_rows = _final_payload_to_button_rows(fd_payload, market_specs, sport) if fd_payload else []
    fd_board = _finalize_button_board(fd_rows, top_n=80)
    if not fd_board.empty:
        return fd_board

    if status_text is not None:
        status_text.write(f"{sport}: FanDuel endpoint was reached, but no matching player prop markets were parsed. Open the FanDuel Response and copy one market with player props if this persists.")
    return pd.DataFrame()


@st.cache_data(ttl=90, show_spinner=False)
def build_sport_level_prop_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
) -> pd.DataFrame:
    return build_direct_candidate_board(sport_key, market_specs, sport)



# =========================
# FINAL HOTFIX: FanDuel event-page parser for player-name selection markets
# =========================
# FanDuel NHL/NBA event-page props often do NOT look like The Odds API Over/Under rows.
# Example: market = "Player 1+ Points" and each selection name is the player, with odds.
# The older parser only looked for explicit Over/Under selections, so it returned empty.

def _fd_threshold_line_from_text(text: str, default_line: Optional[float] = None) -> Optional[float]:
    s = str(text).lower()
    # "Player 1+ Points" means over 0.5; "2+ Shots" means over 1.5.
    import re
    m = re.search(r"(\d+)\s*\+", s)
    if m:
        try:
            return float(int(m.group(1)) - 0.5)
        except Exception:
            pass
    line = _final_extract_line_from_text(s)
    if line is not None:
        return float(line)
    return default_line


def _fd_market_info_from_text(text: str, sport: str) -> Optional[Tuple[str, float]]:
    s = str(text).lower().replace("-", " ")

    if sport == "NHL":
        if "shot" in s and ("player" in s or "sog" in s or "shots on goal" in s):
            return "player_shots_on_goal", _fd_threshold_line_from_text(s, 0.5) or 0.5
        if "goal scorer" in s or "any time goal" in s or "anytime goal" in s:
            return "player_goals", 0.5
        if "goal" in s and "game line" not in s and "total" not in s and "team" not in s:
            return "player_goals", _fd_threshold_line_from_text(s, 0.5) or 0.5
        if "point" in s and ("player" in s or "+ points" in s):
            return "player_points", _fd_threshold_line_from_text(s, 0.5) or 0.5

    if sport == "NBA":
        if ("3 pointer" in s or "3-pointers" in s or "three" in s or "threes" in s) and ("player" in s or "+" in s):
            return "player_threes", _fd_threshold_line_from_text(s, 0.5) or 0.5
        if "point" in s and ("player" in s or "+ points" in s):
            return "player_points", _fd_threshold_line_from_text(s, 0.5) or 0.5

    # Fallback to the older mapper for true Over/Under style markets.
    old = _final_market_from_blob(s, sport)
    if old is not None:
        _, market_key = old
        return market_key, _fd_threshold_line_from_text(s, 0.5) or 0.5
    return None


def _fd_selection_player_name(sel: Dict[str, Any], sport: str) -> str:
    for k in [
        "runnerName", "selectionName", "name", "displayName", "participantName", "playerName",
        "title", "description", "label"
    ]:
        raw = str(sel.get(k) or "").strip()
        if not raw:
            continue
        # Do not treat Over/Under as a player.
        if normalize_name(raw) in {"over", "under", "o", "u", "yes", "no"}:
            continue
        cleaned = _final_clean_player_candidate(raw, sport)
        if cleaned:
            return cleaned
    return ""


def _fd_selection_line(sel: Dict[str, Any], market: Dict[str, Any], default_line: Optional[float]) -> Optional[float]:
    for obj in [sel, market]:
        for k in ["handicap", "runnerHandicap", "line", "points", "point", "spread", "selectionLine"]:
            val = _safe_float_line(obj.get(k))
            if val is not None:
                return float(val)
    text_line = _fd_threshold_line_from_text(_final_text_blob(sel, market), default_line)
    return float(text_line) if text_line is not None else None


@st.cache_data(ttl=60, show_spinner=False)
def _fanduel_event_page_odds_payload(sport: str) -> Dict[str, Any]:
    payloads = _fd_fetch_event_page_payloads(sport)
    grouped: Dict[str, Dict[Tuple[str, float], Dict[str, Any]]] = {}

    for payload in payloads:
        markets = _fd_extract_all_markets(payload)
        selections = _fd_extract_all_selections(payload)

        selections_by_market: Dict[str, List[Dict[str, Any]]] = {}
        for sel in selections:
            mid = _fd_market_id_any(sel)
            if mid:
                selections_by_market.setdefault(str(mid), []).append(sel)

        for market in markets:
            market_id = _fd_market_id_any(market) or str(market.get("id") or "")
            attached: List[Dict[str, Any]] = []
            if market_id:
                attached.extend(selections_by_market.get(str(market_id), []))

            for key in ["runners", "runnerDetails", "outcomes", "selections"]:
                val = market.get(key)
                if isinstance(val, list):
                    attached.extend([x for x in val if isinstance(x, dict)])
                elif isinstance(val, dict):
                    attached.extend([x for x in val.values() if isinstance(x, dict)])

            if not attached:
                continue

            market_blob = _final_text_blob(market)
            prop_info = _fd_market_info_from_text(market_blob, sport)
            if prop_info is None:
                # Some FanDuel payloads put market text near the attached selections.
                prop_info = _fd_market_info_from_text(_final_text_blob(market, *attached[:5]), sport)
            if prop_info is None:
                continue

            odds_market_key, default_line = prop_info
            grouped.setdefault(odds_market_key, {})

            for sel in attached:
                odds = _fd_any_american_odds(sel)
                if odds is None:
                    continue

                side = _fd_side_from_selection(sel)
                player = _fd_selection_player_name(sel, sport)
                line = _fd_selection_line(sel, market, default_line)

                # FanDuel yes-style props: market is "Player 1+ Points" and selection is player name.
                # Treat each player selection as an Over on the threshold line.
                if side is None and player:
                    side = "Over"

                # True Over/Under style props may have player in market and side in selection.
                if not player:
                    player = _fd_player_from_market_or_selection(sel, market, sport)

                if side not in {"Over", "Under"} or not player or line is None:
                    continue

                rec_key = (normalize_name(player), float(line))
                rec = grouped[odds_market_key].setdefault(
                    rec_key,
                    {"player": player, "line": float(line), "over": None, "under": None},
                )
                if side == "Over":
                    rec["over"] = odds
                else:
                    rec["under"] = odds

    shaped_markets = []
    for odds_market_key, recs in grouped.items():
        outcomes = []
        for rec in recs.values():
            player = rec["player"]
            line = rec["line"]
            if rec.get("over") is not None:
                outcomes.append({
                    "name": "Over",
                    "description": player,
                    "participant": player,
                    "point": line,
                    "price": int(rec["over"]),
                })
            if rec.get("under") is not None:
                outcomes.append({
                    "name": "Under",
                    "description": player,
                    "participant": player,
                    "point": line,
                    "price": int(rec["under"]),
                })
        if outcomes:
            shaped_markets.append({"key": odds_market_key, "outcomes": outcomes})

    if not shaped_markets:
        return {}

    return {
        "id": f"fanduel_event_page_{sport.lower()}",
        "home_team": "",
        "away_team": "",
        "bookmakers": [{"key": "fanduel", "title": "FanDuel", "markets": shaped_markets}],
    }


def _fanduel_odds_payload(sport: str) -> Dict[str, Any]:
    event_payload = _fanduel_event_page_odds_payload(sport)
    market_keys = NBA_POINTS_MARKET_KEYS + NBA_THREES_MARKET_KEYS if sport == "NBA" else NHL_POINTS_MARKET_KEYS + NHL_SHOTS_MARKET_KEYS + NHL_GOALS_MARKET_KEYS
    if _event_payload_contains_any_market(event_payload, market_keys):
        return event_payload
    try:
        return _fanduel_odds_payload_OLD_CONTENT_PAGE(sport)  # type: ignore[name-defined]
    except Exception:
        return {}


def get_odds_cache_summary() -> Dict[str, Any]:
    cache = _read_odds_cache()
    today = _odds_cache_day()
    today_entries = []
    all_entries = []
    for entry in cache.values():
        if not isinstance(entry, dict):
            continue
        saved_at = float(entry.get("saved_at", 0) or 0)
        saved_day = str(entry.get("saved_day", ""))
        all_entries.append(entry)
        if saved_day == today:
            today_entries.append(entry)

    latest_today = max([float(e.get("saved_at", 0) or 0) for e in today_entries], default=None)
    latest_any = max([float(e.get("saved_at", 0) or 0) for e in all_entries], default=None)
    return {
        "today": today,
        "today_count": len(today_entries),
        "total_count": len(all_entries),
        "latest_today_age": None if latest_today is None else time.time() - latest_today,
        "latest_any_age": None if latest_any is None else time.time() - latest_any,
    }


def clear_todays_odds_snapshot() -> int:
    cache = _read_odds_cache()
    today = _odds_cache_day()
    kept = {}
    removed = 0
    for key, entry in cache.items():
        if isinstance(entry, dict) and str(entry.get("saved_day", "")) == today:
            removed += 1
        else:
            kept[key] = entry
    _write_odds_cache(kept)
    return removed


def render_daily_odds_snapshot_controls() -> None:
    summary = get_odds_cache_summary()
    latest_age = summary.get("latest_today_age")
    status_text = "Ready" if summary.get("today_count", 0) else "No daily snapshot yet"
    status_sub = (
        f"{summary.get('today_count', 0)} cached odds responses today • Latest pull {_format_cache_age(latest_age)}"
        if summary.get("today_count", 0)
        else "First odds lookup today will create the daily snapshot automatically."
    )

    st.markdown(
        f"""
        <div class="quick-card" style="margin-top: 0.65rem; margin-bottom: 0.8rem;">
            <div class="quick-card-title">Daily Odds Snapshot</div>
            <div class="quick-card-main">{status_text}</div>
            <div class="quick-card-sub">{status_sub}</div>
            <div class="quick-card-sub">Mode: one successful pull per unique odds request per day. Buttons reuse saved data instead of burning credits.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 3])
    with c1:
        refresh_password = st.text_input(
            "Refresh password",
            type="password",
            key="refresh_daily_odds_password",
            placeholder="Enter password",
            help="Required so shared users cannot burn API credits.",
        )
        if st.button("Refresh Today's Odds", key="refresh_daily_odds_snapshot", help="Uses API credits intentionally, then saves a fresh daily snapshot."):
            if refresh_password == "Duncan":
                removed = clear_todays_odds_snapshot()
                st.session_state["odds_force_refresh_until"] = time.time() + ODDS_FORCE_REFRESH_SECONDS
                try:
                    st.cache_data.clear()
                except Exception:
                    pass
                st.success(f"Today's odds snapshot was reset ({removed} cached responses cleared). The next odds load will pull fresh data and save it for the day.")
            else:
                st.error("Incorrect refresh password. Odds were not refreshed and no API credits were intentionally used.")
    with c2:
        st.caption("Leave this alone for normal use. Refreshing is password protected so shared users cannot run through your API credits. Use it only after injuries/news or when odds changed.")


def get_cached_today_game_counts() -> Dict[str, int]:
    """Read saved daily odds snapshots and count today's NBA/NHL games without spending API credits."""
    counts = {"NBA": 0, "NHL": 0}
    cache = _read_odds_cache()
    today = _odds_cache_day()

    for entry in cache.values():
        if not isinstance(entry, dict) or str(entry.get("saved_day", "")) != today:
            continue

        url = str(entry.get("url", "")).lower()
        params = entry.get("params") or {}
        markets = str(params.get("markets", "")).lower()
        data = entry.get("data")

        if not isinstance(data, list):
            continue
        if markets not in {"h2h", ""}:
            continue

        if "basketball_nba" in url:
            counts["NBA"] = max(counts["NBA"], len(data))
        elif "icehockey_nhl" in url:
            counts["NHL"] = max(counts["NHL"], len(data))

    return counts

def render_home_status_bar() -> None:
    summary = get_odds_cache_summary()
    latest_age = summary.get("latest_today_age")
    last_update = _format_cache_age(latest_age) if latest_age is not None else "No snapshot yet"
    today_count = int(summary.get("today_count", 0) or 0)
    cache_main = "Active" if today_count else "Waiting"
    cache_sub = f"{today_count} saved pulls today" if today_count else "First pull creates snapshot"
    game_counts = get_cached_today_game_counts()
    games_main = f"NBA {game_counts.get('NBA', 0)} • NHL {game_counts.get('NHL', 0)}"
    if game_counts.get('NBA', 0) == 0 and game_counts.get('NHL', 0) == 0:
        games_main = "Load odds to count"

    st.markdown(
        f'''
        <div class="daily-dashboard-bar">
            <div class="status-pill">
                <div class="status-icon">📅</div>
                <div>
                    <div class="status-label">Odds Updated</div>
                    <div class="status-main">{last_update}</div>
                    <div class="status-sub">Daily snapshot mode</div>
                </div>
            </div>
            <div class="status-pill">
                <div class="status-icon">💾</div>
                <div>
                    <div class="status-label">Cache Status</div>
                    <div class="status-main">{cache_main}<span class="status-dot"></span></div>
                    <div class="status-sub">{cache_sub}</div>
                </div>
            </div>
            <div class="status-pill">
                <div class="status-icon">🏟️</div>
                <div>
                    <div class="status-label">Today's Games</div>
                    <div class="status-main">{games_main}</div>
                    <div class="status-sub">From saved daily odds snapshot</div>
                </div>
            </div>
            <div class="status-pill">
                <div class="status-icon">🤖</div>
                <div>
                    <div class="status-label">Model</div>
                    <div class="status-main">V2 Active</div>
                    <div class="status-sub">Projection factors + parlay math</div>
                </div>
            </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )


# =========================
# UI
# =========================

st.markdown(
    """
    <div class="app-hero">
        <div class="hero-kicker">Live Props • Model Edge • Parlay Builder</div>
        <div class="app-title">NBA + NHL Prop Parlay Engine</div>
        <div class="app-subtitle">
            A cleaner prop analytics dashboard for finding the strongest player legs, comparing sportsbook odds,
            and building smarter parlays from model probability, expected value, and payout.
        </div>
        <div class="hero-badges">
            <span class="hero-badge">DraftKings / FanDuel odds layer</span>
            <span class="hero-badge">Cached API pulls</span>
            <span class="hero-badge">Best legs + 3 parlay styles</span>
            <span class="hero-badge">NBA + NHL markets</span>
        </div>
    </div>
    <div class="logo-strip">
        <div class="logo-strip-label">Tracking</div>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nba/500/den.png" title="Denver Nuggets"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nba/500/ny.png" title="New York Knicks"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nba/500/bos.png" title="Boston Celtics"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nba/500/okc.png" title="Oklahoma City Thunder"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nba/500/gs.png" title="Golden State Warriors"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nba/500/lal.png" title="Los Angeles Lakers"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nba/500/lac.png" title="LA Clippers"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nba/500/mia.png" title="Miami Heat"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nba/500/mil.png" title="Milwaukee Bucks"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nba/500/phi.png" title="Philadelphia 76ers"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nba/500/dal.png" title="Dallas Mavericks"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nba/500/phx.png" title="Phoenix Suns"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nba/500/min.png" title="Minnesota Timberwolves"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nba/500/cle.png" title="Cleveland Cavaliers"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nba/500/ind.png" title="Indiana Pacers"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nba/500/orl.png" title="Orlando Magic"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nhl/500/col.png" title="Colorado Avalanche"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nhl/500/nyr.png" title="New York Rangers"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nhl/500/nj.png" title="New Jersey Devils"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nhl/500/edm.png" title="Edmonton Oilers"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nhl/500/fla.png" title="Florida Panthers"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nhl/500/bos.png" title="Boston Bruins"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nhl/500/tor.png" title="Toronto Maple Leafs"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nhl/500/tb.png" title="Tampa Bay Lightning"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nhl/500/veg.png" title="Vegas Golden Knights"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nhl/500/car.png" title="Carolina Hurricanes"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nhl/500/dal.png" title="Dallas Stars"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nhl/500/wsh.png" title="Washington Capitals"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nhl/500/van.png" title="Vancouver Canucks"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nhl/500/nyi.png" title="New York Islanders"/>
        <img class="team-logo" src="https://a.espncdn.com/i/teamlogos/nhl/500/pit.png" title="Pittsburgh Penguins"/>
    </div>
    """,
    unsafe_allow_html=True,
)

render_home_status_bar()

st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
render_daily_odds_snapshot_controls()
st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)



# =========================
# FINAL FANDUEL EVENT-PAGE WIRING - ROBUST PLAYER PROP PARSER
# =========================
# This override is intentionally limited to the odds/button path. It uses the
# FanDuel event-page endpoint the user captured in Edge DevTools:
# https://api.sportsbook.fanduel.com/sbapi/event-page?_ak=...&eventId=...
# It handles both formats FanDuel uses:
#   1) Over/Under rows: market/player with selections named Over and Under
#   2) Threshold rows: market = "Player 1+ Points" and selections are player names

FANDUEL_EVENT_PAGE_AK = "FhMFpcPWXMeyZxOx"
FANDUEL_KNOWN_EVENT_IDS = {
    "NHL": ["35558454"],
    "NBA": [],
}
FANDUEL_EVENT_PAGE_TABS = [
    None,
    "same-game-parlay-",
    "player-props",
    "points",
    "shots",
    "goals",
    "period-player-props",
    "quick-hits",
]


def _fd_event_page_headers(sport: str = "NHL") -> Dict[str, str]:
    league = "nhl" if sport == "NHL" else "nba"
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36 Edg/120",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://sportsbook.fanduel.com",
        "Referer": f"https://sportsbook.fanduel.com/navigation/{league}",
        "X-Application": "Sportsbook",
    }


def _fd_fetch_json_url(url: str, sport: str = "NHL") -> Optional[Dict[str, Any]]:
    try:
        resp = requests.get(url, headers=_fd_event_page_headers(sport), timeout=REQUEST_TIMEOUT)
        if not resp.ok:
            return None
        data = resp.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _fd_deep_event_ids(obj: Any) -> List[str]:
    ids: List[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if kl in {"eventid", "event_id", "eventidstr", "eventidlong"} or (kl == "id" and "event" in _final_text_blob(obj).lower()):
                s_val = str(v).strip()
                if s_val.isdigit() and len(s_val) >= 5:
                    ids.append(s_val)
            ids.extend(_fd_deep_event_ids(v))
    elif isinstance(obj, list):
        for item in obj:
            ids.extend(_fd_deep_event_ids(item))
    return ids


@st.cache_data(ttl=300, show_spinner=False)
def _fd_discover_event_ids(sport: str) -> List[str]:
    league = "nhl" if sport == "NHL" else "nba"
    urls = [
        f"https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=CUSTOM&customPageId={league}&pbHorizontal=false&_ak={FANDUEL_EVENT_PAGE_AK}&timezone=America%2FDenver",
        f"https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=CUSTOM&customPageId={league}&tab=player-props&pbHorizontal=false&_ak={FANDUEL_EVENT_PAGE_AK}&timezone=America%2FDenver",
        f"https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=CUSTOM&customPageId={league}&tab=parlay-builder&pbHorizontal=false&_ak={FANDUEL_EVENT_PAGE_AK}&timezone=America%2FDenver",
    ]
    found: List[str] = []
    for url in urls:
        payload = _fd_fetch_json_url(url, sport)
        if isinstance(payload, dict):
            found.extend(_fd_deep_event_ids(payload))

    out: List[str] = []
    for eid in FANDUEL_KNOWN_EVENT_IDS.get(sport, []) + found:
        if eid and eid not in out:
            out.append(eid)
    return out[:40]


@st.cache_data(ttl=90, show_spinner=False)
def _fd_fetch_event_page_payloads(sport: str) -> List[Dict[str, Any]]:
    payloads: List[Dict[str, Any]] = []
    seen_urls = set()
    for event_id in _fd_discover_event_ids(sport):
        for tab in FANDUEL_EVENT_PAGE_TABS:
            base = f"https://api.sportsbook.fanduel.com/sbapi/event-page?_ak={FANDUEL_EVENT_PAGE_AK}&eventId={event_id}&useCombinedTouchdownsVirtualMarket=true&useQuickBets=true"
            url = base if tab is None else base + f"&tab={tab}"
            if url in seen_urls:
                continue
            seen_urls.add(url)
            payload = _fd_fetch_json_url(url, sport)
            if isinstance(payload, dict):
                payloads.append(payload)
    return payloads


def _fd_attachment_dict(payload: Dict[str, Any], key: str) -> Dict[str, Dict[str, Any]]:
    attachments = payload.get("attachments", {}) if isinstance(payload, dict) else {}
    raw = attachments.get(key, {}) if isinstance(attachments, dict) else {}
    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items() if isinstance(v, dict)}
    if isinstance(raw, list):
        out: Dict[str, Dict[str, Any]] = {}
        for x in raw:
            if isinstance(x, dict):
                xid = str(x.get("id") or x.get("marketId") or x.get("selectionId") or len(out))
                out[xid] = x
        return out
    return {}


def _fd_market_id_any(obj: Dict[str, Any]) -> Optional[str]:
    for k in ["marketId", "eventMarketId", "externalMarketId", "selectionMarketId", "parentMarketId", "market_id", "id"]:
        v = obj.get(k)
        if v is not None:
            return str(v)
    return None


def _fd_any_american_odds(obj: Dict[str, Any]) -> Optional[int]:
    def dec_to_american(d: float) -> Optional[int]:
        if d <= 1.0:
            return None
        return decimal_to_american(d)

    preferred = [
        "americanOdds", "americanDisplayOdds", "displayOdds", "price", "odds", "winRunnerOdds", "runnerOdds",
        "currentPrice", "trueOdds", "oddsValue", "numerator", "decimalOdds"
    ]
    for key in preferred:
        val = obj.get(key)
        if isinstance(val, dict):
            for sub in ["americanOdds", "americanDisplayOdds", "american", "displayOdds", "price"]:
                parsed = _safe_int_odds(val.get(sub))
                if parsed is not None and -20000 < parsed < 20000 and parsed not in {0, 1}:
                    return parsed
            for sub in ["decimalOdds", "decimal", "trueOdds"]:
                try:
                    dv = float(val.get(sub))
                    amer = dec_to_american(dv)
                    if amer is not None:
                        return amer
                except Exception:
                    pass
        parsed = _safe_int_odds(val)
        if parsed is not None and -20000 < parsed < 20000 and parsed not in {0, 1}:
            return parsed
        try:
            if isinstance(val, (float, int, str)) and 1.01 <= float(val) <= 100:
                amer = dec_to_american(float(val))
                if amer is not None:
                    return amer
        except Exception:
            pass

    # Fall back to any price-ish field.
    for k, v in obj.items():
        if isinstance(v, dict):
            nested = _fd_any_american_odds(v)
            if nested is not None:
                return nested
        if isinstance(v, (str, int, float)) and any(x in str(k).lower() for x in ["odds", "price"]):
            parsed = _safe_int_odds(v)
            if parsed is not None and -20000 < parsed < 20000 and parsed not in {0, 1}:
                return parsed
            try:
                if 1.01 <= float(v) <= 100:
                    return dec_to_american(float(v))
            except Exception:
                pass
    return None


def _fd_extract_all_selections(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    selections: List[Dict[str, Any]] = []
    for name in ["selections", "runners", "runnerDetails", "outcomes"]:
        selections.extend(_fd_attachment_dict(payload, name).values())

    for obj in _final_flatten_dicts(payload):
        keys = {str(k).lower() for k in obj.keys()}
        if any(k in keys for k in ["selectionid", "runnerid", "runnername", "selectionname", "winrunnerodds", "americanodds"]):
            selections.append(obj)

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for sel in selections:
        sid = str(sel.get("selectionId") or sel.get("runnerId") or sel.get("id") or id(sel))
        mid = str(_fd_market_id_any(sel) or "")
        key = (sid, mid, _final_text_blob(sel)[:120])
        if key not in seen:
            seen.add(key)
            deduped.append(sel)
    return deduped


def _fd_extract_all_markets(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    markets = list(_fd_attachment_dict(payload, "markets").values())
    for obj in _final_flatten_dicts(payload):
        if not isinstance(obj, dict):
            continue
        blob = _final_text_blob(obj).lower()
        if any(k in obj for k in ["marketName", "eventMarketName", "marketType", "marketTypeName", "name", "title", "runners", "runnerDetails", "rows"]):
            if any(x in blob for x in ["player", "points", "shots", "goals", "3-pointers", "three", "threes", "point scorer", "goal scorer"]):
                markets.append(obj)

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for m in markets:
        mid = str(_fd_market_id_any(m) or m.get("id") or id(m))
        if mid not in seen:
            seen.add(mid)
            deduped.append(m)
    return deduped


def _fd_threshold_line_from_text(text: str, default_line: Optional[float] = None) -> Optional[float]:
    s = str(text).lower()
    import re
    # Player 1+ Points = over 0.5, Player 2+ Shots = over 1.5, etc.
    m = re.search(r"(\d+)\s*\+", s)
    if m:
        try:
            return float(int(m.group(1)) - 0.5)
        except Exception:
            pass
    line = _final_extract_line_from_text(s)
    if line is not None:
        return float(line)
    return default_line


def _fd_market_info_from_text(text: str, sport: str) -> Optional[Tuple[str, float]]:
    s = str(text).lower().replace("-", " ")

    if sport == "NHL":
        if "shot" in s and ("player" in s or "shots on goal" in s or "sog" in s):
            return "player_shots_on_goal", _fd_threshold_line_from_text(s, 0.5) or 0.5
        if "goal scorer" in s or "any time goal" in s or "anytime goal" in s:
            return "player_goals", 0.5
        if "goal" in s and "game line" not in s and "total" not in s and "team" not in s:
            return "player_goals", _fd_threshold_line_from_text(s, 0.5) or 0.5
        if "point" in s and ("player" in s or "+ points" in s or "points" in s):
            return "player_points", _fd_threshold_line_from_text(s, 0.5) or 0.5

    if sport == "NBA":
        if ("3 pointer" in s or "3-pointers" in s or "three" in s or "threes" in s) and ("player" in s or "+" in s):
            return "player_threes", _fd_threshold_line_from_text(s, 0.5) or 0.5
        if "point" in s and ("player" in s or "+ points" in s or "points" in s):
            return "player_points", _fd_threshold_line_from_text(s, 0.5) or 0.5

    old = _final_market_from_blob(s, sport)
    if old is not None:
        _, market_key = old
        return market_key, _fd_threshold_line_from_text(s, 0.5) or 0.5
    return None


def _fd_side_from_selection(sel: Dict[str, Any]) -> Optional[str]:
    name = str(sel.get("runnerName") or sel.get("selectionName") or sel.get("name") or sel.get("displayName") or "").strip().lower()
    blob = _final_text_blob(sel).lower()
    if name in {"over", "o"} or " over " in f" {blob} ":
        return "Over"
    if name in {"under", "u"} or " under " in f" {blob} ":
        return "Under"
    return None


def _fd_selection_player_name(sel: Dict[str, Any], market: Dict[str, Any], sport: str) -> str:
    # Selection-first handles threshold markets: selection = player, market = Player 1+ Points.
    for obj in [sel, market]:
        for k in ["participantName", "playerName", "runnerName", "selectionName", "name", "displayName", "title", "description", "label", "marketName", "eventMarketName"]:
            raw = str(obj.get(k) or "").strip()
            if not raw:
                continue
            if normalize_name(raw) in {"over", "under", "o", "u", "yes", "no"}:
                continue
            cleaned = _final_clean_player_candidate(raw, sport)
            if cleaned:
                return cleaned
    return ""


def _fd_line_from_market_or_selection(sel: Dict[str, Any], market: Dict[str, Any], default_line: Optional[float]) -> Optional[float]:
    for obj in [sel, market]:
        for k in ["handicap", "runnerHandicap", "line", "points", "point", "spread", "selectionLine"]:
            val = _safe_float_line(obj.get(k))
            if val is not None:
                return float(val)
    line = _fd_threshold_line_from_text(_final_text_blob(sel, market), default_line)
    return float(line) if line is not None else None


@st.cache_data(ttl=90, show_spinner=False)
def _fanduel_event_page_odds_payload(sport: str) -> Dict[str, Any]:
    payloads = _fd_fetch_event_page_payloads(sport)
    grouped: Dict[str, Dict[Tuple[str, float], Dict[str, Any]]] = {}

    for payload in payloads:
        markets = _fd_extract_all_markets(payload)
        selections = _fd_extract_all_selections(payload)

        selections_by_market: Dict[str, List[Dict[str, Any]]] = {}
        for sel in selections:
            mid = _fd_market_id_any(sel)
            if mid:
                selections_by_market.setdefault(str(mid), []).append(sel)

        for market in markets:
            market_id = _fd_market_id_any(market) or str(market.get("id") or "")
            attached: List[Dict[str, Any]] = []
            if market_id:
                attached.extend(selections_by_market.get(str(market_id), []))
            for key in ["runners", "runnerDetails", "outcomes", "selections"]:
                val = market.get(key)
                if isinstance(val, list):
                    attached.extend([x for x in val if isinstance(x, dict)])
                elif isinstance(val, dict):
                    attached.extend([x for x in val.values() if isinstance(x, dict)])

            if not attached:
                continue

            market_blob = _final_text_blob(market)
            prop_info = _fd_market_info_from_text(market_blob, sport)
            if prop_info is None:
                prop_info = _fd_market_info_from_text(_final_text_blob(market, *attached[:8]), sport)
            if prop_info is None:
                continue

            odds_market_key, default_line = prop_info
            grouped.setdefault(odds_market_key, {})

            for sel in attached:
                odds = _fd_any_american_odds(sel)
                if odds is None:
                    continue

                side = _fd_side_from_selection(sel)
                player = _fd_selection_player_name(sel, market, sport)
                line = _fd_line_from_market_or_selection(sel, market, default_line)

                # FanDuel threshold props: market = "Player 1+ Points" and each selection is a player.
                if side is None and player:
                    side = "Over"

                if side not in {"Over", "Under"} or not player or line is None:
                    continue

                rec_key = (normalize_name(player), float(line))
                rec = grouped[odds_market_key].setdefault(
                    rec_key,
                    {"player": player, "line": float(line), "over": None, "under": None},
                )
                if side == "Over":
                    rec["over"] = odds
                else:
                    rec["under"] = odds

    shaped_markets = []
    for odds_market_key, recs in grouped.items():
        outcomes = []
        for rec in recs.values():
            player = rec["player"]
            line = rec["line"]
            if rec.get("over") is not None:
                outcomes.append({"name": "Over", "description": player, "participant": player, "point": line, "price": int(rec["over"])})
            if rec.get("under") is not None:
                outcomes.append({"name": "Under", "description": player, "participant": player, "point": line, "price": int(rec["under"])})
        if outcomes:
            shaped_markets.append({"key": odds_market_key, "outcomes": outcomes})

    if not shaped_markets:
        return {}
    return {
        "id": f"fanduel_event_page_{sport.lower()}",
        "home_team": "",
        "away_team": "",
        "bookmakers": [{"key": "fanduel", "title": "FanDuel", "markets": shaped_markets}],
    }


def _fanduel_odds_payload(sport: str) -> Dict[str, Any]:
    event_payload = _fanduel_event_page_odds_payload(sport)
    target_markets = NBA_POINTS_MARKET_KEYS + NBA_THREES_MARKET_KEYS if sport == "NBA" else NHL_POINTS_MARKET_KEYS + NHL_SHOTS_MARKET_KEYS + NHL_GOALS_MARKET_KEYS
    if _event_payload_contains_any_market(event_payload, target_markets):
        return event_payload
    try:
        return _fanduel_odds_payload_OLD_CONTENT_PAGE(sport)  # type: ignore[name-defined]
    except Exception:
        return event_payload if isinstance(event_payload, dict) else {}



# =========================
# MANUAL NBA PARLAY BUILDER ODDS FIX
# =========================
# The Best Legs / Best Parlays buttons were repaired to use the cached odds layer and
# public endpoint fallbacks. The NBA manual parlay builder was still relying mostly on
# the old event-only Odds API path, so when the monthly quota was exhausted it could not
# find sportsbook lines/odds even though the buttons could. These helpers let the manual
# builder reuse the same fallback odds payloads without changing the rest of the app.

def _manual_pick_prop_row_from_payload(
    payload: Dict[str, Any],
    player_name: str,
    market_keys: List[str],
    desired_target: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict) or not payload:
        return None

    try:
        rows = extract_main_lines_for_market(payload, market_keys)
    except Exception:
        return None

    candidates = []
    desired_line = None
    if desired_target is not None:
        try:
            desired_line = float(desired_target) - 0.5
        except Exception:
            desired_line = None

    for row in rows:
        try:
            if not player_name_matches(player_name, row.get("player_name_raw", "")):
                continue
            if row.get("line") is None or row.get("over_odds") is None:
                continue

            line = float(row.get("line"))
            line_distance = abs(line - desired_line) if desired_line is not None else 0.0
            odds = row.get("over_odds")
            implied = american_to_implied_prob(odds)
            even_distance = abs((implied or 0.5) - 0.5)
            candidates.append((line_distance, even_distance, row))
        except Exception:
            continue

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][2]


def _manual_nba_prop_sources(event: Optional[Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any]]]:
    sources: List[Tuple[str, Dict[str, Any]]] = []
    market_keys = NBA_POINTS_MARKET_KEYS + NBA_THREES_MARKET_KEYS

    # 1) Existing event-specific path. This uses the persistent cache first, so if the
    # same request was already saved it will not burn another credit.
    if event and event.get("id"):
        try:
            event_payload = get_event_props(NBA_SPORT_KEY, event["id"], market_keys).get("data", {})
            if isinstance(event_payload, dict) and event_payload:
                sources.append(("Event sportsbook/cache", event_payload))
        except Exception:
            pass

    # 2) FanDuel / DraftKings public endpoint payloads used by the Best buttons.
    for label, fn in [
        ("FanDuel endpoint", lambda: _fanduel_odds_payload("NBA")),
        ("DraftKings endpoint", lambda: _final_draftkings_odds_payload("NBA")),
    ]:
        try:
            payload = fn()
            if isinstance(payload, dict) and payload:
                sources.append((label, payload))
        except Exception:
            pass

    return sources


def get_manual_nba_player_props(
    player_name: str,
    event: Optional[Dict[str, Any]],
    target_pts: Optional[int] = None,
    target_3pt: Optional[int] = None,
) -> Dict[str, Any]:
    props = {
        "points_line": None,
        "points_over": None,
        "threes_line": None,
        "threes_over": None,
        "books": None,
        "source": None,
    }

    for source_name, payload in _manual_nba_prop_sources(event):
        if props["points_line"] is None:
            pts_row = _manual_pick_prop_row_from_payload(payload, player_name, NBA_POINTS_MARKET_KEYS, target_pts)
            if pts_row:
                props["points_line"] = pts_row.get("line")
                props["points_over"] = pts_row.get("over_odds")
                props["books"] = dedupe_csv_names([props["books"] or "", pts_row.get("book_key", "")])
                props["source"] = dedupe_csv_names([props["source"] or "", source_name])

        if props["threes_line"] is None:
            threes_row = _manual_pick_prop_row_from_payload(payload, player_name, NBA_THREES_MARKET_KEYS, target_3pt)
            if threes_row:
                props["threes_line"] = threes_row.get("line")
                props["threes_over"] = threes_row.get("over_odds")
                props["books"] = dedupe_csv_names([props["books"] or "", threes_row.get("book_key", "")])
                props["source"] = dedupe_csv_names([props["source"] or "", source_name])

        if props["points_line"] is not None and props["threes_line"] is not None:
            break

    return props

nba_tab, nhl_tab = st.tabs(["🏀 NBA", "🏒 NHL"])

with nba_tab:
    st.subheader("Top Candidate Legs Today")
    if st.button("Find Top Candidate Legs Today", key="nba_top_legs"):
        progress_bar = st.progress(0, text="Starting NBA scan...")
        status_text = st.empty()
        candidate_df = build_ranked_best_leg_board(
            NBA_SPORT_KEY,
            [("PTS", NBA_POINTS_MARKET_KEYS), ("3PT", NBA_THREES_MARKET_KEYS)],
            "NBA",
            progress_bar=progress_bar,
            status_text=status_text,
            top_n=20,
            enrich_rows=36,
        )
        progress_bar.empty()
        status_text.empty()
        render_candidate_table(candidate_df)

    st.markdown("---")
    st.subheader("Best Parlays Today")
    if st.button("Find Best Parlays Today", key="nba_best_parlays", type="primary"):
        progress_bar = st.progress(0, text="Starting NBA parlay engine...")
        status_text = st.empty()
        filtered_df = build_ranked_best_leg_board(
            NBA_SPORT_KEY,
            [("PTS", NBA_POINTS_MARKET_KEYS), ("3PT", NBA_THREES_MARKET_KEYS)],
            "NBA",
            progress_bar=progress_bar,
            status_text=status_text,
            top_n=28,
            enrich_rows=44,
        )
        parlay_2 = generate_parlay_candidates(filtered_df, 2, same_game_penalty=0.08, same_team_penalty=0.05)
        parlay_3 = generate_parlay_candidates(filtered_df.head(18), 3, same_game_penalty=0.08, same_team_penalty=0.05)
        selected = select_top_parlays_with_fallback(parlay_2 + parlay_3)
        progress_bar.empty()
        status_text.empty()
        render_selected_parlays(selected)

    st.markdown("---")
    st.subheader("Safe +200 Alt Points Builder")
    st.caption("Targets NBA parlays with 80%+ model probability and +200 or better sportsbook odds using safer alt player-points lines when available.")
    if st.button("Find 80%+ / +200 Alt Points Parlays", key="nba_safe_plus200_alt_points"):
        progress_bar = st.progress(0, text="Starting NBA Safe +200 engine...")
        status_text = st.empty()

        safe_df = build_nba_safe_plus200_leg_board(
            progress_bar=progress_bar,
            status_text=status_text,
            top_n=32,
        )

        all_candidates: List[Dict[str, Any]] = []
        if not safe_df.empty:
            # 4-6 legs is usually where very safe alt-point legs can still reach +200.
            # Keep candidate counts capped so this stays fast.
            for size in [2, 3, 4, 5, 6]:
                search_df = safe_df.head(28 if size <= 4 else 24)
                all_candidates.extend(
                    generate_parlay_candidates(
                        search_df,
                        size,
                        same_game_penalty=0.06,
                        same_team_penalty=0.04,
                    )
                )

        selected_safe, closest_safe = select_nba_safe_plus200_parlays(all_candidates)
        progress_bar.empty()
        status_text.empty()

        if safe_df.empty:
            st.warning("No safe alt-points sportsbook legs were found. This usually means alt player-points lines are not available from the current odds source/cache.")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Safe alt legs scanned", len(safe_df))
            c2.metric("Parlay combos checked", len(all_candidates))
            c3.metric("Target", "80%+ / +200")
            render_safe_plus200_parlays(selected_safe, closest_safe)

    st.markdown("---")
    st.subheader("Manual Parlay Builder")

    nba_player_names = get_nba_all_player_names()
    nba_num_players = st.number_input("Number of NBA Players", min_value=1, max_value=5, value=2, step=1, key="nba_num_players")

    nba_inputs = []
    for i in range(nba_num_players):
        st.markdown(f"### NBA Player {i+1}")
        c1, c2, c3, c4 = st.columns([2.2, 1, 1, 1.3])
        with c1:
            player_name = st.selectbox(f"Select NBA Player {i+1}", nba_player_names, key=f"nba_player_{i}")
            render_selected_player_photo(player_name, "NBA")
        with c2:
            target_3pt = st.number_input("3PT Target", min_value=0, max_value=15, value=4, key=f"nba_target_3pt_{i}")
        with c3:
            target_pts = st.number_input("Points Target", min_value=0, max_value=60, value=20, key=f"nba_target_pts_{i}")
        with c4:
            leg_type = st.selectbox("Count In Parlay", ["3PT only", "Points only", "Both"], key=f"nba_leg_type_{i}")

        nba_inputs.append({"name": player_name, "target_3pt": int(target_3pt), "target_pts": int(target_pts), "leg_type": leg_type})

    if st.button("Calculate NBA Parlay", key="nba_calc"):
        total_prob = 1.0
        total_ev = 0.0
        defense_map = load_nba_defense_factor()

        for pick in nba_inputs:
            pid = get_nba_player_id(pick["name"])
            if pid is None:
                st.warning(f"Could not find player ID for {pick['name']}.")
                continue

            games = fetch_nba_recent_games(pid)
            if games.empty:
                st.warning(f"No recent game data for {pick['name']}.")
                continue

            team_abbrev = get_nba_player_team(pid)
            opponent = get_nba_confirmed_opponent_today(team_abbrev)
            if opponent is None:
                st.warning(f"{pick['name']}: no confirmed NBA game found today.")
                continue

            events = get_sport_events(NBA_SPORT_KEY)
            event = None
            for e in events:
                if (
                    e.get("home_team") == NBA_TEAM_NAME_MAP.get(team_abbrev) and e.get("away_team") == NBA_TEAM_NAME_MAP.get(opponent)
                ) or (
                    e.get("home_team") == NBA_TEAM_NAME_MAP.get(opponent) and e.get("away_team") == NBA_TEAM_NAME_MAP.get(team_abbrev)
                ):
                    event = e
                    break

            props = get_manual_nba_player_props(
                pick["name"],
                event,
                target_pts=pick["target_pts"],
                target_3pt=pick["target_3pt"],
            )

            avg_3pt = calculate_nba_weighted_avg(games, "FG3M")
            avg_pts = calculate_nba_weighted_avg(games, "PTS")

            prob_3pt, exp_3pt = calculate_poisson_probability(avg_3pt, defense_map.get(opponent, 1.0), pick["target_3pt"])
            prob_pts, exp_pts = calculate_poisson_probability(avg_pts, 1.0, pick["target_pts"])

            fair_3pt = probability_to_fair_american(prob_3pt)
            fair_pts = probability_to_fair_american(prob_pts)
            ev_3pt = calculate_ev(prob_3pt, american_to_decimal(props["threes_over"]))
            ev_pts = calculate_ev(prob_pts, american_to_decimal(props["points_over"]))

            line_3pt = build_manual_line(props["threes_line"], exp_3pt, pick["target_3pt"], 0.5)
            line_pts = build_manual_line(props["points_line"], exp_pts, pick["target_pts"], 6.5)

            if pick["leg_type"] == "3PT only":
                total_prob *= prob_3pt / 100
                total_ev += ev_3pt or 0
            elif pick["leg_type"] == "Points only":
                total_prob *= prob_pts / 100
                total_ev += ev_pts or 0
            else:
                total_prob *= (prob_3pt / 100) * (prob_pts / 100)
                total_ev += (ev_3pt or 0) + (ev_pts or 0)

            st.markdown("---")
            st.subheader(f"{pick['name']} · {team_abbrev} vs {opponent}")
            r1 = st.columns(4)
            r1[0].markdown(metric_card("Tonight 3PT line", safe_line_display(line_3pt), subtext=(props.get("source") or "Sportsbook") if props["threes_line"] else "Model estimate"), unsafe_allow_html=True)
            r1[1].markdown(metric_card("Your 3PT target", str(pick["target_3pt"]), subtext=f"Fair odds: {safe_odds_display(fair_3pt)}"), unsafe_allow_html=True)
            r1[2].markdown(metric_card("3PT hit probability", f"{prob_3pt}%"), unsafe_allow_html=True)
            r1[3].markdown(metric_card("3PT EV", str(ev_3pt) if ev_3pt is not None else "Model only", "good" if (ev_3pt or 0) > 0 else "neutral", f"Book over: {safe_odds_display(props['threes_over'])}"), unsafe_allow_html=True)

            r2 = st.columns(4)
            r2[0].markdown(metric_card("Tonight points line", safe_line_display(line_pts), subtext=(props.get("source") or "Sportsbook") if props["points_line"] else "Model estimate"), unsafe_allow_html=True)
            r2[1].markdown(metric_card("Your points target", str(pick["target_pts"]), subtext=f"Fair odds: {safe_odds_display(fair_pts)}"), unsafe_allow_html=True)
            r2[2].markdown(metric_card("Points hit probability", f"{prob_pts}%"), unsafe_allow_html=True)
            r2[3].markdown(metric_card("Points EV", str(ev_pts) if ev_pts is not None else "Model only", "good" if (ev_pts or 0) > 0 else "neutral", f"Book over: {safe_odds_display(props['points_over'])}"), unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("NBA Parlay Summary")
        c1, c2 = st.columns(2)
        c1.markdown(metric_card("Parlay probability", f"{round(total_prob * 100, 2)}%"), unsafe_allow_html=True)
        c2.markdown(metric_card("Total EV", f"{round(total_ev, 3)}", "good" if total_ev > 0 else "bad"), unsafe_allow_html=True)

with nhl_tab:
    st.subheader("Top Candidate Legs Today")
    if st.button("Find Top Candidate Legs Today", key="nhl_top_legs"):
        progress_bar = st.progress(0, text="Starting NHL scan...")
        status_text = st.empty()
        candidate_df = build_ranked_best_leg_board(
            NHL_SPORT_KEY,
            [("POINTS", NHL_POINTS_MARKET_KEYS), ("SHOTS", NHL_SHOTS_MARKET_KEYS), ("GOALS", NHL_GOALS_MARKET_KEYS)],
            "NHL",
            progress_bar=progress_bar,
            status_text=status_text,
            top_n=20,
            enrich_rows=36,
        )
        progress_bar.empty()
        status_text.empty()
        render_candidate_table(candidate_df)

    st.markdown("---")
    st.subheader("Best Parlays Today")
    if st.button("Find Best Parlays Today", key="nhl_best_parlays", type="primary"):
        progress_bar = st.progress(0, text="Starting NHL parlay engine...")
        status_text = st.empty()
        filtered_df = build_ranked_best_leg_board(
            NHL_SPORT_KEY,
            [("POINTS", NHL_POINTS_MARKET_KEYS), ("SHOTS", NHL_SHOTS_MARKET_KEYS), ("GOALS", NHL_GOALS_MARKET_KEYS)],
            "NHL",
            progress_bar=progress_bar,
            status_text=status_text,
            top_n=28,
            enrich_rows=44,
        )
        parlay_2 = generate_parlay_candidates(filtered_df, 2, same_game_penalty=0.10, same_team_penalty=0.06)
        parlay_3 = generate_parlay_candidates(filtered_df.head(18), 3, same_game_penalty=0.10, same_team_penalty=0.06)
        selected = select_top_parlays_with_fallback(parlay_2 + parlay_3)
        progress_bar.empty()
        status_text.empty()
        render_selected_parlays(selected)

    st.markdown("---")
    st.subheader("Manual Parlay Builder")

    nhl_player_names = get_nhl_all_player_names()
    nhl_num_players = st.number_input("Number of NHL Players", min_value=1, max_value=5, value=2, step=1, key="nhl_num_players")

    nhl_inputs = []
    for i in range(nhl_num_players):
        st.markdown(f"### NHL Player {i+1}")
        c1, c2, c3, c4, c5 = st.columns([2.0, 1, 1, 1, 1.5])
        with c1:
            player_name = st.selectbox(f"Select NHL Player {i+1}", nhl_player_names, key=f"nhl_player_{i}")
            render_selected_player_photo(player_name, "NHL")
        with c2:
            target_points = st.number_input("Points Target", min_value=0, max_value=5, value=1, key=f"nhl_target_points_{i}")
        with c3:
            target_shots = st.number_input("Shots Target", min_value=0, max_value=12, value=3, key=f"nhl_target_shots_{i}")
        with c4:
            target_goals = st.number_input("Goals Target", min_value=0, max_value=5, value=1, key=f"nhl_target_goals_{i}")
        with c5:
            leg_type = st.selectbox(
                "Count In Parlay",
                ["Points only", "Shots only", "Goals only", "Points + Shots", "Goals + Shots", "Points + Goals", "All 3"],
                key=f"nhl_leg_type_{i}",
            )

        nhl_inputs.append(
            {
                "name": player_name,
                "target_points": int(target_points),
                "target_shots": int(target_shots),
                "target_goals": int(target_goals),
                "leg_type": leg_type,
            }
        )

    if st.button("Calculate NHL Parlay", key="nhl_calc"):
        total_prob = 1.0
        total_ev = 0.0

        for pick in nhl_inputs:
            pid = get_nhl_player_id(pick["name"])
            team_abbrev = get_nhl_player_team(pick["name"])
            if pid is None or team_abbrev is None:
                st.warning(f"Could not find NHL player/team for {pick['name']}.")
                continue

            events = get_nhl_today_events()
            event = None
            opponent = None
            for e in events:
                home_abbrev = NHL_NAME_TO_ABBREV.get(e.get("home_team", ""))
                away_abbrev = NHL_NAME_TO_ABBREV.get(e.get("away_team", ""))
                if team_abbrev in {home_abbrev, away_abbrev}:
                    event = e
                    opponent = away_abbrev if team_abbrev == home_abbrev else home_abbrev
                    break

            if not event or not opponent:
                st.warning(f"{pick['name']}: no confirmed NHL game found today.")
                continue

            games_df = fetch_nhl_recent_games(pid)
            if games_df.empty:
                st.warning(f"No recent NHL game log found for {pick['name']}.")
                continue

            avg_toi = games_df["TOI_MIN"].mean()
            if avg_toi < MIN_NHL_TOI_MINUTES:
                st.warning(f"{pick['name']}: low average TOI, skipping.")
                continue

            event_data = get_event_props(
                NHL_SPORT_KEY,
                event["id"],
                NHL_POINTS_MARKET_KEYS + NHL_SHOTS_MARKET_KEYS + NHL_GOALS_MARKET_KEYS,
            ).get("data", {})

            props = {
                "points_line": None, "points_over": None,
                "shots_line": None, "shots_over": None,
                "goals_line": None, "goals_over": None,
                "books": None,
            }

            if event_data:
                for r in extract_main_lines_for_market(event_data, NHL_POINTS_MARKET_KEYS):
                    if player_name_matches(pick["name"], r["player_name_raw"]):
                        props["points_line"] = r["line"]
                        props["points_over"] = r["over_odds"]
                        props["books"] = r["book_key"]
                        break
                for r in extract_main_lines_for_market(event_data, NHL_SHOTS_MARKET_KEYS):
                    if player_name_matches(pick["name"], r["player_name_raw"]):
                        props["shots_line"] = r["line"]
                        props["shots_over"] = r["over_odds"]
                        props["books"] = dedupe_csv_names([props["books"] or "", r["book_key"]])
                        break
                for r in extract_main_lines_for_market(event_data, NHL_GOALS_MARKET_KEYS):
                    if player_name_matches(pick["name"], r["player_name_raw"]):
                        props["goals_line"] = r["line"]
                        props["goals_over"] = r["over_odds"]
                        props["books"] = dedupe_csv_names([props["books"] or "", r["book_key"]])
                        break

            avg_points = calculate_nhl_weighted_avg(games_df, "POINTS")
            avg_shots = calculate_nhl_weighted_avg(games_df, "SHOTS")
            avg_goals = calculate_nhl_weighted_avg(games_df, "GOALS")

            prob_points, exp_points = calculate_poisson_probability(avg_points, 1.0, pick["target_points"])
            prob_shots, exp_shots = calculate_poisson_probability(avg_shots, 1.0, pick["target_shots"])
            prob_goals, exp_goals = calculate_poisson_probability(avg_goals, 1.0, pick["target_goals"])

            fair_points = probability_to_fair_american(prob_points)
            fair_shots = probability_to_fair_american(prob_shots)
            fair_goals = probability_to_fair_american(prob_goals)

            ev_points = calculate_ev(prob_points, american_to_decimal(props["points_over"]))
            ev_shots = calculate_ev(prob_shots, american_to_decimal(props["shots_over"]))
            ev_goals = calculate_ev(prob_goals, american_to_decimal(props["goals_over"]))

            line_points = build_manual_line(props["points_line"], exp_points, pick["target_points"], 0.5)
            line_shots = build_manual_line(props["shots_line"], exp_shots, pick["target_shots"], 0.5)
            line_goals = build_manual_line(props["goals_line"], exp_goals, pick["target_goals"], 0.5)

            legs = pick["leg_type"]
            if legs == "Points only":
                total_prob *= prob_points / 100
                total_ev += ev_points or 0
            elif legs == "Shots only":
                total_prob *= prob_shots / 100
                total_ev += ev_shots or 0
            elif legs == "Goals only":
                total_prob *= prob_goals / 100
                total_ev += ev_goals or 0
            elif legs == "Points + Shots":
                total_prob *= (prob_points / 100) * (prob_shots / 100)
                total_ev += (ev_points or 0) + (ev_shots or 0)
            elif legs == "Goals + Shots":
                total_prob *= (prob_goals / 100) * (prob_shots / 100)
                total_ev += (ev_goals or 0) + (ev_shots or 0)
            elif legs == "Points + Goals":
                total_prob *= (prob_points / 100) * (prob_goals / 100)
                total_ev += (ev_points or 0) + (ev_goals or 0)
            else:
                total_prob *= (prob_points / 100) * (prob_shots / 100) * (prob_goals / 100)
                total_ev += (ev_points or 0) + (ev_shots or 0) + (ev_goals or 0)

            st.markdown("---")
            st.subheader(f"{pick['name']} · {team_abbrev} vs {opponent}")

            r1 = st.columns(4)
            r1[0].markdown(metric_card("Tonight points line", safe_line_display(line_points), subtext=(props.get("source") or "Sportsbook") if props["points_line"] else "Model estimate"), unsafe_allow_html=True)
            r1[1].markdown(metric_card("Points hit probability", f"{prob_points}%"), unsafe_allow_html=True)
            r1[2].markdown(metric_card("Model fair over", safe_odds_display(fair_points)), unsafe_allow_html=True)
            r1[3].markdown(metric_card("Points EV", str(ev_points) if ev_points is not None else "Model only", "good" if (ev_points or 0) > 0 else "neutral", f"Book over: {safe_odds_display(props['points_over'])}"), unsafe_allow_html=True)

            r2 = st.columns(4)
            r2[0].markdown(metric_card("Tonight shots line", safe_line_display(line_shots), subtext="Sportsbook" if props["shots_line"] else "Model estimate"), unsafe_allow_html=True)
            r2[1].markdown(metric_card("Shots hit probability", f"{prob_shots}%"), unsafe_allow_html=True)
            r2[2].markdown(metric_card("Model fair over", safe_odds_display(fair_shots)), unsafe_allow_html=True)
            r2[3].markdown(metric_card("Shots EV", str(ev_shots) if ev_shots is not None else "Model only", "good" if (ev_shots or 0) > 0 else "neutral", f"Book over: {safe_odds_display(props['shots_over'])}"), unsafe_allow_html=True)

            r3 = st.columns(4)
            r3[0].markdown(metric_card("Tonight goals line", safe_line_display(line_goals), subtext="Sportsbook" if props["goals_line"] else "Model estimate"), unsafe_allow_html=True)
            r3[1].markdown(metric_card("Goals hit probability", f"{prob_goals}%"), unsafe_allow_html=True)
            r3[2].markdown(metric_card("Model fair over", safe_odds_display(fair_goals)), unsafe_allow_html=True)
            r3[3].markdown(metric_card("Goals EV", str(ev_goals) if ev_goals is not None else "Model only", "good" if (ev_goals or 0) > 0 else "neutral", f"Book over: {safe_odds_display(props['goals_over'])}"), unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("NHL Parlay Summary")
        c1, c2 = st.columns(2)
        c1.markdown(metric_card("Parlay probability", f"{round(total_prob * 100, 2)}%"), unsafe_allow_html=True)
        c2.markdown(metric_card("Total EV", f"{round(total_ev, 3)}", "good" if total_ev > 0 else "bad"), unsafe_allow_html=True)





