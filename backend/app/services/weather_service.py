import logging
import httpx
from typing import Optional
from app.services.cache_service import cache

logger = logging.getLogger(__name__)

async def fetch_weather_risk(lat: float, lng: float) -> float:
    """
    Fetches the 24h max precipitation probability from Open-Meteo.
    Returns a normalized value between 0.0 and 1.0.
    """
    cache_key = f"weather:{round(lat, 2)}:{round(lng, 2)}"
    
    # Try cache first
    cached_val = await cache.get(cache_key)
    if cached_val is not None:
        try:
            return float(cached_val)
        except: pass

    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lng}&hourly=precipitation_probability&forecast_days=1"
        )
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            
            probs = data.get("hourly", {}).get("precipitation_probability", [])
            if not probs:
                return 0.0
            
            # Max probability in next 24h (normalized 0-1)
            max_prob = max(probs) / 100.0
            
            # Cache for 1 hour
            await cache.set(cache_key, str(max_prob), ttl_seconds=3600)
            return max_prob
            
    except Exception as e:
        logger.error(f"Weather API Fetch Failed: {e}")
        return 0.0
