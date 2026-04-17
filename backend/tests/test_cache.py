import pytest
from unittest.mock import AsyncMock, patch
from app.api import complaints
from app.utils import cache_keys

@pytest.mark.asyncio
async def test_nearby_query_is_cached():
    """Verify that cached data is returned instead of hitting the DB on second call."""
    mock_db = AsyncMock()
    mock_cache = AsyncMock()
    
    # First call - cache miss
    mock_cache.get.return_value = None
    
    with patch("app.services.cache_service.cache", mock_cache):
        with patch("app.services.geo_service.find_nearby_complaints") as mock_geo:
            mock_geo.return_value = []
            
            await complaints.get_nearby_complaints(
                lat=12.9716, lng=77.5946, radius=500, db=mock_db
            )
            
            # Should have called geo service
            mock_geo.assert_called_once()
            # Should have set the cache
            mock_cache.set.assert_called_once()
            
            # Second call - cache hit
            mock_cache.get.return_value = [{"id": 1, "complaint_id": "RD1"}]
            
            res = await complaints.get_nearby_complaints(
                lat=12.9716, lng=77.5946, radius=500, db=mock_db
            )
            
            # Geo service should NOT have been called again
            assert mock_geo.call_count == 1
            assert res[0]["complaint_id"] == "RD1"

@pytest.mark.asyncio
async def test_cache_invalidated_on_submission():
    """Verify that patterns are deleted after a new complaint is submitted."""
    mock_cache = AsyncMock()
    
    with patch("app.services.cache_service.cache", mock_cache):
        with patch("app.services.ai_service.image_hash", return_value="hash"):
            with patch("app.services.geo_service.find_duplicate_complaint", return_value=False):
                # We need to mock the DB and some other things that happen during submission
                import uuid
                mock_request = AsyncMock()
                mock_bg = AsyncMock()
                mock_db = AsyncMock()
                mock_user = AsyncMock(id=1)
                mock_file = AsyncMock(filename="test.jpg", content_type="image/jpeg")
                mock_file.read.return_value = b"bytes"
                
                # Mock validate_image
                async def mock_val(img): return b"bytes", None
                
                with patch("app.utils.file_validators.validate_image", side_effect=mock_val):
                    await complaints.submit(
                        request=mock_request,
                        background_tasks=mock_bg,
                        latitude=12.97,
                        longitude=77.59,
                        nearby_sensitive="School",
                        image=mock_file,
                        db=mock_db,
                        user=mock_user
                    )
                
                # Verify invalidation calls were added to background tasks
                # Note: In our implementation, we use background_tasks.add_task(cache.delete_pattern, ...)
                assert mock_bg.add_task.call_count >= 2
                calls = [c[0][1] for c in mock_bg.add_task.call_args_list]
                assert cache_keys.NEARBY_PATTERN in calls
                assert cache_keys.COMPLAINTS_LIST_PATTERN in calls
