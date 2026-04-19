import os
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("DATABASE_URL", "sqlite://").startswith("sqlite"),
    reason="Clustering requires PostGIS — skipped on SQLite"
)

from unittest.mock import MagicMock
from app.services.clustering_service import cluster_complaints, get_hotspots
from app.models.models import Complaint

def test_python_clustering_logic():
    """Test the Python fallback clustering (used for non-Postgres DBs)."""
    db = MagicMock()
    # Mock dialect to be anything except postgresql to trigger fallback
    db.bind.dialect.name = "sqlite"
    
    # Create mock complaints
    c1 = Complaint(latitude=12.9716, longitude=77.5946, severity="high", damage_type="pothole", status="pending")
    c2 = Complaint(latitude=12.9717, longitude=77.5947, severity="critical", damage_type="pothole", status="pending")
    c3 = Complaint(latitude=13.0000, longitude=77.6000, severity="low", damage_type="crack", status="pending")
    
    db.query.return_value.filter.return_value.all.return_value = [c1, c2, c3]
    
    # 500m grid should group c1 and c2 together, c3 separate
    clusters = cluster_complaints(db, grid_size_meters=500)
    
    assert len(clusters) == 2
    
    # Find the cluster with 2 complaints
    big_cluster = next(c for c in clusters if c.count == 2)
    assert big_cluster.dominant_damage_type == "pothole"
    assert big_cluster.max_severity == "critical"
    # high(3) + critical(5) = 8
    assert big_cluster.weight == 8.0

def test_hotspot_filtering():
    """Test that min_count filter works correctly."""
    db = MagicMock()
    db.bind.dialect.name = "sqlite"
    
    c1 = Complaint(latitude=12.9716, longitude=77.5946, severity="low", damage_type="pothole", status="pending", complaint_id="RD-01")
    c2 = Complaint(latitude=12.9716, longitude=77.5946, severity="low", damage_type="pothole", status="pending", complaint_id="RD-02")
    
    db.query.return_value.filter.return_value.all.return_value = [c1, c2]
    
    # clusters will have 1 entry with count 2
    # get_hotspots with min_count=3 should return empty
    hotspots_none = get_hotspots(db, min_count=3)
    assert len(hotspots_none) == 0
    
    # min_count=2 should return it
    hotspots_ok = get_hotspots(db, min_count=2)
    assert len(hotspots_ok) == 1
    assert hotspots_ok[0].count == 2
    assert hotspots_ok[0].estimated_repair_cost == 100000.0 # 2 * 50000
