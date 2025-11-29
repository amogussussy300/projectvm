"""
Модуль для парсинга данных о компонентах ПК с различных сайтов
и загрузки их в базу данных.
"""
import asyncio
import re
import logging
import os
import subprocess
from typing import List, Dict, Any, Optional
import pandas as pd
from io import StringIO
from DrissionPage import Chromium, ChromiumOptions

logger = logging.getLogger(__name__)

# Путь к браузеру (можно переопределить через переменную окружения)
TARGET_BROWSER_PATH = os.getenv(
    "CHROME_PATH",
    r'C:\Users\user\PycharmProjects\PythonProject2\chrome\win64-142.0.7444.175\chrome-win64\chrome.exe'
)


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
            # Проверка и установка браузера, если нужно
            self._ensure_browser_available()

            co = ChromiumOptions()

            # Если путь к браузеру существует, явно указываем его DrissionPage
            if os.path.exists(TARGET_BROWSER_PATH):
                co.set_browser_path(TARGET_BROWSER_PATH)
                logger.info(f"DrissionPage настроен на использование {TARGET_BROWSER_PATH}")
            else:
                logger.info("Путь к браузеру не подтвержден, DrissionPage будет искать его автоматически.")

            # Настройка для headless режима (для VPS)
            if self.headless:
                co.headless(True)
                logger.info("Браузер запущен в headless режиме")

            # Попытка найти браузер автоматически
            # DrissionPage должен найти Chrome/Chromium в системе
            # На VPS обычно это /usr/bin/chromium-browser или /usr/bin/google-chrome
            logger.info("Попытка инициализации браузера...")
            self.browser = Chromium(addr_or_opts=co)
            self.tab = self.browser.latest_tab
            logger.info("Браузер успешно инициализирован")

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Ошибка при инициализации браузера: {e}")
            logger.error(f"Детали ошибки:\n{error_details}")

            # Полезные советы по устранению проблемы
            import platform
            system = platform.system()
            logger.error("Возможные решения:")
            if system == "Windows":
                logger.error("1. Убедитесь, что Chrome установлен и доступен в PATH")
                logger.error("2. Попробуйте запустить с HEADLESS=false для отладки")
                logger.error("3. Установите Node.js и npm для автоматической установки браузера")
            elif system == "Linux":
                logger.error("1. Установите chromium: sudo apt-get install chromium-browser")
                logger.error("2. Или установите chrome через npx: npx @puppeteer/browsers install chrome@stable")
                logger.error("3. Убедитесь, что установлены зависимости: sudo apt-get install -y libnss3 libatk1.0-0 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2")
            else:
                logger.error("1. Убедитесь, что Chrome/Chromium установлен")
                logger.error("2. Проверьте, что браузер доступен в PATH")

            raise

    def _ensure_browser_available(self):
        """
        Проверяет наличие браузера и пытается установить его, если нужно
        """
        if os.path.exists(TARGET_BROWSER_PATH):
            logger.info(f"Браузер найден по пути: {TARGET_BROWSER_PATH}")
            return

        logger.warning(f"Браузер не найден по пути: {TARGET_BROWSER_PATH}")
        logger.info("Попытка установить или найти его с помощью npx...")

        # Если файла нет, запускаем npx для скачивания в стандартный кеш puppeteer
        npx_command = ['npx', '@puppeteer/browsers', 'install', 'chrome@stable']
        try:
            # Используем shell=True в Windows для корректного выполнения npx
            logger.info("Запуск npx для установки Chrome...")
            result = subprocess.run(
                npx_command,
                capture_output=True,
                text=True,
                check=True,
                shell=True
            )
            logger.info(result.stdout)
            logger.info("Команда npx выполнена успешно.")

            # Примечание: npx скачивает файл в стандартный кеш puppeteer,
            # а не по пути TARGET_BROWSER_PATH.
            # Если вы хотите использовать этот путь, вам нужно вручную переместить файл или
            # найти, куда его скачал npx и обновить переменную TARGET_BROWSER_PATH.

            # Для простоты, если npx успешно отработал, мы предполагаем,
            # что DrissionPage найдет его автоматически в кеше.
            logger.info("Chrome установлен через npx. DrissionPage найдет его автоматически.")

        except subprocess.CalledProcessError as e:
            logger.warning(f"Ошибка при работе с npx: {e.stderr}")
            logger.warning("Продолжаю работу - DrissionPage попытается найти браузер автоматически")
            # Не прерываем выполнение, DrissionPage может найти браузер сам
        except FileNotFoundError:
            logger.warning("Команда 'npx' не найдена. Убедитесь, что Node.js и npm установлены и добавлены в PATH.")
            logger.warning("Продолжаю работу - DrissionPage попытается найти браузер автоматически")
            # Не прерываем выполнение, DrissionPage может найти браузер сам

    def _parse_table(self, url: str, selector: str, timeout: int = 6) -> Optional[pd.DataFrame]:
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

        skipped_count = 0
        for idx, row in df.iterrows():
            try:
                # Получаем значения из строки
                name_val = row.get(name_col) if name_col else None
                consumption_val = row.get(power_col) if power_col else None

                # Преобразуем в строку и очищаем
                name = str(name_val).strip() if name_val is not None and pd.notna(name_val) else ''
                consumption = str(consumption_val).strip() if consumption_val is not None and pd.notna(consumption_val) else ''

                # Пропускаем пустые или некорректные значения
                if name and name.lower() != 'nan' and consumption and consumption.lower() != 'nan':
                    results.append({
                        'name': name,
                        'consumption': consumption
                    })
                else:
                    skipped_count += 1
                    if skipped_count <= 3:  # Логируем первые 3 пропущенные строки для отладки
                        logger.debug(f"Пропущена строка {idx}: name='{name}', consumption='{consumption}'")
            except Exception as e:
                logger.warning(f"Ошибка при обработке строки {idx}: {e}")
                continue

        if skipped_count > 0:
            logger.info(f"Пропущено {skipped_count} строк с некорректными данными")

        logger.info(f"Извлечено {len(results)} валидных записей из {len(df)} строк")
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


async def parse_and_load_data(session_maker, headless: bool = True, database=None):
    """
    Асинхронная функция для парсинга данных и загрузки в БД

    Args:
        session_maker: AsyncSessionMaker для создания сессий БД
        headless: Запуск браузера в headless режиме
    """
    from database.models import CPU, GPU, Cooling, PSU
    from sqlalchemy import select

    logger.info("Начинаю парсинг данных...")

    # Парсинг выполняется в отдельном потоке, т.к. DrissionPage синхронный
    loop = asyncio.get_event_loop()
    parser = ComponentParser(headless=headless)

    try:
        # Запускаем парсинг в executor
        results = await loop.run_in_executor(None, parser.parse_all)

        logger.info(f"Парсинг завершен. Получено: CPU={len(results['cpus'])}, GPU={len(results['gpus'])}, PSU={len(results['psu'])}")

        # Логируем примеры данных для отладки
        if results['cpus']:
            logger.info(f"Пример CPU данных (первые 3): {results['cpus'][:3]}")
        if results['gpus']:
            logger.info(f"Пример GPU данных (первые 3): {results['gpus'][:3]}")
        if results['psu']:
            logger.info(f"Пример PSU данных (первые 3): {results['psu'][:3]}")

        # Загрузка данных в БД
        session = session_maker()
        try:
            # Загрузка CPU
            if results['cpus']:
                logger.info(f"Загрузка {len(results['cpus'])} записей CPU в БД...")
                added_count = 0
                error_count = 0
                for idx, cpu_data in enumerate(results['cpus']):
                    try:
                        name = cpu_data.get('name', '').strip()
                        consumption = cpu_data.get('consumption', '').strip()

                        if not name:
                            logger.warning(f"CPU запись {idx}: пустое имя, пропускаю")
                            continue

                        # Проверяем, существует ли уже запись
                        result = await session.execute(
                            select(CPU).where(CPU.name == name)
                        )
                        existing = result.scalar_one_or_none()

                        if not existing:
                            cpu = CPU(
                                name=name,
                                consumption=consumption
                            )
                            session.add(cpu)
                            added_count += 1
                            if added_count <= 5:  # Логируем первые 5 добавленных
                                logger.debug(f"Добавлен CPU: {name} ({consumption})")
                        else:
                            logger.debug(f"CPU уже существует: {name}")
                    except Exception as e:
                        error_count += 1
                        logger.warning(f"Ошибка при добавлении CPU {cpu_data.get('name', 'unknown')}: {e}")
                        if error_count <= 3:  # Логируем первые 3 ошибки детально
                            import traceback
                            logger.debug(traceback.format_exc())
                        continue

                await session.commit()
                logger.info(f"CPU данные загружены в БД: добавлено {added_count} новых записей из {len(results['cpus'])}")
                if error_count > 0:
                    logger.warning(f"Ошибок при загрузке CPU: {error_count}")

            # Загрузка GPU
            if results['gpus']:
                logger.info(f"Загрузка {len(results['gpus'])} записей GPU в БД...")
                added_count = 0
                error_count = 0
                for idx, gpu_data in enumerate(results['gpus']):
                    try:
                        name = gpu_data.get('name', '').strip()
                        consumption = gpu_data.get('consumption', '').strip()

                        if not name:
                            logger.warning(f"GPU запись {idx}: пустое имя, пропускаю")
                            continue

                        result = await session.execute(
                            select(GPU).where(GPU.name == name)
                        )
                        existing = result.scalar_one_or_none()

                        if not existing:
                            gpu = GPU(
                                name=name,
                                consumption=consumption
                            )
                            session.add(gpu)
                            added_count += 1
                            if added_count <= 5:  # Логируем первые 5 добавленных
                                logger.debug(f"Добавлен GPU: {name} ({consumption})")
                        else:
                            logger.debug(f"GPU уже существует: {name}")
                    except Exception as e:
                        error_count += 1
                        logger.warning(f"Ошибка при добавлении GPU {gpu_data.get('name', 'unknown')}: {e}")
                        if error_count <= 3:
                            import traceback
                            logger.debug(traceback.format_exc())
                        continue

                await session.commit()
                logger.info(f"GPU данные загружены в БД: добавлено {added_count} новых записей из {len(results['gpus'])}")
                if error_count > 0:
                    logger.warning(f"Ошибок при загрузке GPU: {error_count}")

            if results['psu']:
                logger.info(f"Загрузка {len(results['psu'])} записей PSU в БД...")
                added_count = 0
                error_count = 0
                skipped_no_wattage = 0

                for idx, psu_data in enumerate(results['psu']):
                    try:
                        name = psu_data.get('name', '').strip()

                        if not name:
                            logger.warning(f"PSU запись {idx}: пустое имя, пропускаю")
                            continue

                        wattage = None

                        wattage_match = re.search(r'(\d+)\s*W', name, re.IGNORECASE)
                        if wattage_match:
                            wattage = int(wattage_match.group(1))
                            if not (300 <= wattage <= 2000):
                                wattage = None

                        if wattage is None:
                            model_patterns = [
                                r'[-_](\d{3,4})[A-Z]',
                                r'[A-Z](\d{3,4})[A-Z]',
                            ]

                            for pattern in model_patterns:
                                matches = re.findall(pattern, name)
                                for match in matches:
                                    wattage_candidate = int(match)
                                    if 300 <= wattage_candidate <= 2000:
                                        wattage = wattage_candidate
                                        break
                                if wattage is not None:
                                    break

                        if wattage is None:
                            digits_match = re.findall(r'\b(\d{3,4})\b', name)
                            for digit in digits_match:
                                wattage_candidate = int(digit)
                                if 300 <= wattage_candidate <= 2000:
                                    wattage = wattage_candidate
                                    break

                        if wattage is None:
                            skipped_no_wattage += 1
                            if skipped_no_wattage <= 3:
                                logger.debug(f"Не удалось извлечь мощность для PSU: {name}")
                            continue

                        result = await session.execute(
                            select(PSU).where(PSU.name == name)
                        )
                        existing = result.scalar_one_or_none()

                        if not existing:
                            psu = PSU(
                                name=name,
                                wattage=wattage,
                            )
                            session.add(psu)
                            added_count += 1
                            if added_count <= 5:  # Логируем первые 5 добавленных
                                logger.debug(f"Добавлен PSU: {name} ({wattage}W)")
                        else:
                            logger.debug(f"PSU уже существует: {name}")

                    except Exception as e:
                        error_count += 1
                        logger.warning(f"Ошибка при добавлении PSU {psu_data.get('name', 'unknown')}: {e}")
                        if error_count <= 3:
                            import traceback
                            logger.debug(traceback.format_exc())
                        continue

                await session.commit()
                logger.info(
                    f"PSU данные загружены в БД: добавлено {added_count} новых записей из {len(results['psu'])}")
                if error_count > 0:
                    logger.warning(f"Ошибок при загрузке PSU: {error_count}")
                if skipped_no_wattage > 0:
                    logger.info(f"Пропущено {skipped_no_wattage} записей PSU без определяемой мощности")

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




