from __future__ import annotations


def parse_psus_optimized():
    from DrissionPage import Chromium, ChromiumOptions
    import pandas as pd

    co = ChromiumOptions()
    # co.set_argument('--headless=new')
    # co.set_argument('--no-sandbox')
    # co.set_argument('--disable-gpu')

    browser = Chromium()
    tab = browser.latest_tab
    tab.get('https://www.cybenetics.com/index.php?option=psu-performance-database')
    ele = tab.ele('@@class=table table-dark table-striped table-hover mytable sub headers1stLine')
    table = ele.html

    data = pd.read_html(table)[0]
    return data
