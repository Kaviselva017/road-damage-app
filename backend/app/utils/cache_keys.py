"""
Cache Key Constants
"""

# Nearby queries grouping key
# Grouped by rounded lat/lng (3 decimals ~ 111m)
NEARBY_QUERY_KEY = "complaints:nearby:{lat}:{lng}:{radius}"
NEARBY_PATTERN = "complaints:nearby:*"

# Complaints list grouping key
COMPLAINTS_LIST_KEY = "complaints:list:{page}:{status}"
COMPLAINTS_LIST_PATTERN = "complaints:list:*"

# Individual complaint detail
COMPLAINT_DETAIL_KEY = "complaint:detail:{cid}"


def get_nearby_key(lat: float, lng: float, radius: int) -> str:
    # Round to 3 decimal places to increase cache hit rate for nearby users
    return NEARBY_QUERY_KEY.format(lat=round(lat, 3), lng=round(lng, 3), radius=radius)


def get_list_key(page: int, status_filter: str) -> str:
    return COMPLAINTS_LIST_KEY.format(page=page, status=status_filter or "all")
