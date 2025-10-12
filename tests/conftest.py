import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pymongo import MongoClient

from app.database import QuoteTracker
from app.models import QuoteSnapshot


@pytest.fixture
def mock_mongo_client():
    """Mock MongoDB client for testing"""
    with patch("pymongo.MongoClient") as mock_client:
        yield mock_client


@pytest.fixture
def sample_api_response():
    """Sample API response data for testing"""
    return {
        "app1": {
            "quotes": [
                {
                    "symbol": "BRLARS",
                    "buy": 1850.5,
                    "sell": 1860.0,
                    "spread": 9.5,
                    "spread_pct": 0.51,
                }
            ],
            "logo": "https://example.com/logo1.png",
            "url": "https://app1.com",
            "isPix": True,
            "hasFees": False,
        },
        "app2": {
            "quotes": [
                {
                    "symbol": "BRLARS",
                    "buy": 1852.0,
                    "sell": 1862.5,
                    "spread": 10.5,
                    "spread_pct": 0.57,
                }
            ],
            "logo": "https://example.com/logo2.png",
            "url": "https://app2.com",
            "isPix": False,
            "hasFees": True,
        },
    }


@pytest.fixture
def sample_quote_snapshot():
    """Sample QuoteSnapshot for testing"""
    return QuoteSnapshot(
        timestamp=datetime.now(timezone.utc),
        quotes={"app1": 1850.5, "app2": 1852.0, "app3": 1848.75},
    )


@pytest.fixture
def mock_tracker():
    """Mock QuoteTracker for testing"""
    with patch("app.database.tracker") as mock:
        mock.get_latest_snapshot = AsyncMock()
        mock.get_app_history = AsyncMock()
        mock.save_snapshot = AsyncMock()
        mock.get_mongo_ping_time = Mock(return_value=5.5)
        yield mock


@pytest.fixture
def tracker_instance():
    """QuoteTracker instance for testing"""
    with patch("app.database.settings") as mock_settings:
        mock_settings.MONGO_URI = "mongodb://localhost:27017"
        mock_settings.DB_NAME = "test_db"
        with patch("pymongo.MongoClient"):
            with patch.object(QuoteTracker, "createIndexes"):
                tracker = QuoteTracker()
                yield tracker


@pytest.fixture
def mock_requests():
    """Mock requests module for testing"""
    with patch("app.services.requests") as mock:
        mock.get.return_value.json.return_value = {
            "app1": {
                "quotes": [{"symbol": "BRLARS", "buy": 1850.5}],
                "logo": "https://example.com/logo1.png",
                "url": "https://app1.com",
                "isPix": True,
            }
        }
        mock.get.return_value.raise_for_status = Mock()
        yield mock


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_database():
    """Test database fixture for integration tests"""
    # Use a test database
    test_db_name = "test_pix_historial"
    test_client = MongoClient("mongodb://localhost:27017")
    test_db = test_client[test_db_name]

    # Clean up before tests
    test_db.snapshots.delete_many({})

    yield test_db

    # Clean up after tests
    test_client.drop_database(test_db_name)
    test_client.close()


@pytest.fixture
def sample_history_data():
    """Sample history data for testing"""
    now = datetime.now(timezone.utc)
    return [
        {"timestamp": now - timedelta(hours=3), "rate": 1850.5},
        {"timestamp": now - timedelta(hours=2), "rate": 1852.0},
        {"timestamp": now - timedelta(hours=1), "rate": 1848.75},
        {"timestamp": now, "rate": 1851.25},
    ]
