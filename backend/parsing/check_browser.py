import os
import subprocess


TARGET_BROWSER_PATH = r'C:\Users\user\PycharmProjects\PythonProject2\chrome\win64-142.0.7444.175\chrome-win64\chrome.exe'

if not os.path.exists(TARGET_BROWSER_PATH):
    print(f"Внимание: Браузер не найден по пути: {TARGET_BROWSER_PATH}")
    print("Попытка установить или найти его с помощью npx...")

    # Если файла нет, запускаем npx для скачивания в стандартный кеш puppeteer
    npx_command = ['npx', '@puppeteer/browsers', 'install', 'chrome@stable']
    try:
        result = subprocess.run(npx_command, capture_output=True, text=True, check=True, shell=True)
        print(result.stdout)
        print("Команда npx выполнена успешно.")

    except subprocess.CalledProcessError as e:
        print(f"Критическая ошибка при работе с npx/файлами: {e.stderr}")
        exit()
    except FileNotFoundError:
        print("Команда 'npx' не найдена. Убедитесь, что Node.js и npm установлены и добавлены в PATH.")
        exit()

