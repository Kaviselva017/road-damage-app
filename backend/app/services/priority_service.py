import logging
from typing import Dict, TypedDict
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class PriorityResult(TypedDict):
    score: float
    urgency_label: str
    factors: Dict[str, float]
    recommended_sla_hours: int

def calculate_priority_score(
    damage_type: str,
    severity: str,
    confidence: float,
    area_type: str,
    nearby_sensitive: str,
    report_count: int,
    latitude: float,
    longitude: float,
    weather_risk: float,
    db: Session
) -> PriorityResult:
    """
    Calculates a weighted priority score from 0-100 based on physical and contextual factors.
    """
    factors = {}
    
    # 1. Damage Type Base (25 pts max)
    damage_bases = {
        "pothole": 15,
        "crack": 8,
        "subsidence": 25,
        "flooding": 20,
        "debris": 10
    }
    base_score = damage_bases.get(damage_type.lower(), 10)
    factors["damage_base"] = float(base_score)
    
    # 2. Severity Multiplier (20 pts max)
    # Scales the damage base score.
    severity_multipliers = {
        "low": 0.5,
        "medium": 1.0,
        "high": 1.5,
        "critical": 2.0
    }
    mult = severity_multipliers.get(severity.lower(), 1.0)
    severity_contribution = min(base_score * mult, 20)
    factors["severity_bonus"] = float(severity_contribution)
    
    # 3. Sensitive Area Bonus (20 pts max)
    area_bonus = 0
    area_t = area_type.lower()
    nearby = nearby_sensitive.lower()
    
    if "hospital" in nearby: area_bonus = max(area_bonus, 20)
    elif "school" in nearby: area_bonus = max(area_bonus, 15)
    elif "highway" in area_t: area_bonus = max(area_bonus, 18)
    elif "commercial" in area_t: area_bonus = max(area_bonus, 8)
    elif "residential" in area_t: area_bonus = max(area_bonus, 5)
    
    factors["area_bonus"] = float(area_bonus)
    
    # 4. Report Count Bonus (15 pts max)
    count_bonus = min(max(report_count, 1) * 3, 15)
    factors["volume_bonus"] = float(count_bonus)
    
    # 5. AI Confidence Factor (10 pts max)
    ai_bonus = confidence * 10
    factors["ai_confidence_factor"] = float(ai_bonus)
    
    # 6. Weather Risk Bonus (10 pts max)
    weather_bonus = weather_risk * 10
    factors["weather_risk_factor"] = float(weather_bonus)
    
    total_score = min(
        factors["damage_base"] + 
        factors["severity_bonus"] + 
        factors["area_bonus"] + 
        factors["volume_bonus"] + 
        factors["ai_confidence_factor"] + 
        factors["weather_risk_factor"], 
        100
    )
    
    # Urgency Label & SLA
    if total_score >= 80:
        label = "critical"
        sla = 4
    elif total_score >= 60:
        label = "high"
        sla = 24
    elif total_score >= 35:
        label = "medium"
        sla = 48
    else:
        label = "low"
        sla = 72
        
    return {
        "score": round(total_score, 1),
        "urgency_label": label,
        "factors": factors,
        "recommended_sla_hours": sla
    }
