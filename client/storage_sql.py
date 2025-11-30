# storage_sql.py
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from sqlalchemy import inspect, text
from models import init_db, get_engine, Config
import json

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
    try:
        psus = data.get("psus", None)
        psus_text = None
        if psus is not None:
            if isinstance(psus, str):
                try:
                    json.loads(psus)
                    psus_text = psus
                except Exception:
                    psus_text = json.dumps(psus, ensure_ascii=False)
            else:
                psus_text = json.dumps(psus, ensure_ascii=False)

        cfg = Config(
            name=data.get("name") or "Untitled",
            cpu=data.get("cpu"),
            gpu=data.get("gpu"),
            ram=data.get("ram"),
            mem=data.get("mem"),
            watts=str(data.get("watts", "")),
            psus=psus_text,
            created_at=data.get("created_at") or datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(cfg)
        session.commit()
        session.refresh(cfg)
        new_id = cfg.id
    finally:
        session.close()
    return new_id


def update_config_psus(config_id: int, psus):
    session = get_session()
    try:
        cfg = session.get(Config, config_id)
        if not cfg:
            return False
        if psus is None:
            cfg.psus = None
        else:
            if isinstance(psus, str):
                try:
                    json.loads(psus)
                    cfg.psus = psus
                except Exception:
                    cfg.psus = json.dumps(psus, ensure_ascii=False)
            else:
                cfg.psus = json.dumps(psus, ensure_ascii=False)
        cfg.updated_at = datetime.utcnow()
        session.commit()
        return True
    except Exception as e:
        print("update_config_psus error:", e)
        return False
    finally:
        session.close()


def get_all_configs():
    session = get_session()
    try:
        rows = session.query(Config).order_by(Config.created_at.desc()).all()
        result = []
        for r in rows:
            psus_val = None
            try:
                if getattr(r, "psus", None):
                    psus_val = json.loads(r.psus)
            except Exception:
                psus_val = None

            result.append({
                "id": r.id,
                "name": r.name,
                "cpu": r.cpu,
                "gpu": r.gpu,
                "ram": r.ram,
                "mem": r.mem,
                "watts": r.watts,
                "psus": psus_val,
                "created_at": r.created_at.isoformat() if r.created_at else None
            })
    finally:
        session.close()
    return result


def delete_config(cfg_id: int):
    if cfg_id is None:
        return
    session = get_session()
    try:
        session.query(Config).filter(Config.id == cfg_id).delete()
        session.commit()
    finally:
        session.close()


def rename_config(cfg_id: int, new_name: str):
    session = get_session()
    try:
        cfg = session.get(Config, cfg_id)
        if cfg:
            cfg.name = new_name
            cfg.updated_at = datetime.utcnow()
            session.commit()
    finally:
        session.close()


def get_config(cfg_id: int):
    session = get_session()
    try:
        cfg = session.get(Config, cfg_id)
        if not cfg:
            return None
        psus_val = None
        try:
            if getattr(cfg, "psus", None):
                psus_val = json.loads(cfg.psus)
        except Exception:
            psus_val = None

        result = {
            "id": cfg.id, "name": cfg.name, "cpu": cfg.cpu, "gpu": cfg.gpu,
            "ram": cfg.ram, "mem": cfg.mem, "watts": cfg.watts,
            "created_at": cfg.created_at.isoformat() if cfg.created_at else None,
            "psus": psus_val
        }
        return result
    finally:
        session.close()
