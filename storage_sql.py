from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from models import init_db, get_engine, Config
import os

APP_DIR = Path.home() / ".client_app"
DB_PATH = APP_DIR / "configs.db"

_engine = None
_SessionFactory = None

def setup(db_path: Path = DB_PATH):
    global _engine, _SessionFactory
    _engine = init_db(db_path)
    _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)

def get_session():
    if _SessionFactory is None:
        setup()
    return _SessionFactory()

def add_config_dict(data: dict):
    session = get_session()
    cfg = Config(
        name=data.get("name") or "Untitled",
        cpu=data.get("cpu"),
        gpu=data.get("gpu"),
        ram=data.get("ram"),
        mem=data.get("mem"),
        watts=str(data.get("watts", "")),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    session.close()
    return cfg.id

def get_all_configs():
    session = get_session()
    rows = session.query(Config).order_by(Config.created_at.desc()).all()
    result = []
    for r in rows:
        result.append({
            "id": r.id,
            "name": r.name,
            "cpu": r.cpu,
            "gpu": r.gpu,
            "ram": r.ram,
            "mem": r.mem,
            "watts": r.watts,
            "created_at": r.created_at.isoformat() if r.created_at else None
        })
    session.close()
    return result

def delete_config(cfg_id: int):
    if cfg_id is None:
        return
    session = get_session()
    session.query(Config).filter(Config.id == cfg_id).delete()
    session.commit()
    session.close()

def rename_config(cfg_id: int, new_name: str):
    session = get_session()
    cfg = session.get(Config, cfg_id)
    if cfg:
        cfg.name = new_name
        cfg.updated_at = datetime.utcnow()
        session.commit()
    session.close()

def get_config(cfg_id: int):
    session = get_session()
    cfg = session.get(Config, cfg_id)
    if not cfg:
        session.close()
        return None
    result = {
        "id": cfg.id, "name": cfg.name, "cpu": cfg.cpu, "gpu": cfg.gpu,
        "ram": cfg.ram, "mem": cfg.mem, "watts": cfg.watts,
        "created_at": cfg.created_at.isoformat() if cfg.created_at else None
    }
    session.close()
    return result
