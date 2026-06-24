from app.db.session import SessionLocal
from app.models import league, team, match, odds as odds_model
from app.schemas.odds import OddsCreate
from app.db.repositories import odds_repository
from app.ml.providers.odds_fetcher import fetch_odds_for_fixture
from fastapi import HTTPException


def get_sample_fixtures(db, per_league=20):
    """
    Pull up to `per_league` finished matches per league, spread across
    the season (not just the first N chronologically), so the sample
    isn't biased toward early-season matches only.
    """
    leagues = db.query(league.League).all()
    sample = []

    for lg in leagues:
        matches = db.query(match.Match).filter(
            match.Match.league_id == lg.id,
            match.Match.status == "FT",
        ).order_by(match.Match.match_date.asc()).all()

        if not matches:
            continue

        step = max(1, len(matches) // per_league)
        selected = matches[::step][:per_league]
        sample.extend(selected)
        print(f"{lg.name}: selected {len(selected)} of {len(matches)} matches")

    return sample


def ingest_odds_sample():
    db = SessionLocal()
    saved = 0
    skipped_existing = 0
    skipped_no_data = 0

    try:
        fixtures = get_sample_fixtures(db, per_league=20)
        print(f"\nTotal sample size: {len(fixtures)} fixtures")
        print("Fetching odds (this will take a while due to rate limiting)...\n")

        for i, m in enumerate(fixtures, 1):
            existing = db.query(odds_model.Odds).filter(
                odds_model.Odds.match_id == m.id
            ).first()
            if existing:
                skipped_existing += 1
                print(f"[{i}/{len(fixtures)}] SKIP (already have odds): match {m.id}")
                continue

            print(f"[{i}/{len(fixtures)}] Fetching odds for fixture api_id={m.api_id}...")
            odds_data = fetch_odds_for_fixture(m.api_id)

            if not odds_data:
                skipped_no_data += 1
                print(f"  -> No odds data available")
                continue

            try:
                odds_repository.create_odds(db, OddsCreate(
                    match_id=m.id,
                    bookmaker=odds_data["bookmaker"],
                    home_win=odds_data["home_win"],
                    draw=odds_data["draw"],
                    away_win=odds_data["away_win"],
                ))
                saved += 1
                print(f"  -> Saved: H={odds_data['home_win']} D={odds_data['draw']} A={odds_data['away_win']}")
            except HTTPException as e:
                print(f"  -> Skipped: {e.detail}")

        print(f"\n=== Done ===")
        print(f"Saved: {saved}, Already existed: {skipped_existing}, No data available: {skipped_no_data}")
    finally:
        db.close()


if __name__ == "__main__":
    ingest_odds_sample()
