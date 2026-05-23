from sqlalchemy import Column, Integer, String, Date, DateTime, Float, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(200))
    created_at = Column(DateTime, default=func.now())


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    employees = relationship("Employee", back_populates="department")


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    embedding = Column(Text, nullable=False)
    image_path = Column(String(500))
    created_at = Column(DateTime, default=func.now())

    employee = relationship("Employee", back_populates="face_embeddings")


class LeaveType(Base):
    __tablename__ = "leave_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    max_days = Column(Integer, default=12)
    leave_requests = relationship("LeaveRequest", back_populates="leave_type")


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), unique=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    phone = Column(String(20))
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    designation = Column(String(100))
    date_of_joining = Column(Date)
    profile_image = Column(String(500))
    is_active = Column(Boolean, default=True)
    self_registered = Column(Boolean, default=False)  # True = registered via app
    created_at = Column(DateTime, default=func.now())

    department = relationship("Department", back_populates="employees")
    face_embeddings = relationship("FaceEmbedding", back_populates="employee", cascade="all, delete-orphan")
    attendances = relationship("Attendance", back_populates="employee", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="employee", cascade="all, delete-orphan")

    activity_heartbeats = relationship("ActivityHeartbeat", back_populates="employee", cascade="all, delete-orphan")
    activity_app_logs = relationship("ActivityAppLog", back_populates = "employee", cascade = "all, delete-orphan")
    activity_daily_summaries = relationship("ActivityDailySummary", back_populates = "employee", cascade = "all, delete-orphan")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    date = Column(Date, nullable=False)
    check_in = Column(DateTime)
    check_out = Column(DateTime)
    status = Column(String(20), default="present")
    work_hours = Column(Float, default=0.0)
    notes = Column(Text)

    #geofence columns 
    latitude = Column(Float, nullable= True)
    longitude = Column(Float, nullable = True)
    distance_meters = Column(Float, nullable = True)
    location_verified = Column(Boolean, default = False)

    employee = relationship("Employee", back_populates="attendances")


class Holiday(Base):
    __tablename__ = "holidays"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    date = Column(Date, nullable=False, unique=True)
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(Text)
    status = Column(String(20), default="pending")
    admin_comment = Column(Text)
    applied_at = Column(DateTime, default=func.now())
    reviewed_at = Column(DateTime)

    employee = relationship("Employee", back_populates="leave_requests")
    leave_type = relationship("LeaveType", back_populates="leave_requests")

class ActivityHeartbeat(Base):
    __tablename__ = "activity_heartbeats"

    id = Column(Integer, primary_key = True, index = True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable= False)
    timestamp = Column(DateTime, nullable= False, index = True)
    is_idle = Column(Boolean, default = False)
    idle_seconds = Column(Float, default = 0)
    mouse_moves = Column(Integer, default = 0)
    key_presses = Column(Integer, default = 0)
    active_app = Column(String(200))
    os = Column(String(20))
    agent_version = Column(String(20))
    created_at = Column(DateTime, default = func.now())

    employee = relationship("Employee", back_populates = "activity_heartbeats")


class ActivityAppLog(Base):
    __tablename__ = "activity_app_logs"

    id = Column(Integer, primary_key = True, index = True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable = False)
    date = Column(Date, nullable = False, index = True)
    app_name = Column(String(200), nullable=False)
    seconds = Column(Integer, default = 0)
    updated_at = Column(DateTime, default = func.now(), onupdate = func.now())

    employee = relationship("Employee", back_populates = "activity_app_logs")


class ActivityDailySummary(Base):
    __tablename__ = "activity_daily_summaries"

    id = Column(Integer, primary_key = True, index = True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable = False)
    date = Column(Date, nullable = False, index = True)
    active_seconds = Column(Integer, default = 0)
    idle_seconds = Column(Integer, default = 0)
    total_seconds = Column(Integer, default = 0)
    active_pct = Column(Float, default = 0)
    mouse_moves = Column(Integer, default = 0)
    key_presses = Column(Integer, default = 0)
    top_app = Column(String(200))
    heartbeat_count = Column(Integer, default = 0)
    updated_at = Column(DateTime, default = func.now(), onupdate = func.now())

    employee = relationship("Employee", back_populates="activity_daily_summaries")
