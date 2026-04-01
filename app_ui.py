import math
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

SEASON = "2025-26"
MAX_RECENT_GAMES = 10
SPORT_KEY = "basketball_nba"
PREFERRED_BOOKMAKERS = "draftkings,fanduel"
REQUEST_TIMEOUT = 20

POINTS_MARKET_KEYS = [
    "player_points",
    "player_points_alternate",
]

THREES_MARKET_KEYS = [
    "player_threes",
    "player_threes_alternate",
]

TEAM_NAME_MAP = {
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

TEAM_NAME_ALIASES = {
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

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

# =========================
# PAGE / STYLE
# =========================

st.set_page_config(page_title="NBA Prop Parlay Engine", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
    .metric-card {
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 14px 16px;
        background: white;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        min-height: 86px;
    }
    .metric-label {
        font-size: 12px;
        color: #6b7280;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 28px;
        font-weight: 700;
        color: #111827;
    }
    .metric-sub {
        font-size: 12px;
        color: #6b7280;
        margin-top: 4px;
    }
    .metric-good { color: #0f9d58; }
    .metric-bad { color: #d93025; }
    .metric-neutral { color: #111827; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# GENERIC HELPERS
# =========================

def metric_card(label: str, value: str, tone: str = "neutral", subtext: str = "") -> str:
    tone_class = {
        "good": "metric-good",
        "bad": "metric-bad",
        "neutral": "metric-neutral",
    }.get(tone, "metric-neutral")

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
        str(s)
        .lower()
        .replace(".", "")
        .replace("’", "'")
        .replace("-", " ")
        .replace(" jr", "")
        .replace(" sr", "")
        .replace(" iii", "")
        .replace(" ii", "")
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

def normalize_team_text(s: Any) -> str:
    return (
        str(s)
        .lower()
        .replace(".", "")
        .replace("'", "")
        .replace("-", "")
        .replace(" ", "")
        .replace("&", "and")
        .strip()
    )

def team_alias_set(team_name: str, team_abbrev: str) -> set:
    norm_name = normalize_team_text(team_name)
    aliases = set(TEAM_NAME_ALIASES.get(norm_name, {norm_name}))
    aliases.add(normalize_team_text(team_abbrev))
    return aliases

def teams_match(team_name: str, team_abbrev: str, candidate_team: Any) -> bool:
    candidate_norm = normalize_team_text(candidate_team)
    if not candidate_norm:
        return False

    aliases = team_alias_set(team_name, team_abbrev)
    if candidate_norm in aliases:
        return True

    for alias in aliases:
        if alias and (alias in candidate_norm or candidate_norm in alias):
            return True

    return False

def american_to_decimal(odds: Optional[int]) -> Optional[float]:
    if odds is None:
        return None
    if odds > 0:
        return 1 + odds / 100
    return 1 + 100 / abs(odds)

def calculate_ev(prob_pct: float, decimal_odds: Optional[float]) -> Optional[float]:
    if decimal_odds is None:
        return None
    p = prob_pct / 100
    ev = p * (decimal_odds - 1) - (1 - p)
    return round(ev, 3)

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
    cleaned = []
    seen = set()
    for part in names:
        for item in str(part).split(","):
            val = item.strip()
            if val and val not in seen:
                seen.add(val)
                cleaned.append(val)
    return ", ".join(cleaned) if cleaned else None

# =========================
# LIVE OPPONENT LOOKUP
# =========================

@st.cache_data(ttl=120, show_spinner=False)
def get_today_scoreboard_games() -> List[Dict[str, Any]]:
    try:
        board = scoreboard.ScoreBoard()
        data = board.get_dict()
        games = data.get("scoreboard", {}).get("games", [])
        return games if isinstance(games, list) else []
    except Exception:
        return []

def get_confirmed_opponent_today(team_abbrev: str) -> Optional[str]:
    games = get_today_scoreboard_games()
    if not games:
        return None

    for game in games:
        home_team = game.get("homeTeam", {})
        away_team = game.get("awayTeam", {})

        home_abbrev = home_team.get("teamTricode")
        away_abbrev = away_team.get("teamTricode")

        if team_abbrev == home_abbrev:
            return away_abbrev
        if team_abbrev == away_abbrev:
            return home_abbrev

    return None

# =========================
# ODDS API HELPERS
# =========================

def extract_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
        if isinstance(payload, dict):
            for key in ["message", "error", "detail"]:
                if payload.get(key):
                    return str(payload.get(key))
            return str(payload)
    except Exception:
        pass
    return response.text[:500] if response.text else "Unknown API error"

def odds_api_get(url: str, params: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
    meta: Dict[str, Any] = {
        "ok": False,
        "status_code": None,
        "error": None,
        "requests_remaining": None,
        "requests_used": None,
        "requests_last": None,
    }

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        meta["status_code"] = resp.status_code
        meta["requests_remaining"] = resp.headers.get("x-requests-remaining")
        meta["requests_used"] = resp.headers.get("x-requests-used")
        meta["requests_last"] = resp.headers.get("x-requests-last")

        if not resp.ok:
            meta["error"] = extract_error_message(resp)
            return None, meta

        try:
            data = resp.json()
            meta["ok"] = True
            return data, meta
        except Exception as e:
            meta["error"] = f"JSON parse error: {e}"
            return None, meta

    except Exception as e:
        meta["error"] = str(e)
        return None, meta

@st.cache_data(ttl=180, show_spinner=False)
def get_upcoming_odds_events() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not API_KEY:
        return [], {"ok": False, "error": "No API key provided."}

    url = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "bookmakers": PREFERRED_BOOKMAKERS,
        "markets": "h2h",
        "oddsFormat": "american",
    }

    data, meta = odds_api_get(url, params)
    if isinstance(data, list):
        return data, meta
    return [], meta

@st.cache_data(ttl=180, show_spinner=False)
def get_scores_feed_events() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not API_KEY:
        return [], {"ok": False, "error": "No API key provided."}

    url = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/scores"
    params = {
        "apiKey": API_KEY,
        "daysFrom": 1,
    }

    data, meta = odds_api_get(url, params)
    if isinstance(data, list):
        return data, meta
    return [], meta

@st.cache_data(ttl=120, show_spinner=False)
def get_event_props(event_id: str) -> Dict[str, Any]:
    if not API_KEY:
        return {
            "data": {},
            "meta": {"ok": False, "error": "No API key provided."},
            "source": None,
        }

    url = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/events/{event_id}/odds"

    base_params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": ",".join(POINTS_MARKET_KEYS + THREES_MARKET_KEYS),
        "oddsFormat": "american",
    }

    preferred_params = base_params.copy()
    preferred_params["bookmakers"] = PREFERRED_BOOKMAKERS

    preferred_data, preferred_meta = odds_api_get(url, preferred_params)
    if isinstance(preferred_data, dict) and preferred_data.get("bookmakers"):
        return {
            "data": preferred_data,
            "meta": preferred_meta,
            "source": "preferred_books",
        }

    fallback_data, fallback_meta = odds_api_get(url, base_params)
    if isinstance(fallback_data, dict):
        return {
            "data": fallback_data,
            "meta": fallback_meta,
            "source": "all_books_fallback",
        }

    return {
        "data": preferred_data if isinstance(preferred_data, dict) else {},
        "meta": fallback_meta if fallback_meta.get("error") else preferred_meta,
        "source": "failed",
    }

def find_event_for_team(team_abbrev: str, opponent_abbrev: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], str, Dict[str, Any]]:
    team_name = TEAM_NAME_MAP.get(team_abbrev)
    if not team_name:
        return None, f"No team-name mapping found for {team_abbrev}.", {}

    opponent_name = TEAM_NAME_MAP.get(opponent_abbrev) if opponent_abbrev else None

    upcoming_events, upcoming_meta = get_upcoming_odds_events()
    scores_events, scores_meta = get_scores_feed_events()

    meta_bundle = {
        "upcoming_meta": upcoming_meta,
        "scores_meta": scores_meta,
    }

    candidate_sources = [
        ("odds endpoint", upcoming_events),
        ("scores endpoint", scores_events),
    ]

    if opponent_abbrev and opponent_name:
        for source_name, events in candidate_sources:
            for event in events:
                home_team = event.get("home_team", "")
                away_team = event.get("away_team", "")

                has_team = teams_match(team_name, team_abbrev, home_team) or teams_match(team_name, team_abbrev, away_team)
                has_opp = teams_match(opponent_name, opponent_abbrev, home_team) or teams_match(opponent_name, opponent_abbrev, away_team)

                if has_team and has_opp:
                    return event, f"Matched by team + opponent via {source_name}.", meta_bundle

    for source_name, events in candidate_sources:
        for event in events:
            home_team = event.get("home_team", "")
            away_team = event.get("away_team", "")

            if teams_match(team_name, team_abbrev, home_team) or teams_match(team_name, team_abbrev, away_team):
                return event, f"Matched by team via {source_name}.", meta_bundle

    return None, f"No event matched for {team_abbrev}" + (f" vs {opponent_abbrev}" if opponent_abbrev else "") + ".", meta_bundle

def parse_prop_market(
    event_data: Dict[str, Any],
    player_name: str,
    target_market_keys: List[str],
) -> Tuple[Optional[float], Optional[int], Optional[int], Optional[str], List[str]]:
    bookmakers = event_data.get("bookmakers", [])
    lines: List[float] = []
    overs: List[int] = []
    unders: List[int] = []
    books_used: List[str] = []
    matched_market_keys: List[str] = []

    for bookmaker in bookmakers:
        book_key = bookmaker.get("key", "")
        for market in bookmaker.get("markets", []):
            market_key = market.get("key")
            if market_key not in target_market_keys:
                continue

            outcomes = market.get("outcomes", [])
            matched = []

            for outcome in outcomes:
                if player_name_matches(
                    player_name,
                    outcome.get("description", ""),
                    outcome.get("participant", ""),
                    outcome.get("label", ""),
                    outcome.get("name", ""),
                ):
                    matched.append(outcome)

            if not matched:
                continue

            matched_market_keys.append(f"{book_key}:{market_key}")

            this_line = None
            this_over = None
            this_under = None

            for outcome in matched:
                name = normalize_name(outcome.get("name", ""))
                desc = normalize_name(outcome.get("description", ""))
                label = normalize_name(outcome.get("label", ""))
                side = normalize_name(outcome.get("side", ""))

                price = outcome.get("price")
                point = outcome.get("point")

                try:
                    price = int(price) if price is not None else None
                except Exception:
                    price = None

                try:
                    point = float(point) if point is not None else None
                except Exception:
                    point = None

                if point is not None:
                    this_line = point

                if "over" in {name, desc, label, side}:
                    this_over = price
                elif "under" in {name, desc, label, side}:
                    this_under = price

            if this_line is not None:
                lines.append(this_line)
            if this_over is not None:
                overs.append(this_over)
            if this_under is not None:
                unders.append(this_under)

            if this_line is not None or this_over is not None or this_under is not None:
                books_used.append(book_key)

    median_line = round(float(pd.Series(lines).median()), 1) if lines else None
    median_over = int(pd.Series(overs).median()) if overs else None
    median_under = int(pd.Series(unders).median()) if unders else None
    books = ", ".join(sorted(set(books_used))) if books_used else None

    return median_line, median_over, median_under, books, sorted(set(matched_market_keys))

def summarize_event_markets(event_data: Dict[str, Any]) -> List[str]:
    results = []
    bookmakers = event_data.get("bookmakers", [])

    for bookmaker in bookmakers:
        book_key = bookmaker.get("key", "")
        market_keys = []
        for market in bookmaker.get("markets", []):
            if market.get("key"):
                market_keys.append(market.get("key"))
        if market_keys:
            results.append(f"{book_key}: {', '.join(sorted(set(market_keys))[:25])}")

    return results

def fetch_player_props(player_name: str, team_abbrev: str, opponent_abbrev: Optional[str]) -> Dict[str, Any]:
    event, event_debug, event_meta = find_event_for_team(team_abbrev, opponent_abbrev)

    if not event:
        return {
            "event_found": False,
            "event_id": None,
            "points_line": None,
            "points_over": None,
            "points_under": None,
            "threes_line": None,
            "threes_over": None,
            "threes_under": None,
            "books": None,
            "debug": event_debug,
            "props_source": None,
            "api_meta": event_meta,
            "matched_point_markets": [],
            "matched_three_markets": [],
            "available_market_summary": [],
        }

    event_id = event.get("id")
    if not event_id:
        return {
            "event_found": False,
            "event_id": None,
            "points_line": None,
            "points_over": None,
            "points_under": None,
            "threes_line": None,
            "threes_over": None,
            "threes_under": None,
            "books": None,
            "debug": f"Matched event but no id returned. {event_debug}",
            "props_source": None,
            "api_meta": event_meta,
            "matched_point_markets": [],
            "matched_three_markets": [],
            "available_market_summary": [],
        }

    props_response = get_event_props(event_id)
    event_data = props_response.get("data", {})
    props_meta = props_response.get("meta", {})
    props_source = props_response.get("source")

    combined_meta = {
        **event_meta,
        "props_meta": props_meta,
    }

    if not isinstance(event_data, dict) or not event_data:
        return {
            "event_found": True,
            "event_id": event_id,
            "points_line": None,
            "points_over": None,
            "points_under": None,
            "threes_line": None,
            "threes_over": None,
            "threes_under": None,
            "books": None,
            "debug": f"Matched event id {event_id}, but props response was empty.",
            "props_source": props_source,
            "api_meta": combined_meta,
            "matched_point_markets": [],
            "matched_three_markets": [],
            "available_market_summary": [],
        }

    bookmakers = event_data.get("bookmakers", [])
    market_summary = summarize_event_markets(event_data)

    if not bookmakers:
        return {
            "event_found": True,
            "event_id": event_id,
            "points_line": None,
            "points_over": None,
            "points_under": None,
            "threes_line": None,
            "threes_over": None,
            "threes_under": None,
            "books": None,
            "debug": f"Matched event id {event_id}, but no bookmakers were returned for requested markets.",
            "props_source": props_source,
            "api_meta": combined_meta,
            "matched_point_markets": [],
            "matched_three_markets": [],
            "available_market_summary": market_summary,
        }

    pts_line, pts_over, pts_under, pts_books, pts_matches = parse_prop_market(
        event_data, player_name, POINTS_MARKET_KEYS
    )
    thr_line, thr_over, thr_under, thr_books, thr_matches = parse_prop_market(
        event_data, player_name, THREES_MARKET_KEYS
    )

    player_match_found = any([pts_line, pts_over, pts_under, thr_line, thr_over, thr_under])

    debug_msg = event_debug
    if not player_match_found:
        debug_msg = f"{event_debug} Event returned books/markets, but no matching player prop was found for {player_name}."

    return {
        "event_found": True,
        "event_id": event_id,
        "points_line": pts_line,
        "points_over": pts_over,
        "points_under": pts_under,
        "threes_line": thr_line,
        "threes_over": thr_over,
        "threes_under": thr_under,
        "books": dedupe_csv_names([pts_books or "", thr_books or ""]),
        "debug": debug_msg,
        "props_source": props_source,
        "api_meta": combined_meta,
        "matched_point_markets": pts_matches,
        "matched_three_markets": thr_matches,
        "available_market_summary": market_summary,
    }

def inspect_event_props(team_abbrev: str, opponent_abbrev: Optional[str], player_name: str) -> List[str]:
    lines: List[str] = []

    props = fetch_player_props(player_name, team_abbrev, opponent_abbrev)

    lines.append(props.get("debug", "No debug message."))
    lines.append(f"Matched event id={props.get('event_id') or 'None'}")
    lines.append(f"Props source used: {props.get('props_source') or 'None'}")

    api_meta = props.get("api_meta", {})
    props_meta = api_meta.get("props_meta", {})
    if props_meta:
        lines.append(
            "Props request meta: "
            f"status={props_meta.get('status_code')} | "
            f"remaining={props_meta.get('requests_remaining')} | "
            f"used={props_meta.get('requests_used')} | "
            f"last_cost={props_meta.get('requests_last')} | "
            f"error={props_meta.get('error')}"
        )

    if not props.get("books"):
        lines.append("No matched sportsbook prices for this player.")
        if props.get("available_market_summary"):
            lines.append("Available markets returned by books:")
            lines.extend(props["available_market_summary"][:20])

        lines.append(f"Requested points markets: {', '.join(POINTS_MARKET_KEYS)}")
        lines.append(f"Requested threes markets: {', '.join(THREES_MARKET_KEYS)}")
        lines.append(f"Preferred books first: {PREFERRED_BOOKMAKERS}")
        return lines

    lines.append(f"Matched books: {props['books']}")
    lines.append(f"Matched point markets: {', '.join(props['matched_point_markets']) or 'None'}")
    lines.append(f"Matched three markets: {', '.join(props['matched_three_markets']) or 'None'}")

    return lines[:200]

# =========================
# NBA STATS HELPERS
# =========================

@st.cache_data(ttl=3600, show_spinner=False)
def get_all_players() -> List[str]:
    return sorted([p["full_name"] for p in players.get_players()])

def get_player_id(name: str) -> Optional[int]:
    plist = players.get_players()
    match = [p for p in plist if p["full_name"] == name]
    return match[0]["id"] if match else None

@st.cache_data(ttl=3600, show_spinner=False)
def get_player_team(pid: int) -> str:
    info = commonplayerinfo.CommonPlayerInfo(player_id=pid).get_data_frames()[0]
    return str(info.loc[0, "TEAM_ABBREVIATION"])

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_recent_games(pid: int, num_games: int = MAX_RECENT_GAMES) -> pd.DataFrame:
    gamelog = playergamelog.PlayerGameLog(player_id=pid, season=SEASON)
    df = gamelog.get_data_frames()[0]

    fg3m_col = "FG3M" if "FG3M" in df.columns else None
    fga3_col = "FGA3" if "FGA3" in df.columns else ("FG3A" if "FG3A" in df.columns else None)

    if not fg3m_col or not fga3_col or "PTS" not in df.columns:
        return pd.DataFrame()

    df = df[["GAME_DATE", "MATCHUP", "MIN", "PTS", fg3m_col, fga3_col]].copy()
    df = df.rename(columns={fg3m_col: "FG3M", fga3_col: "FGA3"})
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    return df.head(num_games)

def calculate_weighted_avg(df: pd.DataFrame, stat: str) -> float:
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

def calculate_probability(avg: float, factor: float, target: int) -> Tuple[float, float]:
    adj = avg * factor
    cumulative = 0.0
    for k in range(int(target)):
        cumulative += (adj ** k * math.exp(-adj)) / math.factorial(k)
    return round((1 - cumulative) * 100, 2), adj

def load_defense() -> Dict[str, float]:
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

# =========================
# SMART LINE FALLBACKS
# =========================

def build_smart_lines(
    avg_3pt: float,
    avg_pts: float,
    target_3pt: int,
    target_pts: int,
    api_threes_line: Optional[float],
    api_points_line: Optional[float],
) -> Dict[str, Any]:
    model_threes_line = max(0.5, round(max(avg_3pt * 0.9, target_3pt - 0.5) * 2) / 2)
    model_points_line = max(6.5, round(max(avg_pts * 0.95, target_pts - 0.5) * 2) / 2)

    threes_line = api_threes_line if api_threes_line is not None else model_threes_line
    points_line = api_points_line if api_points_line is not None else model_points_line

    threes_source = "Sportsbook" if api_threes_line is not None else "Model estimate"
    points_source = "Sportsbook" if api_points_line is not None else "Model estimate"

    return {
        "threes_line": threes_line,
        "points_line": points_line,
        "threes_source": threes_source,
        "points_source": points_source,
    }

def build_stat_chart(df: pd.DataFrame, stat_col: str, line_value: float, target: int, title: str):
    chart_df = df.sort_values("GAME_DATE")[["GAME_DATE", stat_col]].copy()
    base = alt.Chart(chart_df).encode(x=alt.X("GAME_DATE:T", title="Game Date"))
    series = base.mark_line(point=True).encode(y=alt.Y(f"{stat_col}:Q", title=title))

    line_rule = alt.Chart(pd.DataFrame({"y": [line_value]})).mark_rule(strokeDash=[6, 4]).encode(y="y:Q")
    target_rule = alt.Chart(pd.DataFrame({"y": [target]})).mark_rule(strokeDash=[2, 2]).encode(y="y:Q")

    return alt.layer(series, line_rule, target_rule).properties(height=220)

# =========================
# UI
# =========================

st.title("NBA Prop Parlay Engine")
st.caption("Opponent uses today's live NBA scoreboard only. Odds/EV use sportsbook feed when available.")

all_players = get_all_players()
defense_map = load_defense()

num_players = st.number_input("Number of Players", min_value=1, max_value=5, value=2, step=1)

inputs: List[Dict[str, Any]] = []
for i in range(num_players):
    st.markdown(f"### Player {i+1}")
    c1, c2, c3, c4 = st.columns([2.2, 1, 1, 1.3])

    with c1:
        player_name = st.selectbox(f"Select Player {i+1}", all_players, key=f"player_{i}")
    with c2:
        target_3pt = st.number_input("3PT Target", min_value=0, max_value=15, value=4, key=f"target_3pt_{i}")
    with c3:
        target_pts = st.number_input("Points Target", min_value=0, max_value=60, value=20, key=f"target_pts_{i}")
    with c4:
        leg_type = st.selectbox("Count In Parlay", ["3PT only", "Points only", "Both"], key=f"leg_type_{i}")

    inputs.append(
        {
            "name": player_name,
            "target_3pt": int(target_3pt),
            "target_pts": int(target_pts),
            "leg_type": leg_type,
        }
    )

if st.button("Calculate Parlay", type="primary"):
    total_prob = 1.0
    total_ev = 0.0
    included_legs: List[Dict[str, Any]] = []

    if not API_KEY or API_KEY == "PASTE_YOUR_ODDS_API_KEY_HERE":
        st.error("Paste your Odds API key into the API_KEY line near the top of the script.")
        st.stop()

    for pick in inputs:
        player_name = pick["name"]
        pid = get_player_id(player_name)

        if not pid:
            st.warning(f"Could not find player ID for {player_name}.")
            continue

        games = fetch_recent_games(pid)
        if games.empty:
            st.warning(f"No recent game data for {player_name}.")
            continue

        team_abbrev = get_player_team(pid)
        opponent = get_confirmed_opponent_today(team_abbrev)

        if opponent is None:
            st.warning(f"{player_name}: no confirmed game found on today's live NBA scoreboard. Skipping this player.")
            continue

        factor = defense_map.get(opponent, 1.0)
        props = fetch_player_props(player_name, team_abbrev, opponent)

        avg_3pt = calculate_weighted_avg(games, "FG3M")
        avg_pts = calculate_weighted_avg(games, "PTS")

        smart_lines = build_smart_lines(
            avg_3pt=avg_3pt,
            avg_pts=avg_pts,
            target_3pt=pick["target_3pt"],
            target_pts=pick["target_pts"],
            api_threes_line=props["threes_line"],
            api_points_line=props["points_line"],
        )

        prob_3pt, adj_3pt = calculate_probability(avg_3pt, factor, pick["target_3pt"])
        prob_pts, adj_pts = calculate_probability(avg_pts, 1.0, pick["target_pts"])

        fair_3pt_odds = probability_to_fair_american(prob_3pt)
        fair_pts_odds = probability_to_fair_american(prob_pts)

        ev_3pt = calculate_ev(prob_3pt, american_to_decimal(props["threes_over"]))
        ev_pts = calculate_ev(prob_pts, american_to_decimal(props["points_over"]))

        if pick["leg_type"] == "3PT only":
            total_prob *= prob_3pt / 100
            included_legs.append({"player": player_name, "leg": f"3PT {pick['target_3pt']}+", "prob": prob_3pt})
        elif pick["leg_type"] == "Points only":
            total_prob *= prob_pts / 100
            included_legs.append({"player": player_name, "leg": f"PTS {pick['target_pts']}+", "prob": prob_pts})
        else:
            total_prob *= prob_3pt / 100
            total_prob *= prob_pts / 100
            included_legs.append({"player": player_name, "leg": f"3PT {pick['target_3pt']}+", "prob": prob_3pt})
            included_legs.append({"player": player_name, "leg": f"PTS {pick['target_pts']}+", "prob": prob_pts})

        total_ev += (ev_3pt or 0) + (ev_pts or 0)

        avg5_3 = games.head(5)["FG3M"].mean()
        avg10_3 = games.head(10)["FG3M"].mean()
        avg5_pts = games.head(5)["PTS"].mean()
        avg10_pts = games.head(10)["PTS"].mean()

        st.markdown("---")
        st.subheader(f"{player_name} · {team_abbrev} vs {opponent}")

        if props["books"] is None:
            st.info(
                f"No sportsbook player-prop prices returned for {player_name}. "
                f"Using model fallback lines. Debug: {props.get('debug', 'None')}"
            )

        r1 = st.columns(4)
        with r1[0]:
            st.markdown(
                metric_card(
                    "Tonight 3PT line",
                    safe_line_display(smart_lines["threes_line"]),
                    subtext=smart_lines["threes_source"],
                ),
                unsafe_allow_html=True,
            )
        with r1[1]:
            st.markdown(
                metric_card(
                    "Your 3PT target",
                    str(pick["target_3pt"]),
                    subtext=f"Fair odds: {safe_odds_display(fair_3pt_odds)}",
                ),
                unsafe_allow_html=True,
            )
        with r1[2]:
            st.markdown(metric_card("3PT hit probability", f"{prob_3pt}%"), unsafe_allow_html=True)
        with r1[3]:
            if ev_3pt is None:
                ev_text = "Model only"
                ev_sub = f"Fair over: {safe_odds_display(fair_3pt_odds)}"
                tone = "neutral"
            else:
                ev_text = str(ev_3pt)
                ev_sub = f"Book over: {safe_odds_display(props['threes_over'])}"
                tone = "good" if ev_3pt > 0 else "bad"
            st.markdown(metric_card("3PT EV", ev_text, tone, ev_sub), unsafe_allow_html=True)

        r2 = st.columns(4)
        with r2[0]:
            st.markdown(
                metric_card(
                    "Tonight points line",
                    safe_line_display(smart_lines["points_line"]),
                    subtext=smart_lines["points_source"],
                ),
                unsafe_allow_html=True,
            )
        with r2[1]:
            st.markdown(
                metric_card(
                    "Your points target",
                    str(pick["target_pts"]),
                    subtext=f"Fair odds: {safe_odds_display(fair_pts_odds)}",
                ),
                unsafe_allow_html=True,
            )
        with r2[2]:
            st.markdown(metric_card("Points hit probability", f"{prob_pts}%"), unsafe_allow_html=True)
        with r2[3]:
            if ev_pts is None:
                ev_text = "Model only"
                ev_sub = f"Fair over: {safe_odds_display(fair_pts_odds)}"
                tone = "neutral"
            else:
                ev_text = str(ev_pts)
                ev_sub = f"Book over: {safe_odds_display(props['points_over'])}"
                tone = "good" if ev_pts > 0 else "bad"
            st.markdown(metric_card("Points EV", ev_text, tone, ev_sub), unsafe_allow_html=True)

        info = st.columns(4)
        info[0].write(f"**Expected 3PTs:** {adj_3pt:.2f}")
        info[1].write(f"**Expected points:** {adj_pts:.2f}")
        info[2].write(f"**Books found:** {props['books'] or 'None returned by API'}")
        info[3].write(f"**Parlay mode:** {pick['leg_type']}")

        with st.expander("Advanced analysis", expanded=False):
            a1, a2 = st.columns(2)
            with a1:
                st.write(f"Last 5 average 3PTM: {avg5_3:.2f}")
                st.write(f"Last 10 average 3PTM: {avg10_3:.2f}")
                st.write(f"3PT line source: {smart_lines['threes_source']}")
                st.write(f"Book over odds (3PT): {safe_odds_display(props['threes_over'])}")
                st.write(f"Book under odds (3PT): {safe_odds_display(props['threes_under'])}")
                st.write(f"Model fair over (3PT): {safe_odds_display(fair_3pt_odds)}")
            with a2:
                st.write(f"Last 5 average points: {avg5_pts:.2f}")
                st.write(f"Last 10 average points: {avg10_pts:.2f}")
                st.write(f"Points line source: {smart_lines['points_source']}")
                st.write(f"Book over odds (points): {safe_odds_display(props['points_over'])}")
                st.write(f"Book under odds (points): {safe_odds_display(props['points_under'])}")
                st.write(f"Model fair over (points): {safe_odds_display(fair_pts_odds)}")

            st.write(f"**Matched event id:** {props['event_id'] or 'None'}")
            st.write(f"**Odds debug:** {props.get('debug', 'None')}")
            st.write(f"**Props source:** {props.get('props_source', 'None')}")

            props_meta = props.get("api_meta", {}).get("props_meta", {})
            if props_meta:
                st.write(
                    f"**Props request status:** {props_meta.get('status_code')} | "
                    f"remaining={props_meta.get('requests_remaining')} | "
                    f"used={props_meta.get('requests_used')} | "
                    f"last_cost={props_meta.get('requests_last')}"
                )
                st.write(f"**Props request error:** {props_meta.get('error')}")

            if props.get("matched_point_markets"):
                st.write(f"**Matched point markets:** {', '.join(props['matched_point_markets'])}")
            if props.get("matched_three_markets"):
                st.write(f"**Matched three markets:** {', '.join(props['matched_three_markets'])}")

            if props.get("available_market_summary"):
                st.write("**Available market keys returned by books:**")
                for item in props["available_market_summary"][:20]:
                    st.code(item)

            st.altair_chart(
                build_stat_chart(games, "FG3M", smart_lines["threes_line"], pick["target_3pt"], "3PT Made"),
                use_container_width=True,
            )
            st.altair_chart(
                build_stat_chart(games, "PTS", smart_lines["points_line"], pick["target_pts"], "Points"),
                use_container_width=True,
            )

            st.markdown("**Raw odds inspector**")
            for line in inspect_event_props(team_abbrev, opponent, player_name):
                st.code(line)

    if not included_legs:
        total_prob = 0.0
        total_ev = 0.0

    st.markdown("---")
    st.subheader("Parlay summary")

    summary1, summary2 = st.columns(2)
    with summary1:
        st.markdown(metric_card("Parlay probability", f"{round(total_prob * 100, 2)}%"), unsafe_allow_html=True)
    with summary2:
        tone = "good" if total_ev > 0 else "bad"
        st.markdown(metric_card("Total EV", f"{round(total_ev, 3)}", tone), unsafe_allow_html=True)

    with st.expander("Parlay advanced analysis", expanded=True):
        if included_legs:
            legs_df = pd.DataFrame(included_legs).sort_values("prob")
            weakest = legs_df.iloc[0]
            strongest = legs_df.iloc[-1]
            avg_leg_prob = round(legs_df["prob"].mean(), 2)

            parlay_pct = total_prob * 100
            if parlay_pct < 10:
                risk_text = "Very high risk parlay."
                confidence = "Low"
            elif parlay_pct < 25:
                risk_text = "High risk parlay."
                confidence = "Below average"
            elif parlay_pct < 45:
                risk_text = "Moderate risk parlay."
                confidence = "Decent"
            else:
                risk_text = "Relatively strong parlay."
                confidence = "Strong"

            st.write(f"**Included legs:** {len(legs_df)}")
            st.write(f"**Average leg probability:** {avg_leg_prob}%")
            st.write(f"**Weakest leg:** {weakest['player']} — {weakest['leg']} ({weakest['prob']}%)")
            st.write(f"**Strongest leg:** {strongest['player']} — {strongest['leg']} ({strongest['prob']}%)")
            st.write(f"**Risk summary:** {risk_text}")
            st.write(f"**Confidence tier:** {confidence}")

            st.dataframe(
                legs_df.rename(
                    columns={
                        "player": "Player",
                        "leg": "Included Leg",
                        "prob": "Probability %",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.write("No legs were included in the parlay calculation.")
