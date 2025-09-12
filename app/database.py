import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from .config import settings
from .models import ApiResponse, Exchange, HistoryElement, QuoteSnapshot


class QuoteTracker:
    def __init__(self):
        self.client = MongoClient(settings.MONGO_URI)
        self.db: Database = self.client[settings.DB_NAME]
        self.collection: Collection = self.db.snapshots

        self.createIndexes()

    def createIndexes(self):
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
        doc = self.collection.find_one(sort=[("timestamp", DESCENDING)])
        if doc:
            doc.pop("_id", None)
            return QuoteSnapshot(**doc)
        return None

    async def get_snapshots_since(
        self, since: datetime, limit: int = 100
    ) -> List[QuoteSnapshot]:
        """Get validated snapshots since a given time"""
        docs = list(
            self.collection.find(
                {"timestamp": {"$gte": since}},
                sort=[("timestamp", DESCENDING)],
                limit=limit,
            )
        )

        return [
            QuoteSnapshot(**{k: v for k, v in doc.items() if k != "_id"})
            for doc in docs
        ]

    async def get_app_history(self, app_name: str, hours: int) -> List[HistoryElement]:
        """Get rate history for a specific app"""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        snapshots = await self.get_snapshots_since(since)

        history = []
        for snapshot in snapshots:
            if app_name in snapshot.quotes:
                history.append(
                    {"timestamp": snapshot.timestamp, "rate": snapshot.quotes[app_name]}
                )

        return history

    def get_mongo_ping_time(self) -> float:
        start = time.perf_counter()
        self.db.command("ping")
        end = time.perf_counter()
        return round((end - start) * 1000, 2)  # milliseconds


tracker = QuoteTracker()
