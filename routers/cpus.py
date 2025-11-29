from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from dependencies import SessionDep
from database.models import CPU
from schemas.schemas import CPUCreate

router = APIRouter(prefix="/cpus", tags=["CPUs"])

@router.post("/")
async def create_cpu(cpu_data: CPUCreate, session: SessionDep):
    try:
        cpu = CPU(**cpu_data.model_dump())
        session.add(cpu)
        await session.commit()
        await session.refresh(cpu)
        return {"success": True, "data": cpu}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating CPU: {str(e)}")

@router.get("/")
async def get_cpus(session: SessionDep):
    try:
        result = await session.execute(select(CPU))
        cpus = result.scalars().all()
        return {"success": True, "data": cpus}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching CPUs: {str(e)}")

@router.get("/{cpu_name}")
async def get_cpu_by_name(cpu_name: str, session: SessionDep):
    try:
        result = await session.execute(
            select(CPU).where(CPU.name.ilike(f"%{cpu_name}%"))
        )
        cpus = result.scalars().all()
        if not cpus:
            raise HTTPException(status_code=404, detail="CPUs not found")
        return {"success": True, "data": cpus}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching CPUs: {str(e)}")