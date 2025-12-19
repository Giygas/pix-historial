from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pymongo.collection import Collection
from pymongo.database import Database

from app.database import QuoteTracker
from app.models import Exchange, Quote, QuoteSnapshot


class TestQuoteTracker:
    """Test QuoteTracker class"""

    @pytest.fixture
    def mock_client(self):
        """Mock MongoDB client"""
        with patch("app.database.MongoClient") as mock:
            yield mock

    @pytest.fixture
    def tracker_instance(self, mock_client):
        """Create QuoteTracker instance with mocked dependencies"""
        with patch("app.database.settings"):
            tracker = QuoteTracker()
            # Set private attributes to mock lazy properties
            tracker._client = mock_client
            tracker._db = Mock(spec=Database)
            tracker._collection = Mock(spec=Collection)
            tracker._usd_collection = Mock(spec=Collection)  # Add USD collection mock
            return tracker

    def test_tracker_initialization(self, mock_client):
        """Test QuoteTracker initialization"""
        with patch("app.database.settings") as mock_settings:
            mock_settings.MONGO_URI = "mongodb://localhost:27017"
            mock_settings.DB_NAME = "test_db"

            tracker = QuoteTracker()

            # Access client property to trigger lazy initialization
            _ = tracker.client

            mock_client.assert_called_once_with("mongodb://localhost:27017")
            assert hasattr(tracker, "db")
            assert hasattr(tracker, "collection")

    def test_create_indexes(self, tracker_instance):
        """Test index creation"""
        tracker_instance.collection.create_index = Mock()
        tracker_instance.usd_collection.create_index = Mock()

        tracker_instance.createIndexes()

        # Verify indexes were created for both collections
        assert tracker_instance.collection.create_index.call_count == 2
        assert tracker_instance.usd_collection.create_index.call_count == 2

        # Verify BRLARS collection indexes
        tracker_instance.collection.create_index.assert_any_call([("timestamp", -1)])
        tracker_instance.collection.create_index.assert_any_call(
            [("timestamp", -1), ("quotes", 1)]
        )

        # Verify USD collection indexes
        tracker_instance.usd_collection.create_index.assert_any_call(
            [("timestamp", -1)]
        )
        tracker_instance.usd_collection.create_index.assert_any_call(
            [("timestamp", -1), ("quotes", 1)]
        )

    def test_extract_brlars_rate_found(self, tracker_instance):
        """Test extracting BRLARS rate when found"""
        exchange = Exchange(
            quotes=[
                Quote(symbol="USDARS", buy=365.5),
                Quote(symbol="BRLARS", buy=1850.5, sell=1860.0),
                Quote(symbol="EURARS", buy=395.5),
            ],
            logo="https://example.com/logo.png",
            url="https://example.com",
            isPix=True,
        )

        rate = tracker_instance.extract_brlars_rate(exchange)

        assert rate == 1850.5

    def test_extract_brlars_rate_not_found(self, tracker_instance):
        """Test extracting BRLARS rate when not found"""
        exchange = Exchange(
            quotes=[
                Quote(symbol="USDARS", buy=365.5),
                Quote(symbol="EURARS", buy=395.5),
            ],
            logo="https://example.com/logo.png",
            url="https://example.com",
            isPix=True,
        )

        rate = tracker_instance.extract_brlars_rate(exchange)

        assert rate is None

    @pytest.mark.asyncio
    async def test_save_snapshot_success(self, tracker_instance, sample_api_response):
        """Test successful snapshot saving with USD data"""
        # Mock insert_one results for both collections
        mock_result = Mock()
        mock_result.inserted_id = "507f1f77bcf86cd799439011"
        tracker_instance.collection.insert_one = Mock(return_value=mock_result)

        mock_usd_result = Mock()
        mock_usd_result.inserted_id = "507f1f77bcf86cd799439012"
        tracker_instance.usd_collection.insert_one = Mock(return_value=mock_usd_result)

        result = await tracker_instance.save_snapshot(sample_api_response)

        # Check return format - app1 has BRLUSD, app2 has BRLUSDT, app3 has no USD
        assert "brlars=3 apps" in result
        assert "usd=2 apps" in result

        # Verify both collections were called
        tracker_instance.collection.insert_one.assert_called_once()
        tracker_instance.usd_collection.insert_one.assert_called_once()

        # Verify BRLARS data structure
        brlars_call_args = tracker_instance.collection.insert_one.call_args[0][0]
        assert "quotes" in brlars_call_args
        assert "timestamp" in brlars_call_args
        assert isinstance(brlars_call_args["quotes"], dict)
        assert len(brlars_call_args["quotes"]) == 3  # app1, app2, app3

        # Verify USD data structure
        usd_call_args = tracker_instance.usd_collection.insert_one.call_args[0][0]
        assert "quotes" in usd_call_args
        assert "timestamp" in usd_call_args
        assert isinstance(usd_call_args["quotes"], dict)
        assert len(usd_call_args["quotes"]) == 2  # app1, app2

        # Verify specific USD rates (BRLUSD preference)
        usd_quotes = usd_call_args["quotes"]
        assert usd_quotes["app1"] == 0.186  # BRLUSD rate
        assert usd_quotes["app2"] == 0.1855  # BRLUSDT rate
        assert "app3" not in usd_quotes  # No USD data

    @pytest.mark.asyncio
    async def test_save_snapshot_no_brlars_quotes(self, tracker_instance):
        """Test saving snapshot with no BRLARS quotes"""
        api_data = {
            "app1": {
                "quotes": [{"symbol": "USDARS", "buy": 365.5}],
                "logo": "https://example.com/logo.png",
                "url": "https://example.com",
                "isPix": True,
            }
        }

        with pytest.raises(ValueError, match="No BRLARS quotes found"):
            await tracker_instance.save_snapshot(api_data)

    @pytest.mark.asyncio
    async def test_save_snapshot_brlars_only(self, tracker_instance):
        """Test saving snapshot with only BRLARS data (no USD)"""
        api_data = {
            "app1": {
                "quotes": [{"symbol": "BRLARS", "buy": 1850.5}],
                "logo": "https://example.com/logo.png",
                "url": "https://example.com",
                "isPix": True,
            }
        }

        # Mock BRLARS insert
        mock_result = Mock()
        mock_result.inserted_id = "507f1f77bcf86cd799439011"
        tracker_instance.collection.insert_one = Mock(return_value=mock_result)
        tracker_instance.usd_collection.insert_one = Mock()

        result = await tracker_instance.save_snapshot(api_data)

        assert "brlars=1 apps" in result
        assert "usd=0 apps" in result
        tracker_instance.collection.insert_one.assert_called_once()
        tracker_instance.usd_collection.insert_one.assert_not_called()

    def test_extract_brlusd_rate_priority_test(self, tracker_instance):
        """Test that BRLUSD is preferred over BRLUSDT when both present"""
        # BRLUSDT comes first in the array, but BRLUSD should be chosen
        from app.models import Exchange, Quote

        exchange = Exchange(
            quotes=[
                Quote(symbol="BRLUSDT", buy=0.1855),
                Quote(symbol="BRLARS", buy=1850.5),
                Quote(symbol="BRLUSD", buy=0.186),  # This should be chosen
            ],
            logo="https://example.com/logo.png",
            url="https://example.com",
            isPix=True,
        )

        rate = tracker_instance.extract_brlusd_rate(exchange)
        assert rate == 0.186  # Should return BRLUSD, not BRLUSDT

    @pytest.mark.asyncio
    async def test_save_snapshot_usd_only(self, tracker_instance):
        """Test saving snapshot with only USD data (no BRLARS)"""
        api_data = {
            "app1": {
                "quotes": [{"symbol": "BRLUSD", "buy": 0.186}],
                "logo": "https://example.com/logo.png",
                "url": "https://example.com",
                "isPix": True,
            }
        }

        with pytest.raises(ValueError, match="No BRLARS quotes found"):
            await tracker_instance.save_snapshot(api_data)

    @pytest.mark.asyncio
    async def test_extract_brlusd_rate_found(self, tracker_instance):
        """Test extracting USD rate when found"""
        from app.models import Exchange, Quote

        exchange = Exchange(
            quotes=[
                Quote(symbol="BRLARS", buy=1850.5),
                Quote(symbol="BRLUSD", buy=0.186),
                Quote(symbol="USDARS", buy=365.5),
            ],
            logo="https://example.com/logo.png",
            url="https://example.com",
            isPix=True,
        )

        rate = tracker_instance.extract_brlusd_rate(exchange)
        assert rate == 0.186

    def test_extract_brlusd_rate_not_found(self, tracker_instance):
        """Test extracting USD rate when not found"""
        from app.models import Exchange, Quote

        exchange = Exchange(
            quotes=[
                Quote(symbol="BRLARS", buy=1850.5),
                Quote(symbol="USDARS", buy=365.5),
            ],
            logo="https://example.com/logo.png",
            url="https://example.com",
            isPix=True,
        )

        rate = tracker_instance.extract_brlusd_rate(exchange)
        assert rate is None

    def test_extract_brlusd_rate_only_brlusdt(self, tracker_instance):
        """Test extracting BRLUSDT when no BRLUSD available"""
        from app.models import Exchange, Quote

        exchange = Exchange(
            quotes=[
                Quote(symbol="BRLARS", buy=1850.5),
                Quote(symbol="BRLUSDT", buy=0.1855),  # Should be chosen
            ],
            logo="https://example.com/logo.png",
            url="https://example.com",
            isPix=True,
        )

        rate = tracker_instance.extract_brlusd_rate(exchange)
        assert rate == 0.1855

    def test_extract_brlusd_rate_only_brlusd(self, tracker_instance):
        """Test extracting BRLUSD when only BRLUSD available"""
        from app.models import Exchange, Quote

        exchange = Exchange(
            quotes=[
                Quote(symbol="BRLARS", buy=1850.5),
                Quote(symbol="BRLUSD", buy=0.186),  # Should be chosen
            ],
            logo="https://example.com/logo.png",
            url="https://example.com",
            isPix=True,
        )

        rate = tracker_instance.extract_brlusd_rate(exchange)
        assert rate == 0.186

    @pytest.mark.asyncio
    async def test_get_latest_snapshot_found(
        self, tracker_instance, sample_quote_snapshot
    ):
        """Test getting latest snapshot when found"""
        # Mock database response
        mock_doc = sample_quote_snapshot.model_dump()
        mock_doc["_id"] = "507f1f77bcf86cd799439011"

        tracker_instance.collection.find_one = Mock(return_value=mock_doc)

        result = await tracker_instance.get_latest_snapshot()

        assert result is not None
        assert isinstance(result, QuoteSnapshot)
        assert result.quotes == sample_quote_snapshot.quotes
        assert not hasattr(result, "_id")  # _id should be removed

    @pytest.mark.asyncio
    async def test_get_latest_snapshot_not_found(self, tracker_instance):
        """Test getting latest snapshot when not found"""
        tracker_instance.collection.find_one = Mock(return_value=None)

        result = await tracker_instance.get_latest_snapshot()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_snapshots_since(self, tracker_instance):
        """Test getting snapshots since a given time"""
        since = datetime.now(timezone.utc) - timedelta(hours=24)

        # Mock database documents
        mock_docs = [
            {
                "_id": "507f1f77bcf86cd799439011",
                "timestamp": datetime.now(timezone.utc),
                "quotes": {"app1": 1850.5, "app2": 1852.0},
            },
            {
                "_id": "507f1f77bcf86cd799439012",
                "timestamp": datetime.now(timezone.utc) - timedelta(hours=1),
                "quotes": {"app1": 1848.5, "app2": 1850.0},
            },
        ]

        tracker_instance.collection.find = Mock(return_value=mock_docs)

        results = await tracker_instance.get_snapshots_since(since)

        assert len(results) == 2
        assert all(isinstance(result, QuoteSnapshot) for result in results)
        assert all(not hasattr(result, "_id") for result in results)

        # Verify query parameters
        tracker_instance.collection.find.assert_called_once_with(
            {"timestamp": {"$gte": since}}, sort=[("timestamp", -1)]
        )

    @pytest.mark.asyncio
    async def test_get_app_history_found(self, tracker_instance, sample_history_data):
        """Test getting app history when found"""
        app_name = "app1"
        hours = 24

        # Mock get_snapshots_since to return sample data
        tracker_instance.get_snapshots_since = AsyncMock(
            return_value=[
                QuoteSnapshot(
                    timestamp=item["timestamp"], quotes={app_name: item["rate"]}
                )
                for item in sample_history_data
            ]
        )

        history = await tracker_instance.get_app_history(app_name, hours)

        assert len(history) == 4
        assert all(
            hasattr(item, "timestamp") and hasattr(item, "rate") for item in history
        )
        assert all(item.rate > 0 for item in history)

        # Verify get_snapshots_since was called with correct time range
        tracker_instance.get_snapshots_since.assert_called_once()
        call_args = tracker_instance.get_snapshots_since.call_args[0][0]
        expected_since = datetime.now(timezone.utc) - timedelta(hours=hours)
        assert (
            abs((call_args - expected_since).total_seconds()) < 60
        )  # Allow 1 minute difference

    @pytest.mark.asyncio
    async def test_get_app_history_not_found(self, tracker_instance):
        """Test getting app history when app not found in snapshots"""
        app_name = "nonexistent_app"
        hours = 24

        # Mock snapshots without the requested app
        tracker_instance.get_snapshots_since = AsyncMock(
            return_value=[
                QuoteSnapshot(
                    timestamp=datetime.now(timezone.utc), quotes={"other_app": 1850.5}
                )
            ]
        )

        history = await tracker_instance.get_app_history(app_name, hours)

        assert history == []

    def test_get_mongo_ping_time(self, tracker_instance):
        """Test MongoDB ping time measurement"""
        # Mock database command
        tracker_instance.db.command = Mock()

        ping_time = tracker_instance.get_mongo_ping_time()

        assert isinstance(ping_time, float)
        assert ping_time >= 0
        tracker_instance.db.command.assert_called_once_with("ping")

    def test_get_mongo_ping_time_with_exception(self, tracker_instance):
        """Test MongoDB ping time measurement with exception"""
        # Mock database command to raise exception
        tracker_instance.db.command = Mock(side_effect=Exception("Connection error"))

        with pytest.raises(Exception, match="Connection error"):
            tracker_instance.get_mongo_ping_time()


class TestQuoteTrackerIntegration:
    """Integration tests for QuoteTracker"""

    @pytest.mark.asyncio
    async def test_full_workflow(self, tracker_instance, sample_api_response):
        """Test full workflow: save -> retrieve latest -> get history"""
        # Setup mocks for both collections
        mock_result = Mock()
        mock_result.inserted_id = "507f1f77bcf86cd799439011"
        tracker_instance.collection.insert_one = Mock(return_value=mock_result)

        mock_usd_result = Mock()
        mock_usd_result.inserted_id = "507f1f77bcf86cd799439012"
        tracker_instance.usd_collection.insert_one = Mock(return_value=mock_usd_result)

        # Mock database responses
        mock_brlars_doc = {
            "_id": "507f1f77bcf86cd799439011",
            "timestamp": datetime.now(timezone.utc),
            "quotes": {"app1": 1850.5, "app2": 1852.0, "app3": 1848.0},
        }
        tracker_instance.collection.find_one = Mock(return_value=mock_brlars_doc)

        mock_usd_doc = {
            "_id": "507f1f77bcf86cd799439012",
            "timestamp": datetime.now(timezone.utc),
            "quotes": {"app1": 0.186, "app2": 0.1855},
        }
        tracker_instance.usd_collection.find_one = Mock(return_value=mock_usd_doc)

        # Test save
        result = await tracker_instance.save_snapshot(sample_api_response)
        assert "brlars=3 apps" in result
        assert "usd=2 apps" in result

        # Test get latest BRLARS
        latest_brlars = await tracker_instance.get_latest_snapshot()
        assert latest_brlars is not None
        assert "app1" in latest_brlars.quotes
        assert "app2" in latest_brlars.quotes
        assert "app3" in latest_brlars.quotes

        # Test get latest USD
        latest_usd = await tracker_instance.get_latest_snapshot(is_usd=True)
        assert latest_usd is not None
        assert "app1" in latest_usd.quotes
        assert "app2" in latest_usd.quotes
        assert "app3" not in latest_usd.quotes  # app3 has no USD

        # Test get history
        tracker_instance.get_snapshots_since = AsyncMock(return_value=[latest_brlars])
        history = await tracker_instance.get_app_history("app1", 24)
        assert len(history) == 1
        assert history[0].rate == 1850.5
