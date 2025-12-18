"""Unit tests for DI container wiring."""

import pytest


class TestContainerWiring:
    """Tests for DI container smoke checks."""

    @pytest.mark.unit
    def test_container_import(self) -> None:
        """Container should be importable without side effects."""
        from deeplecture.di.container import Container, get_container, reset_container

        assert Container is not None
        assert get_container is not None
        assert reset_container is not None

    @pytest.mark.unit
    def test_reset_container(self) -> None:
        """reset_container should clear container cache."""
        from deeplecture.di.container import get_container, reset_container

        # Get initial container
        container1 = get_container()

        # Reset and get new container
        reset_container()
        container2 = get_container()

        # Should be different instances after reset
        assert container1 is not container2
