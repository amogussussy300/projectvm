"""
Модуль для парсинга данных о компонентах ПК с различных сайтов
и загрузки их в базу данных.
"""
import asyncio
import re
import logging
from typing import List, Dict, Any, Optional
import pandas as pd

from .new_cpu_parser import main as parse_cpus_clean
from .gpu_parser import parse_gpus_optimized
from .psu_parser import parse_psus_optimized

logger = logging.getLogger(__name__)

def _extract_name_and_consumption(df: pd.DataFrame, name_keywords: List[str],
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

def parse_all_components() -> Dict[str, List[Dict[str, str]]]:
    """
    Парсинг всех типов компонентов используя новые парсеры

    Returns:
        Словарь с данными по каждому типу компонентов
    """
    results = {
        'cpus': [],
        'gpus': [],
        'psu': []
    }

    try:
        # Парсинг CPU
        logger.info("Начинаю парсинг CPU...")
        cpu_df = parse_cpus_clean()
        if not cpu_df.empty:
            results['cpus'] = _extract_name_and_consumption(
                cpu_df,
                name_keywords=['cpu name', 'name', 'cpu', 'processor'],
                consumption_keywords=['tdp', 'power', 'wattage', 'w']
            )
            logger.info(f"Распарсено {len(results['cpus'])} записей CPU")
        else:
            logger.warning("CPU DataFrame пуст")

        # Парсинг GPU
        logger.info("Начинаю парсинг GPU...")
        gpu_df = parse_gpus_optimized(start_page=1, end_page=120)
        if not gpu_df.empty:
            results['gpus'] = _extract_name_and_consumption(
                gpu_df,
                name_keywords=['gpu name', 'name', 'gpu', 'model', 'chip'],
                consumption_keywords=['tdp', 'power', 'board power', 'wattage']
            )
            logger.info(f"Распарсено {len(results['gpus'])} записей GPU")
        else:
            logger.warning("GPU DataFrame пуст")

        # Парсинг PSU
        logger.info("Начинаю парсинг PSU...")
        psu_df = parse_psus_optimized()

        if not psu_df.empty:
            psu_results = []
            logger.info(f"Доступные колонки PSU: {list(psu_df.columns)}")

            cols_lower = {col: col.lower() for col in psu_df.columns}

            manufacturer_col = None
            for col, col_l in cols_lower.items():
                if "manufacturer" in col_l:
                    manufacturer_col = col
                    break

            model_col = None
            for col, col_l in cols_lower.items():
                if "model" in col_l and col != manufacturer_col:
                    model_col = col
                    break

            def extract_wattage(text):
                if text is None or (isinstance(text, float) and pd.isna(text)):
                    return None
                s = str(text)

                m = re.search(r"(\d{2,5})\s*[Ww]\b", s)
                if m:
                    return m.group(1)
                m2 = re.search(r"\b([1-9]\d{2,3})\b", s)
                if m2:
                    return m2.group(1)
                m3 = re.search(r"\b([6-9]\d)\b", s)
                if m3:
                    return m3.group(1)
                return None

            def find_wattage(row):
                if model_col and model_col in psu_df.columns:
                    v = row.get(model_col)
                    res = extract_wattage(v)
                    if res:
                        return res

                if manufacturer_col and manufacturer_col in psu_df.columns:
                    v = row.get(manufacturer_col)
                    res = extract_wattage(v)
                    if res:
                        return res

                for col in psu_df.columns:
                    if col in {manufacturer_col, model_col}:
                        continue
                    v = row.get(col)
                    res = extract_wattage(v)
                    if res:
                        return res
                return None


            for idx, row in psu_df.iterrows():
                try:
                    parts = []
                    if manufacturer_col and manufacturer_col in psu_df.columns:
                        man_val = row.get(manufacturer_col)
                        if pd.notna(man_val) and str(man_val).strip().lower() != "nan":
                            parts.append(str(man_val).strip())
                    if model_col and model_col in psu_df.columns and model_col != manufacturer_col:
                        mod_val = row.get(model_col)
                        if pd.notna(mod_val) and str(mod_val).strip().lower() != "nan":
                            parts.append(str(mod_val).strip())

                    name = " ".join(parts).strip()
                    if name == "":
                        name = None

                    watt = find_wattage(row)

                    if name:
                        psu_results.append({
                            'name': name,
                            'consumption': watt
                        })

                except Exception as e:
                    logger.warning(f"Ошибка при обработке PSU строки {idx}: {e}")
                    continue

            results['psu'] = psu_results
            logger.info(f"Распарсено {len(results['psu'])} записей PSU")
        else:
            logger.warning("PSU DataFrame пуст")

    except Exception as e:
        logger.error(f"Ошибка при парсинге компонентов: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

    return results


async def parse_and_load_data(session_maker, headless: bool = True, database=None):
    """
    Асинхронная функция для парсинга данных и загрузки в БД

    Args:
        session_maker: AsyncSessionMaker для создания сессий БД
        headless: Параметр для совместимости (не используется в новой версии)
    """
    from database.models import CPU, GPU, Cooling, PSU
    from sqlalchemy import select

    logger.info("Начинаю парсинг данных...")

    # Парсинг выполняется в отдельном потоке
    loop = asyncio.get_event_loop()

    try:
        # Запускаем парсинг в executor
        results = await loop.run_in_executor(None, parse_all_components)

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
                        consumption = psu_data.get('consumption', '').strip()

                        if not name:
                            logger.warning(f"PSU запись {idx}: пустое имя, пропускаю")
                            continue

                        wattage = None

                        # Сначала пытаемся извлечь из поля consumption
                        if consumption:
                            # Извлекаем число из строки (например, "750W" -> 750)
                            wattage_match = re.search(r'(\d+)\s*W?', consumption, re.IGNORECASE)
                            if wattage_match:
                                wattage = int(wattage_match.group(1))
                                if not (300 <= wattage <= 2000):
                                    wattage = None
                            else:
                                # Пытаемся просто преобразовать в число
                                try:
                                    wattage = int(re.sub(r'[^\d]', '', consumption))
                                    if not (300 <= wattage <= 2000):
                                        wattage = None
                                except ValueError:
                                    pass

                        # Если не получилось из consumption, пытаемся из имени
                        if wattage is None:
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
                                logger.debug(f"Не удалось извлечь мощность для PSU: {name} (consumption: {consumption})")
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



