import sys
import os
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.services.data_ingestion_service import ingestion_service
import logging

logging.basicConfig(level=logging.INFO)

def start_ingestion_scheduler():
    scheduler = BackgroundScheduler()
    
    scheduler.add_job(
        ingestion_service.run_daily_ingestion,
        trigger=IntervalTrigger(hours=24),
        id='daily_ingestion',
        replace_existing=True
    )
    
    scheduler.start()
    print("⏰ Ingestion Scheduler started - runs every 24 hours")
    return scheduler

if __name__ == "__main__":
    print("🚀 Starting Ingestion Worker...")
    scheduler = start_ingestion_scheduler()
    
    # Run once immediately for testing
    ingestion_service.run_daily_ingestion()
    
    try:
        input("\nPress Enter to stop the scheduler...\n")
    except KeyboardInterrupt:
        print("\nShutting down scheduler...")
    finally:
        scheduler.shutdown()