# Bug Fixes and Deployment Guide

## Critical Bugs Fixed

### 1. **WebSocket/Channels Configuration (Online Matching & Messaging)**
**Root Cause:**
- Used `InMemoryChannelLayer` instead of Redis (won't work across processes)
- WebSocket URL patterns used `\w+` which doesn't match UUIDs with hyphens
- ASGI import order issue: imported models before Django settings were initialized
- Procfile used Gunicorn (WSGI) instead of Daphne (ASGI), so WebSockets couldn't connect

**Fixes:**
- Changed to `RedisChannelLayer` in `settings.py`
- Updated WebSocket URL patterns to `[0-9a-f-]+` to match UUIDs
- Fixed `asgi.py` import order: call `get_asgi_application()` BEFORE importing routing
- Updated `Procfile` to use Daphne instead of Gunicorn
- Updated `ChatConsumer` to actually save and broadcast messages

**Files Changed:**
- `chayakada/settings.py` - Redis channel layer configuration
- `chatkada/routing.py` - Fixed UUID pattern in WebSocket routes
- `chayakada/asgi.py` - Fixed import order to prevent ImproperlyConfigured error
- `Procfile` - Changed from `gunicorn` to `daphne`
- `chatkada/consumers.py` - Implemented proper message saving and broadcasting

### 2. **Messaging System (Messages Not Delivered)**
**Root Cause:**
- `ChatConsumer.receive()` didn't save messages to database
- Messages weren't being broadcast to all room participants
- chat_room.html template had broken JavaScript/CSS syntax

**Fixes:**
- Implemented `save_message()` in ChatConsumer with proper database persistence
- Added message broadcasting to all connected clients in room
- Completely rewrote `chat_room.html` with working WebSocket client code
- Added reconnection logic for dropped connections

**Files Changed:**
- `chatkada/consumers.py` - Added message persistence and broadcasting
- `chatkada/templates/chat_room.html` - Complete rewrite with functional UI

### 3. **Benches (Creating Chat Rooms)**
**Root Cause:**
- No validation or proper POST handling
- Missing participants when creating theatre rooms

**Fixes:**
- Added proper POST requirement for theatre room creation
- Created `create_theatre.html` template for proper form submission
- Added creator as participant when creating theatre rooms
- Fixed GET redirect for `create_private_bench`

**Files Changed:**
- `chatkada/views.py` - `create_theatre_room()` now requires POST
- `chatkada/templates/create_theatre.html` - New template for theatre creation

### 4. **Theatre Feature (Channel Loading)**
**Root Cause:**
- External IPTV playlist fetch had no error handling
- Failures showed generic "Loading Channels..." indefinitely

**Fixes:**
- Added comprehensive error handling for IPTV fetch
- User-friendly error messages when channel source is unreachable
- Retry button and fallback messaging

**Files Changed:**
- `chatkada/templates/theatre_room.html` - Added error handling with clear user feedback

### 5. **UI Issues (Broken Layouts & No Items)**
**Root Cause:**
- Empty database (no menu items seeded)
- Management command folder had typo: `managment` instead of `management`
- Broken template syntax in chat_room.html

**Fixes:**
- Renamed folder from `managment` to `management`
- Created data migration to populate initial menu items (18 items across chai/snacks/sweets)
- Fixed all template syntax errors

**Files Changed:**
- Renamed `chatkada/managment/` → `chatkada/management/`
- `chatkada/migrations/0005_populate_items.py` - New data migration for menu items
- `chatkada/templates/chat_room.html` - Fixed all syntax errors

### 6. **Online User Detection**
**Root Cause:**
- Middleware was correct but online status query had minor issues

**Fixes:**
- Fixed `get_online_status()` view to properly query online users
- Verified middleware updates `last_activity` and `is_online` correctly

**Files Changed:**
- `chatkada/views.py` - Fixed online status query

---

## Render Deployment Requirements

### Required Environment Variables

Set these in your Render web service (Dashboard → Environment):

```bash
SECRET_KEY=<generate-a-secure-random-key>
DEBUG=False
ALLOWED_HOSTS=chaya-kada-244m.onrender.com
DATABASE_URL=<your-postgres-internal-url>
REDIS_URL=<your-redis-internal-url>
```

### Required Services

1. **PostgreSQL Database**
   - Create: Render Dashboard → New+ → PostgreSQL
   - Copy the "Internal Database URL" to `DATABASE_URL`

2. **Redis Instance** (CRITICAL - Required for WebSockets)
   - Create: Render Dashboard → New+ → Redis
   - Copy the "Internal Redis URL" to `REDIS_URL`
   - Format: `redis://red-xxxxx:6379` or `rediss://...` for TLS

### Start Command

The Procfile is now configured correctly:
```bash
daphne -b 0.0.0.0 -p $PORT chayakada.asgi:application
```

### Build Command (render.yaml or Dashboard)

```bash
chmod +x build.sh && ./build.sh
```

The `build.sh` already handles:
- Installing system dependencies
- Installing Python packages
- Collecting static files

### Post-Deployment

After first deploy, run migrations manually once:
```bash
python manage.py migrate
```

This will:
1. Create all database tables
2. Run the data migration to populate menu items (18 items)

---

## Local Development Setup

### Prerequisites
- Python 3.11+
- PostgreSQL
- Redis server

### Installation

1. **Clone and setup virtual environment:**
   ```bash
   git clone <repo-url>
   cd chaya-kada
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Setup environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your local settings
   ```

4. **Start Redis:**
   ```bash
   redis-server
   ```

5. **Run migrations:**
   ```bash
   python manage.py migrate
   ```
   This automatically populates the menu with 18 items.

6. **Create superuser (optional):**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run development server with Daphne (for WebSocket support):**
   ```bash
   daphne -b 127.0.0.1 -p 8000 chayakada.asgi:application
   ```

   Or use Django's runserver for quick testing (WebSockets may not work):
   ```bash
   python manage.py runserver
   ```

8. **Access the application:**
   - Main app: http://127.0.0.1:8000/
   - Admin: http://127.0.0.1:8000/admin/

---

## Testing the Fixes

### Test 1: Online User Matching
1. Open two browsers (or incognito windows)
2. Register/login as two different users
3. Both navigate to `/find-chat/`
4. Verify online count shows "1 online" for each user
5. Click "Find a Stranger" - both should match instantly

### Test 2: Messaging
1. After matching (or join same bench), send messages
2. Messages should appear in real-time for both users
3. Refresh page - messages should persist

### Test 3: Benches
1. Go to `/find-chat/`
2. Create Private Bench with a name
3. Click "Invite" to generate an invite link
4. Share link with another user
5. Both users should see each other's messages

### Test 4: Theatre
1. Click "Create Theatre" button (POST form submission)
2. Enter theatre name and submit
3. If IPTV source loads: search for channels
4. If IPTV fails: should show clear error message with retry button
5. Chat should work in theatre room
6. Seat selection should work

### Test 5: UI
1. Go to `/kada/`
2. Should see 5 Chai items, 7 Snacks, 6 Sweets
3. Buy items with coins
4. Items should appear in profile for sharing

---

## Known Limitations & Future Improvements

### Current Limitations:
1. **IPTV Source**: The external IPTV playlist (iptv-org.github.io) may be unreachable due to CORS or availability. This is gracefully handled with error messages.

2. **Redis Required in Production**: Unlike development with InMemoryChannelLayer, production REQUIRES Redis for WebSocket/Channels to work across multiple workers.

3. **Theatre Seats**: Currently seat updates trigger a page reload. Could be improved with WebSocket-based real-time updates.

### Recommended Improvements:
1. Add rate limiting for message sending
2. Implement message encryption for stranger chats
3. Add user blocking/reporting features
4. Implement Redis session backend for better scalability
5. Add comprehensive error logging (Sentry integration)

---

## Configuration Changes Needed on Render

**Before these fixes will work, you MUST:**

1. ✅ Add Redis service to your Render account
2. ✅ Set `REDIS_URL` environment variable
3. ✅ Verify `DATABASE_URL` is set correctly
4. ✅ The Procfile change will auto-deploy (uses Daphne now)
5. ✅ Run migrations after deployment

**Do NOT commit secrets or API keys to the repository.**

---

## File Summary

### Modified Files:
- `chayakada/settings.py` - Redis channel layer
- `chayakada/asgi.py` - Fixed import order
- `chatkada/routing.py` - UUID patterns
- `chatkada/consumers.py` - Message persistence
- `chatkada/views.py` - Theatre POST requirement, online status
- `chatkada/templates/chat_room.html` - Complete rewrite
- `chatkada/templates/theatre_room.html` - Error handling
- `Procfile` - Daphne instead of Gunicorn
- `requirements.txt` - Added redis package

### New Files:
- `chatkada/templates/create_theatre.html` - Theatre creation form
- `chatkada/migrations/0005_populate_items.py` - Menu items seed data
- `.env.example` - Environment variable template
- `DEPLOYMENT_FIXES.md` - This file

### Renamed:
- `chatkada/managment/` → `chatkada/management/` - Fixed typo

---

## Support

If issues persist after deployment:
1. Check Render logs for errors
2. Verify Redis connection: `redis-cli ping`
3. Verify DATABASE_URL and REDIS_URL are set
4. Ensure migrations ran: `python manage.py showmigrations`
5. Check WebSocket connection in browser console
