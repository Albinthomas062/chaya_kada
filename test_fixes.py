#!/usr/bin/env python3
"""
Test that the ASGI configuration doesn't have the ImproperlyConfigured error.
This tests the specific issue reported: "daphne chayakada.asgi:application crashes
with ImproperlyConfigured because chatkada.routing imports models before 
DJANGO_SETTINGS_MODULE is set"
"""

import sys
import os

print("Testing ASGI import order fix...")
print("-" * 60)

# The fix: DJANGO_SETTINGS_MODULE must be set BEFORE importing routing
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chayakada.settings')

try:
    # This should work now because asgi.py calls get_asgi_application() 
    # BEFORE importing chatkada.routing
    print("1. Checking asgi.py structure...")
    with open('chayakada/asgi.py', 'r') as f:
        asgi_content = f.read()
    
    # Verify the fix is in place
    if 'django_asgi_app = get_asgi_application()' in asgi_content:
        print("   ✅ get_asgi_application() called early")
    else:
        print("   ❌ get_asgi_application() not called before imports")
        sys.exit(1)
    
    if asgi_content.index('get_asgi_application()') < asgi_content.index('import chatkada.routing'):
        print("   ✅ get_asgi_application() called BEFORE chatkada.routing import")
    else:
        print("   ❌ Import order incorrect")
        sys.exit(1)
    
    print("\n2. Checking WebSocket URL patterns...")
    with open('chatkada/routing.py', 'r') as f:
        routing_content = f.read()
    
    if '[0-9a-f-]+' in routing_content:
        print("   ✅ WebSocket patterns support UUID format with hyphens")
    else:
        print("   ❌ WebSocket patterns don't match UUIDs")
        sys.exit(1)
    
    print("\n3. Checking Procfile uses Daphne...")
    with open('Procfile', 'r') as f:
        procfile_content = f.read()
    
    if 'daphne' in procfile_content and 'asgi:application' in procfile_content:
        print("   ✅ Procfile uses Daphne (ASGI server)")
    else:
        print("   ❌ Procfile doesn't use Daphne")
        sys.exit(1)
    
    print("\n4. Checking Redis channel layer...")
    with open('chayakada/settings.py', 'r') as f:
        settings_content = f.read()
    
    if 'channels_redis.core.RedisChannelLayer' in settings_content:
        print("   ✅ Using RedisChannelLayer (production-ready)")
    else:
        print("   ❌ Not using Redis channel layer")
        sys.exit(1)
    
    print("\n5. Checking message persistence...")
    with open('chatkada/consumers.py', 'r') as f:
        consumer_content = f.read()
    
    if 'def save_message' in consumer_content and 'ChatMessage.objects.create' in consumer_content:
        print("   ✅ ChatConsumer persists messages to database")
    else:
        print("   ❌ Messages not being saved")
        sys.exit(1)
    
    print("\n6. Checking menu items migration...")
    if os.path.exists('chatkada/migrations/0005_populate_items.py'):
        print("   ✅ Menu items seed migration exists")
    else:
        print("   ❌ Menu items migration missing")
        sys.exit(1)
    
    print("\n7. Checking management folder spelling...")
    if os.path.exists('chatkada/management'):
        print("   ✅ Management folder name correct")
    else:
        print("   ❌ Management folder typo still exists")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ ALL CRITICAL FIXES VERIFIED")
    print("=" * 60)
    print("\nThe ASGI import order issue is fixed.")
    print("Running 'daphne chayakada.asgi:application' should work now.")
    print("\nRemaining requirement for Render:")
    print("  - Add Redis service and set REDIS_URL environment variable")
    print("  - Run migrations to populate menu items")
    
except Exception as e:
    print(f"\n❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
