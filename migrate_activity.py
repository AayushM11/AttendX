import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine
from sqlalchemy import text

migrations = [
    """
    CREATE TABLE IF NOT EXISTS activity_heartbeats (
        id            SERIAL PRIMARY KEY,
        employee_id   INTEGER REFERENCES employees(id) ON DELETE CASCADE,
        timestamp     TIMESTAMP NOT NULL,
        is_idle       BOOLEAN DEFAULT FALSE,
        idle_seconds  FLOAT DEFAULT 0,
        mouse_moves   INTEGER DEFAULT 0,
        key_presses   INTEGER DEFAULT 0,
        active_app    VARCHAR(200),
        os            VARCHAR(20),
        agent_version VARCHAR(20),
        created_at    TIMESTAMP DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_heartbeat_emp_ts ON activity_heartbeats(employee_id, timestamp)",

    """
    CREATE TABLE IF NOT EXISTS activity_app_logs (
        id          SERIAL PRIMARY KEY,
        employee_id INTEGER REFERENCES employees(id) ON DELETE CASCADE,
        date        DATE NOT NULL,
        app_name    VARCHAR(200) NOT NULL,
        seconds     INTEGER DEFAULT 0,
        updated_at  TIMESTAMP DEFAULT NOW(),
        UNIQUE(employee_id, date, app_name)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_applog_emp_date ON activity_app_logs(employee_id, date)",

    """
    CREATE TABLE IF NOT EXISTS activity_daily_summaries (
        id              SERIAL PRIMARY KEY,
        employee_id     INTEGER REFERENCES employees(id) ON DELETE CASCADE,
        date            DATE NOT NULL,
        active_seconds  INTEGER DEFAULT 0,
        idle_seconds    INTEGER DEFAULT 0,
        total_seconds   INTEGER DEFAULT 0,
        active_pct      FLOAT DEFAULT 0,
        mouse_moves     INTEGER DEFAULT 0,
        key_presses     INTEGER DEFAULT 0,
        top_app         VARCHAR(200),
        heartbeat_count INTEGER DEFAULT 0,
        updated_at      TIMESTAMP DEFAULT NOW(),
        UNIQUE(employee_id, date)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_summary_emp_date ON activity_daily_summaries(employee_id, date)",
]

print("Running activity tracking migrations...")
with engine.connect() as conn:
    for sql in migrations:
        try:
            conn.execute(text(sql.strip()))
            conn.commit()
            print(f"  ✓ {sql.strip().split(chr(10))[0][:70]}")
        except Exception as e:
            conn.rollback()
            print(f"  · Already exists / skipped: {str(e)[:80]}")

print("\n✅ Activity tables ready!")
print("   Now restart uvicorn and deploy activity_agent.py to employee PCs.")