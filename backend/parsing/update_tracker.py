"""
Модуль для отслеживания последнего обновления данных
"""
import os
import json
from datetime import datetime, timedelta
from pathlib import Path

# Путь к файлу отслеживания обновлений (в корне проекта backend)
UPDATE_TRACKER_FILE = Path(__file__).parent.parent / ".last_update.json"
UPDATE_INTERVAL_DAYS = 180  # 6 месяцев


def get_last_update_date() -> datetime | None:
    """Получить дату последнего обновления"""
    if not UPDATE_TRACKER_FILE.exists():
        return None
    
    try:
        with open(UPDATE_TRACKER_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            date_str = data.get('last_update')
            if date_str:
                return datetime.fromisoformat(date_str)
    except Exception as e:
        print(f"Ошибка при чтении даты обновления: {e}")
    
    return None


def save_update_date():
    """Сохранить текущую дату как дату последнего обновления"""
    try:
        UPDATE_TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(UPDATE_TRACKER_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'last_update': datetime.now().isoformat()
            }, f, indent=2)
    except Exception as e:
        print(f"Ошибка при сохранении даты обновления: {e}")


def should_update() -> bool:
    """
    Проверить, нужно ли обновлять данные
    
    Returns:
        True если нужно обновить (прошло больше 6 месяцев или данных нет)
    """
    last_update = get_last_update_date()
    
    if last_update is None:
        # Данных нет, нужно обновить
        return True
    
    # Проверяем, прошло ли 6 месяцев
    days_since_update = (datetime.now() - last_update).days
    return days_since_update >= UPDATE_INTERVAL_DAYS


def reset_update_date():
    """Удалить файл отслеживания обновлений для принудительного парсинга"""
    try:
        if UPDATE_TRACKER_FILE.exists():
            UPDATE_TRACKER_FILE.unlink()
            return True
        return False
    except Exception as e:
        print(f"Ошибка при удалении файла отслеживания: {e}")
        return False

