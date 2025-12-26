"""Test script to check if Cooper Flagg is in the Dallas Mavericks roster."""
import sys
sys.path.insert(0, '/Users/giorgio/personal/boxscore-backend')

from app.nba_client import NBAClient

def main():
    print("Checking Dallas Mavericks roster for Cooper Flagg...")
    print("=" * 60)
    
    # Get Dallas Mavericks roster (team_id = 1610612742)
    roster = NBAClient.get_team_roster(1610612742, season='2025-26')
    print(f'\nTotal players on roster: {len(roster)}')
    
    # Search for Cooper Flagg
    flagg = [p for p in roster if 'Flagg' in p['name']]
    
    if flagg:
        print(f'\n✅ Found Cooper Flagg!')
        print(f'   Name: {flagg[0]["name"]}')
        print(f'   NBA Player ID: {flagg[0]["nba_player_id"]}')
        print(f'   Position: {flagg[0]["position"]}')
        print(f'   Number: {flagg[0]["number"]}')
    else:
        print('\n❌ Cooper Flagg NOT found in Dallas Mavericks roster')
        print('\nShowing all players on roster:')
        for i, p in enumerate(roster, 1):
            print(f'  {i}. {p["name"]} (ID: {p["nba_player_id"]}, Pos: {p["position"]})')

if __name__ == '__main__':
    main()
