from fastapi import FastAPI
from database import database
from routers import cpus, gpus, system, ram, storages, cooling

app = FastAPI()

app.include_router(system.router)
app.include_router(cpus.router)
app.include_router(gpus.router)
app.include_router(ram.router)
app.include_router(storages.router)
app.include_router(cooling.router)

@app.get("/")
async def root():
    return {"message": "PC Components API"}