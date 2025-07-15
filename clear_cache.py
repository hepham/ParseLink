#!/usr/bin/env python3
import redis
import sys

# Redis config from the application
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0

try:
    # Connect to Redis
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    
    # Test connection
    r.ping()
    print("✅ Connected to Redis")
    
    # Get current cache info
    cache_keys = r.keys('parsed_url:*')
    print(f"📊 Found {len(cache_keys)} cached URLs")
    
    if cache_keys:
        # Clear all cache keys
        r.flushdb()
        print("🗑️ Cache cleared successfully!")
        
        # Verify cache is empty
        remaining_keys = r.keys('parsed_url:*')
        print(f"📊 Remaining cached URLs: {len(remaining_keys)}")
        
    else:
        print("ℹ️ Cache is already empty")
        
except redis.ConnectionError:
    print("❌ Failed to connect to Redis")
    print("Make sure Redis server is running on localhost:6379")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1) 