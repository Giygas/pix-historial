import time
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from .config import settings
from .models import ApiResponse, Exchange, HistoryElement, QuoteSnapshot


class QuoteTracker:
    def __init__(self) -> None:
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None
        self._collection: Optional[Collection] = None
        self._indexes_created = False

    @property
    def client(self) -> MongoClient:
        if self._client is None:
            self._client = MongoClient(settings.MONGO_URI)
        return self._client

    @property
    def db(self) -> Database:
        if self._db is None:
            self._db = self.client[settings.DB_NAME]
        return self._db

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            self._collection = self.db.snapshots
        return self._collection

    def _ensure_indexes(self) -> None:
        if not self._indexes_created:
            self.createIndexes()
            self._indexes_created = True

    def createIndexes(self) -> None:
        """Create indexes for faster query time"""
        # Index for time-based queries
        self.collection.create_index([("timestamp", DESCENDING)])

        # Compound index for app-specific queries
        self.collection.create_index([("timestamp", DESCENDING), ("quotes", ASCENDING)])

    def extract_brlars_rate(self, exchange: Exchange) -> Optional[float]:
        """Extract BRLARS rate from exchange quotes"""
        for quote in exchange.quotes:
            if quote.symbol == "BRLARS":
                return quote.buy
        return None

    async def save_snapshot(self, api_data: dict) -> str:
        """Parse API response and save grouped snapshot"""
        self._ensure_indexes()

        # Parse and validate API response
        api_response = ApiResponse(api_data)

        # Extract BRLARS rates
        quotes = {}
        for app_name, exchange in api_response.items():
            brlars_rate = self.extract_brlars_rate(exchange)
            if brlars_rate:
                quotes[app_name] = brlars_rate

        if not quotes:
            raise ValueError("No BRLARS quotes found in API response")

        # Create and save validated snapshot
        snapshot = QuoteSnapshot(quotes=quotes)
        result = self.collection.insert_one(snapshot.model_dump())

        return str(result.inserted_id)

    async def get_latest_snapshot(self) -> Optional[QuoteSnapshot]:
        """Get the most recent snapshot"""
        self._ensure_indexes()
        doc = self.collection.find_one(sort=[("timestamp", DESCENDING)])
        if doc:
            doc.pop("_id", None)
            return QuoteSnapshot(**doc)
        return None

    async def get_snapshots_since(self, since: datetime) -> List[QuoteSnapshot]:
        """Get validated snapshots since a given time"""
        self._ensure_indexes()
        docs = list(
            self.collection.find(
                {"timestamp": {"$gte": since}},
                sort=[("timestamp", DESCENDING)],
            )
        )

        return [
            QuoteSnapshot(**{k: v for k, v in doc.items() if k != "_id"})
            for doc in docs
        ]

    async def get_app_history(self, app_name: str, hours: int) -> List[HistoryElement]:
        """Get rate history for a specific app"""
        self._ensure_indexes()
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        snapshots = await self.get_snapshots_since(since)

        history = []
        for snapshot in snapshots:
            if app_name in snapshot.quotes:
                history.append(
                    HistoryElement(
                        timestamp=snapshot.timestamp, rate=snapshot.quotes[app_name]
                    )
                )

        return history

    def get_mongo_ping_time(self) -> float:
        start = time.perf_counter()
        self.db.command("ping")
        end = time.perf_counter()
        return round((end - start) * 1000, 2)  # milliseconds


# Global tracker instance (lazy initialization)
_tracker: Optional[QuoteTracker] = None


def get_tracker() -> QuoteTracker:
    """Get the global tracker instance (lazy initialization)"""
    global _tracker
    if _tracker is None:
        _tracker = QuoteTracker()
    return _tracker


# For backward compatibility, use a property-like access
class _TrackerProxy:
    """Proxy for lazy tracker initialization"""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_tracker(), name)


# Create proxy instance
tracker = _TrackerProxy()
