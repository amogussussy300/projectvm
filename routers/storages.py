from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from dependencies import SessionDep
from database.models import Storage
from schemas.schemas import StorageCreate

router = APIRouter(prefix="/storages", tags=["Storages"])

@router.post("/")
async def create_storage(storage_data: StorageCreate, session: SessionDep):
    try:
        storage = Storage(**storage_data.model_dump())
        session.add(storage)
        await session.commit()
        await session.refresh(storage)
        return {"success": True, "data": storage}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating Storage: {str(e)}")

@router.get("/")
async def get_storages(session: SessionDep):
    try:
        result = await session.execute(select(Storage))
        storages = result.scalars().all()
        return {"success": True, "data": storages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching storages: {str(e)}")
#
# @router.get("/{storage_name}")
# async def get_storage_by_name(storage_name: str, session: SessionDep):
#     try:
#         result = await session.execute(
#             select(Storage).where(Storage.name.ilike(f"%{storage_name}%"))
#         )
#         storages = result.scalars().all()
#         if not storages:
#             raise HTTPException(status_code=404, detail="Storages not found")
#         return {"success": True, "data": storages}
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error fetching Storages: {str(e)}")
#
# @router.get('/{type}/{number}')
# async def get_storage_by_type(type: str, number: int, session: SessionDep):
#     try:
#         result = await session.execute(
#             select(Storage).where(Storage.name.ilike(f"%{type}%"))
#         )
#         storages = result.scalars().all()
#         if not storages:
#             raise HTTPException(status_code=404, detail="Storage not found")
#         return {"success": True, "data": storages}
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error fetching Storage: {str(e)}")