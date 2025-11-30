import logging
import os
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from database import database
from database.database import engine, Base
from routers import cpus, gpus, system, ram, storages, cooling, psus
from parsing import parse_and_load_data

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Запуск приложения...")
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при создании БД: {e}")

    try:
        logger.info("Начинаю парсинг данных и загрузку в БД...")

        headless = os.getenv("HEADLESS", "true").lower() == "true"

        logger.info(f"Режим headless: {headless}")

        # Запускаем парсинг и загрузку данных
        await parse_and_load_data(
            database.new_session,
            headless=headless
        )

        logger.info("Парсинг и загрузка данных завершены успешно")
    except Exception as e:
        logger.error(f"Ошибка при парсинге данных: {e}")

    yield

app = FastAPI(lifespan=lifespan)

app.include_router(system.router)
app.include_router(cpus.router)
app.include_router(gpus.router)
app.include_router(psus.router)
app.include_router(ram.router)
app.include_router(storages.router)
app.include_router(cooling.router)

@app.get("/")
async def root():
    return {"message": "PC Components API"}

@app.post("/parsing/force-update")
async def force_update_parsing():
    """
    Принудительно запустить парсинг данных, игнорируя дату последнего обновления.
    Сбрасывает дату последнего обновления и запускает парсинг заново.
    """
    from parsing import parse_and_load_data
    import os
    
    try:
        logger.info("Запуск принудительного парсинга данных...")
        
        headless = os.getenv("HEADLESS", "true").lower() == "true"
        
        # Запускаем парсинг и загрузку данных
        await parse_and_load_data(
            database.new_session,
            headless=headless
        )

        logger.info("Принудительный парсинг завершен успешно")
        
        return {
            "success": True,
            "message": "Парсинг данных выполнен успешно",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Ошибка при принудительном парсинге: {e}")

