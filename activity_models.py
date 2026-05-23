from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class ActivityHeartbeat(Base):
    """
    Raw heartbeat record sent by the desktop agent every 30 seconds.
    Stores what app was active and whether the user was idle/active.
    """
    __tablename__ = "activity_heartbeats"

    id            = Column(Integer, primary_key=True, index=True)
    employee_id   = Column(Integer, ForeignKey("employees.id"), nullable=False)
    timestamp     = Column(DateTime, nullable=False, index=True)
    is_idle       = Column(Boolean, default=False)
    idle_seconds  = Column(Float, default=0.0)
    mouse_moves   = Column(Integer, default=0)
    key_presses   = Column(Integer, default=0)
    active_app    = Column(String(200))
    os            = Column(String(20))
    agent_version = Column(String(20))
    created_at    = Column(DateTime, default=func.now())

    employee = relationship("Employee", back_populates="activity_heartbeats")


class ActivityAppLog(Base):
    """
    Per-app time log derived from each heartbeat.
    e.g. employee spent 120s in Chrome during one 30s heartbeat window.
    """
    __tablename__ = "activity_app_logs"

    id          = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    date        = Column(Date, nullable=False, index=True)
    app_name    = Column(String(200), nullable=False)
    seconds     = Column(Integer, default=0)   # total seconds for this app on this date
    updated_at  = Column(DateTime, default=func.now(), onupdate=func.now())

    employee = relationship("Employee", back_populates="activity_app_logs")


class ActivityDailySummary(Base):
    """
    Aggregated per-employee per-day summary.
    Recomputed from heartbeats at EOD or on-demand.
    """
    __tablename__ = "activity_daily_summaries"

    id              = Column(Integer, primary_key=True, index=True)
    employee_id     = Column(Integer, ForeignKey("employees.id"), nullable=False)
    date            = Column(Date, nullable=False, index=True)
    active_seconds  = Column(Integer, default=0)
    idle_seconds    = Column(Integer, default=0)
    total_seconds   = Column(Integer, default=0)   # active + idle
    active_pct      = Column(Float, default=0.0)   # 0–100
    mouse_moves     = Column(Integer, default=0)
    key_presses     = Column(Integer, default=0)
    top_app         = Column(String(200))           # most-used app
    heartbeat_count = Column(Integer, default=0)
    updated_at      = Column(DateTime, default=func.now(), onupdate=func.now())

    employee = relationship("Employee", back_populates="activity_daily_summaries")