"""Database configuration and SQLAlchemy ORM models."""
import os
os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    Index,
    ForeignKey,
    event
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Default to SQLite database in data directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "experience_recorder.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False
)

# Enable foreign key support in SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Branch(Base):
    """Branch metadata table."""
    __tablename__ = "branches"

    branch_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    region = Column(String(50), nullable=False)
    wan_type = Column(String(50), default="MPLS Primary")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    events = relationship("Event", back_populates="branch", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="branch", cascade="all, delete-orphan")
    user_reports = relationship("UserReport", back_populates="branch", cascade="all, delete-orphan")


class Event(Base):
    """Raw telemetry and probe events from all simulated sources."""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    event_time = Column(DateTime, nullable=False, index=True)
    arrival_time = Column(DateTime, nullable=False)
    branch_id = Column(String(50), ForeignKey("branches.branch_id"), nullable=False, index=True)
    source = Column(String(50), nullable=False)  # ACTIVE_PROBE, WIFI, APPLICATION, USER_REPORT

    # Active Probe Metrics
    latency_ms = Column(Float, nullable=True)
    jitter_ms = Column(Float, nullable=True)
    packet_loss_percent = Column(Float, nullable=True)
    dns_response_ms = Column(Float, nullable=True)

    # Wi-Fi Metrics
    wifi_rssi = Column(Float, nullable=True)
    wifi_retry_rate = Column(Float, nullable=True)
    channel_utilisation = Column(Float, nullable=True)

    # Application Monitor Metrics
    application_response_ms = Column(Float, nullable=True)
    http_status = Column(Integer, nullable=True)
    transaction_duration_ms = Column(Float, nullable=True)

    # User Report Reference / Text
    user_report = Column(Text, nullable=True)
    sequence_number = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship
    branch = relationship("Branch", back_populates="events")

    __table_args__ = (
        Index("idx_events_branch_time", "branch_id", "event_time"),
        Index("idx_events_source", "source"),
    )


class Incident(Base):
    """Recorded incidents representing detected degradations and forensic evidence."""
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(64), unique=True, nullable=False, index=True)
    branch_id = Column(String(50), ForeignKey("branches.branch_id"), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(30), nullable=False, default="SUSPECTED")  # NORMAL, SUSPECTED, ACTIVE, RECOVERED
    probable_cause = Column(String(100), nullable=False)
    peak_latency = Column(Float, nullable=True)
    peak_packet_loss = Column(Float, nullable=True)
    peak_application_response = Column(Float, nullable=True)
    user_report_count = Column(Integer, default=0)
    severity = Column(String(20), nullable=False, default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    supporting_evidence = Column(Text, nullable=True)  # JSON-formatted detailed evidence breakdown
    duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship
    branch = relationship("Branch", back_populates="incidents")

    __table_args__ = (
        Index("idx_incidents_branch_status", "branch_id", "status"),
        Index("idx_incidents_start_time", "start_time"),
    )


class UserReport(Base):
    """User complaints submitted from branches."""
    __tablename__ = "user_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String(64), unique=True, nullable=False, index=True)
    branch_id = Column(String(50), ForeignKey("branches.branch_id"), nullable=False, index=True)
    event_time = Column(DateTime, nullable=False, index=True)
    location = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), default="HIGH")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    branch = relationship("Branch", back_populates="user_reports")


class EventProcessingLog(Base):
    """Audit log tracking collector validation, deduplication, and anomaly handling."""
    __tablename__ = "event_processing_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), nullable=False, index=True)
    processing_status = Column(String(50), nullable=False)  # VALID, DUPLICATE_REJECTED, OUT_OF_ORDER, DELAYED, VALIDATION_FAILED, BUFFERED, RECOVERED
    reason = Column(Text, nullable=True)
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db(target_engine=None):
    """Initialise database tables."""
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)


def get_db():
    """FastAPI and service dependency to yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
