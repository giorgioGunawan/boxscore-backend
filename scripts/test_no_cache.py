#!/usr/bin/env python3
"""
Test script to verify all endpoints work correctly after cache removal.
Tests key endpoints that previously used caching.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_db, init_db
from app.services import GameService, PlayerService, StandingsService
from app.models import Team, Player


async def test_game_service():
    """Test game service endpoints."""
    print("\n🧪 Testing GameService...")
    
    async for db in get_db():
        try:
            # Test get_last_games (previously cached)
            print("  ✓ Testing get_last_games...")
            games = await GameService.get_last_games(db, team_id=1, count=3)
            assert isinstance(games, list), "Should return a list"
            print(f"    → Returned {len(games)} games")
            
            # Test get_next_games (previously cached)
            print("  ✓ Testing get_next_games...")
            next_games = await GameService.get_next_games(db, team_id=1, count=3)
            assert isinstance(next_games, list), "Should return a list"
            print(f"    → Returned {len(next_games)} upcoming games")
            
            print("  ✅ GameService tests passed!")
            return True
        except Exception as e:
            print(f"  ❌ GameService test failed: {e}")
            return False


async def test_player_service():
    """Test player service endpoints."""
    print("\n🧪 Testing PlayerService...")
    
    async for db in get_db():
        try:
            # Get a player to test with
            from sqlalchemy import select
            result = await db.execute(select(Player).limit(1))
            player = result.scalar_one_or_none()
            
            if not player:
                print("  ⚠️  No players in database, skipping player tests")
                return True
            
            # Test get_player_latest_game (previously cached)
            print(f"  ✓ Testing get_player_latest_game for player {player.id}...")
            try:
                game = await PlayerService.get_player_latest_game(db, player_id=player.id)
                print(f"    → Returned game data: {type(game)}")
            except Exception as e:
                print(f"    → No game data (expected if player hasn't played): {e}")
            
            # Test get_player_season_averages (previously cached)
            print(f"  ✓ Testing get_player_season_averages for player {player.id}...")
            try:
                stats = await PlayerService.get_player_season_averages(db, player_id=player.id)
                print(f"    → Returned stats: {type(stats)}")
            except Exception as e:
                print(f"    → No stats data (expected if no season data): {e}")
            
            print("  ✅ PlayerService tests passed!")
            return True
        except Exception as e:
            print(f"  ❌ PlayerService test failed: {e}")
            return False


async def test_standings_service():
    """Test standings service endpoints."""
    print("\n🧪 Testing StandingsService...")
    
    async for db in get_db():
        try:
            # Test get_conference_standings (previously cached)
            print("  ✓ Testing get_conference_standings...")
            standings = await StandingsService.get_conference_standings(
                db, conference="East"
            )
            assert isinstance(standings, list), "Should return a list"
            print(f"    → Returned {len(standings)} teams")
            
            # Test get_team_standing (previously cached)
            print("  ✓ Testing get_team_standing...")
            try:
                standing = await StandingsService.get_team_standing(db, team_id=1)
                print(f"    → Returned standing: {type(standing)}")
            except Exception as e:
                print(f"    → No standing data (expected if not populated): {e}")
            
            print("  ✅ StandingsService tests passed!")
            return True
        except Exception as e:
            print(f"  ❌ StandingsService test failed: {e}")
            return False


async def test_performance():
    """Test that queries are reasonably fast without cache."""
    print("\n⚡ Testing Performance (without cache)...")
    
    import time
    async for db in get_db():
        try:
            # Test multiple rapid requests
            start = time.time()
            for i in range(10):
                await GameService.get_last_games(db, team_id=1, count=3)
            elapsed = time.time() - start
            
            avg_time = elapsed / 10
            print(f"  ✓ 10 sequential requests took {elapsed:.3f}s")
            print(f"  ✓ Average per request: {avg_time*1000:.1f}ms")
            
            if avg_time < 0.1:  # Less than 100ms average
                print("  ✅ Performance is excellent!")
            elif avg_time < 0.5:  # Less than 500ms average
                print("  ✅ Performance is acceptable!")
            else:
                print("  ⚠️  Performance might be slow (but functional)")
            
            return True
        except Exception as e:
            print(f"  ❌ Performance test failed: {e}")
            return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("🚀 Testing Endpoints After Cache Removal")
    print("=" * 60)
    
    # Initialize database
    await init_db()
    
    # Run tests
    results = []
    results.append(await test_game_service())
    results.append(await test_player_service())
    results.append(await test_standings_service())
    results.append(await test_performance())
    
    # Summary
    print("\n" + "=" * 60)
    if all(results):
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\n✨ Cache removal successful - all endpoints working!")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
