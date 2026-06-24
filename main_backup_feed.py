import os
import json
from typing import Optional
from fastapi import FastAPI, HTTPException
import psycopg2
import psycopg2.extras

app = FastAPI(title="STREAM API")

# ---------- Helper ----------
def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="sports_db",
        user="postgres",
        password=os.getenv("PG_PASSWORD", "")
    )

# ---------- ROOT ----------
@app.get("/")
def root():
    return {"message": "STREAM API running"}

# ---------- BOND ENDPOINTS ----------
@app.get("/api/bonds")
async def get_bonds(user_id: int = None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, description, bond_type, match_ids, price, expires_at, status
        FROM bonds
        ORDER BY created_at DESC
    """)
    bonds = cur.fetchall()
    unlocked_ids = set()
    if user_id:
        cur.execute("SELECT bond_id FROM user_bond_unlocks WHERE user_id = %s", (user_id,))
        unlocked_ids = {row[0] for row in cur.fetchall()}
    result = []
    for b in bonds:
        result.append({
            "id": b[0],
            "title": b[1],
            "description": b[2],
            "bond_type": b[3],
            "match_count": len(b[4]),
            "price": b[5],
            "expires_at": b[6].isoformat() if b[6] else None,
            "status": b[7],
            "unlocked": b[0] in unlocked_ids
        })
    cur.close()
    conn.close()
    return result

@app.post("/api/bonds/{bond_id}/unlock")
async def unlock_bond(bond_id: int, user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM user_bond_unlocks WHERE user_id = %s AND bond_id = %s", (user_id, bond_id))
    if cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Already unlocked")
    cur.execute("SELECT price FROM bonds WHERE id = %s", (bond_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Bond not found")
    price = row[0]
    cur.execute("SELECT coins FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    coins = row[0]
    if coins < price:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Insufficient coins")
    cur.execute("UPDATE users SET coins = coins - %s WHERE id = %s", (price, user_id))
    cur.execute("INSERT INTO user_bond_unlocks (user_id, bond_id) VALUES (%s, %s)", (user_id, bond_id))
    conn.commit()
    cur.close()
    conn.close()
    return {"success": True, "message": f"Bond unlocked! Spent {price} coins."}

@app.get("/api/bonds/{bond_id}/matches")
async def get_bond_matches(bond_id: int, user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM user_bond_unlocks WHERE user_id = %s AND bond_id = %s", (user_id, bond_id))
    if not cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(status_code=403, detail="Bond not unlocked")
    cur.execute("SELECT match_ids, predictions FROM bonds WHERE id = %s", (bond_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Bond not found")
    match_ids, predictions = row
    # predictions is already a dict from JSONB column
    match_ids_text = [str(mid) for mid in match_ids]
    cur.execute("""
        SELECT m.match_id, ht.name as home_team, at.name as away_team,
               m.match_date, m.status, m.score_home, m.score_away
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        WHERE m.match_id::text = ANY(%s)
    """, (match_ids_text,))
    matches = cur.fetchall()
    result = []
    for m in matches:
        match_id, home, away, match_date, status, score_home, score_away = m
        pred = predictions.get(str(match_id), {})
        result.append({
            "match_id": match_id,
            "home_team": home,
            "away_team": away,
            "match_date": match_date.isoformat() if match_date else None,
            "status": status,
            "score": {"home": score_home, "away": score_away} if status == 'FT' else None,
            "prediction": pred,
            "analysis": " | ".join([f"{k}: {v}" for k, v in pred.items()]) or "Analysis coming soon."
        })
    cur.close()
    conn.close()
    return result

# ----- REBUILD PYDANTIC MODELS -----
for route in app.routes:
    if hasattr(route, 'response_model') and route.response_model:
        try:
            route.response_model.model_rebuild()
        except AttributeError:
            pass

# ---------- FEED ENDPOINT ----------
@app.get("/api/feed")
async def get_feed(user_id: int = None):
    conn = get_db_connection()
    cur = conn.cursor()
    feed_items = []

    # 1. System announcements (hardcoded)
    announcements = [
        {"title": "New Bond: Champions League", "body": "Unlock premium analysis for 6 UCL matches with just 50 coins!", "link": "/bonds/1"},
        {"title": "Model Update", "body": "Our prediction engine now covers 15 leagues. Accuracy improved by 4%.", "link": "/blog/model-update"},
    ]
    for i, ann in enumerate(announcements):
        feed_items.append({
            "id": f"ann_{i}",
            "type": "announcement",
            "title": ann["title"],
            "body": ann["body"],
            "posted_at": datetime.now().isoformat(),
            "author": {"name": "STREAM System", "handle": "@stream_sys", "avatar_bg": "linear-gradient(135deg, #6B7280, #374151)"},
            "link": {"url": ann.get("link", ""), "text": "Learn More"},
            "engagement": {"likes": 0, "comments": 0, "shares": 0, "reactions": ["📢"]}
        })

    # 2. Model highlights (value bets)
    cur.execute("""
        SELECT 
            p.match_id, m.home_team_id, m.away_team_id, m.match_date,
            p.home_win_prob, o.home_win_odds
        FROM predictions p
        JOIN matches m ON p.match_id = m.match_id
        LEFT JOIN odds o ON o.event_id = m.match_id
        WHERE o.home_win_odds IS NOT NULL
        ORDER BY (p.home_win_prob - (1/o.home_win_odds)) DESC
        LIMIT 5
    """)
    rows = cur.fetchall()
    for row in rows:
        match_id, home_id, away_id, match_date, home_prob, home_odds = row
        # Get team names
        cur.execute("SELECT name FROM teams WHERE team_id = %s", (home_id,))
        home = cur.fetchone()[0]
        cur.execute("SELECT name FROM teams WHERE team_id = %s", (away_id,))
        away = cur.fetchone()[0]
        implied = 1/home_odds if home_odds else 0
        value = home_prob - implied
        body = f"🔍 Our model gives **{home}** a **{home_prob*100:.1f}%** chance to win, while the market implies **{implied*100:.1f}%**. That's a **{value*100:.1f}%** edge!"
        feed_items.append({
            "id": f"highlight_{match_id}",
            "type": "model_highlight",
            "title": f"Value Bet: {home} vs {away}",
            "body": body,
            "posted_at": match_date.isoformat() if match_date else datetime.now().isoformat(),
            "author": {"name": "STREAM AI", "handle": "@stream_ai", "avatar_bg": "linear-gradient(135deg, var(--terracotta), var(--sky))"},
            "link": {"url": f"/match/{match_id}", "text": "View Details"},
            "engagement": {"likes": 0, "comments": 0, "shares": 0, "reactions": ["🦅"]}
        })

    # 3. Free analysis (low odds 1.02–1.10)
    cur.execute("""
        SELECT 
            p.match_id, m.home_team_id, m.away_team_id, m.match_date,
            p.home_win_prob, o.home_win_odds
        FROM predictions p
        JOIN matches m ON p.match_id = m.match_id
        JOIN odds o ON o.event_id = m.match_id
        WHERE o.home_win_odds BETWEEN 1.02 AND 1.10
        ORDER BY m.match_date
        LIMIT 3
    """)
    rows = cur.fetchall()
    for row in rows:
        match_id, home_id, away_id, match_date, home_prob, odds = row
        cur.execute("SELECT name FROM teams WHERE team_id = %s", (home_id,))
        home = cur.fetchone()[0]
        cur.execute("SELECT name FROM teams WHERE team_id = %s", (away_id,))
        away = cur.fetchone()[0]
        body = f"⚡ Free analysis for {home} vs {away}: Odds {odds:.2f}, model gives {home_prob*100:.1f}% win probability. The low odds suggest high confidence, but beware of upsets."
        feed_items.append({
            "id": f"free_{match_id}",
            "type": "free_analysis",
            "title": f"Free Analysis: {home} vs {away}",
            "body": body,
            "posted_at": match_date.isoformat() if match_date else datetime.now().isoformat(),
            "author": {"name": "STREAM AI", "handle": "@stream_ai", "avatar_bg": "linear-gradient(135deg, #F59E0B, #D97706)"},
            "link": {"url": f"/match/{match_id}", "text": "Full Analysis"},
            "engagement": {"likes": 0, "comments": 0, "shares": 0, "reactions": ["📊"]}
        })

    # 4. Bond results (for unlocked bonds with FT matches)
    if user_id:
        cur.execute("""
            SELECT b.id, b.title, b.match_ids, b.predictions, b.bond_type
            FROM bonds b
            JOIN user_bond_unlocks u ON u.bond_id = b.id
            WHERE u.user_id = %s
        """, (user_id,))
        bonds = cur.fetchall()
        for bond in bonds:
            bond_id, title, match_ids, predictions_json, bond_type = bond
            predictions = predictions_json  # already a dict
            # Get matches results
            cur.execute("""
                SELECT match_id, home_team_id, away_team_id, score_home, score_away, status
                FROM matches
                WHERE match_id = ANY(%s)
            """, (match_ids,))
            matches = cur.fetchall()
            correct = 0
            total = 0
            for m in matches:
                match_id, home_id, away_id, score_home, score_away, status = m
                if status != 'FT':
                    continue
                total += 1
                predicted = predictions.get(str(match_id), {})
                if score_home > score_away:
                    actual = 'home'
                elif score_home < score_away:
                    actual = 'away'
                else:
                    actual = 'draw'
                if predicted.get('result') == actual:
                    correct += 1
            if total > 0:
                feed_items.append({
                    "id": f"bond_{bond_id}",
                    "type": "bond_result",
                    "title": f"{title} – {bond_type.replace('_',' ').title()}",
                    "body": f"🏆 You predicted {correct} out of {total} correctly!",
                    "posted_at": datetime.now().isoformat(),
                    "author": {"name": "STREAM System", "handle": "@stream_sys", "avatar_bg": "linear-gradient(135deg, #10B981, #059669)"},
                    "link": {"url": f"/bonds/{bond_id}", "text": "View Bond"},
                    "engagement": {"likes": 0, "comments": 0, "shares": 0, "reactions": ["🎯"]}
                })

    cur.close()
    conn.close()

    # Sort by posted_at (most recent first)
    feed_items.sort(key=lambda x: x["posted_at"], reverse=True)
    return feed_items
