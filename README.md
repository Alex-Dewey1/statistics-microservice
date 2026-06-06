# MS6 — Statistics Microservice

A generic statistics service. Log any numeric data for any user and retrieve daily totals or historical trends over a date range.

## What it does
- Logs any JSON numeric fields per user per day
- Aggregates daily totals with floating-point precision
- Returns historical reports over custom date ranges (max 31 days, under 500ms)
- Fully decoupled — does NOT call any other service

## Quick start
```bash
pip install -r requirements.txt
python app.py          # runs on port 5006
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/log` | Log a new entry |
| GET | `/log` | List raw entries for a user/date |
| DELETE | `/log/<id>` | Delete an entry |
| GET | `/stats/daily` | Daily aggregated totals |
| GET | `/stats/history` | Per-day totals over a date range |

### Log an entry
```json
POST /log
{
  "user_id": "user_123",
  "item_name": "Greek Yogurt",
  "item_id": "food_42",
  "logged_at": "2026-06-05",
  "fields": {
    "calories": 59,
    "protein_g": 10.0,
    "carbs_g": 3.6
  }
}
```
The `fields` object can contain **any numeric keys** — the service doesn't know or care what they represent.

### Get daily stats
```
GET /stats/daily?user_id=user_123&date=2026-06-05
```
```json
{
  "user_id": "user_123",
  "date": "2026-06-05",
  "totals": { "calories": 1840.0, "protein_g": 95.3, "carbs_g": 210.4 },
  "entry_count": 5
}
```

### Get history
```
GET /stats/history?user_id=user_123&start=2026-06-01&end=2026-06-07
```

## Using it in your project

The `fields` object is completely open — map it to whatever your project needs:

| Project | Example fields |
|---------|---------------|
| Calorie tracker | `{"calories": 500, "protein_g": 30}` |
| Workout tracker | `{"reps": 10, "sets": 3, "weight_kg": 80}` |
| Finance app | `{"amount": 42.50, "category_id": 3}` |
| Sleep tracker | `{"hours": 7.5, "quality_score": 8}` |

## Connecting to a badge/notification service

This service is intentionally decoupled. To notify MS9 (or any other service) after a log:

**Option A — Webhook (recommended):** Set `WEBHOOK_URL` in env. The service will POST daily totals there after each log.

**Option B — Poll:** Your orchestrator polls `/stats/daily` after logging and decides what to do.

**Option C — Direct call from your main app:** Your main app calls `/log` on MS6, then calls `/milestones/check` on MS9 directly.

```bash
# Option A: set webhook
WEBHOOK_URL=http://ms9-badges:5009/milestones/check python app.py
```

## Environment variables
| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `5006` | Port to run on |
| `DB_PATH` | `data.db` | SQLite database path |
| `WEBHOOK_URL` | *(none)* | Optional URL to POST daily totals after each log |
| `DEBUG` | `false` | Enable Flask debug mode |
