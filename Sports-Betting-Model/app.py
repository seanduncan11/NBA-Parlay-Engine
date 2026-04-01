# Imports
from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog
from scipy.stats import poisson

# --- USER INPUT ---
player_name = "Stephen Curry"  # Change to any NBA player
X = 4  # Number of threes you want to calculate probability for

# --- FIND PLAYER ---
player_list = players.get_players()
player_matches = [p for p in player_list if p['full_name'] == player_name]

if not player_matches:
    print(f"Player '{player_name}' not found.")
    exit()

player_id = player_matches[0]['id']

# --- PULL GAME LOG ---
gamelog = playergamelog.PlayerGameLog(player_id=player_id)
df = gamelog.get_data_frames()[0]

# --- CALCULATE AVERAGE 3-POINTERS ---
avg_3s = df['FG3M'].mean()
print(f"{player_name} average 3-pointers per game (last {len(df)} games): {avg_3s:.2f}")

# --- CALCULATE PROBABILITY ---
prob = 1 - poisson.cdf(X-1, avg_3s)
print(f"Probability of hitting {X}+ threes: {prob*100:.2f}%")

# --- OPTIONAL: SHOW LAST 5 GAMES ---
print("\nLast 5 games:")
print(df[['GAME_DATE', 'FG3M']].head())