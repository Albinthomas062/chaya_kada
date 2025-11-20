# Render Deployment Guide for Chaya Kada

## Current Status
✅ Build is successful  
❌ Deployment failing due to database connection issue

## Issues to Fix

### 1. Database Connection Error
**Error:** `could not translate host name "dpg-d2nanandiees73cdcstg-a" to address`

**Solution:**
1. Go to your Render Dashboard
2. Create a PostgreSQL database (if not already created):
   - Click "New +" → "PostgreSQL"
   - Choose a name (e.g., `chayakada-db`)
   - Select the same region as your web service
   - Click "Create Database"

3. Update the `DATABASE_URL` environment variable in your web service:
   - Go to your web service → "Environment" tab
   - Find or add `DATABASE_URL`
   - Copy the **Internal Database URL** from your PostgreSQL database settings
   - Paste it as the value for `DATABASE_URL`
   - The format should be: `postgresql://username:password@hostname:port/database_name`

### 2. Redis Configuration (Required for WebSockets/Channels)
Your app uses Django Channels which requires Redis.

**Solution:**
1. Create a Redis instance:
   - **Option A (Recommended):** Use Render Redis
     - Click "New +" → "Redis"
     - Choose a name (e.g., `chayakada-redis`)
     - Select the same region as your web service
     - Click "Create Redis"
   
   - **Option B:** Use an external Redis provider (e.g., Upstash, Redis Cloud)

2. Add the `REDIS_URL` environment variable:
   - Go to your web service → "Environment" tab
   - Add a new environment variable: `REDIS_URL`
   - Copy the **Internal Redis URL** from your Redis instance
   - The format should be: `redis://hostname:port` or `rediss://hostname:port` (for TLS)

## Required Environment Variables

Make sure these are set in your Render web service environment:

```
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-app-name.onrender.com,yourdomain.com
DATABASE_URL=postgresql://user:password@hostname:port/dbname
REDIS_URL=redis://hostname:port
```

## Deployment Steps

1. **Fix environment variables** (as described above)
2. **Commit and push the updated settings.py:**
   ```bash
   git add chayakada/settings.py
   git commit -m "Update Redis configuration for production"
   git push
   ```
3. **Wait for automatic redeployment** on Render
4. **Monitor the logs** to ensure successful deployment

## Verification

Once deployed successfully, you should see:
- Migrations running successfully
- Gunicorn starting
- "Listening at: http://0.0.0.0:XXXX" in the logs

## Common Issues

### Issue: "No open ports detected"
- Make sure your app binds to `0.0.0.0` and the port from the `PORT` environment variable
- Render automatically sets the `PORT` variable

### Issue: Static files not loading
- Already configured with WhiteNoise
- Run `python manage.py collectstatic --noinput` in build.sh (should already be there)

### Issue: WebSocket connections failing
- Ensure Redis is properly configured
- Check that `REDIS_URL` is set correctly
- Verify ASGI application is running (you may need to use Daphne instead of Gunicorn for WebSocket support)

## Important Note: ASGI vs WSGI

Your app uses Django Channels (WebSockets), which requires an ASGI server. Currently, your start command uses Gunicorn (WSGI).

**You should update your start command to use Daphne:**

In Render dashboard → Your web service → Settings → Start Command:
```bash
python manage.py migrate && daphne -b 0.0.0.0 -p $PORT chayakada.asgi:application
```

Or keep both by running them separately (requires Background Worker):
- Web Service: `daphne -b 0.0.0.0 -p $PORT chayakada.asgi:application`
- Background Worker: `celery -A chayakada worker -l info`
