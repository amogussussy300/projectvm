from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from dependencies import SessionDep
from database.models import RAM
from schemas.schemas import RAMCreate

router = APIRouter(prefix="/ram", tags=["RAM"])

@router.post("/")
async def create_ram(ram_data: RAMCreate, session: SessionDep):
    try:
        ram = RAM(**ram_data.model_dump())
        session.add(ram)
        await session.commit()
        await session.refresh(ram)
        return {"success": True, "data": ram}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating RAM: {str(e)}")

@router.get("/")
async def get_ram(session: SessionDep):
    try:
        result = await session.execute(select(RAM))
        ram = result.scalars().all()
        return {"success": True, "data": ram}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching RAM: {str(e)}")

@router.get("/{ram_name}")
async def get_ram_by_name(ram_name: str, session: SessionDep):
    try:
        result = await session.execute(
            select(RAM).where(RAM.name.ilike(f"%{ram_name}%"))
        )
        ram = result.scalars().all()
        if not ram:
            raise HTTPException(status_code=404, detail="RAM not found")
        return {"success": True, "data": ram}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching RAM: {str(e)}")