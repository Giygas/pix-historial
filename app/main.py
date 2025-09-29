from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.config import settings
from app.database import tracker
from app.logger import logger
from app.models import AppHistoryResponse, HealthCheckResponse, SnapshotResponse
from app.services import QuoteService, collect_quotes_background

scheduler = AsyncIOScheduler()


# Start time
app_start_time = datetime.now(timezone.utc)


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
    root_path="/pix-historial",
    description="Realice un seguimiento y analice los tipos \
    de cambio de BRLARS en múltiples aplicaciones",
    version=settings.API_VERSION,
    lifespan=lifespan_with_scheduler,
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": settings.API_TITLE,
        "status": "running",
        "version": settings.API_VERSION,
    }


@app.get("/latest", response_model=SnapshotResponse)
async def get_latest():
    """Get the most recent quote snapshot"""
    latest = await tracker.get_latest_snapshot()

    if not latest:
        raise HTTPException(status_code=404, detail="No snapshots found")

    return SnapshotResponse(
        id="latest",
        timestamp=latest.timestamp,
        quotes=latest.quotes,
        total_apps=len(latest.quotes),
    )


@app.get("/apps/{app_name}", response_model=AppHistoryResponse)
async def app_history(app_name, hours: int = 24):
    """Get rate history for a specific app"""
    history = await tracker.get_app_history(app_name, hours)

    if not history:
        raise HTTPException(
            status_code=404, detail=f"No history found for app '{app_name}'"
        )

    return AppHistoryResponse(
        app_name=app_name, history=history, total_records=len(history)
    )


@app.get("/snapshot")
async def save_snapshot():
    """Manually trigger quote collection"""
    try:
        doc_id = await QuoteService.fetch_and_save_quotes()

        return f"Snapshot saved with the id: {doc_id}"

    except Exception as e:
        logger.error(f"Manual collection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Collection failed: {str(e)}")


@app.get("/favicon.ico")
async def favicon():
    """Serve the favicon"""
    return FileResponse("favicon.ico", media_type="image/x-icon")


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint"""
    try:
        latest = await tracker.get_latest_snapshot()
        db_status = "connected"
        last_update = latest.timestamp.astimezone(timezone.utc) if latest else None

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        db_status = f"error: {str(e)}"
        last_update = None

    now = datetime.now(timezone.utc)
    uptime_seconds = (now - app_start_time).total_seconds()
    uptime = timedelta(seconds=uptime_seconds)

    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "database": db_status,
        "last_update": last_update,
        "timestamp": datetime.now(),
        "uptime": str(uptime),
        "mongo_ping": str(tracker.get_mongo_ping_time()) + " ms",
    }
