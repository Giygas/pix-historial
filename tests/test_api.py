import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models import QuoteSnapshot, HistoryElement


class TestAPIEndpoints:
    """Test API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_root_endpoint(self, client):
        """Test root endpoint serves HTML"""
        response = client.get("/")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert "PIX Historial" in response.text
        assert "BRL/ARS exchange rates" in response.text

    def test_favicon_endpoint(self, client):
        """Test favicon endpoint"""
        response = client.get("/favicon.ico")

        # Should return 200 or 404 depending on if favicon exists
        assert response.status_code in [200, 404]

    @patch("app.main.tracker")
    def test_latest_endpoint_success(self, mock_tracker):
        """Test latest endpoint with successful response"""
        mock_snapshot = QuoteSnapshot(
            timestamp=datetime.now(timezone.utc),
            quotes={"app1": 1850.5, "app2": 1852.0},
        )
        mock_tracker.get_latest_snapshot = AsyncMock(return_value=mock_snapshot)

        client = TestClient(app)
        response = client.get("/latest")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "latest"
        assert data["total_apps"] == 2
        assert len(data["quotes"]) == 2

        # Check quote structure
        quote_names = [quote["app_name"] for quote in data["quotes"]]
        assert "app1" in quote_names
        assert "app2" in quote_names

    @patch("app.main.tracker")
    def test_latest_endpoint_no_snapshots(self, mock_tracker):
        """Test latest endpoint when no snapshots exist"""
        mock_tracker.get_latest_snapshot = AsyncMock(return_value=None)

        client = TestClient(app)
        response = client.get("/latest")

        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "NotFound"
        assert "No snapshots found" in data["message"]

    @patch("app.main.tracker")
    def test_latest_endpoint_database_error(self, mock_tracker):
        """Test latest endpoint with database error"""
        mock_tracker.get_latest_snapshot = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        client = TestClient(app)

        # The /latest endpoint doesn't handle database errors gracefully
        # It will raise an exception that crashes the request
        with pytest.raises(Exception, match="Database connection failed"):
            client.get("/latest")

    @patch("app.main.tracker")
    def test_app_history_success(self, mock_tracker, sample_history_data):
        """Test app history endpoint with successful response"""
        app_name = "app1"
        hours = 24

        # Convert sample data to HistoryElement objects
        history_elements = [
            HistoryElement(timestamp=item["timestamp"], rate=item["rate"])
            for item in sample_history_data
        ]

        mock_tracker.get_app_history = AsyncMock(
            return_value=[
                {"timestamp": item.timestamp, "rate": item.rate}
                for item in history_elements
            ]
        )

        client = TestClient(app)
        response = client.get(f"/apps/{app_name}?hours={hours}")

        assert response.status_code == 200
        data = response.json()
        assert data["app_name"] == app_name
        assert data["total_records"] == 4
        assert len(data["history"]) == 4

        # Check history structure
        for item in data["history"]:
            assert "timestamp" in item
            assert "rate" in item
            assert isinstance(item["rate"], (int, float))

    @patch("app.main.tracker")
    def test_app_history_default_hours(self, mock_tracker, client):
        """Test app history endpoint with default hours parameter"""
        app_name = "app1"

        mock_tracker.get_app_history = AsyncMock(return_value=[])

        response = client.get(f"/apps/{app_name}")

        assert response.status_code == 404  # No history found
        mock_tracker.get_app_history.assert_called_once_with(app_name, 24)

    @patch("app.main.tracker")
    def test_app_history_not_found(self, mock_tracker, client):
        """Test app history endpoint when app not found"""
        app_name = "nonexistent_app"

        mock_tracker.get_app_history = AsyncMock(return_value=[])

        response = client.get(f"/apps/{app_name}")

        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "NotFound"
        assert "No history found for app" in data["message"]
        assert app_name in data["message"]

    @patch("app.main.tracker")
    def test_app_history_database_error(self, mock_tracker):
        """Test app history endpoint with database error"""
        app_name = "app1"

        mock_tracker.get_app_history = AsyncMock(
            side_effect=Exception("Database error")
        )

        client = TestClient(app)

        # The /apps endpoint doesn't handle database errors gracefully
        # It will raise an exception that crashes the request
        with pytest.raises(Exception, match="Database error"):
            client.get(f"/apps/{app_name}")

    @patch("app.main.tracker")
    def test_health_check_healthy(self, mock_tracker, client):
        """Test health check endpoint when healthy"""
        # Mock healthy responses
        mock_snapshot = QuoteSnapshot(
            timestamp=datetime.now(timezone.utc), quotes={"app1": 1850.5}
        )
        mock_tracker.get_latest_snapshot = AsyncMock(return_value=mock_snapshot)
        mock_tracker.get_mongo_ping_time.return_value = 5.5

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["last_update"] is not None
        assert data["timestamp"] is not None
        assert "uptime" in data
        assert "mongo_ping" in data
        assert "5.5 ms" in data["mongo_ping"]

    @patch("app.main.tracker")
    def test_health_check_unhealthy(self, mock_tracker, client):
        """Test health check endpoint when unhealthy"""
        # Mock unhealthy responses
        mock_tracker.get_latest_snapshot = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "error" in data["database"]
        assert data["last_update"] is None

    @patch("app.main.tracker")
    def test_health_check_no_data(self, mock_tracker, client):
        """Test health check endpoint with no data"""
        # Mock no snapshots
        mock_tracker.get_latest_snapshot = AsyncMock(return_value=None)
        mock_tracker.get_mongo_ping_time.return_value = 5.5

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"  # Still healthy if DB is connected
        assert data["database"] == "connected"
        assert data["last_update"] is None


class TestAPIValidation:
    """Test API input validation"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @patch("app.main.tracker")
    def test_app_history_invalid_hours_negative(self, mock_tracker, client):
        """Test app history with negative hours"""
        mock_tracker.get_app_history = AsyncMock(return_value=[])

        response = client.get("/apps/app1?hours=-1")

        # FastAPI should validate this, but let's check the behavior
        assert response.status_code in [422, 404]  # Validation error or not found

    @patch("app.main.tracker")
    def test_app_history_invalid_hours_zero(self, mock_tracker, client):
        """Test app history with zero hours"""
        mock_tracker.get_app_history = AsyncMock(return_value=[])

        response = client.get("/apps/app1?hours=0")

        assert response.status_code in [422, 404]

    @patch("app.main.tracker")
    def test_app_history_invalid_hours_string(self, mock_tracker, client):
        """Test app history with string hours"""
        mock_tracker.get_app_history = AsyncMock(return_value=[])

        response = client.get("/apps/app1?hours=invalid")

        assert response.status_code == 422  # Validation error


class TestAPIIntegration:
    """Integration tests for API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @patch("app.main.tracker")
    def test_full_workflow(self, mock_tracker, client):
        """Test full workflow: health -> latest -> history"""
        # Setup mock data
        now = datetime.now(timezone.utc)
        mock_snapshot = QuoteSnapshot(
            timestamp=now, quotes={"app1": 1850.5, "app2": 1852.0}
        )

        mock_history = [
            {"timestamp": (now - timedelta(hours=i)), "rate": 1850.5 + i}
            for i in range(5)
        ]

        mock_tracker.get_latest_snapshot = AsyncMock(return_value=mock_snapshot)
        mock_tracker.get_app_history = AsyncMock(return_value=mock_history)
        mock_tracker.get_mongo_ping_time.return_value = 5.5

        # Test health check
        health_response = client.get("/health")
        assert health_response.status_code == 200
        assert health_response.json()["status"] == "healthy"

        # Test latest
        latest_response = client.get("/latest")
        assert latest_response.status_code == 200
        latest_data = latest_response.json()
        assert latest_data["total_apps"] == 2

        # Test app history
        history_response = client.get("/apps/app1")
        assert history_response.status_code == 200
        history_data = history_response.json()
        assert history_data["total_records"] == 5

    @patch("app.main.tracker")
    def test_error_handling_consistency(self, mock_tracker):
        """Test consistent error handling across endpoints"""
        # Mock database errors
        mock_tracker.get_latest_snapshot = AsyncMock(side_effect=Exception("DB Error"))
        mock_tracker.get_app_history = AsyncMock(side_effect=Exception("DB Error"))

        client = TestClient(app)

        # /latest and /apps endpoints don't handle database errors gracefully
        with pytest.raises(Exception, match="DB Error"):
            client.get("/latest")

        with pytest.raises(Exception, match="DB Error"):
            client.get("/apps/app1")

        # Health check should still work and report unhealthy status
        health_response = client.get("/health")
        assert health_response.status_code == 200
        assert health_response.json()["status"] == "unhealthy"


class TestAPIDocumentation:
    """Test API documentation endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_docs_endpoint(self, client):
        """Test OpenAPI docs endpoint"""
        response = client.get("/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_redoc_endpoint(self, client):
        """Test ReDoc endpoint"""
        response = client.get("/redoc")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_openapi_schema(self, client):
        """Test OpenAPI schema endpoint"""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema
        assert "components" in schema
