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
    """Sample API response data for testing with both BRLARS and USD"""
    return {
        "app1": {
            "quotes": [
                {
                    "symbol": "BRLARS",
                    "buy": 1850.5,
                    "sell": 1860.0,
                    "spread": 9.5,
                    "spread_pct": 0.51,
                },
                {
                    "symbol": "BRLUSD",
                    "buy": 0.186,
                    "sell": 0.188,
                    "spread": 0.002,
                    "spread_pct": 1.07,
                },
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
                },
                {
                    "symbol": "BRLUSDT",
                    "buy": 0.1855,
                    "sell": 0.1875,
                    "spread": 0.002,
                    "spread_pct": 1.07,
                },
            ],
            "logo": "https://example.com/logo2.png",
            "url": "https://app2.com",
            "isPix": False,
            "hasFees": True,
        },
        "app3": {
            "quotes": [
                {
                    "symbol": "BRLARS",
                    "buy": 1848.0,
                    "sell": 1858.5,
                    "spread": 10.5,
                    "spread_pct": 0.57,
                }
            ],
            "logo": "https://example.com/logo3.png",
            "url": "https://app3.com",
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
    with patch("app.database.get_tracker") as mock_get_tracker:
        mock_tracker = AsyncMock()
        mock_tracker.get_latest_snapshot = AsyncMock()
        mock_tracker.get_app_history = AsyncMock()
        mock_tracker.save_snapshot = AsyncMock()
        mock_tracker.get_mongo_ping_time = Mock(return_value=5.5)
        mock_get_tracker.return_value = mock_tracker
        yield mock_tracker


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


@pytest.fixture
def api_response_brlusd_priority():
    """API response with both BRLUSD and BRLUSDT to test priority"""
    return {
        "priority_test_app": {
            "quotes": [
                {
                    "symbol": "BRLUSDT",  # First but should be ignored
                    "buy": 0.1855,
                    "sell": 0.1875,
                    "spread": 0.002,
                    "spread_pct": 1.07,
                },
                {
                    "symbol": "BRLARS",
                    "buy": 1850.5,
                    "sell": 1860.0,
                    "spread": 9.5,
                    "spread_pct": 0.51,
                },
                {
                    "symbol": "BRLUSD",  # Second but should be chosen
                    "buy": 0.186,
                    "sell": 0.188,
                    "spread": 0.002,
                    "spread_pct": 1.07,
                },
            ],
            "logo": "https://example.com/priority.png",
            "url": "https://priority.com",
            "isPix": True,
            "hasFees": False,
        }
    }
