"""Unit tests for infrastructure shared utilities."""

import pytest


class TestRateLimiter:
    """Tests for RateLimiter utility."""

    @pytest.mark.unit
    def test_rate_limiter_import(self) -> None:
        """RateLimiter should be importable."""
        from deeplecture.infrastructure.shared import RateLimiter

        assert RateLimiter is not None


class TestRetryConfig:
    """Tests for retry configuration."""

    @pytest.mark.unit
    def test_retry_config_import(self) -> None:
        """RetryConfig should be importable."""
        from deeplecture.infrastructure.shared import RetryConfig

        assert RetryConfig is not None

    @pytest.mark.unit
    def test_retry_config_creation(self) -> None:
        """RetryConfig should accept required parameters."""
        from deeplecture.infrastructure.shared import RetryConfig

        config = RetryConfig(max_retries=3, min_wait=1.0, max_wait=60.0)
        assert config.max_retries == 3
        assert config.min_wait == 1.0
        assert config.max_wait == 60.0

    @pytest.mark.unit
    def test_retry_config_validation(self) -> None:
        """RetryConfig should maintain invariant: max_wait >= min_wait."""
        from deeplecture.infrastructure.shared import RetryConfig

        config = RetryConfig(max_retries=5, min_wait=2.0, max_wait=120.0)
        assert config.max_wait >= config.min_wait
