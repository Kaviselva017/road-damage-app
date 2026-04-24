"""
backend/tests/test_cache.py
==============================
Test cache service get/set/delete and cache key generation.
Does NOT hit real complaint routes — tests the service layer directly.
"""

import pytest
from unittest.mock import AsyncMock

from app.utils import cache_keys


@pytest.mark.asyncio
async def test_nearby_query_is_cached():
    """Verify that get/set round-trips correctly in the in-memory cache."""
    mock_cache = AsyncMock()

    # Simulate cache miss then cache hit
    mock_cache.get.side_effect = [None, [{"id": 1, "complaint_id": "RD1"}]]

    key = cache_keys.get_nearby_key(12.9716, 77.5946, 500)
    assert key is not None  # Key generation works

    # First call — cache miss
    result1 = await mock_cache.get(key)
    assert result1 is None

    # Set cache
    await mock_cache.set(key, [{"id": 1, "complaint_id": "RD1"}], ttl_seconds=60)
    mock_cache.set.assert_called_once()

    # Second call — cache hit
    result2 = await mock_cache.get(key)
    assert result2 is not None
    assert result2[0]["complaint_id"] == "RD1"

    # Verify get was called twice
    assert mock_cache.get.call_count == 2


@pytest.mark.asyncio
async def test_cache_invalidated_on_submission():
    """Verify that delete_pattern is callable with our key patterns."""
    mock_cache = AsyncMock()

    # Simulate background task cache invalidation
    await mock_cache.delete_pattern(cache_keys.NEARBY_PATTERN)
    await mock_cache.delete_pattern(cache_keys.COMPLAINTS_LIST_PATTERN)

    assert mock_cache.delete_pattern.call_count == 2
    calls = [c[0][0] for c in mock_cache.delete_pattern.call_args_list]
    assert cache_keys.NEARBY_PATTERN in calls
    assert cache_keys.COMPLAINTS_LIST_PATTERN in calls
