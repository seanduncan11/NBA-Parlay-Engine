# app_ui.py

import math
from typing import Any, Dict, List, Optional, Tuple

import altair as alt
import pandas as pd
import requests
import streamlit as st
from nba_api.stats.endpoints import commonplayerinfo, playergamelog
from nba_api.stats.static import players

# =========================
# CONFIG
# =========================

API_KEY = "c86b551f2e51c698515893c141c6c1a6"
SEASON = "2025-26"
MAX_RECENT_GAMES = 10
SPORT_KEY = "basketball_nba"
REGIONS = "us,us2"
PREFERRED_BOOKS = {"draftkings", "fanduel"}

POINTS_MARKET_KEYS = ["player_points"]
THREES_MARKET_KEYS = ["player_threes"]

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

next_opponent_map = {
    "DEN": "GSW",
    "GSW": "DEN",
    "MIL": "PHI",
    "PHI": "MIL",
    "LAL": "LAC",
    "LAC": "LAL",
    "BKN": "BOS",
    "BOS": "BKN",
    "NYK": "CHI",
    "CHI": "NYK",
    "MIA": "TOR",
    "TOR": "MIA",
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

def metric_card(label: str, value: str, tone: str = "neutral") -> str:
    tone_class = {
        "good": "metric-good",
        "bad": "metric-bad",
        "neutral": "metric-neutral",
    }.get(tone, "metric-neutral")

    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value {tone_class}">{value}</div>
    </div>
    """

def normalize_name(s: str) -> str:
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

def player_name_matches(player_name: str, outcome_name: Any, outcome_description: Any) -> bool:
    p = normalize_name(player_name)
    n = normalize_name(outcome_name)
    d = normalize_name(outcome_description)
    return p == n or p == d or p in n or p in d or n in p or d in p

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

# =========================
# ODDS API HELPERS
# =========================

@st.cache_data(ttl=300, show_spinner=False)
def get_events() -> List[Dict[str, Any]]:
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/events"
    params = {"apiKey": API_KEY}
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []

@st.cache_data(ttl=300, show_spinner=False)
def get_event_props(event_id: str) -> Dict[str, Any]:
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/events/{event_id}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": ",".join(POINTS_MARKET_KEYS + THREES_MARKET_KEYS),
        "oddsFormat": "american",
    }
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()

def find_event_for_team(team_abbrev: str) -> Optional[Dict[str, Any]]:
    team_name = TEAM_NAME_MAP.get(team_abbrev)
    if not team_name:
        return None
    try:
        events = get_events()
    except Exception:
        return None

    for event in events:
        home_team = event.get("home_team")
        away_team = event.get("away_team")
        if team_name == home_team or team_name == away_team:
            return event
    return None

def get_opponent_from_event(event: Dict[str, Any], team_abbrev: str) -> str:
    reverse_map = {v: k for k, v in TEAM_NAME_MAP.items()}
    team_name = TEAM_NAME_MAP.get(team_abbrev)
    home_team = event.get("home_team")
    away_team = event.get("away_team")

    if team_name == home_team:
        return reverse_map.get(away_team, "UNKNOWN")
    if team_name == away_team:
        return reverse_map.get(home_team, "UNKNOWN")
    return next_opponent_map.get(team_abbrev, "UNKNOWN")

def parse_prop_market(
    event_data: Dict[str, Any],
    player_name: str,
    target_market_keys: List[str],
    preferred_only: bool,
) -> Tuple[Optional[float], Optional[int], Optional[int], Optional[str], List[str]]:
    bookmakers = event_data.get("bookmakers", [])
    lines: List[float] = []
    overs: List[int] = []
    unders: List[int] = []
    books_used: List[str] = []
    debug_lines: List[str] = []

    for bookmaker in bookmakers:
        book_key = bookmaker.get("key", "")
        if preferred_only and book_key not in PREFERRED_BOOKS:
            continue

        markets = bookmaker.get("markets", [])
        for market in markets:
            market_key = market.get("key", "")
            if market_key not in target_market_keys:
                continue

            outcomes = market.get("outcomes", [])
            matched = []

            for outcome in outcomes:
                if player_name_matches(player_name, outcome.get("name", ""), outcome.get("description", "")):
                    matched.append(outcome)

            if not matched:
                if outcomes:
                    for s in outcomes[:2]:
                        debug_lines.append(
                            f"{book_key} | {market_key} | "
                            f"name={s.get('name')} | desc={s.get('description')} | "
                            f"point={s.get('point')} | price={s.get('price')}"
                        )
                continue

            this_line = None
            this_over = None
            this_under = None

            for outcome in matched:
                name = str(outcome.get("name", "")).lower().strip()
                desc = str(outcome.get("description", "")).lower().strip()
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

                if name == "over" or desc == "over":
                    this_over = price
                elif name == "under" or desc == "under":
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

    return median_line, median_over, median_under, books, debug_lines[:8]

def fetch_player_props(player_name: str, team_abbrev: str) -> Dict[str, Any]:
    event = find_event_for_team(team_abbrev)
    if not event:
        return {
            "event_found": False,
            "opponent": next_opponent_map.get(team_abbrev, "UNKNOWN"),
            "points_line": None,
            "points_over": None,
            "points_under": None,
            "threes_line": None,
            "threes_over": None,
            "threes_under": None,
            "books": None,
            "debug": ["No upcoming event matched for this team."],
        }

    opponent = get_opponent_from_event(event, team_abbrev)

    try:
        event_data = get_event_props(event["id"])
    except Exception as e:
        return {
            "event_found": True,
            "opponent": opponent,
            "points_line": None,
            "points_over": None,
            "points_under": None,
            "threes_line": None,
            "threes_over": None,
            "threes_under": None,
            "books": None,
            "debug": [f"Event props request failed: {e}"],
        }

    pts_line, pts_over, pts_under, pts_books, pts_debug = parse_prop_market(
        event_data, player_name, POINTS_MARKET_KEYS, preferred_only=True
    )
    thr_line, thr_over, thr_under, thr_books, thr_debug = parse_prop_market(
        event_data, player_name, THREES_MARKET_KEYS, preferred_only=True
    )

    if pts_line is None and pts_over is None and pts_under is None:
        pts_line, pts_over, pts_under, pts_books, pts_debug = parse_prop_market(
            event_data, player_name, POINTS_MARKET_KEYS, preferred_only=False
        )
    if thr_line is None and thr_over is None and thr_under is None:
        thr_line, thr_over, thr_under, thr_books, thr_debug = parse_prop_market(
            event_data, player_name, THREES_MARKET_KEYS, preferred_only=False
        )

    books = ", ".join(sorted(set(filter(None, [pts_books, thr_books])))) or None

    return {
        "event_found": True,
        "opponent": opponent,
        "points_line": pts_line,
        "points_over": pts_over,
        "points_under": pts_under,
        "threes_line": thr_line,
        "threes_over": thr_over,
        "threes_under": thr_under,
        "books": books,
        "debug": pts_debug + thr_debug,
    }

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

def build_stat_chart(df: pd.DataFrame, stat_col: str, vegas_line: Optional[float], target: int, title: str):
    chart_df = df.sort_values("GAME_DATE")[["GAME_DATE", stat_col]].copy()
    base = alt.Chart(chart_df).encode(x=alt.X("GAME_DATE:T", title="Game Date"))
    series = base.mark_line(point=True).encode(y=alt.Y(f"{stat_col}:Q", title=title))

    layers = [series]

    if vegas_line is not None:
        vegas_rule = alt.Chart(pd.DataFrame({"y": [vegas_line]})).mark_rule(
            strokeDash=[6, 4]
        ).encode(y="y:Q")
        layers.append(vegas_rule)

    target_rule = alt.Chart(pd.DataFrame({"y": [target]})).mark_rule(
        strokeDash=[2, 2]
    ).encode(y="y:Q")
    layers.append(target_rule)

    return alt.layer(*layers).properties(height=220)

# =========================
# UI
# =========================

st.title("NBA Prop Parlay Engine")
st.caption("Choose which prop types count toward parlay probability")

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
        leg_type = st.selectbox(
            "Count In Parlay",
            ["3PT only", "Points only", "Both"],
            key=f"leg_type_{i}",
        )

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
        props = fetch_player_props(player_name, team_abbrev)
        opponent = props["opponent"]
        factor = defense_map.get(opponent, 1.0)

        avg_3pt = calculate_weighted_avg(games, "FG3M")
        avg_pts = calculate_weighted_avg(games, "PTS")

        prob_3pt, adj_3pt = calculate_probability(avg_3pt, factor, pick["target_3pt"])
        prob_pts, adj_pts = calculate_probability(avg_pts, 1.0, pick["target_pts"])

        ev_3pt = calculate_ev(prob_3pt, american_to_decimal(props["threes_over"]))
        ev_pts = calculate_ev(prob_pts, american_to_decimal(props["points_over"]))

        if pick["leg_type"] == "3PT only":
            total_prob *= prob_3pt / 100
            included_legs.append({
                "player": player_name,
                "leg": f"3PT {pick['target_3pt']}+",
                "prob": prob_3pt,
            })
        elif pick["leg_type"] == "Points only":
            total_prob *= prob_pts / 100
            included_legs.append({
                "player": player_name,
                "leg": f"PTS {pick['target_pts']}+",
                "prob": prob_pts,
            })
        else:
            total_prob *= prob_3pt / 100
            total_prob *= prob_pts / 100
            included_legs.append({
                "player": player_name,
                "leg": f"3PT {pick['target_3pt']}+",
                "prob": prob_3pt,
            })
            included_legs.append({
                "player": player_name,
                "leg": f"PTS {pick['target_pts']}+",
                "prob": prob_pts,
            })

        total_ev += (ev_3pt or 0) + (ev_pts or 0)

        avg5_3 = games.head(5)["FG3M"].mean()
        avg10_3 = games.head(10)["FG3M"].mean()
        avg5_pts = games.head(5)["PTS"].mean()
        avg10_pts = games.head(10)["PTS"].mean()

        st.markdown("---")
        st.subheader(f"{player_name} · {team_abbrev} vs {opponent}")

        r1 = st.columns(4)
        with r1[0]:
            st.markdown(metric_card("Vegas 3PT line", str(props["threes_line"]) if props["threes_line"] is not None else "N/A"), unsafe_allow_html=True)
        with r1[1]:
            st.markdown(metric_card("Your 3PT target", str(pick["target_3pt"])), unsafe_allow_html=True)
        with r1[2]:
            st.markdown(metric_card("3PT hit probability", f"{prob_3pt}%"), unsafe_allow_html=True)
        with r1[3]:
            tone = "neutral" if ev_3pt is None else ("good" if ev_3pt > 0 else "bad")
            st.markdown(metric_card("3PT EV", "N/A" if ev_3pt is None else str(ev_3pt), tone), unsafe_allow_html=True)

        r2 = st.columns(4)
        with r2[0]:
            st.markdown(metric_card("Vegas points line", str(props["points_line"]) if props["points_line"] is not None else "N/A"), unsafe_allow_html=True)
        with r2[1]:
            st.markdown(metric_card("Your points target", str(pick["target_pts"])), unsafe_allow_html=True)
        with r2[2]:
            st.markdown(metric_card("Points hit probability", f"{prob_pts}%"), unsafe_allow_html=True)
        with r2[3]:
            tone = "neutral" if ev_pts is None else ("good" if ev_pts > 0 else "bad")
            st.markdown(metric_card("Points EV", "N/A" if ev_pts is None else str(ev_pts), tone), unsafe_allow_html=True)

        info = st.columns(4)
        info[0].write(f"**Expected 3PTs:** {adj_3pt:.2f}")
        info[1].write(f"**Expected points:** {adj_pts:.2f}")
        info[2].write(f"**Books found:** {props['books'] or 'None'}")
        info[3].write(f"**Parlay mode:** {pick['leg_type']}")

        with st.expander("Advanced analysis", expanded=False):
            a1, a2 = st.columns(2)
            with a1:
                st.write(f"Last 5 average 3PTM: {avg5_3:.2f}")
                st.write(f"Last 10 average 3PTM: {avg10_3:.2f}")
                st.write(f"Over odds (3PT): {props['threes_over'] if props['threes_over'] is not None else 'N/A'}")
                st.write(f"Under odds (3PT): {props['threes_under'] if props['threes_under'] is not None else 'N/A'}")
            with a2:
                st.write(f"Last 5 average points: {avg5_pts:.2f}")
                st.write(f"Last 10 average points: {avg10_pts:.2f}")
                st.write(f"Over odds (points): {props['points_over'] if props['points_over'] is not None else 'N/A'}")
                st.write(f"Under odds (points): {props['points_under'] if props['points_under'] is not None else 'N/A'}")

            st.altair_chart(
                build_stat_chart(games, "FG3M", props["threes_line"], pick["target_3pt"], "3PT Made"),
                use_container_width=True,
            )
            st.altair_chart(
                build_stat_chart(games, "PTS", props["points_line"], pick["target_pts"], "Points"),
                use_container_width=True,
            )

            if props["threes_line"] is None or props["points_line"] is None:
                st.markdown("**Odds debug**")
                if props["debug"]:
                    for line in props["debug"]:
                        st.code(line)
                else:
                    st.write("No debug samples available.")

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
            legs_df = pd.DataFrame(included_legs)
            legs_df = legs_df.sort_values("prob")

            weakest = legs_df.iloc[0]
            strongest = legs_df.iloc[-1]
            avg_leg_prob = round(legs_df["prob"].mean(), 2)

            st.write(f"**Included legs:** {len(legs_df)}")
            st.write(f"**Average leg probability:** {avg_leg_prob}%")
            st.write(f"**Weakest leg:** {weakest['player']} — {weakest['leg']} ({weakest['prob']}%)")
            st.write(f"**Strongest leg:** {strongest['player']} — {strongest['leg']} ({strongest['prob']}%)")

            if total_prob * 100 < 10:
                risk_text = "Very high risk parlay."
            elif total_prob * 100 < 25:
                risk_text = "High risk parlay."
            elif total_prob * 100 < 45:
                risk_text = "Moderate risk parlay."
            else:
                risk_text = "Relatively strong parlay."

            st.write(f"**Risk summary:** {risk_text}")

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