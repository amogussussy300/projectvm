from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from dependencies import SessionDep
from database.models import Cooling
from schemas.schemas import CoolingCreate

router = APIRouter(prefix="/cooling", tags=["Cooling"])

@router.post("/")
async def create_cooling(cooling_data: CoolingCreate, session: SessionDep):
    try:
        cooling = Cooling(**cooling_data.model_dump())
        session.add(cooling)
        await session.commit()
        await session.refresh(cooling)
        return {"success": True, "data": cooling}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating Cooling: {str(e)}")

@router.get("/")
async def get_cooling(session: SessionDep):
    try:
        result = await session.execute(select(Cooling))
        cooling = result.scalars().all()
        return {"success": True, "data": cooling}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching Cooling: {str(e)}")

@router.get("/{cooling_name}")
async def get_cooling_by_name(cooling_name: str, session: SessionDep):
    try:
        result = await session.execute(
            select(Cooling).where(Cooling.name.ilike(f"%{cooling_name}%"))
        )
        cooling = result.scalars().all()
        if not cooling:
            raise HTTPException(status_code=404, detail="Cooling not found")
        return {"success": True, "data": cooling}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching Cooling: {str(e)}")