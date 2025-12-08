"""
Test script to check NBA API directly for LeBron's stats.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nba_api.stats.endpoints import playergamelog, boxscoretraditionalv2
from app.config import get_settings

settings = get_settings()

# LeBron's NBA Player ID
LEBRON_ID = 2544
GAME_ID = "0022500362"

print("=" * 60)
print("TESTING NBA API DIRECTLY")
print("=" * 60)

# Test 1: Get LeBron's game log
print("\n1. Testing PlayerGameLog API for LeBron James (ID: 2544)")
print("-" * 60)
try:
    game_log = playergamelog.PlayerGameLog(
        player_id=LEBRON_ID,
        season=settings.current_season,
        season_type_all_star="Regular Season"
    )
    df = game_log.get_data_frames()[0]
    
    print(f"✅ Successfully fetched game log")
    print(f"   Total games in log: {len(df)}")
    
    # Check if game 0022500362 is in the log
    game_found = df[df['Game_ID'] == GAME_ID]
    
    if len(game_found) > 0:
        print(f"\n✅ Game {GAME_ID} FOUND in LeBron's game log!")
        row = game_found.iloc[0]
        print(f"   Date: {row.get('GAME_DATE', 'N/A')}")
        print(f"   PTS: {row.get('PTS', 0)}")
        print(f"   REB: {row.get('REB', 0)}")
        print(f"   AST: {row.get('AST', 0)}")
        print(f"   MIN: {row.get('MIN', 'N/A')}")
    else:
        print(f"\n❌ Game {GAME_ID} NOT FOUND in LeBron's game log")
        print(f"\n   Most recent games in log:")
        for idx, row in df.head(5).iterrows():
            print(f"   - Game ID: {row.get('Game_ID')}, Date: {row.get('GAME_DATE')}, PTS: {row.get('PTS')}")
    
except Exception as e:
    print(f"❌ Error fetching game log: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Get boxscore for the game
print("\n\n2. Testing BoxScoreTraditionalV2 API for game 0022500362")
print("-" * 60)
try:
    boxscore = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=GAME_ID)
    dfs = boxscore.get_data_frames()
    
    if len(dfs) > 0:
        player_stats_df = dfs[0]  # PlayerStats dataframe
        
        print(f"✅ Successfully fetched boxscore")
        print(f"   Total players in boxscore: {len(player_stats_df)}")
        
        # Check if LeBron is in the boxscore
        lebron_stats = player_stats_df[player_stats_df['PLAYER_ID'] == LEBRON_ID]
        
        if len(lebron_stats) > 0:
            print(f"\n✅ LeBron James FOUND in boxscore!")
            row = lebron_stats.iloc[0]
            print(f"   Name: {row.get('PLAYER_NAME', 'N/A')}")
            print(f"   PTS: {row.get('PTS', 0)}")
            print(f"   REB: {row.get('REB', 0)}")
            print(f"   AST: {row.get('AST', 0)}")
            print(f"   MIN: {row.get('MIN', 'N/A')}")
        else:
            print(f"\n❌ LeBron James NOT FOUND in boxscore")
            print(f"\n   Players found in boxscore (first 10):")
            for idx, row in player_stats_df.head(10).iterrows():
                print(f"   - {row.get('PLAYER_NAME')} (ID: {row.get('PLAYER_ID')})")
    else:
        print(f"❌ Boxscore returned empty dataframes")
        
except Exception as e:
    print(f"❌ Error fetching boxscore: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)

