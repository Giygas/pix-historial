from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, RootModel


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
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    quotes: Dict[str, float] = Field(..., description="App name to quote mapping")

    class Config:
        arbitrary_types_allowed = True


# API Response Models
class SnapshotResponse(BaseModel):
    id: str
    timestamp: datetime
    quotes: Dict[str, float]
    total_apps: int


class AppHistoryResponse(BaseModel):
    app_name: str
    history: List[Dict[str, Any]]
    total_records: int
