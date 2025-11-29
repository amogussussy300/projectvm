import logging
import os
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from database import database
from database.database import engine, Base
from routers import cpus, gpus, system, ram, storages, cooling
from parsing import parse_and_load_data
from parsing.update_tracker import should_update, save_update_date, get_last_update_date

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения.
    При запуске создается БД (если не существует) и выполняется парсинг данных.
    Автоматическое обновление данных раз в полгода.
    """
    # Startup: создание БД и парсинг данных
    logger.info("Запуск приложения...")
    
    # Создание таблиц БД, если их нет
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при создании БД: {e}")
        # Продолжаем работу, возможно БД уже существует
    
    # Проверяем, нужно ли выполнять парсинг при старте
    # Можно добавить переменную окружения для управления этим поведением
    should_parse = os.getenv("SKIP_PARSING", "false").lower() != "true"
    
    if should_parse:
        # Проверяем, нужно ли обновлять данные (раз в полгода)
        needs_update = should_update()
        
        if needs_update:
            last_update = get_last_update_date()
            if last_update:
                days_since = (datetime.now() - last_update).days
                logger.info(f"Последнее обновление было {days_since} дней назад. Требуется обновление.")
            else:
                logger.info("Данные еще не парсились. Выполняю первый парсинг.")
            
            try:
                logger.info("Начинаю парсинг данных и загрузку в БД...")
                # Определяем, запущено ли на VPS (headless режим)
                # По умолчанию используем headless для продакшена
                # Для локальной разработки можно установить HEADLESS=false
                headless = os.getenv("HEADLESS", "true").lower() == "true"
                
                logger.info(f"Режим headless: {headless}")
                
                # Запускаем парсинг и загрузку данных
                await parse_and_load_data(
                    database.new_session,
                    headless=headless
                )
                
                # Сохраняем дату обновления
                save_update_date()
                logger.info("Парсинг и загрузка данных завершены успешно")
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                logger.error(f"Ошибка при парсинге данных: {e}")
                logger.error(f"Детали ошибки:\n{error_details}")
                logger.warning("Приложение продолжит работу с существующими данными в БД")
                # Не прерываем запуск приложения, если парсинг не удался
                # API все равно будет работать с существующими данными
        else:
            last_update = get_last_update_date()
            if last_update:
                days_since = (datetime.now() - last_update).days
                logger.info(f"Данные актуальны. Последнее обновление было {days_since} дней назад. Парсинг не требуется.")
            else:
                logger.info("Парсинг пропущен (данные актуальны)")
    else:
        logger.info("Парсинг пропущен (SKIP_PARSING=true)")
    
    yield
    
    # Shutdown (если нужно что-то сделать при остановке)
    logger.info("Остановка приложения...")


app = FastAPI(lifespan=lifespan)

app.include_router(system.router)
app.include_router(cpus.router)
app.include_router(gpus.router)
app.include_router(ram.router)
app.include_router(storages.router)
app.include_router(cooling.router)

@app.get("/")
async def root():
    return {"message": "PC Components API"}

@app.get("/parsing/status")
async def parsing_status():
    """Получить информацию о статусе парсинга"""
    last_update = get_last_update_date()
    needs_update = should_update()
    
    if last_update:
        days_since = (datetime.now() - last_update).days
        return {
            "last_update": last_update.isoformat(),
            "days_since_update": days_since,
            "needs_update": needs_update,
            "update_interval_days": 180
        }
    else:
        return {
            "last_update": None,
            "days_since_update": None,
            "needs_update": True,
            "update_interval_days": 180
        }