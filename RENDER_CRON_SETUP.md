# Render Cron Jobs Setup Guide

This guide shows you how to set up Render's native Cron Jobs feature to replace the in-app APScheduler.

## Why Use Render Cron Jobs?

✅ **Isolated execution** - Jobs run in separate containers, don't block your web service  
✅ **No multi-instance issues** - Each job runs once, not duplicated across containers  
✅ **Better monitoring** - View logs and status directly in Render dashboard  
✅ **Automatic retries** - Render can retry failed jobs  
✅ **No stop/cancel issues** - Jobs naturally complete and shut down  

## Step 1: Create Cron Jobs in Render Dashboard

Go to your Render Dashboard → Your Web Service → Add New → **Cron Job**

### Job 1: Update Finished Games (Every 2 Hours)

**Name:** `update-finished-games`  
**Command:** `python scripts/cron_update_finished_games.py`  
**Schedule:** `0 */2 * * *` (every 2 hours at minute 0)  
**Region:** Same as your web service  
**Environment:** Copy all environment variables from your web service  

**Optional Environment Variables:**
- `HOURS_BACK=12` (default: look back 12 hours for finished games)

---

### Job 2: Update Player Season Stats (Every 3 Days)

**Name:** `update-player-season-stats`  
**Command:** `python scripts/cron_update_player_season_stats.py`  
**Schedule:** `0 0 */3 * *` (every 3 days at midnight UTC)  
**Region:** Same as your web service  
**Environment:** Copy all environment variables from your web service  

---

### Job 3: Check Schedule Changes (Every 3 Days)

**Name:** `check-schedule-changes`  
**Command:** `python scripts/cron_check_schedule_changes.py`  
**Schedule:** `0 6 */3 * *` (every 3 days at 6am UTC)  
**Region:** Same as your web service  
**Environment:** Copy all environment variables from your web service  

---

## Step 2: Update Your render.yaml (Optional)

If you're using Infrastructure as Code, add this to your `render.yaml`:

```yaml
services:
  - type: web
    name: boxscore-backend
    runtime: python
    plan: starter
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: REDIS_URL
        sync: false
      - key: CURRENT_SEASON
        value: "2025-26"

  # Cron Job 1: Update Finished Games
  - type: cron
    name: update-finished-games
    runtime: python
    schedule: "0 */2 * * *"
    buildCommand: pip install -r requirements.txt
    startCommand: python scripts/cron_update_finished_games.py
    envVars:
      - key: DATABASE_URL
        fromService:
          name: boxscore-backend
          type: web
          envVarKey: DATABASE_URL
      - key: REDIS_URL
        fromService:
          name: boxscore-backend
          type: web
          envVarKey: REDIS_URL
      - key: CURRENT_SEASON
        value: "2025-26"
      - key: HOURS_BACK
        value: "12"

  # Cron Job 2: Update Player Season Stats
  - type: cron
    name: update-player-season-stats
    runtime: python
    schedule: "0 0 */3 * *"
    buildCommand: pip install -r requirements.txt
    startCommand: python scripts/cron_update_player_season_stats.py
    envVars:
      - key: DATABASE_URL
        fromService:
          name: boxscore-backend
          type: web
          envVarKey: DATABASE_URL
      - key: REDIS_URL
        fromService:
          name: boxscore-backend
          type: web
          envVarKey: REDIS_URL
      - key: CURRENT_SEASON
        value: "2025-26"

  # Cron Job 3: Check Schedule Changes
  - type: cron
    name: check-schedule-changes
    runtime: python
    schedule: "0 6 */3 * *"
    buildCommand: pip install -r requirements.txt
    startCommand: python scripts/cron_check_schedule_changes.py
    envVars:
      - key: DATABASE_URL
        fromService:
          name: boxscore-backend
          type: web
          envVarKey: DATABASE_URL
      - key: REDIS_URL
        fromService:
          name: boxscore-backend
          type: web
          envVarKey: REDIS_URL
      - key: CURRENT_SEASON
        value: "2025-26"
```

---

## Step 3: Test Locally

Before deploying, test the scripts work:

```bash
# Test update finished games
python scripts/cron_update_finished_games.py

# Test with custom hours_back
HOURS_BACK=24 python scripts/cron_update_finished_games.py

# Test player season stats
python scripts/cron_update_player_season_stats.py

# Test schedule changes
python scripts/cron_check_schedule_changes.py
```

---

## Step 4: Monitoring & Logs

### View Logs in Render
1. Go to Render Dashboard
2. Click on the Cron Job
3. Go to "Logs" tab
4. See execution history and output

### View in Admin Dashboard
Your existing admin dashboard will still show all runs in the "Cron Management" tab:
- All cron runs are logged to the database
- You can see which jobs succeeded/failed
- View detailed logs for each run
- **Manual triggers from admin will still work!**

---

## Step 5: Manual Triggers (Optional)

You can still manually trigger jobs from:
1. **Render Dashboard** - Click "Trigger Run" on any cron job
2. **Your Admin Dashboard** - Still works! Runs directly in your web service
3. **SSH/Shell** - Run the Python scripts directly

---

## What About APScheduler?

### Option A: Keep Both (Recommended)
- **Render Cron Jobs** for production (reliable, isolated)
- **APScheduler** for local development and manual admin triggers
- No code changes needed!

### Option B: Remove APScheduler
If you want to fully remove APScheduler:
1. Remove `APScheduler` from `requirements.txt`
2. Remove `app/cron/scheduler.py`
3. Remove scheduler initialization from `app/main.py`
4. Keep the admin trigger endpoints (they'll just run scripts directly)

---

## Cron Schedule Reference

```
# Every 2 hours
0 */2 * * *

# Every 3 days at midnight UTC
0 0 */3 * *

# Every day at 3am UTC
0 3 * * *

# Every 6 hours
0 */6 * * *

# Every hour during game days (7pm-11pm EST = 0am-4am UTC)
0 0-4 * * *
```

---

## Troubleshooting

### Job fails with "Module not found"
- Make sure `buildCommand` is set to `pip install -r requirements.txt`
- Check that all dependencies are in `requirements.txt`

### Job can't connect to database
- Make sure `DATABASE_URL` environment variable is set
- Check that the database is in the same region as the cron job

### Job times out
- Render cron jobs have a **1 hour timeout** by default
- If jobs take longer, consider breaking them into smaller chunks

### Logs show "database is locked"
- This is normal for SQLite with concurrent access
- Consider upgrading to PostgreSQL for production

---

## Migration Checklist

- [ ] Test all 3 scripts locally
- [ ] Create 3 cron jobs in Render Dashboard
- [ ] Set correct schedules and environment variables
- [ ] Wait for first scheduled run
- [ ] Check logs in Render Dashboard
- [ ] Verify runs appear in Admin Dashboard
- [ ] (Optional) Update `render.yaml`
- [ ] (Optional) Remove APScheduler code

---

## Next Steps

Once you've verified Render Cron Jobs are working:
1. Monitor the first few runs
2. Adjust schedules if needed (e.g., more/less frequent)
3. Add alerting (Render can send alerts on job failures)
4. Consider PostgreSQL if you're using SQLite in production

