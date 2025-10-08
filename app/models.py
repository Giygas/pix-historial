from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, RootModel, ConfigDict


# API Response Models
class Quote(BaseModel):
    symbol: str
    buy: float
    sell: Optional[float] = None
    spread: Optional[float] = None
    spread_pct: Optional[float] = None


class Exchange(BaseModel):
    quotes: List[Quote]
    logo: str
    url: str
    isPix: bool
    hasFees: Optional[bool] = None


class ApiResponse(RootModel[Dict[str, Exchange]]):
    root: Dict[str, Exchange]

    def items(self):
        return self.root.items()


# Database Models
class QuoteSnapshot(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    quotes: Dict[str, float] = Field(..., description="App name to quote mapping")


class AppRate(BaseModel):
    app_name: str
    rate: float


# API Response Models
class SnapshotResponse(BaseModel):
    id: str
    timestamp: datetime
    quotes: List[AppRate]
    total_apps: int


class HistoryElement(BaseModel):
    timestamp: datetime
    rate: float


class AppHistoryResponse(BaseModel):
    app_name: str
    history: List[HistoryElement]
    total_records: int


class HealthCheckResponse(BaseModel):
    status: Literal["healthy", "unhealthy"]
    database: str
    last_update: Optional[datetime]
    timestamp: datetime
    uptime: str
    mongo_ping: str


# Error Response Models
class ErrorDetail(BaseModel):
    """Detailed error information for debugging."""

    field: Optional[str] = None
    value: Optional[Any] = None
    constraint: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standardized error response format for API endpoints."""

    error: str = Field(..., description="Error type/class name")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional error context"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: Optional[str] = Field(
        default=None, description="Request correlation ID"
    )
    path: Optional[str] = Field(default=None, description="API endpoint path")

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Override model_dump to handle datetime serialization."""
        data = super().model_dump(**kwargs)
        if "timestamp" in data and isinstance(data["timestamp"], datetime):
            data["timestamp"] = data["timestamp"].isoformat()
        return data


class ValidationErrorResponse(ErrorResponse):
    """Specialized error response for validation errors."""

    validation_errors: List[ErrorDetail] = Field(
        default_factory=list, description="Field-level validation errors"
    )


class NotFoundErrorResponse(ErrorResponse):
    """Specialized error response for 404 not found errors."""

    resource: Optional[str] = Field(
        default=None, description="Type of resource that was not found"
    )
    resource_id: Optional[str] = Field(
        default=None, description="ID of the resource that was not found"
    )
