from datetime import datetime, timedelta
from typing import List, Optional

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from .config import settings
from .models import ApiResponse, Exchange, QuoteSnapshot


class QuoteTracker:
    def __init__(self):
        self.client = MongoClient(settings.MONGO_URI)
        self.db: Database = self.client[settings.DB_NAME]
        self.collection: Collection = self.db.snapshots

        self.createIndexes()

    def saveData(self):
        result = self.collection.insert_one({"one": "row"})
        return str(result.inserted_id)

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


tracker = QuoteTracker()
