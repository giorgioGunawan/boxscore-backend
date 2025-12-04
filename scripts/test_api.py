#!/usr/bin/env python3
"""
Quick test script to verify the API is working.
"""
import httpx
import json
import sys

BASE_URL = "http://localhost:8000"


def test_endpoint(name: str, url: str, expected_keys: list = None):
    """Test an API endpoint."""
    print(f"\n🔍 Testing: {name}")
    print(f"   URL: {url}")
    
    try:
        response = httpx.get(f"{BASE_URL}{url}", timeout=30.0)
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Status: {response.status_code}")
            
            if expected_keys:
                for key in expected_keys:
                    if key in data:
                        print(f"   ✅ Has key: {key}")
                    else:
                        print(f"   ❌ Missing key: {key}")
            
            # Print sample data
            print(f"   📦 Response preview: {json.dumps(data, indent=2)[:200]}...")
            return True
        else:
            print(f"   ❌ Status: {response.status_code}")
            print(f"   Error: {response.text[:200]}")
            return False
            
    except httpx.ConnectError:
        print(f"   ❌ Connection failed - is the server running?")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    print("🏀 NBA Boxscore API Test Suite")
    print("=" * 50)
    
    results = []
    
    # Test basic endpoints
    results.append(test_endpoint(
        "Health Check",
        "/health",
        ["status"]
    ))
    
    results.append(test_endpoint(
        "Root",
        "/",
        ["name", "version"]
    ))
    
    results.append(test_endpoint(
        "List Teams",
        "/api/teams",
        ["teams", "count"]
    ))
    
    results.append(test_endpoint(
        "Admin Stats",
        "/api/admin/stats",
        ["tables"]
    ))
    
    results.append(test_endpoint(
        "Cache Metrics",
        "/api/admin/metrics",
        ["cache"]
    ))
    
    # Test team endpoints (if teams exist)
    results.append(test_endpoint(
        "Team by Abbreviation (GSW)",
        "/api/teams/abbr/GSW",
        ["id", "name", "abbreviation"]
    ))
    
    results.append(test_endpoint(
        "Conference Standings (West)",
        "/api/teams/standings/West",
        ["conference", "standings"]
    ))
    
    results.append(test_endpoint(
        "Player Search",
        "/api/players/search?name=curry",
        ["players"]
    ))
    
    # Summary
    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✨ All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

