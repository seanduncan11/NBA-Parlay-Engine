
import math
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
    "Vancouver Canucks": "VAN",
    "Vegas Golden Knights": "VGK",
    "Washington Capitals": "WSH",
    "Winnipeg Jets": "WPG",
}

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

# =========================
# PAGE / STYLE
# =========================

st.set_page_config(page_title="NBA + NHL Prop Parlay Engine", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.1rem; padding-bottom: 2rem;}
    .metric-card {
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 14px 16px;
        background: white;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        min-height: 86px;
    }
    .metric-label {font-size: 12px; color: #6b7280; margin-bottom: 6px;}
    .metric-value {font-size: 28px; font-weight: 700; color: #111827;}
    .metric-sub {font-size: 12px; color: #6b7280; margin-top: 4px;}
    .metric-good { color: #0f9d58; }
    .metric-bad { color: #d93025; }
    .metric-neutral { color: #111827; }
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

            model_prob, expected_stat = calculate_poisson_probability(avg_stat, factor, target)
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
            row["line_source"] = "Recent form + defense + sportsbook"

            enriched_rows.append(row)

        except Exception:
            enriched_rows.append(row)

    return pd.DataFrame(enriched_rows)

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
        return board

    board = sort_best_leg_board(board, top_n=max(enrich_rows, top_n))
    board = enrich_best_leg_board(board, sport, max_rows=enrich_rows)
    return sort_best_leg_board(board, top_n=top_n)

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

def odds_api_get(url: str, params: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
    meta = {"ok": False, "status_code": None, "error": None}
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        meta["status_code"] = resp.status_code
        if not resp.ok:
            try:
                meta["error"] = resp.json()
            except Exception:
                meta["error"] = resp.text[:500]
            return None, meta
        meta["ok"] = True
        return resp.json(), meta
    except Exception as e:
        meta["error"] = str(e)
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

                if market_name == "3PT":
                    model_prob, expected_stat = calculate_poisson_probability(avg_3pt, defense_map.get(opponent, 1.0), target)
                else:
                    model_prob, expected_stat = calculate_poisson_probability(avg_pts, 1.0, target)

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

                model_prob, expected_stat = calculate_poisson_probability(avg_stat, 1.0, target)
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
                    "EV": leg["ev"],
                    "Leg Score": leg["leg_score"],
                }
                for leg in p["legs"]
            ]
        )
        st.dataframe(legs_table, use_container_width=True, hide_index=True)

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

def _get_event_props_any_books(sport_key: str, event_id: str, market_keys: List[str]) -> Dict[str, Any]:
    event_data = get_event_props(sport_key, event_id, market_keys).get("data", {})
    if isinstance(event_data, dict) and event_data.get("bookmakers"):
        return event_data

    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/events/{event_id}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": ",".join(market_keys),
        "oddsFormat": "american",
    }
    data, _ = odds_api_get(url, params)
    return data if isinstance(data, dict) else {}

def build_direct_candidate_board(
    sport_key: str,
    market_specs: List[Tuple[str, List[str]]],
    sport: str,
    progress_bar=None,
    status_text=None,
) -> pd.DataFrame:
    # Fast path for Top Candidate Legs Today only.
    # This intentionally avoids player-by-player game-log calls so the button does not take 10 minutes.
    rows: List[Dict[str, Any]] = []
    events = get_sport_events(sport_key)
    if not events:
        return pd.DataFrame()

    total = len(events)
    reverse_nba = _reverse_nba_team_map()
    reverse_nhl = _reverse_nhl_team_map()

    market_key_to_label = {}
    all_market_keys: List[str] = []
    for market_label, market_keys in market_specs:
        for mk in market_keys:
            market_key_to_label[mk] = market_label
            all_market_keys.append(mk)

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

        if sport == "NBA":
            home_abbrev = reverse_nba.get(event.get("home_team", ""), "")
            away_abbrev = reverse_nba.get(event.get("away_team", ""), "")
        else:
            home_abbrev = reverse_nhl.get(event.get("home_team", ""), "")
            away_abbrev = reverse_nhl.get(event.get("away_team", ""), "")

        for bookmaker in event_data.get("bookmakers", []):
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
                    player_name = (outcome.get("participant") or outcome.get("description") or "").strip()
                    if not player_name:
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

                    token_blob = " ".join([
                        str(outcome.get("name", "")),
                        str(outcome.get("description", "")),
                        str(outcome.get("label", "")),
                        str(outcome.get("side", "")),
                    ]).lower()

                    # Best legs board is for overs only.
                    if "under" in token_blob:
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
                            "line_source": "Sportsbook fast model",
                            "leg_label": f"{player_name} over {safe_line_display(line)} {label_suffix}".strip(),
                            "leg_score": leg_score,
                        }
                    )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Keep this filter local to Top Candidate Legs Today only.
    # It avoids returning legs that are very likely but have almost no payout.
    balanced_df = df[
        (df["book_over_odds"].notna()) &
        (df["book_over_odds"] >= -250) &
        (df["book_over_odds"] <= 250)
    ].copy()

    if len(balanced_df) >= 5:
        df = balanced_df

    return (
        df.sort_values(by=["leg_score", "ev", "model_prob", "book_over_odds"], ascending=[False, False, False, False])
        .drop_duplicates(subset=["leg_label", "book"])
        .head(80)
        .reset_index(drop=True)
    )

# =========================
# UI
# =========================

st.title("NBA + NHL Prop Parlay Engine")
st.caption("This first draft keeps the NBA flow and adds an NHL tab with points, shots, and goals.")

nba_tab, nhl_tab = st.tabs(["NBA", "NHL"])

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
        selected = select_top_parlays(filter_parlay_candidates(parlay_2 + parlay_3))
        progress_bar.empty()
        status_text.empty()
        render_selected_parlays(selected)

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

            props = {"points_line": None, "points_over": None, "threes_line": None, "threes_over": None, "books": None}
            if event:
                event_data = get_event_props(NBA_SPORT_KEY, event["id"], NBA_POINTS_MARKET_KEYS + NBA_THREES_MARKET_KEYS).get("data", {})
                if event_data:
                    for r in extract_main_lines_for_market(event_data, NBA_POINTS_MARKET_KEYS):
                        if player_name_matches(pick["name"], r["player_name_raw"]):
                            props["points_line"] = r["line"]
                            props["points_over"] = r["over_odds"]
                            props["books"] = r["book_key"]
                            break
                    for r in extract_main_lines_for_market(event_data, NBA_THREES_MARKET_KEYS):
                        if player_name_matches(pick["name"], r["player_name_raw"]):
                            props["threes_line"] = r["line"]
                            props["threes_over"] = r["over_odds"]
                            props["books"] = dedupe_csv_names([props["books"] or "", r["book_key"]])
                            break

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
            r1[0].markdown(metric_card("Tonight 3PT line", safe_line_display(line_3pt), subtext="Sportsbook" if props["threes_line"] else "Model estimate"), unsafe_allow_html=True)
            r1[1].markdown(metric_card("Your 3PT target", str(pick["target_3pt"]), subtext=f"Fair odds: {safe_odds_display(fair_3pt)}"), unsafe_allow_html=True)
            r1[2].markdown(metric_card("3PT hit probability", f"{prob_3pt}%"), unsafe_allow_html=True)
            r1[3].markdown(metric_card("3PT EV", str(ev_3pt) if ev_3pt is not None else "Model only", "good" if (ev_3pt or 0) > 0 else "neutral", f"Book over: {safe_odds_display(props['threes_over'])}"), unsafe_allow_html=True)

            r2 = st.columns(4)
            r2[0].markdown(metric_card("Tonight points line", safe_line_display(line_pts), subtext="Sportsbook" if props["points_line"] else "Model estimate"), unsafe_allow_html=True)
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
        selected = select_top_parlays(filter_parlay_candidates(parlay_2 + parlay_3))
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
            r1[0].markdown(metric_card("Tonight points line", safe_line_display(line_points), subtext="Sportsbook" if props["points_line"] else "Model estimate"), unsafe_allow_html=True)
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



