from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from dependencies import SessionDep
from database.models import GPU
from schemas.schemas import GPUCreate

router = APIRouter(prefix="/gpus", tags=["GPUs"])

@router.post("/")
async def create_gpu(gpu_data: GPUCreate, session: SessionDep):
    try:
        gpu = GPU(**gpu_data.model_dump())
        session.add(gpu)
        await session.commit()
        await session.refresh(gpu)
        return {"success": True, "data": gpu}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating GPU: {str(e)}")

@router.get("/")
async def get_gpus(session: SessionDep):
    try:
        result = await session.execute(select(GPU))
        gpus = result.scalars().all()
        return {"success": True, "data": gpus}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching GPUs: {str(e)}")

@router.get("/{gpu_name}")
async def get_gpu_by_name(gpu_name: str, session: SessionDep):
    try:
        result = await session.execute(
            select(GPU).where(GPU.name.ilike(f"%{gpu_name}%"))
        )
        gpus = result.scalars().all()
        if not gpus:
            raise HTTPException(status_code=404, detail="GPUs not found")
        return {"success": True, "data": gpus}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching GPUs: {str(e)}")