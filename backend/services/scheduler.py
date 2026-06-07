import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import AsyncSessionLocal
from config import SALE_LOCK_MINUTES
from models.motorcycle import Motorcycle, MotorcycleStatus

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def cleanup_expired_locks():
    """
    Runs every 60 seconds.
    Finds all motorcycles with status reserved_for_sale whose locked_at
    has exceeded SALE_LOCK_MINUTES and reverts them to their previous status.
    """
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=SALE_LOCK_MINUTES)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Motorcycle).where(
                    Motorcycle.status    == MotorcycleStatus.reserved_for_sale,
                    Motorcycle.locked_at <= cutoff,
                )
            )
            expired = result.scalars().all()
            if expired:
                for moto in expired:
                    moto.status          = MotorcycleStatus(moto.previous_status or "in_stock")
                    moto.previous_status = None
                    moto.locked_at       = None
                    moto.locked_by       = None
                await db.commit()
                logger.info(f"[SCHEDULER] Released {len(expired)} expired lock(s)")
    except Exception as e:
        logger.error(f"[SCHEDULER] cleanup_expired_locks failed: {e}")


def start_scheduler():
    scheduler.add_job(
        cleanup_expired_locks,
        trigger="interval",
        seconds=60,
        id="cleanup_expired_locks",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("[SCHEDULER] Started — cleanup_expired_locks every 60s")


def stop_scheduler():
    scheduler.shutdown(wait=False)
    logger.info("[SCHEDULER] Stopped")
