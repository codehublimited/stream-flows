from app.db.session import SessionLocal
from app.models import league, team, player, venue, match, odds, prediction, season


def backfill_seasons():
    db = SessionLocal()
    try:
        leagues = db.query(league.League).all()
        for lg in leagues:
            existing = db.query(season.Season).filter(
                season.Season.league_id == lg.id, season.Season.year == 2024
            ).first()
            if existing:
                season_obj = existing
                print(f"Season 2024 already exists for {lg.name}")
            else:
                season_obj = season.Season(league_id=lg.id, year=2024, is_current=1)
                db.add(season_obj)
                db.commit()
                db.refresh(season_obj)
                print(f"Created season 2024 for {lg.name} (id={season_obj.id})")

            updated = db.query(match.Match).filter(
                match.Match.league_id == lg.id,
                match.Match.season_id.is_(None)
            ).update({"season_id": season_obj.id})
            db.commit()
            print(f"  -> Linked {updated} matches to season {season_obj.id}")
    finally:
        db.close()


if __name__ == "__main__":
    backfill_seasons()
