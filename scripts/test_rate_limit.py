
import requests
import sys
import time

BASE_URL = "http://localhost:8000"

def test_rate_limit(endpoint, limit=100):
    print(f"\nTesting Rate Limit for {endpoint} (Limit: {limit})...")
    
    # Send requests up to the limit + buffer
    count = limit + 20
    
    print(f"Sending {count} requests...")
    start_time = time.time()
    
    got_429 = False
    results = []
    
    for i in range(count):
        try:
            r = requests.get(f"{BASE_URL}{endpoint}", headers={"X-Device-ID": "test-device-1"})
            results.append(r.status_code)
            if r.status_code == 429:
                got_429 = True
                print(f"✅ Hit Rate Limit (429) at request #{i+1}")
                break
        except Exception as e:
            print(f"❌ Error: {e}")
            
    if got_429:
        print(f"✅ Rate limiting working as expected for {endpoint}")
        return True
    else:
        print(f"❌ Failed to hit rate limit for {endpoint}")
        print(f"Status codes: {results[:10]} ... {results[-10:]}")
        return False

def main():
    print("Waiting for server to be ready...")
    for i in range(5):
        try:
            requests.get(f"{BASE_URL}/health")
            print("Server is up!")
            break
        except:
            time.sleep(1)
    else:
        print("Server failed to start")
        sys.exit(1)

    success = True
    # Test teams endpoint (Limit 100)
    # Actually, sending 120 requests takes time.
    # Be mindful of execution time.
    # To test quickly, maybe we should have set a lower limit for testing?
    # Or just spam it.
    
    # Since I already implemented 100/minute, I'll spam 110 requests.
    success &= test_rate_limit("/api/teams/", limit=100)
    
    # Test search (Limit 20) - Faster to test
    success &= test_rate_limit("/api/players/search?name=test", limit=20)
    
    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
