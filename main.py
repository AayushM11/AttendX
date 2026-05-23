from dotenv import load_dotenv
load_dotenv()   # reads backend/.env into os.environ automatically

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from database import engine, Base
import models
from routes import admin_routes, employee_routes, attendance_routes
from routes.activity_routes import router as activity_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Face Recognition Attendance System", version="2.0.0")

app.include_router(activity_router)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "super-secret-key-change-in-production")
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static", exist_ok=True)
os.makedirs("uploaded_images", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploaded_images", StaticFiles(directory="uploaded_images"), name="uploaded_images")

app.include_router(admin_routes.router)
app.include_router(employee_routes.router)
app.include_router(attendance_routes.router)


@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login")


@app.on_event("startup")
async def seed_data():
    #  Warm up face recognition model 
    # Loads Facenet weights into memory at startup so first registration
    # and first attendance scan are not slow.
    try:
        from recognition import warmup
        warmup()
    except Exception as e:
        print(f"[Startup] Face model warmup failed: {e}")

    #  Verify email is configured 
    mail_user = os.getenv("MAIL_USERNAME")
    mail_pass = os.getenv("MAIL_PASSWORD")
    if mail_user and mail_pass:
        print(f"[Startup] ✅ Email OTP configured: {mail_user}")
    else:
        print("[Startup] ⚠️  Email OTP not configured — OTPs will print to terminal.")
        print("[Startup]    Add MAIL_USERNAME and MAIL_PASSWORD to backend/.env")

    #  Seed default data 
    import hashlib
    from database import SessionLocal
    from models import Admin, Department, LeaveType

    db = SessionLocal()
    try:
        if not db.query(Admin).first():
            db.add(Admin(
                username      = "admin",
                password_hash = hashlib.sha256("admin123".encode()).hexdigest(),
                email         = "admin@company.com"
            ))

        for name in ["Engineering", "HR", "Finance", "Marketing", "Operations", "Sales"]:
            if not db.query(Department).filter(Department.name == name).first():
                db.add(Department(name=name))

        for name, days in [
            ("Casual Leave", 12), ("Sick Leave", 10), ("Earned Leave", 15),
            ("Maternity Leave", 180), ("Paternity Leave", 15)
        ]:
            if not db.query(LeaveType).filter(LeaveType.name == name).first():
                db.add(LeaveType(name=name, max_days=days))

        db.commit()
    finally:
        db.close()
