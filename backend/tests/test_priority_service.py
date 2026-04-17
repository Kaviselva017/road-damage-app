import pytest
from unittest.mock import MagicMock
from app.services.priority_service import calculate_priority_score

def test_hospital_nearby_priority():
    """Test that mentions of 'hospital' yield a critical/high score."""
    db = MagicMock()
    result = calculate_priority_score(
        damage_type="subsidence",
        severity="high",
        confidence=0.9,
        area_type="commercial",
        nearby_sensitive="city hospital, main gate",
        report_count=1,
        latitude=0.0,
        longitude=0.0,
        weather_risk=0.0,
        db=db
    )
    # subsidence(25) + severity high(20 max) + hospital(20) + count(3) + ai(9) = 77
    assert result["score"] >= 70
    assert result["urgency_label"] in ["high", "critical"]

def test_low_severity_no_context():
    """Test a minor pothole with no special context."""
    db = MagicMock()
    result = calculate_priority_score(
        damage_type="crack",
        severity="low",
        confidence=0.8,
        area_type="residential",
        nearby_sensitive="",
        report_count=1,
        latitude=0.0,
        longitude=0.0,
        weather_risk=0.0,
        db=db
    )
    # crack(8) + low multiplier(8 * 0.5 = 4) + residential(5) + count(3) + ai(8) = 28
    assert result["score"] < 30
    assert result["urgency_label"] == "low"

def test_report_volume_bonus():
    """Test that multiple reports significantly bump the score."""
    db = MagicMock()
    # Base case: 1 report
    res1 = calculate_priority_score("pothole", "medium", 1.0, "res", "", 1, 0, 0, 0, db)
    # Volume case: 5 reports
    res5 = calculate_priority_score("pothole", "medium", 1.0, "res", "", 5, 0, 0, 0, db)
    
    # 5 reports should add roughly 12 pts over 1 report (4 * 3)
    assert res5["score"] > res1["score"]
    assert res5["factors"]["volume_bonus"] == 15.0

def test_weather_risk_impact():
    """Test that weather risk (e.g. rain) increases priority."""
    db = MagicMock()
    # No rain
    res0 = calculate_priority_score("pothole", "medium", 1.0, "res", "", 1, 0, 0, 0.0, db)
    # 80% chance of rain
    res8 = calculate_priority_score("pothole", "medium", 1.0, "res", "", 1, 0, 0, 0.8, db)
    
    assert res8["score"] == res0["score"] + 8.0
    assert res8["factors"]["weather_risk_factor"] == 8.0
