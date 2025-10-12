from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR

from app.config import settings
from app.correlation import CorrelationIDMiddleware, get_correlation_id
from app.database import tracker
from app.exceptions import (
    QuoteAPIConnectionError,
    QuoteAPITimeoutError,
    QuoteDatabaseError,
    QuoteDataParsingError,
    QuoteDataValidationError,
    QuoteServiceError,
)
from app.logger import logger
from app.models import (
    AppHistoryResponse,
    AppRate,
    ErrorDetail,
    ErrorResponse,
    HealthCheckResponse,
    NotFoundErrorResponse,
    SnapshotResponse,
    ValidationErrorResponse,
)
from app.rate_limiter import rate_limit_middleware
from app.services import collect_quotes_background

# from app.services import QuoteService, collect_quotes_background

scheduler = AsyncIOScheduler()


# Start time
app_start_time = datetime.now(timezone.utc)


@asynccontextmanager
async def lifespan_with_scheduler(app: FastAPI) -> AsyncGenerator[None, None]:
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

        # Add the job with cron-based scheduling
        scheduler.add_job(
            collect_quotes_background,
            trigger=CronTrigger(minute=settings.COLLECTION_CRON),
            id="quote_collection",
            name="Periodic Quote Collection",
            replace_existing=True,
        )

        scheduler.start()
        logger.info(f"Started scheduler - runs in {settings.COLLECTION_CRON}")

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

# Add correlation ID middleware (should be first to capture all requests)
app.add_middleware(CorrelationIDMiddleware)

# Note: rate_limit_middleware is a function, not a class middleware
# It will be added as a route-specific middleware or converted to class later

# Add rate limiting middleware
app.add_middleware(BaseHTTPMiddleware, dispatch=rate_limit_middleware)


# Exception Handlers for Structured Error Responses
@app.exception_handler(QuoteServiceError)
async def quote_service_exception_handler(
    request: Request, exc: QuoteServiceError
) -> JSONResponse:
    """Handle all custom quote service exceptions."""
    correlation_id = get_correlation_id(request)
    logger.error(
        f"[{correlation_id}] QuoteServiceError in {request.url.path}: {exc.message}"
    )

    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error=exc.__class__.__name__,
            message=exc.message,
            details=exc.details,
            path=str(request.url.path),
            request_id=correlation_id,
        ).model_dump(),
    )


@app.exception_handler(QuoteAPIConnectionError)
async def api_connection_error_handler(
    request: Request, exc: QuoteAPIConnectionError
) -> JSONResponse:
    """Handle API connection errors with specific status code."""
    correlation_id = get_correlation_id(request)
    logger.error(
        f"[{correlation_id}] API connection error in {request.url.path}: {exc.message}"
    )

    return JSONResponse(
        status_code=503,  # Service Unavailable
        content=ErrorResponse(
            error=exc.__class__.__name__,
            message="External API service is currently unavailable",
            details=exc.details,
            path=str(request.url.path),
            request_id=correlation_id,
        ).model_dump(),
    )


@app.exception_handler(QuoteAPITimeoutError)
async def api_timeout_error_handler(
    request: Request, exc: QuoteAPITimeoutError
) -> JSONResponse:
    """Handle API timeout errors with specific status code."""
    correlation_id = get_correlation_id(request)
    logger.warning(
        f"[{correlation_id}] API timeout in {request.url.path}: {exc.message}"
    )

    return JSONResponse(
        status_code=408,  # Request Timeout
        content=ErrorResponse(
            error=exc.__class__.__name__,
            message="External API request timed out",
            details=exc.details,
            path=str(request.url.path),
            request_id=correlation_id,
        ).model_dump(),
    )


@app.exception_handler(QuoteDatabaseError)
async def database_error_handler(
    request: Request, exc: QuoteDatabaseError
) -> JSONResponse:
    """Handle database errors with specific status code."""
    correlation_id = get_correlation_id(request)
    logger.error(
        f"[{correlation_id}] Database error in {request.url.path}: {exc.message}"
    )

    return JSONResponse(
        status_code=503,  # Service Unavailable
        content=ErrorResponse(
            error=exc.__class__.__name__,
            message="Database service is currently unavailable",
            details=exc.details,
            path=str(request.url.path),
            request_id=correlation_id,
        ).model_dump(),
    )


@app.exception_handler(QuoteDataValidationError)
async def validation_error_handler(
    request: Request, exc: QuoteDataValidationError
) -> JSONResponse:
    """Handle data validation errors."""
    correlation_id = get_correlation_id(request)
    logger.warning(
        f"[{correlation_id}] Validation error in {request.url.path}: {exc.message}"
    )

    return JSONResponse(
        status_code=422,  # Unprocessable Entity
        content=ErrorResponse(
            error=exc.__class__.__name__,
            message="Data validation failed",
            details=exc.details,
            path=str(request.url.path),
            request_id=correlation_id,
        ).model_dump(),
    )


@app.exception_handler(QuoteDataParsingError)
async def parsing_error_handler(
    request: Request, exc: QuoteDataParsingError
) -> JSONResponse:
    """Handle data parsing errors."""
    correlation_id = get_correlation_id(request)
    logger.error(
        f"[{correlation_id}] Data parsing error in {request.url.path}: {exc.message}"
    )

    return JSONResponse(
        status_code=502,  # Bad Gateway
        content=ErrorResponse(
            error=exc.__class__.__name__,
            message="Failed to parse external API response",
            details=exc.details,
            path=str(request.url.path),
            request_id=correlation_id,
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle FastAPI/Pydantic validation errors with structured format."""
    correlation_id = get_correlation_id(request)
    logger.warning(
        f"[{correlation_id}] Validation error in {request.url.path}: {exc.errors()}"
    )

    # Convert FastAPI validation errors to our format
    validation_errors = []
    for error in exc.errors():
        validation_errors.append(
            ErrorDetail(
                field=".".join(str(loc) for loc in error["loc"]),
                value=error.get("input"),
                constraint=f"{error['type']}: {error['msg']}",
            )
        )

    return JSONResponse(
        status_code=422,  # Unprocessable Entity
        content=ValidationErrorResponse(
            error="RequestValidationError",
            message="Input validation failed",
            validation_errors=validation_errors,
            path=str(request.url.path),
            request_id=correlation_id,
        ).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTPExceptions with structured format."""
    correlation_id = get_correlation_id(request)
    logger.warning(
        f"[{correlation_id}] HTTPException in {request.url.path}: {exc.detail}"
    )

    if exc.status_code == HTTP_404_NOT_FOUND:
        return JSONResponse(
            status_code=exc.status_code,
            content=NotFoundErrorResponse(
                error="NotFound",
                message=str(exc.detail),
                path=str(request.url.path),
                request_id=correlation_id,
            ).model_dump(),
        )

    # Handle rate limit exceptions
    if exc.status_code == 429:
        # For rate limit errors, detail is typically a string message
        message = str(exc.detail)
        detail_dict: Dict[str, Any] = {"message": message}

        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error="RateLimitExceeded",
                message=detail_dict.get("message", "Too many requests"),
                details=detail_dict,
                path=str(request.url.path),
                request_id=correlation_id,
            ).model_dump(),
        )

    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error="HTTPException",
            message=str(exc.detail),
            path=str(request.url.path),
            request_id=correlation_id,
        ).model_dump(),
    )


@app.get("/")
async def root() -> FileResponse:
    """Root endpoint - serve HTML documentation"""
    return FileResponse("html/index.html", media_type="text/html")


@app.get("/latest", response_model=SnapshotResponse)
async def get_latest() -> SnapshotResponse:
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
    hours: int = Query(default=24, ge=1, le=720),  # 1 hour to 1 month
) -> AppHistoryResponse:
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
async def favicon() -> FileResponse:
    """Serve the favicon"""
    return FileResponse("favicon.ico", media_type="image/x-icon")


@app.get("/health", response_model=HealthCheckResponse)
async def health_check() -> dict[str, object]:
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
