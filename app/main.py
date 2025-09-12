import logging
from contextlib import asynccontextmanager

import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, HTTPException

from app.config import settings
from app.database import tracker
from app.logger import logger
from app.services import QuoteService, collect_quotes_background

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan_with_scheduler(app: FastAPI):
    """Scheduler setup"""
    try:
        # Configure scheduler with better defaults
        scheduler.configure(
            jobstores={"default": {"type": "memory"}},
            executors={"default": {"type": "asyncio"}},
            job_defaults={
                "coalesce": True,  # Combine missed jobs
                "max_instances": 1,  # Only one instance at a time
                "misfire_grace_time": 60,  # Grace period for missed jobs
            },
        )

        # Add the job
        scheduler.add_job(
            collect_quotes_background,
            trigger=IntervalTrigger(seconds=settings.COLLECTION_INTERVAL),
            id="quote_collection",
            name="Periodic Quote Collection",
            replace_existing=True,
        )

        scheduler.start()
        logger.info(
            f"Started scheduler - next run in {settings.COLLECTION_INTERVAL} seconds"
        )

        print(f"Started scheduler - next run in {settings.COLLECTION_INTERVAL} seconds")
        yield

    except Exception as e:
        logger.error(f"Error with scheduler: {e}")
        raise
    finally:
        # Ensure scheduler shuts down cleanly
        if scheduler.running:
            scheduler.shutdown(wait=True)
        logger.info("Scheduler shutdown complete")


app = FastAPI(
    title=settings.API_TITLE,
    description="Track and analyze BRLARS exchange rates across multiple apps",
    version=settings.API_VERSION,
    lifespan=lifespan_with_scheduler,
)


@app.get("/")
async def root():
    res = await tracker.get_latest_snapshot()
    return res


@app.get("/apps/{app_name}")
async def app_history(app_name):
    res = await tracker.get_app_history(app_name, 24)
    return res


@app.get("/snapshot")
async def save_snapshot():
    """Manually trigger quote collection"""
    try:
        doc_id = await QuoteService.fetch_and_save_quotes()

        return f"Snapshot saved with the id: {doc_id}"

    except Exception as e:
        logger.error(f"Manual collection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Collection failed: {str(e)}")
