import requests
import pandas as pd
from datetime import datetime

def fetch_fanduel_odds():
    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/"
    params = {
        "apiKey": "c86b551f2e51c698515893c141c6c1a6",
        "regions": "us",
        "markets": "player_points",
        "oddsFormat": "american"
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    odds_list = []

    for game in data:
        home_team = game['home_team']
        away_team = game['away_team']

        for bookmaker in game.get('bookmakers', []):
            if bookmaker.get('key') == 'fanduel':
                for market in bookmaker.get('markets', []):
                    if market.get('key') == 'player_points':
                        for outcome in market.get('outcomes', []):
                            player = outcome.get('name')
                            team_side = outcome.get('team')  # 'home' or 'away'
                            team = home_team if team_side == 'home' else away_team
                            opponent = away_team if team_side == 'home' else home_team
                            odds = outcome.get('price')

                            odds_list.append({
                                'Player': player,
                                'Team': team,
                                'Opponent': opponent,
                                'Odds': odds
                            })

    df = pd.DataFrame(odds_list)
    return df

def save_odds(df):
    filename = "odds_today.csv"
    df.to_csv(filename, index=False)
    print(f"Saved {len(df)} odds entries to {filename}")

if __name__ == "__main__":
    try:
        odds_df = fetch_fanduel_odds()
        save_odds(odds_df)
    except Exception as e:
        print(f"Error fetching odds: {e}")