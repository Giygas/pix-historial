from typing import Dict, List, Optional
from pydantic import BaseModel, Field, RootModel
from datetime import datetime, timezone


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


class ApiResponse(BaseModel):
    RootModel: Dict[str, Exchange]

    def items(self):
        return self.items()


# Database Models
class QuoteSnapshot(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    quotes: Dict[str, float] = Field(..., description="App name to quote mapping")

    class Config:
        arbitrary_types_allowed = True
