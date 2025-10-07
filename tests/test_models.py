import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.models import (
    Quote,
    Exchange,
    ApiResponse,
    QuoteSnapshot,
    AppRate,
    SnapshotResponse,
    HistoryElement,
    AppHistoryResponse,
    HealthCheckResponse,
)


class TestQuote:
    """Test Quote model"""

    def test_quote_creation_valid(self):
        """Test creating a valid Quote"""
        quote = Quote(
            symbol="BRLARS", buy=1850.5, sell=1860.0, spread=9.5, spread_pct=0.51
        )

        assert quote.symbol == "BRLARS"
        assert quote.buy == 1850.5
        assert quote.sell == 1860.0
        assert quote.spread == 9.5
        assert quote.spread_pct == 0.51

    def test_quote_minimal_fields(self):
        """Test creating Quote with minimal required fields"""
        quote = Quote(symbol="BRLARS", buy=1850.5)

        assert quote.symbol == "BRLARS"
        assert quote.buy == 1850.5
        assert quote.sell is None
        assert quote.spread is None
        assert quote.spread_pct is None

    def test_quote_invalid_symbol(self):
        """Test Quote with invalid symbol type"""
        with pytest.raises(ValidationError):
            Quote(symbol=123, buy=1850.5)  # symbol should be string

    def test_quote_invalid_buy(self):
        """Test Quote with invalid buy type"""
        with pytest.raises(ValidationError):
            Quote(symbol="BRLARS", buy="invalid")  # buy should be float, not string


class TestExchange:
    """Test Exchange model"""

    def test_exchange_creation_valid(self):
        """Test creating a valid Exchange"""
        quotes = [
            Quote(symbol="BRLARS", buy=1850.5, sell=1860.0),
            Quote(symbol="USDARS", buy=365.5, sell=366.0),
        ]

        exchange = Exchange(
            quotes=quotes,
            logo="https://example.com/logo.png",
            url="https://example.com",
            isPix=True,
            hasFees=False,
        )

        assert len(exchange.quotes) == 2
        assert exchange.logo == "https://example.com/logo.png"
        assert exchange.url == "https://example.com"
        assert exchange.isPix is True
        assert exchange.hasFees is False

    def test_exchange_minimal_fields(self):
        """Test creating Exchange with minimal required fields"""
        quotes = [Quote(symbol="BRLARS", buy=1850.5)]

        exchange = Exchange(
            quotes=quotes,
            logo="https://example.com/logo.png",
            url="https://example.com",
            isPix=False,
        )

        assert len(exchange.quotes) == 1
        assert exchange.hasFees is None  # Optional field


class TestApiResponse:
    """Test ApiResponse model"""

    def test_api_response_creation(self):
        """Test creating ApiResponse"""
        quotes = [Quote(symbol="BRLARS", buy=1850.5)]
        exchange = Exchange(
            quotes=quotes,
            logo="https://example.com/logo.png",
            url="https://example.com",
            isPix=True,
        )

        api_data = {"app1": exchange}
        response = ApiResponse(api_data)

        assert len(response.root) == 1
        assert "app1" in response.root
        assert response.root["app1"].isPix is True

    def test_api_response_items(self):
        """Test ApiResponse items method"""
        quotes = [Quote(symbol="BRLARS", buy=1850.5)]
        exchange = Exchange(
            quotes=quotes,
            logo="https://example.com/logo.png",
            url="https://example.com",
            isPix=True,
        )

        api_data = {"app1": exchange, "app2": exchange}
        response = ApiResponse(api_data)

        items = list(response.items())
        assert len(items) == 2
        assert items[0][0] == "app1"
        assert items[1][0] == "app2"


class TestQuoteSnapshot:
    """Test QuoteSnapshot model"""

    def test_quote_snapshot_creation(self):
        """Test creating QuoteSnapshot"""
        timestamp = datetime.now(timezone.utc)
        quotes = {"app1": 1850.5, "app2": 1852.0}

        snapshot = QuoteSnapshot(timestamp=timestamp, quotes=quotes)

        assert snapshot.timestamp == timestamp
        assert snapshot.quotes == quotes
        assert len(snapshot.quotes) == 2

    def test_quote_snapshot_default_timestamp(self):
        """Test QuoteSnapshot with default timestamp"""
        quotes = {"app1": 1850.5}
        snapshot = QuoteSnapshot(quotes=quotes)

        assert isinstance(snapshot.timestamp, datetime)
        assert snapshot.quotes == quotes

    def test_quote_snapshot_empty_quotes(self):
        """Test QuoteSnapshot with empty quotes - this actually passes validation"""
        # Note: Pydantic doesn't validate empty dict by default
        # This test documents the current behavior
        snapshot = QuoteSnapshot(quotes={})
        assert snapshot.quotes == {}


class TestAppRate:
    """Test AppRate model"""

    def test_app_rate_creation(self):
        """Test creating AppRate"""
        app_rate = AppRate(app_name="app1", rate=1850.5)

        assert app_rate.app_name == "app1"
        assert app_rate.rate == 1850.5


class TestSnapshotResponse:
    """Test SnapshotResponse model"""

    def test_snapshot_response_creation(self):
        """Test creating SnapshotResponse"""
        timestamp = datetime.now(timezone.utc)
        quotes = [
            AppRate(app_name="app1", rate=1850.5),
            AppRate(app_name="app2", rate=1852.0),
        ]

        response = SnapshotResponse(
            id="latest", timestamp=timestamp, quotes=quotes, total_apps=2
        )

        assert response.id == "latest"
        assert response.timestamp == timestamp
        assert len(response.quotes) == 2
        assert response.total_apps == 2


class TestHistoryElement:
    """Test HistoryElement model"""

    def test_history_element_creation(self):
        """Test creating HistoryElement"""
        timestamp = datetime.now(timezone.utc)
        element = HistoryElement(timestamp=timestamp, rate=1850.5)

        assert element.timestamp == timestamp
        assert element.rate == 1850.5


class TestAppHistoryResponse:
    """Test AppHistoryResponse model"""

    def test_app_history_response_creation(self):
        """Test creating AppHistoryResponse"""
        now = datetime.now(timezone.utc)
        history = [
            HistoryElement(timestamp=now, rate=1850.5),
            HistoryElement(timestamp=now, rate=1852.0),
        ]

        response = AppHistoryResponse(app_name="app1", history=history, total_records=2)

        assert response.app_name == "app1"
        assert len(response.history) == 2
        assert response.total_records == 2


class TestHealthCheckResponse:
    """Test HealthCheckResponse model"""

    def test_health_check_response_healthy(self):
        """Test creating healthy HealthCheckResponse"""
        timestamp = datetime.now(timezone.utc)
        last_update = timestamp

        response = HealthCheckResponse(
            status="healthy",
            database="connected",
            last_update=last_update,
            timestamp=timestamp,
            uptime="0:05:30",
            mongo_ping="5.5 ms",
        )

        assert response.status == "healthy"
        assert response.database == "connected"
        assert response.last_update == last_update

    def test_health_check_response_unhealthy(self):
        """Test creating unhealthy HealthCheckResponse"""
        timestamp = datetime.now(timezone.utc)

        response = HealthCheckResponse(
            status="unhealthy",
            database="connection error",
            last_update=None,
            timestamp=timestamp,
            uptime="0:05:30",
            mongo_ping="timeout",
        )

        assert response.status == "unhealthy"
        assert response.database == "connection error"
        assert response.last_update is None

    def test_health_check_invalid_status(self):
        """Test HealthCheckResponse with invalid status"""
        timestamp = datetime.now(timezone.utc)

        # This should raise ValidationError due to invalid status
        with pytest.raises(ValidationError):
            HealthCheckResponse(
                status="invalid_status",  # Should be "healthy" or "unhealthy"
                database="connected",
                last_update=None,
                timestamp=timestamp,
                uptime="0:05:30",
                mongo_ping="5.5 ms",
            )
