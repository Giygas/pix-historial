from datetime import datetime, timedelta

from app.rate_limiter import InMemoryRateLimiter


class TestInMemoryRateLimiter:
    """Test the in-memory rate limiter"""

    def setup_method(self):
        """Setup for each test"""
        self.limiter = InMemoryRateLimiter()

    def test_is_allowed_first_request(self):
        """Test that first request is always allowed"""
        assert self.limiter.is_allowed("test_key") is True

    def test_is_allowed_under_limit(self):
        """Test requests under the limit are allowed"""
        # Make requests up to limit - 1
        for _ in range(99):
            assert self.limiter.is_allowed("test_key") is True

    def test_is_allowed_over_limit(self):
        """Test requests over the limit are blocked"""
        # Make requests up to limit
        for _ in range(100):
            self.limiter.is_allowed("test_key")

        # Next request should be blocked
        assert self.limiter.is_allowed("test_key") is False

    def test_different_keys_independent(self):
        """Test that different keys are rate limited independently"""
        # Exhaust limit for first key
        for _ in range(100):
            self.limiter.is_allowed("key1")

        # First key should be blocked
        assert self.limiter.is_allowed("key1") is False

        # Second key should still be allowed
        assert self.limiter.is_allowed("key2") is True

    def test_window_expiration(self):
        """Test that old requests expire after window"""
        # Exhaust limit
        for _ in range(100):
            self.limiter.is_allowed("test_key")

        # Should be blocked
        assert self.limiter.is_allowed("test_key") is False

        # Simulate time passing by manipulating internal state
        # Set all requests to be older than window
        old_time = datetime.now() - timedelta(seconds=120)
        self.limiter.requests["test_key"] = [old_time] * 100

        # Should now be allowed again
        assert self.limiter.is_allowed("test_key") is True

    def test_get_remaining_requests(self):
        """Test getting remaining requests count"""
        # Initially should have full limit
        assert self.limiter.get_remaining_requests("new_key") == 100

        # After some requests
        for _ in range(30):
            self.limiter.is_allowed("test_key")

        assert self.limiter.get_remaining_requests("test_key") == 70

        # After exhausting limit
        for _ in range(70):
            self.limiter.is_allowed("test_key")

        assert self.limiter.get_remaining_requests("test_key") == 0
