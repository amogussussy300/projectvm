from __future__ import annotations
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from bs4 import BeautifulSoup
import pandas as pd

DEFAULT_MAX_WORKERS = 12
REQUESTS_TIMEOUT = 15.0


def _requests_session(max_retries: int = 3, pool_connections: int = 100, pool_maxsize: int = 100) -> requests.Session:
    s = requests.Session()
    retries = Retry(total=max_retries, backoff_factor=0.3,
                    status_forcelist=(429, 500, 502, 503, 504),
                    allowed_methods=frozenset(["GET", "POST"]))
    adapter = HTTPAdapter(max_retries=retries, pool_connections=pool_connections, pool_maxsize=pool_maxsize)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; GPU-Scraper/1.0; +https://example.local)",
        "Accept": "text/html,application/json,application/xhtml+xml,*/*;q=0.9",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
    })
    return s


def _parse_table_html(html: str) -> List[Dict[str, Optional[str]]]:
    soup = BeautifulSoup(html, "lxml")

    tables = soup.find_all("table")
    if not tables:
        return []

    def header_index_map(table):
        thead = table.find("thead")
        if thead:
            headers = [th.get_text(strip=True) for th in thead.find_all("th")]
        else:
            first = table.find("tr")
            if first:
                headers = [td.get_text(strip=True) for td in first.find_all(["td", "th"])]
            else:
                headers = []

        lower = [h.lower() for h in headers]

        def find_idx(cand):
            for i, h in enumerate(lower):
                if cand in h:
                    return i
            return None

        return find_idx("gpu"), find_idx("manufacturer"), find_idx("tdp")

    best_rows = []

    for table in tables:
        gpu_idx, manufacturer_idx, tdp_idx = header_index_map(table)

        first_row = table.find("tr")
        if not first_row:
            continue

        colcount = len(first_row.find_all(["td", "th"]))
        if colcount == 0:
            continue

        if gpu_idx is None:
            gpu_idx = 0
        if tdp_idx is None:
            tdp_idx = max(1, colcount - 1)

        trs = table.select("tbody tr")
        if not trs:
            trs = table.find_all("tr")

        rows = []
        for tr in trs:
            cells = tr.find_all("td")
            if len(cells) <= gpu_idx:
                continue

            gpu = cells[gpu_idx].get_text(strip=True)
            man = cells[manufacturer_idx].get_text(strip=True)
            if not gpu:
                continue

            gpu = " ".join(gpu.split())
            man = " ".join(man.split())

            if tdp_idx < len(cells):
                raw_tdp = cells[tdp_idx].get_text(strip=True)
                tdp = " ".join(raw_tdp.split()) if raw_tdp else None
            else:
                tdp = None

            rows.append({"GPU Name": f'{man} {gpu}', "TDP": tdp})

        if len(rows) > len(best_rows):
            best_rows = rows

    return best_rows


def _try_requests_fastpath(base_url: str, start_page: int, end_page: int, session: requests.Session) -> Optional[
    List[Dict[str, Optional[str]]]]:
    params = {"page": start_page, "q": "", "sort": "name", "manufacturer": "", "architecture": "",
              "generation": "", "memory_type": "", "bus_interface": "", "directx_version": ""}
    try:
        r = session.get(base_url, params=params, timeout=REQUESTS_TIMEOUT)
    except requests.RequestException as exc:
        return None

    html = r.text or ""

    parsed = _parse_table_html(html)
    if parsed:
        all_rows = list(parsed)
        pages = list(range(start_page + 1, end_page + 1))
        if pages:
            def fetch_page(p):
                try:
                    rr = session.get(base_url, params={**params, "page": p}, timeout=REQUESTS_TIMEOUT)
                    return _parse_table_html(rr.text)
                except requests.RequestException as e:
                    return []

            with ThreadPoolExecutor(max_workers=DEFAULT_MAX_WORKERS) as ex:
                for res in ex.map(fetch_page, pages):
                    if res:
                        all_rows.extend(res)
        return all_rows

def parse_gpus_optimized(start_page: int = 1,
                         end_page: int = 120,
                         base_url: str = "https://gpus.axiomgaming.net/search") -> pd.DataFrame:
    session = _requests_session()
    rows = _try_requests_fastpath(base_url, start_page, end_page, session)


    df = pd.DataFrame(rows)
    return df
