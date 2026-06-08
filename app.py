import os
import sqlite3
import json
from datetime import datetime, date
from flask import Flask, request, jsonify

app = Flask(__name__)
DB_PATH = os.environ.get("DB_PATH", "data.db")


# Database helpers

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS log_entries (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT NOT NULL,
                item_id    TEXT,                  -- optional reference to an item
                item_name  TEXT,                  -- human label
                logged_at  TEXT NOT NULL,          -- ISO date string YYYY-MM-DD
                fields     TEXT NOT NULL           -- JSON: {"calories": 200, "protein_g": 30}
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_user_date ON log_entries(user_id, logged_at)")
        db.commit()


# Helpers

#Sum all numbers across a list of entries
def aggregate_entries(entries):
    totals = {}
    for entry in entries:
        fields = json.loads(entry["fields"])
        for key, val in fields.items():
            if isinstance(val, (int, float)):
                totals[key] = round(totals.get(key, 0) + val, 4)
    #round to 1 decimal
    return {k: round(v, 1) for k, v in totals.items()}


# Routes

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "ms6-statistics"})


def fire_webhook(user_id, day):
    webhook_url = os.environ.get("WEBHOOK_URL")
    if not webhook_url:
        return
    try:
        import threading
        import urllib.request

        with get_db() as db:
            entries = db.execute(
                (user_id, day)
            ).fetchall()
        totals = aggregate_entries(entries)
        payload = json.dumps({"user_id": user_id, "date": day, "totals": totals}).encode()

        def _post():
            try:
                req = urllib.request.Request(
                    webhook_url, data=payload,
                    headers={"Content-Type": "application/json"}, method="POST"
                )
                urllib.request.urlopen(req, timeout=2)
            except Exception:
                pass 

        threading.Thread(target=_post, daemon=True).start()
    except Exception:
        pass


@app.route("/log", methods=["POST"])
def log_entry():
    body = request.get_json(force=True)

    if not body.get("user_id"):
        return jsonify({"error": "user_id is required"}), 400
    if not body.get("fields") or not isinstance(body["fields"], dict):
        return jsonify({"error": "fields must be a non-empty object"}), 400

    logged_at = body.get("logged_at") or date.today().isoformat()

    with get_db() as db:
        cur = db.execute(
            """INSERT INTO log_entries (user_id, item_id, item_name, logged_at, fields)
               VALUES (?, ?, ?, ?, ?)""",
            (
                body["user_id"],
                body.get("item_id"),
                body.get("item_name"),
                logged_at,
                json.dumps(body["fields"])
            )
        )
        db.commit()

    fire_webhook(body["user_id"], logged_at)
    return jsonify({"id": cur.lastrowid, "status": "logged"}), 201


#Returns totals for loggen entries on a date
@app.route("/stats/daily")
def daily_stats():
    user_id = request.args.get("user_id")
    day     = request.args.get("date") or date.today().isoformat()

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    with get_db() as db:
        entries = db.execute(
            "SELECT * FROM log_entries WHERE user_id=? AND logged_at=?",
            (user_id, day)
        ).fetchall()

    totals = aggregate_entries(entries)

    return jsonify({
        "user_id":       user_id,
        "date":          day,
        "totals":        totals,
        "entry_count":   len(entries),
        "entries":       [dict(e) | {"fields": json.loads(e["fields"])} for e in entries]
    })


#Returns per-day totals across range
@app.route("/stats/history")
def history_stats():
    user_id = request.args.get("user_id")
    start   = request.args.get("start")
    end     = request.args.get("end")

    if not all([user_id, start, end]):
        return jsonify({"error": "user_id, start, and end are required"}), 400

    with get_db() as db:
        entries = db.execute(
            "SELECT * FROM log_entries WHERE user_id=? AND logged_at BETWEEN ? AND ? ORDER BY logged_at",
            (user_id, start, end)
        ).fetchall()

    # Group by date
    by_date = {}
    for entry in entries:
        d = entry["logged_at"]
        by_date.setdefault(d, []).append(entry)

    history = [
        {"date": d, "totals": aggregate_entries(rows), "entry_count": len(rows)}
        for d, rows in sorted(by_date.items())
    ]

    return jsonify({
        "user_id": user_id,
        "start":   start,
        "end":     end,
        "days":    history,
        "total_entries": len(entries)
    })

#remove a logged entry
@app.route("/log/<int:entry_id>", methods=["DELETE"])
def delete_entry(entry_id):
    with get_db() as db:
        db.execute("DELETE FROM log_entries WHERE id=?", (entry_id,))
        db.commit()
    return jsonify({"status": "deleted", "id": entry_id})


#raw entries for a user
@app.route("/log")
def list_entries():
    user_id = request.args.get("user_id")
    day     = request.args.get("date") or date.today().isoformat()
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    with get_db() as db:
        entries = db.execute(
            "SELECT * FROM log_entries WHERE user_id=? AND logged_at=?",
            (user_id, day)
        ).fetchall()

    return jsonify([dict(e) | {"fields": json.loads(e["fields"])} for e in entries])


# Startup

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5006))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("DEBUG", "false") == "true")

