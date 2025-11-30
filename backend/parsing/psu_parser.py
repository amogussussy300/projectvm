from __future__ import annotations


def parse_psus_optimized():
    from DrissionPage import Chromium, ChromiumOptions
    from .check_browser import ensure_chrome_available
    import pandas as pd

    chrome_path = ensure_chrome_available()  # Гарантируем правильный chrome.exe
    co = ChromiumOptions()
    co.set_paths(browser_path=chrome_path)  # Задать путь к chrome.exe
    browser = Chromium(co)  # Передаём опции как первый аргумент
    try:
        tab = browser.latest_tab
        tab.get('https://www.cybenetics.com/index.php?option=psu-performance-database')
        ele = tab.ele('@@class=table table-dark table-striped table-hover mytable sub headers1stLine')
        table = ele.html

        data = pd.read_html(table)[0]
        return data
    finally:
        browser.quit()
