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
    match_ids, predictions = row  # predictions is already a dict (JSONB)
    # Convert match_ids to text for comparison
    match_ids_text = [str(mid) for mid in match_ids]
    # Join with teams table to get team names
    cur.execute("""
        SELECT m.match_id, 
               ht.team_name AS home_team, 
               at.team_name AS away_team, 
               m.match_date, 
               m.status, 
               m.score_home, 
               m.score_away
        FROM matches m
        LEFT JOIN teams ht ON m.home_team_id = ht.team_id
        LEFT JOIN teams at ON m.away_team_id = at.team_id
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

