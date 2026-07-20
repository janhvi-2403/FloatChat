
import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv(override=False)

logger = logging.getLogger(__name__)
Base = declarative_base()


class ArgoProfile(Base):
    __tablename__ = "argo_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    float_id = Column(String(50))
    date = Column(DateTime)
    latitude = Column(Float)
    longitude = Column(Float)
    pressure = Column(JSON)
    temperature = Column(JSON)
    salinity = Column(JSON)
    depth = Column(JSON)


class ArgoMetadata(Base):
    __tablename__ = "argo_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    float_id = Column(String(50), unique=True)
    wmo_id = Column(String(50))
    deploy_date = Column(DateTime)
    deploy_location = Column(String(100))
    instrument_type = Column(String(50))
    description = Column(String(500))


class CachedRequest(Base):
    __tablename__ = "cached_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(String(255), unique=True, index=True)
    query_type = Column(String(50))
    query_payload = Column(JSON)
    result_payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)


class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    path = Column(String(255))
    method = Column(String(20))
    status_code = Column(Integer)
    response_time_ms = Column(Float)
    cache_status = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)


class CacheMetric(Base):
    __tablename__ = "cache_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String(100))
    metric_value = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password123@localhost:5432/floatchat")


def _build_engine(database_url: str):
    if database_url.startswith("postgresql"):
        try:
            return create_engine(database_url, pool_pre_ping=True)
        except SQLAlchemyError as exc:
            logger.warning("PostgreSQL unavailable, falling back to SQLite: %s", exc)
    return create_engine("sqlite:///floatchat.db")


engine = _build_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    try:
        Base.metadata.create_all(engine)
    except SQLAlchemyError as exc:
        logger.warning("Database initialization failed, using fallback DB: %s", exc)


def get_session():
    init_db()
    return SessionLocal()


def get_db_connection():
    return get_session()


init_db()
print("[OK] Database models created successfully!")
