from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from dependencies import SessionDep
from database.models import PSU
from schemas.schemas import PSUCreate

router = APIRouter(prefix="/psus", tags=["PSUs"])

@router.post("/")
async def create_psu(psu_data: PSUCreate, session: SessionDep):
    try:
        psu = PSU(**psu_data.model_dump())
        session.add(psu)
        await session.commit()
        await session.refresh(psu)
        return {"success": True, "data": psu}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating PSUs: {str(e)}")

@router.get("/")
async def get_psus(session: SessionDep):
    try:
        result = await session.execute(select(PSU))
        psus = result.scalars().all()
        return {"success": True, "data": psus}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching PSUs: {str(e)}")

@router.get("/{psu_name}")
async def get_psu_by_name(psu_name: str, session: SessionDep):
    try:
        result = await session.execute(
            select(PSU).where(PSU.name.ilike(f"%{psu_name}%"))
        )
        psus = result.scalars().all()
        if not psus:
            raise HTTPException(status_code=404, detail="PSUs not found")
        return {"success": True, "data": psus}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching PSUs: {str(e)}")
