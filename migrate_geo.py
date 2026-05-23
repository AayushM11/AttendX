import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import engine
from sqlalchemy import text

migrations = [
    """
    CREATE TABLE IF NOT EXISTS company_settings (
        id          SERIAL PRIMARY KEY,
        key         VARCHAR(100) UNIQUE NOT NULL,
        value       TEXT NOT NULL,
        description TEXT,
        updated_at  TIMESTAMP DEFAULT NOW()
    )
    """,
    # Add location column to attendance for audit trail
    "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS latitude  FLOAT",
    "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS longitude FLOAT",
    "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS distance_meters FLOAT",
    "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS location_verified BOOLEAN DEFAULT FALSE",
]

print("Running geofence migrations...")
with engine.connect() as conn:
    for sql in migrations:
        try:
            conn.execute(text(sql.strip()))
            conn.commit()
            print(f"  ✓ {sql.strip().split(chr(10))[0][:70]}")
        except Exception as e:
            conn.rollback()
            print(f"  ⚠ Skipped: {str(e)[:80]}")

# Seed default company location
from database import SessionLocal
db = SessionLocal()
try:
    from sqlalchemy import text as t
    defaults = [
        ("company_lat",    "22.55630805480531",  "Company latitude"),
        ("company_lng",    "72.95262732498357",  "Company longitude"),
        ("geo_radius_m",   "100",                "Geofence radius in meters"),
        ("geo_enabled",    "true",               "Enable geofence check"),
        ("company_name",   "Company HQ",         "Company location name"),
    ]
    for key, value, desc in defaults:
        existing = db.execute(
            text("SELECT id FROM company_settings WHERE key = :k"), {"k": key}
        ).fetchone()
        if not existing:
            db.execute(
                text("INSERT INTO company_settings (key, value, description) VALUES (:k, :v, :d)"),
                {"k": key, "v": value, "d": desc}
            )
            print(f"  ✓ Seeded: {key} = {value}")
        else:
            print(f"  · Already exists: {key}")
    db.commit()
finally:
    db.close()
 
print("\n✅ Migration complete!")
print("   Now restart uvicorn and visit: http://127.0.0.1:8000/admin/geofence")