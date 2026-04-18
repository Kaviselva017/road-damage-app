from prometheus_client import Counter, Gauge, Histogram

# --- Counters ---
COMPLAINTS_SUBMITTED_TOTAL = Counter("complaints_submitted_total", "Total number of complaints submitted", ["area_type", "status"])

COMPLAINTS_DUPLICATE_TOTAL = Counter(
    "complaints_duplicate_total",
    "Total number of duplicate complaints detected",
    ["detection_method"],  # 'hash' or 'geo'
)

AI_INFERENCE_TOTAL = Counter(
    "ai_inference_total",
    "Total number of AI inference attempts",
    ["result"],  # 'detected', 'undetected', 'failed'
)

# --- Histograms ---
AI_INFERENCE_DURATION_SECONDS = Histogram("ai_inference_duration_seconds", "Time spent running YOLOv8 inference", ["damage_type"], buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, float("inf")))

COMPLAINT_SUBMISSION_DURATION_SECONDS = Histogram("complaint_submission_duration_seconds", "End-to-end duration of the submission API call (request-response)", buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, float("inf")))

# --- Gauges ---
ACTIVE_WEBSOCKET_CONNECTIONS = Gauge("active_websocket_connections", "Current number of active WebSocket connections for live status updates")

REDIS_CACHE_TOTAL = Counter(
    "redis_cache_access_total",
    "Total number of Redis cache access attempts",
    ["result"],  # 'hit', 'miss'
)


# Helper to calculate ratio indirectly via Prometheus queries
def track_redis_access(hit: bool):
    REDIS_CACHE_TOTAL.labels(result="hit" if hit else "miss").inc()
