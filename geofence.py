import math
from typing import Tuple, Optional
from sqlalchemy.orm import Session


def harvesine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two GPS coordinates in meters.
    Uses the harvesine formula - accurate for short distances.
    """
    R = 6_371_000 # Earth radius in meteers

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def get_company_settings(db: Session) -> dict:
    """
    Load Geofence settings from DB. return defaults if not configured
    always return a dict with keys: lat, lng, radius_m, enabled, name
    """
    #safe defult - return on any error
    defaults = {
        "lat": 22.55636568111515, 
        "lng": 72.95267951534373,
        "radius_m" : 100.0,
        "enabled": True,
        "name": "Company HQ"
    }

    try:
        from sqlalchemy import text
        rows = db.execute(text("SELECT key, value FROM company_settings")).fetchall()
        if not rows:
            return defaults
        raw = {row[0]: row[1] for row in rows}
        return {
            "lat":      float(raw.get("company_lat",  defaults["lat"])),
            "lng":      float(raw.get("company_lng",  defaults["lng"])),
            "radius_m": float(raw.get("geo_radius_m", defaults["radius_m"])),
            # Fix: was "enables" (typo) — now correctly "enabled"
            "enabled":  raw.get("geo_enabled", "true").strip().lower() == "true",
            "name":     raw.get("company_name", defaults["name"]),
        }
    
    except Exception as e:
        print(f"[Geofence] could not load settigs:{e} - using defaults")

        return defaults
    
def check_geofence(
        employee_lat: float,
        employee_lng: float,
        db: Session,
)->  Tuple[bool, float, dict]:
    """
    Check if employee is within company geofence.

    Returns:
        (is_inside, distance_meters, settings)
    """
    settings = get_company_settings(db)

    if not settings["enabled"]:
        return True, 0.0, settings
    
    distance = harvesine_distance(
        employee_lat, employee_lng,
        settings["lat"], settings["lng"]
    )

    is_inside = distance <= settings["radius_m"]
    return is_inside, round(distance, 1), settings

