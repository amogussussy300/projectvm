import os
import shutil
import subprocess

# Список вероятных путей для chrome.exe в Windows
CANDIDATE_PATHS = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    os.path.join(os.path.dirname(__file__), 'chrome', 'win64-142.0.7444.175', 'chrome-win64', 'chrome.exe'),  # локальная папка
]

chrome_path = None
for path in CANDIDATE_PATHS:
    if os.path.exists(path):
        chrome_path = path
        break

# Альтернативная попытка: найти chrome.exe через PATH
if not chrome_path:
    chrome_path = shutil.which('chrome.exe')

if not chrome_path:
    print("Внимание: Chrome не найден ни в одном из стандартных путей.")
    print("Попытка установить или найти его с помощью npx...")
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
else:
    print(f"Обнаружен Chrome: {chrome_path}")

