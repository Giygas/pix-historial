import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pymongo.collection import Collection
from pymongo.database import Database

from app.database import QuoteTracker
from app.models import QuoteSnapshot, ApiResponse, Exchange, Quote


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
            tracker.client = mock_client
            tracker.db = Mock(spec=Database)
            tracker.collection = Mock(spec=Collection)
            return tracker

    def test_tracker_initialization(self, mock_client):
        """Test QuoteTracker initialization"""
        with patch("app.database.settings"):
            tracker = QuoteTracker()

            assert tracker.client == mock_client
            assert hasattr(tracker, "db")
            assert hasattr(tracker, "collection")

    def test_create_indexes(self, tracker_instance):
        """Test index creation"""
        tracker_instance.collection.create_index = Mock()

        tracker_instance.createIndexes()

        # Verify indexes were created
        assert tracker_instance.collection.create_index.call_count == 2
        tracker_instance.collection.create_index.assert_any_call([("timestamp", -1)])
        tracker_instance.collection.create_index.assert_any_call(
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
        """Test successful snapshot saving"""
        # Mock the insert_one result
        mock_result = Mock()
        mock_result.inserted_id = "507f1f77bcf86cd799439011"
        tracker_instance.collection.insert_one = Mock(return_value=mock_result)

        doc_id = await tracker_instance.save_snapshot(sample_api_response)

        assert doc_id == "507f1f77bcf86cd799439011"
        tracker_instance.collection.insert_one.assert_called_once()

        # Verify the data structure
        call_args = tracker_instance.collection.insert_one.call_args[0][0]
        assert "quotes" in call_args
        assert "timestamp" in call_args
        assert isinstance(call_args["quotes"], dict)
        assert len(call_args["quotes"]) == 2  # app1 and app2

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
        assert all("timestamp" in item and "rate" in item for item in history)
        assert all(item["rate"] > 0 for item in history)

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
        # Setup mocks
        mock_result = Mock()
        mock_result.inserted_id = "507f1f77bcf86cd799439011"
        tracker_instance.collection.insert_one = Mock(return_value=mock_result)

        mock_doc = {
            "_id": "507f1f77bcf86cd799439011",
            "timestamp": datetime.now(timezone.utc),
            "quotes": {"app1": 1850.5, "app2": 1852.0},
        }
        tracker_instance.collection.find_one = Mock(return_value=mock_doc)

        # Test save
        doc_id = await tracker_instance.save_snapshot(sample_api_response)
        assert doc_id == "507f1f77bcf86cd799439011"

        # Test get latest
        latest = await tracker_instance.get_latest_snapshot()
        assert latest is not None
        assert "app1" in latest.quotes
        assert "app2" in latest.quotes

        # Test get history
        tracker_instance.get_snapshots_since = AsyncMock(return_value=[latest])
        history = await tracker_instance.get_app_history("app1", 24)
        assert len(history) == 1
        assert history[0]["rate"] == 1850.5
