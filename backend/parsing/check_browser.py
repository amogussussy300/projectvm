import os
import subprocess
import logging

def ensure_chrome_available():
    logger = logging.getLogger(__name__)
    local_chrome_path = os.path.join(
        os.path.dirname(__file__), 'chrome', 'win64-142.0.7444.175', 'chrome-win64', 'chrome.exe'
    )
    if os.path.exists(local_chrome_path):
        logger.info(f"Локальный Chrome найден: {local_chrome_path}")
        return local_chrome_path

    logger.warning("Локальный Chrome не найден — будет предпринята попытка установить его через npx puppeteer")
    npx_command = ['npx', '@puppeteer/browsers', 'install', 'chrome@stable']
    try:
        result = subprocess.run(npx_command, capture_output=True, text=True, check=True, shell=True, cwd=os.path.dirname(__file__))
        logger.info(result.stdout)
        logger.info("Chrome установлен локально через npx.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при попытке установки Chrome через npx: {e.stderr}")
        raise RuntimeError(f"Ошибка установки Chrome: {e.stderr}")
    except FileNotFoundError:
        logger.error("npx не найден. Установите Node.js и npm, чтобы получилось скачать Chrome.")
        raise RuntimeError("npx не найден для установки Chrome.")

    if os.path.exists(local_chrome_path):
        logger.info(f"Успешно установлен локальный Chrome: {local_chrome_path}")
        return local_chrome_path
    else:
        logger.error(f"Chrome не найден даже после установки. Путь: {local_chrome_path}")
        raise RuntimeError("Chrome не найден после попытки установки!")

