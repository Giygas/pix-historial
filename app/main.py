from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR, HTTP_404_NOT_FOUND

from app.config import settings
from app.database import tracker
from app.exceptions import (
    QuoteServiceError,
    QuoteAPIConnectionError,
    QuoteAPITimeoutError,
    QuoteDatabaseError,
    QuoteDataValidationError,
    QuoteDataParsingError,
)
from app.logger import logger
from app.models import (
    AppHistoryResponse,
    AppRate,
    ErrorResponse,
    NotFoundErrorResponse,
    HealthCheckResponse,
    SnapshotResponse,
)
from app.services import collect_quotes_background

# from app.services import QuoteService, collect_quotes_background

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
    docs_url="/docs",
    redoc_url="/redoc",
)


# Exception Handlers for Structured Error Responses
@app.exception_handler(QuoteServiceError)
async def quote_service_exception_handler(
    request: Request, exc: QuoteServiceError
) -> JSONResponse:
    """Handle all custom quote service exceptions."""
    logger.error(f"QuoteServiceError in {request.url.path}: {exc.message}")

    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error=exc.__class__.__name__,
            message=exc.message,
            details=exc.details,
            path=str(request.url.path),
            request_id=request.headers.get("X-Request-ID"),
        ).model_dump(),
    )


@app.exception_handler(QuoteAPIConnectionError)
async def api_connection_error_handler(
    request: Request, exc: QuoteAPIConnectionError
) -> JSONResponse:
    """Handle API connection errors with specific status code."""
    logger.error(f"API connection error in {request.url.path}: {exc.message}")

    return JSONResponse(
        status_code=503,  # Service Unavailable
        content=ErrorResponse(
            error=exc.__class__.__name__,
            message="External API service is currently unavailable",
            details=exc.details,
            path=str(request.url.path),
            request_id=request.headers.get("X-Request-ID"),
        ).model_dump(),
    )


@app.exception_handler(QuoteAPITimeoutError)
async def api_timeout_error_handler(
    request: Request, exc: QuoteAPITimeoutError
) -> JSONResponse:
    """Handle API timeout errors with specific status code."""
    logger.warning(f"API timeout in {request.url.path}: {exc.message}")

    return JSONResponse(
        status_code=408,  # Request Timeout
        content=ErrorResponse(
            error=exc.__class__.__name__,
            message="External API request timed out",
            details=exc.details,
            path=str(request.url.path),
            request_id=request.headers.get("X-Request-ID"),
        ).model_dump(),
    )


@app.exception_handler(QuoteDatabaseError)
async def database_error_handler(
    request: Request, exc: QuoteDatabaseError
) -> JSONResponse:
    """Handle database errors with specific status code."""
    logger.error(f"Database error in {request.url.path}: {exc.message}")

    return JSONResponse(
        status_code=503,  # Service Unavailable
        content=ErrorResponse(
            error=exc.__class__.__name__,
            message="Database service is currently unavailable",
            details=exc.details,
            path=str(request.url.path),
            request_id=request.headers.get("X-Request-ID"),
        ).model_dump(),
    )


@app.exception_handler(QuoteDataValidationError)
async def validation_error_handler(
    request: Request, exc: QuoteDataValidationError
) -> JSONResponse:
    """Handle data validation errors."""
    logger.warning(f"Validation error in {request.url.path}: {exc.message}")

    return JSONResponse(
        status_code=422,  # Unprocessable Entity
        content=ErrorResponse(
            error=exc.__class__.__name__,
            message="Data validation failed",
            details=exc.details,
            path=str(request.url.path),
            request_id=request.headers.get("X-Request-ID"),
        ).model_dump(),
    )


@app.exception_handler(QuoteDataParsingError)
async def parsing_error_handler(
    request: Request, exc: QuoteDataParsingError
) -> JSONResponse:
    """Handle data parsing errors."""
    logger.error(f"Data parsing error in {request.url.path}: {exc.message}")

    return JSONResponse(
        status_code=502,  # Bad Gateway
        content=ErrorResponse(
            error=exc.__class__.__name__,
            message="Failed to parse external API response",
            details=exc.details,
            path=str(request.url.path),
            request_id=request.headers.get("X-Request-ID"),
        ).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTPExceptions with structured format."""
    logger.warning(f"HTTPException in {request.url.path}: {exc.detail}")

    if exc.status_code == HTTP_404_NOT_FOUND:
        return JSONResponse(
            status_code=exc.status_code,
            content=NotFoundErrorResponse(
                error="NotFound",
                message=str(exc.detail),
                path=str(request.url.path),
                request_id=request.headers.get("X-Request-ID"),
            ).model_dump(),
        )

    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error="HTTPException",
            message=str(exc.detail),
            path=str(request.url.path),
            request_id=request.headers.get("X-Request-ID"),
        ).model_dump(),
    )


@app.get("/")
async def root():
    """Root endpoint - serve HTML documentation"""
    return FileResponse("html/index.html", media_type="text/html")


@app.get("/latest", response_model=SnapshotResponse)
async def get_latest():
    """Get the most recent quote snapshot"""
    latest = await tracker.get_latest_snapshot()

    if not latest:
        raise HTTPException(status_code=404, detail="No snapshots found")

    return SnapshotResponse(
        id="latest",
        timestamp=latest.timestamp,
        quotes=[AppRate(app_name=k, rate=v) for k, v in latest.quotes.items()],
        total_apps=len(latest.quotes),
    )


@app.get("/apps/{app_name}", response_model=AppHistoryResponse)
async def app_history(
    app_name: str,
    hours: int = Query(default=24, ge=1, le=168),  # 1 hour to 1 week
):
    """Get rate history for a specific app"""
    history = await tracker.get_app_history(app_name, hours)

    if not history:
        raise HTTPException(
            status_code=404, detail=f"No history found for app '{app_name}'"
        )

    return AppHistoryResponse(
        app_name=app_name, history=history, total_records=len(history)
    )


# @app.get("/snapshot", include_in_schema=False)
# async def save_snapshot():
#     """Manually trigger quote collection"""
#     try:
#         doc_id = await QuoteService.fetch_and_save_quotes()
#
#         return f"Snapshot saved with the id: {doc_id}"
#
#     except Exception as e:
#         logger.error(f"Manual collection failed: {e}")
#         raise HTTPException(status_code=500, detail=f"Collection failed: {str(e)}")


@app.get("/favicon.ico", include_in_schema=False)
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

    except QuoteServiceError as e:
        logger.error(f"Health check failed: {e}")
        db_status = f"service_error: {str(e)}"
        last_update = None
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        db_status = f"error: {str(e)}"
        last_update = None

    now = datetime.now(timezone.utc)
    uptime_seconds = (now - app_start_time).total_seconds()
    uptime = timedelta(seconds=uptime_seconds)

    try:
        mongo_ping = tracker.get_mongo_ping_time()
    except Exception:
        mongo_ping = None

    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "database": db_status,
        "last_update": last_update,
        "timestamp": datetime.now(),
        "uptime": str(uptime),
        "mongo_ping": f"{mongo_ping} ms" if mongo_ping else "unknown",
    }
