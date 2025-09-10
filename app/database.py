from typing import Optional, List
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.collection import Collection
from datetime import datetime, timedelta

from .models import QuoteSnapshot, ApiResponse, Exchange
from .config import settings


class QuoteTracker:
    def __init__(self):
        self.client = MongoClient(settings.MONGO_URI)
        self.db: Database = self.client[settings.DB_NAME]
        self.collection: Collection = self.db.snapshots

    def saveData(self):
        result = self.collection.insert_one({"one": "row"})
        return str(result.inserted_id)


tracker = QuoteTracker()
