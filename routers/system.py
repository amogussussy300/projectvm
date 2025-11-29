from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from database.database import engine, Base
from database.models import CPU, GPU, RAM, Storage, Cooling

router = APIRouter(tags=["System"])

@router.post("/setup_database")
async def setup_database():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        return {"success": True, "message": "database created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database setup error: {str(e)}")

@router.get("/health")
async def health_check():
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}

@router.get("/test_connection")
async def test_connection():
    try:
        async with engine.begin() as conn:
            await conn.execute(select(1))
        return {"status": "success", "message": "Database connection successful"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")