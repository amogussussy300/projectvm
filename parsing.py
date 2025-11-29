from DrissionPage import Chromium, ChromiumOptions
import pandas as pd
import os
from io import StringIO
import subprocess
import time

# --- Конфигурация и проверка пути к браузеру ---

# Используем одну переменную для пути к исполняемому файлу Chrome
TARGET_BROWSER_PATH = r'C:\Users\user\PycharmProjects\PythonProject2\chrome\win64-142.0.7444.175\chrome-win64\chrome.exe'

if not os.path.exists(TARGET_BROWSER_PATH):
    print(f"Внимание: Браузер не найден по пути: {TARGET_BROWSER_PATH}")
    print("Попытка установить или найти его с помощью npx...")

    # Если файла нет, запускаем npx для скачивания в стандартный кеш puppeteer
    npx_command = ['npx', '@puppeteer/browsers', 'install', 'chrome@stable']
    try:
        # Используем shell=True в Windows для корректного выполнения npx
        result = subprocess.run(npx_command, capture_output=True, text=True, check=True, shell=True)
        print(result.stdout)
        print("Команда npx выполнена успешно.")

        # Примечание: npx скачивает файл в стандартный кеш puppeteer,
        # а не по пути TARGET_BROWSER_PATH.
        # Если вы хотите использовать этот путь, вам нужно вручную переместить файл или
        # найти, куда его скачал npx и обновить переменную TARGET_BROWSER_PATH.

        # Для простоты, если npx успешно отработал, мы предполагаем,
        # что DrissionPage найдет его автоматически в кеше.
        # Комментируем строку ниже, чтобы DrissionPage искал браузер сам.
        # raise FileNotFoundError("Не удалось получить рабочий путь к браузеру после npx.")

    except subprocess.CalledProcessError as e:
        print(f"Критическая ошибка при работе с npx/файлами: {e.stderr}")
        exit()
    except FileNotFoundError:
        print("Команда 'npx' не найдена. Убедитесь, что Node.js и npm установлены и добавлены в PATH.")
        exit()

# --- Настройка DrissionPage ---

co = ChromiumOptions()

# Если путь существует, явно указываем его DrissionPage
if os.path.exists(TARGET_BROWSER_PATH):
    co.set_browser_path(TARGET_BROWSER_PATH)
    print(f"DrissionPage настроен на использование {TARGET_BROWSER_PATH}")
else:
    print("Путь к браузеру не подтвержден, DrissionPage будет искать его автоматически.")

# Инициализируем браузер (используя опции co)
browser = Chromium(addr_or_opts=co)
tab = browser.latest_tab

# --- Списки URL и селекторов ---

links = [
    "https://www.cybenetics.com/index.php?option=psu-performance-database",
    "https://www.techpowerup.com/gpu-specs/",
    "https://www.techpowerup.com/cpu-specs/"
]
# Список селекторов для таблиц на каждом сайте
selectors = [
    '@@class=table table-dark table-striped table-hover mytable sub headers1stLine',
    '@@tag=table',  # Для AJAX страницы TechPowerUp просто ищем тег table
    '@@tag=table'   # Для AJAX страницы TechPowerUp просто ищем тег table
]

# --- Основной цикл скрапинга ---

for i, link in enumerate(links):
    print(f"\n=== Обрабатывается сайт: {link} ===")

    try:
        tab.get(link)
        # Удалена проблемная строка tab.wait.load_complete()

        selector = selectors[i]

        print(f"Ожидание появления таблицы с селектором: {selector}")

        # Используем надежное ожидание появления элемента на странице
        if tab.wait.ele_displayed(selector, timeout=20):
            print("Элемент таблицы найден, приступаю к парсингу.")

            # Получаем элемент и его HTML
            ele = tab.ele(selector)
            table_html = ele.html

            try:
                # Используем pandas для чтения HTML
                # read_html возвращает список DataFrame'ов, берем первый [0]
                tables = pd.read_html(StringIO(table_html), encoding='utf-8')
                if tables:
                    data = tables[0]
                    print(f"Парсинг успешен. Найдена таблица с {len(data)} строками и {len(data.columns)} колонками")

                    # Сохраняем в CSV файл для каждого сайта
                    filename = f"data_{i + 1}.csv"
                    data.to_csv(filename, index=False, encoding='utf-8')
                    print(f"Данные сохранены в файл: {filename}")

                    # (Опционально) Сохранение в JSON
                    # json_str = data.to_json(orient='records', indent=2, force_ascii=False)
                    # print(json_str[:500] + "...") # Печать первых 500 символов JSON

                else:
                    print("Не удалось распарсить таблицу (pandas не нашел таблицы в HTML).")
            except Exception as e:
                print(f"Ошибка при парсинге HTML-кода в DataFrame: {e}")
        else:
            print(f"Элемент таблицы '{selector}' не был найден на странице в течение 20 секунд.")

    except Exception as e:
        print(f"Критическая ошибка при обработке сайта {link}: {e}")

    # Небольшая пауза между запросами
    tab.wait(2)
    time.sleep(1) # Дополнительная пауза для вежливости

# Закрываем браузер после обработки всех ссылок
print("\n=== Обработка завершена ===")
browser.quit()
