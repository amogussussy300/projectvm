from sqlalchemy import Column, Integer, String, DateTime, Text, create_engine
from sqlalchemy.orm import declarative_base
from datetime import datetime
from pathlib import Path

Base = declarative_base()

class Config(Base):
    __tablename__ = "configs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True)
    cpu = Column(String(200))
    gpu = Column(String(200))
    ram = Column(String(100))
    mem = Column(String(100))
    watts = Column(String(50))
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def get_engine(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    uri = f"sqlite:///{str(db_path)}"
    engine = create_engine(uri, future=True)
    return engine


def init_db(db_path: Path):
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine
