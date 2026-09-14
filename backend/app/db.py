"""SQLite for the Sept 16 demo build. PostgreSQL is the stated production
choice (see architecture-document.md §2) - swapping later is a connection
string + dialect change, not a rearchitecture, since everything above this
file talks to SQLAlchemy sessions, not to SQLite directly."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./sentra.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401  (ensures models are registered on Base)
    Base.metadata.create_all(bind=engine)
