import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models import QuoteSnapshot, AppRate, HistoryElement


class TestAPIEndpointsSimple:
    """Simplified API endpoint tests with proper mocking"""

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

    @patch("app.main.tracker")
    def test_latest_endpoint_success(self, mock_tracker, client):
        """Test latest endpoint with successful response"""
        # Mock the tracker response
        mock_snapshot = QuoteSnapshot(
            timestamp=datetime.now(timezone.utc),
            quotes={"app1": 1850.5, "app2": 1852.0},
        )
        mock_tracker.get_latest_snapshot = AsyncMock(return_value=mock_snapshot)

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
    def test_latest_endpoint_no_snapshots(self, mock_tracker, client):
        """Test latest endpoint when no snapshots exist"""
        mock_tracker.get_latest_snapshot = AsyncMock(return_value=None)

        response = client.get("/latest")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "No snapshots found"

    @patch("app.main.tracker")
    def test_app_history_success(self, mock_tracker, client):
        """Test app history endpoint with successful response"""
        app_name = "app1"
        hours = 24

        # Mock history data
        mock_history = [
            {"timestamp": datetime.now(timezone.utc).isoformat(), "rate": 1850.5},
            {
                "timestamp": (
                    datetime.now(timezone.utc) - timedelta(hours=1)
                ).isoformat(),
                "rate": 1852.0,
            },
        ]

        mock_tracker.get_app_history = AsyncMock(return_value=mock_history)

        response = client.get(f"/apps/{app_name}?hours={hours}")

        assert response.status_code == 200
        data = response.json()
        assert data["app_name"] == app_name
        assert data["total_records"] == 2
        assert len(data["history"]) == 2

        # Check history structure
        for item in data["history"]:
            assert "timestamp" in item
            assert "rate" in item
            assert isinstance(item["rate"], (int, float))

    @patch("app.main.tracker")
    def test_app_history_not_found(self, mock_tracker, client):
        """Test app history endpoint when app not found"""
        app_name = "nonexistent_app"

        mock_tracker.get_app_history = AsyncMock(return_value=[])

        response = client.get(f"/apps/{app_name}")

        assert response.status_code == 404
        data = response.json()
        assert "No history found for app" in data["detail"]
        assert app_name in data["detail"]

    @patch("app.main.tracker")
    def test_health_check_healthy(self, mock_tracker, client):
        """Test health check endpoint when healthy"""
        # Mock healthy responses
        mock_snapshot = QuoteSnapshot(
            timestamp=datetime.now(timezone.utc), quotes={"app1": 1850.5}
        )
        mock_tracker.get_latest_snapshot = AsyncMock(return_value=mock_snapshot)
        mock_tracker.get_mongo_ping_time = Mock(return_value=5.5)

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

    def test_favicon_endpoint(self, client):
        """Test favicon endpoint"""
        response = client.get("/favicon.ico")

        # Should return 200 or 404 depending on if favicon exists
        assert response.status_code in [200, 404]

    def test_docs_endpoint(self, client):
        """Test OpenAPI docs endpoint"""
        response = client.get("/docs")

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


class TestAPIValidationSimple:
    """Test API input validation"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_app_history_invalid_hours_negative(self, client):
        """Test app history with negative hours"""
        response = client.get("/apps/app1?hours=-1")

        # FastAPI should validate this
        assert response.status_code == 422

    def test_app_history_invalid_hours_zero(self, client):
        """Test app history with zero hours"""
        response = client.get("/apps/app1?hours=0")

        assert response.status_code == 422

    def test_app_history_invalid_hours_string(self, client):
        """Test app history with string hours"""
        response = client.get("/apps/app1?hours=invalid")

        assert response.status_code == 422
