from __future__ import annotations

import os
import time
import random
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup
import pandas as pd


BASE_URL = "https://www.techpowerup.com/cpu-specs/"
TIMEOUT = 1
MAX_WORKERS = 10


def make_session() -> requests.Session:
    s = requests.Session()

    base = os.path.dirname(os.path.abspath(__file__))
    user_agents = os.path.join(base, "user-agents.txt")

    with open(user_agents, encoding="utf8") as agents:
        user_agent = random.choice([i.strip() for i in agents.readlines() if i.strip()])

    agents.close()

    s.headers.update({
        "User-Agent": user_agent,
        "Accept": "text/html",
    })
    return s



def parse_table(html: str) -> List[Dict[str, Optional[str]]]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="items-desktop-table")
    if table is None:
        return []

    headers = [th.get_text(strip=True).lower() for th in table.select("thead th")]

    def idx(name):
        for i, h in enumerate(headers):
            if name in h:
                return i
        return None

    name_idx = idx("name")
    tdp_idx = idx("tdp")

    if name_idx is None:
        return []

    rows = []
    for tr in table.select("tbody tr"):
        cells = tr.find_all("td")
        if len(cells) <= name_idx:
            continue

        name = cells[name_idx].get_text(strip=True)
        tdp = cells[tdp_idx].get_text(strip=True) if tdp_idx and tdp_idx < len(cells) else None

        rows.append({"CPU Name": name, "TDP": tdp})

    return rows


def build_f_param(filters: dict) -> str:
    return "~".join(f"{k}_{v}" if v not in (None, "") else k for k, v in filters.items())

def fetch_one(session: requests.Session, manufacturer: str, year: object, market: str):
    time.sleep(random.uniform(0.01, 0.05))
    filters = {
        "mfgr": manufacturer,
        "year": None if year == "Unknown" else year,
        "market": market
    }

    f_param = build_f_param(filters)

    print(f"[REQ] {manufacturer} {year} {market}")

    try:
        r = session.get(BASE_URL, params={"f": f_param}, timeout=TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        print(f"[ERR] {manufacturer} {year}: {e}")
        return []

    rows = parse_table(r.text)
    for r in rows:
        r["CPU Name"] += f" {manufacturer}"

    print(f"[OK] {manufacturer} {year} {market} → {len(rows)} rows")
    return rows


def parse_cpus_clean() -> pd.DataFrame:
    # Импортируем main из нового парсера
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    try:
        from new_cpu_parser import main as new_cpu_main
    except ImportError:
        raise ImportError("Не удалось импортировать main из new_cpu_parser.py")
    result = new_cpu_main()
    if result is None:
        import pandas as pd
        return pd.DataFrame()
    return result


