import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine
from sqlalchemy import text

migrations = [
    # Fix admins table
    "ALTER TABLE admins ADD COLUMN IF NOT EXISTS email VARCHAR(200)",
    "ALTER TABLE admins ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()",

    # Fix employees table (add any missing columns)
    "ALTER TABLE employees ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
    "ALTER TABLE employees ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()",
    "ALTER TABLE employees ADD COLUMN IF NOT EXISTS designation VARCHAR(100)",
    "ALTER TABLE employees ADD COLUMN IF NOT EXISTS date_of_joining DATE",
    "ALTER TABLE employees ADD COLUMN IF NOT EXISTS profile_image VARCHAR(500)",
    "ALTER TABLE employees ADD COLUMN IF NOT EXISTS department_id INTEGER",

    # Create new tables if they don't exist at all
    """
    CREATE TABLE IF NOT EXISTS departments (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) UNIQUE NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS leave_types (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        max_days INTEGER DEFAULT 12
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS holidays (
        id SERIAL PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        date DATE UNIQUE NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS face_embeddings (
        id SERIAL PRIMARY KEY,
        employee_id INTEGER REFERENCES employees(id),
        embedding TEXT NOT NULL,
        image_path VARCHAR(500),
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS leave_requests (
        id SERIAL PRIMARY KEY,
        employee_id INTEGER REFERENCES employees(id),
        leave_type_id INTEGER REFERENCES leave_types(id),
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        reason TEXT,
        status VARCHAR(20) DEFAULT 'pending',
        admin_comment TEXT,
        applied_at TIMESTAMP DEFAULT NOW(),
        reviewed_at TIMESTAMP
    )
    """,

    # Fix attendance table
    "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'present'",
    "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS work_hours FLOAT DEFAULT 0.0",
    "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS notes TEXT",
    "ALTER TABLE attendance ADD COLUMN IF NOT EXISTS date DATE",

    # Update email to be unique if it was added fresh
    "UPDATE admins SET email = 'admin@company.com' WHERE email IS NULL",
]

print("Running database migrations...")
with engine.connect() as conn:
    for sql in migrations:
        try:
            conn.execute(text(sql.strip()))
            conn.commit()
            short = sql.strip().split('\n')[0][:80]
            print(f"  ✓ {short}")
        except Exception as e:
            conn.rollback()
            print(f"  ⚠ Skipped (already exists or not needed): {str(e)[:100]}")

print("\n✅ Migration complete! Now run: uvicorn main:app --reload")