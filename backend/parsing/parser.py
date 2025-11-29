"""
Модуль для парсинга данных о компонентах ПК с различных сайтов
и загрузки их в базу данных.
"""
import asyncio
import logging
import os
from typing import List, Dict, Any, Optional
import pandas as pd
from io import StringIO
from DrissionPage import Chromium, ChromiumOptions

logger = logging.getLogger(__name__)


class ComponentParser:
    """Класс для парсинга компонентов ПК"""
    
    def __init__(self, headless: bool = True):
        """
        Инициализация парсера
        
        Args:
            headless: Запуск браузера в headless режиме (для VPS)
        """
        self.headless = headless
        self.browser: Optional[Chromium] = None
        self.tab = None
        
    def _setup_browser(self):
        """Настройка и инициализация браузера"""
        try:
            co = ChromiumOptions()
            
            # Настройка для headless режима (для VPS)
            if self.headless:
                co.headless(True)
                logger.info("Браузер запущен в headless режиме")
            
            # Попытка найти браузер автоматически
            # DrissionPage должен найти Chrome/Chromium в системе
            # На VPS обычно это /usr/bin/chromium-browser или /usr/bin/google-chrome
            self.browser = Chromium(addr_or_opts=co)
            self.tab = self.browser.latest_tab
            logger.info("Браузер успешно инициализирован")
            
        except Exception as e:
            logger.error(f"Ошибка при инициализации браузера: {e}")
            raise
    
    def _parse_table(self, url: str, selector: str, timeout: int = 30) -> Optional[pd.DataFrame]:
        """
        Парсинг таблицы с указанного URL
        
        Args:
            url: URL страницы для парсинга
            selector: CSS селектор или XPath для таблицы
            timeout: Таймаут ожидания элемента (секунды)
            
        Returns:
            DataFrame с данными или None в случае ошибки
        """
        try:
            logger.info(f"Открытие страницы: {url}")
            self.tab.get(url)
            
            logger.info(f"Ожидание появления таблицы с селектором: {selector}")
            if not self.tab.wait.ele_displayed(selector, timeout=timeout):
                logger.warning(f"Таблица не найдена на странице {url} в течение {timeout} секунд")
                return None
            
            logger.info("Таблица найдена, начинаю парсинг")
            ele = self.tab.ele(selector)
            table_html = ele.html
            
            # Парсинг HTML таблицы в DataFrame
            tables = pd.read_html(StringIO(table_html), encoding='utf-8')
            if not tables:
                logger.warning("Не удалось распарсить таблицу")
                return None
            
            data = tables[0]
            logger.info(f"Парсинг успешен. Найдено {len(data)} строк и {len(data.columns)} колонок")
            return data
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге {url}: {e}")
            return None
    
    def _extract_name_and_consumption(self, df: pd.DataFrame, name_keywords: List[str], 
                                      consumption_keywords: List[str]) -> List[Dict[str, str]]:
        """
        Извлечение имени и потребления из DataFrame
        
        Args:
            df: DataFrame с данными
            name_keywords: Ключевые слова для поиска колонки с названием
            consumption_keywords: Ключевые слова для поиска колонки с потреблением
            
        Returns:
            Список словарей с полями name и consumption
        """
        results = []
        
        # Логируем доступные колонки для отладки
        logger.info(f"Доступные колонки: {list(df.columns)}")
        
        # Ищем колонки с названием и потреблением
        name_cols = [col for col in df.columns 
                    if any(keyword.lower() in str(col).lower() for keyword in name_keywords)]
        power_cols = [col for col in df.columns 
                     if any(keyword.lower() in str(col).lower() for keyword in consumption_keywords)]
        
        name_col = name_cols[0] if name_cols else (df.columns[0] if len(df.columns) > 0 else None)
        power_col = power_cols[0] if power_cols else (df.columns[1] if len(df.columns) > 1 else None)
        
        if not name_col:
            logger.warning("Не найдена колонка с названием")
            return results
        
        for _, row in df.iterrows():
            try:
                name = str(row.get(name_col, '')).strip()
                consumption = str(row.get(power_col, '')).strip() if power_col else ''
                
                # Пропускаем пустые или некорректные значения
                if name and name != 'nan' and name and consumption and consumption != 'nan':
                    results.append({
                        'name': name,
                        'consumption': consumption
                    })
            except Exception as e:
                logger.debug(f"Ошибка при обработке строки: {e}")
                continue
        
        return results
    
    def parse_psu_data(self) -> List[Dict[str, str]]:
        """
        Парсинг данных о блоках питания (PSU)
        
        Returns:
            Список словарей с данными о PSU
        """
        url = "https://www.cybenetics.com/index.php?option=psu-performance-database"
        selector = "@@class=table table-dark table-striped table-hover mytable sub headers1stLine"
        
        df = self._parse_table(url, selector)
        if df is None:
            return []
        
        return self._extract_name_and_consumption(
            df,
            name_keywords=['model', 'name', 'product'],
            consumption_keywords=['power', 'wattage', 'consumption', 'w']
        )
    
    def parse_gpu_data(self) -> List[Dict[str, str]]:
        """
        Парсинг данных о видеокартах (GPU)
        
        Returns:
            Список словарей с данными о GPU
        """
        url = "https://www.techpowerup.com/gpu-specs/"
        selector = "@@tag=table"
        
        df = self._parse_table(url, selector)
        if df is None:
            return []
        
        return self._extract_name_and_consumption(
            df,
            name_keywords=['gpu', 'name', 'model', 'chip'],
            consumption_keywords=['tdp', 'power', 'board power', 'wattage']
        )
    
    def parse_cpu_data(self) -> List[Dict[str, str]]:
        """
        Парсинг данных о процессорах (CPU)
        
        Returns:
            Список словарей с данными о CPU
        """
        url = "https://www.techpowerup.com/cpu-specs/"
        selector = "@@tag=table"
        
        df = self._parse_table(url, selector)
        if df is None:
            return []
        
        return self._extract_name_and_consumption(
            df,
            name_keywords=['cpu', 'name', 'model', 'processor'],
            consumption_keywords=['tdp', 'power', 'wattage', 'w']
        )
    
    def parse_all(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Парсинг всех типов компонентов
        
        Returns:
            Словарь с данными по каждому типу компонентов
        """
        if self.browser is None:
            self._setup_browser()
        
        try:
            results = {
                'cpus': [],
                'gpus': [],
                'psu': []  # PSU можно использовать для cooling или создать отдельную таблицу
            }
            
            logger.info("Начинаю парсинг CPU...")
            results['cpus'] = self.parse_cpu_data()
            logger.info(f"Распарсено {len(results['cpus'])} записей CPU")
            
            logger.info("Начинаю парсинг GPU...")
            results['gpus'] = self.parse_gpu_data()
            logger.info(f"Распарсено {len(results['gpus'])} записей GPU")
            
            logger.info("Начинаю парсинг PSU...")
            results['psu'] = self.parse_psu_data()
            logger.info(f"Распарсено {len(results['psu'])} записей PSU")
            
            return results
            
        finally:
            if self.browser:
                self.browser.quit()
                logger.info("Браузер закрыт")
    
    def close(self):
        """Закрытие браузера"""
        if self.browser:
            self.browser.quit()
            self.browser = None
            logger.info("Браузер закрыт")


async def parse_and_load_data(session_maker, headless: bool = True):
    """
    Асинхронная функция для парсинга данных и загрузки в БД
    
    Args:
        session_maker: AsyncSessionMaker для создания сессий БД
        headless: Запуск браузера в headless режиме
    """
    from database.models import CPU, GPU, Cooling
    from sqlalchemy import select
    
    logger.info("Начинаю парсинг данных...")
    
    # Парсинг выполняется в отдельном потоке, т.к. DrissionPage синхронный
    loop = asyncio.get_event_loop()
    parser = ComponentParser(headless=headless)
    
    try:
        # Запускаем парсинг в executor
        results = await loop.run_in_executor(None, parser.parse_all)
        
        logger.info(f"Парсинг завершен. Получено: CPU={len(results['cpus'])}, GPU={len(results['gpus'])}, PSU={len(results['psu'])}")
        
        # Загрузка данных в БД
        session = session_maker()
        try:
            # Загрузка CPU
            if results['cpus']:
                logger.info(f"Загрузка {len(results['cpus'])} записей CPU в БД...")
                added_count = 0
                for cpu_data in results['cpus']:
                    try:
                        # Проверяем, существует ли уже запись
                        result = await session.execute(
                            select(CPU).where(CPU.name == cpu_data['name'])
                        )
                        existing = result.scalar_one_or_none()
                        
                        if not existing:
                            cpu = CPU(
                                name=cpu_data['name'],
                                consumption=cpu_data['consumption']
                            )
                            session.add(cpu)
                            added_count += 1
                    except Exception as e:
                        logger.debug(f"Ошибка при добавлении CPU {cpu_data.get('name', 'unknown')}: {e}")
                        continue
                
                await session.commit()
                logger.info(f"CPU данные загружены в БД: добавлено {added_count} новых записей")
            
            # Загрузка GPU
            if results['gpus']:
                logger.info(f"Загрузка {len(results['gpus'])} записей GPU в БД...")
                added_count = 0
                for gpu_data in results['gpus']:
                    try:
                        result = await session.execute(
                            select(GPU).where(GPU.name == gpu_data['name'])
                        )
                        existing = result.scalar_one_or_none()
                        
                        if not existing:
                            gpu = GPU(
                                name=gpu_data['name'],
                                consumption=gpu_data['consumption']
                            )
                            session.add(gpu)
                            added_count += 1
                    except Exception as e:
                        logger.debug(f"Ошибка при добавлении GPU {gpu_data.get('name', 'unknown')}: {e}")
                        continue
                
                await session.commit()
                logger.info(f"GPU данные загружены в БД: добавлено {added_count} новых записей")
            
            # Загрузка PSU как Cooling (или можно создать отдельную таблицу)
            if results['psu']:
                logger.info(f"Загрузка {len(results['psu'])} записей PSU в БД...")
                added_count = 0
                for psu_data in results['psu']:
                    try:
                        result = await session.execute(
                            select(Cooling).where(Cooling.name == psu_data['name'])
                        )
                        existing = result.scalar_one_or_none()
                        
                        if not existing:
                            # PSU можно сохранить как Cooling с дефолтными значениями
                            cooling = Cooling(
                                name=psu_data['name'],
                                consumption=psu_data['consumption'],
                                size="N/A",  # Для PSU размер не применим
                                has_led=False
                            )
                            session.add(cooling)
                            added_count += 1
                    except Exception as e:
                        logger.debug(f"Ошибка при добавлении PSU {psu_data.get('name', 'unknown')}: {e}")
                        continue
                
                await session.commit()
                logger.info(f"PSU данные загружены в БД: добавлено {added_count} новых записей")
            
            logger.info("Все данные успешно загружены в БД")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при загрузке данных в БД: {e}")
            raise
        finally:
            await session.close()
                
    except Exception as e:
        logger.error(f"Ошибка при парсинге данных: {e}")
        raise
    finally:
        parser.close()


