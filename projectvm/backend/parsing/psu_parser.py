"""
Модуль для парсинга данных о блоках питания (PSU)
"""
from __future__ import annotations
import logging
import re
from typing import List, Dict, Optional
import json
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from bs4 import BeautifulSoup
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_MAX_WORKERS = 12
REQUESTS_TIMEOUT = 15.0


def _requests_session(max_retries: int = 3, pool_connections: int = 100, pool_maxsize: int = 100) -> requests.Session:
    """Создание сессии requests с настройками retry"""
    s = requests.Session()
    retries = Retry(total=max_retries, backoff_factor=0.3,
                    status_forcelist=(429, 500, 502, 503, 504),
                    allowed_methods=frozenset(["GET", "POST"]))
    adapter = HTTPAdapter(max_retries=retries, pool_connections=pool_connections, pool_maxsize=pool_maxsize)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; PSU-Scraper/1.0; +https://example.local)",
        "Accept": "text/html,application/json,application/xhtml+xml,*/*;q=0.9",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
    })
    return s


def _parse_table_html(html: str) -> List[Dict[str, Optional[str]]]:
    """Парсинг HTML таблицы для извлечения данных PSU"""
    soup = BeautifulSoup(html, "lxml")
    rows_out: List[Dict[str, Optional[str]]] = []

    tables = soup.find_all("table")
    if not tables:
        return rows_out

    def header_index_map(table):
        headers = []
        thead = table.find("thead")
        if thead:
            headers = [th.get_text(strip=True) for th in thead.find_all("th")]
        if not headers:
            first = table.find("tr")
            if first:
                headers = [td.get_text(strip=True) for td in first.find_all(["td", "th"])]
        lower = [h.lower() for h in headers]
        def find_idx(cands):
            for i, h in enumerate(lower):
                for c in cands:
                    if c in h:
                        return i
            return None
        return find_idx(["psu", "name", "model", "product"]), find_idx(["power", "wattage", "watt", "watts"])

    best = []
    for table in tables:
        pidx, widx = header_index_map(table)
        if pidx is None:
            pidx = 0
        if widx is None:
            colcount = len(table.find_all("tr")[0].find_all(["td", "th"])) if table.find("tr") else 2
            widx = max(1, colcount - 1)
        body_trs = table.select("tbody tr") or table.find_all("tr")
        out = []
        for tr in body_trs:
            cells = tr.find_all("td")
            if not cells:
                continue
            if pidx >= len(cells):
                continue
            name = cells[pidx].get_text(strip=True)
            wattage = cells[widx].get_text(strip=True) if widx < len(cells) else None
            if name:
                out.append({"PSU Name": " ".join(name.split()), "Wattage": (" ".join(wattage.split()) if wattage else None)})
        if len(out) > len(best):
            best = out

    return best


def _try_requests_fastpath(base_url: str, start_page: int, end_page: int, session: requests.Session) -> Optional[List[Dict[str, Optional[str]]]]:
    """Попытка быстрого парсинга через requests"""
    params = {"page": start_page, "q": "", "sort": "name"}
    url = base_url
    try:
        r = session.get(url, params=params, timeout=REQUESTS_TIMEOUT)
    except Exception as exc:
        logger.debug("Requests fastpath initial fetch failed: %s", exc)
        return None

    html = r.text
    if "This site requires JavaScript" not in html and "doesn't work properly without JavaScript" not in html:
        parsed = _parse_table_html(html)
        if parsed:
            all_rows = parsed
            pages = list(range(start_page + 1, end_page + 1))
            if pages:
                def fetch_page(p):
                    try:
                        rr = session.get(url, params={**params, "page": p}, timeout=REQUESTS_TIMEOUT)
                        return _parse_table_html(rr.text)
                    except Exception as e:
                        logger.debug("page %d request failed: %s", p, e)
                        return []

                with ThreadPoolExecutor(max_workers=min(DEFAULT_MAX_WORKERS, 20)) as ex:
                    for res in ex.map(fetch_page, pages):
                        if res:
                            all_rows.extend(res)
            return all_rows

    js_text = "".join(script.get_text() or "" for script in BeautifulSoup(html, "lxml").find_all("script"))

    cand_urls = set()
    for m in re.finditer(r"""fetch\(['"]([^'"]+)['"]""", js_text):
        cand_urls.add(m.group(1))
    for m in re.finditer(r"""axios\.get\(['"]([^'"]+)['"]""", js_text):
        cand_urls.add(m.group(1))
    for m in re.finditer(r"""xhr\.open\(['"]GET['"],\s*['"]([^'"]+)['"]""", js_text):
        cand_urls.add(m.group(1))

    def norm(u):
        if u.startswith("http"):
            return u
        if u.startswith("/"):
            return re.sub(r"/+$", "", base_url) + u
        return base_url.rstrip("/") + "/" + u.lstrip("/")

    for u in cand_urls:
        full = norm(u)
        try:
            resp = session.get(full, timeout=REQUESTS_TIMEOUT)
            ct = resp.headers.get("content-type", "")
            if resp.status_code == 200 and ("application/json" in ct or resp.text.strip().startswith("{") or resp.text.strip().startswith("[")):
                try:
                    payload = resp.json()
                except Exception:
                    payload = json.loads(resp.text) if resp.text.strip() else None
                rows = []
                if isinstance(payload, dict):
                    for key in ("items", "data", "results", "rows"):
                        if key in payload and isinstance(payload[key], (list, tuple)):
                            for item in payload[key]:
                                name = item.get("name") if isinstance(item, dict) else None
                                wattage = None
                                if isinstance(item, dict):
                                    for k in ("wattage", "power", "watt", "watts"):
                                        if k in item:
                                            wattage = item[k]
                                            break
                                if name:
                                    rows.append({"PSU Name": name, "Wattage": str(wattage) if wattage is not None else None})
                elif isinstance(payload, list):
                    for item in payload:
                        if isinstance(item, dict):
                            name = item.get("name") or item.get("title") or item.get("psu") or item.get("model")
                            wattage = None
                            for k in ("wattage", "power", "watt", "watts"):
                                if k in item:
                                    wattage = item[k]
                                    break
                            if name:
                                rows.append({"PSU Name": name, "Wattage": str(wattage) if wattage is not None else None})
                if rows:
                    if "page=" in full:
                        base_api = re.sub(r"page=\d+", "page={page}", full)
                    else:
                        if "?" in full:
                            base_api = full + "&page={page}"
                        else:
                            base_api = full + "?page={page}"
                    out = []
                    pages = list(range(start_page, end_page + 1))
                    def fetch_api(p):
                        try:
                            r = session.get(base_api.format(page=p), timeout=REQUESTS_TIMEOUT)
                            if r.status_code != 200:
                                return []
                            try:
                                pl = r.json()
                            except Exception:
                                pl = json.loads(r.text)
                            sub = []
                            if isinstance(pl, dict):
                                for key in ("items", "data", "results", "rows"):
                                    if key in pl and isinstance(pl[key], list):
                                        for item in pl[key]:
                                            if isinstance(item, dict):
                                                name = item.get("name") or item.get("title") or item.get("psu") or item.get("model")
                                                wattage = None
                                                for k in ("wattage", "power", "watt", "watts"):
                                                    if k in item:
                                                        wattage = item[k]
                                                        break
                                                if name:
                                                    sub.append({"PSU Name": name, "Wattage": str(wattage) if wattage is not None else None})
                            elif isinstance(pl, list):
                                for item in pl:
                                    if isinstance(item, dict):
                                        name = item.get("name") or item.get("title") or item.get("psu") or item.get("model")
                                        wattage = None
                                        for k in ("wattage", "power", "watt", "watts"):
                                            if k in item:
                                                wattage = item[k]
                                                break
                                        if name:
                                            sub.append({"PSU Name": name, "Wattage": str(wattage) if wattage is not None else None})
                            return sub
                        except Exception as e:
                            logger.debug("api fetch failed for page %d: %s", p, e)
                            return []

                    with ThreadPoolExecutor(max_workers=min(DEFAULT_MAX_WORKERS, 20)) as ex:
                        for res in ex.map(fetch_api, pages):
                            if res:
                                out.extend(res)
                    if out:
                        return out
                    return rows
        except Exception:
            continue

    return None


def _rows_to_df(rows: List[Dict[str, Optional[str]]]) -> pd.DataFrame:
    """Преобразование списка словарей в DataFrame"""
    if not rows:
        return pd.DataFrame(columns=["PSU Name", "Wattage"])

    df = pd.DataFrame(rows)
    if "PSU Name" not in df.columns:
        if "name" in df.columns:
            df = df.rename(columns={"name": "PSU Name", "wattage": "Wattage"})
    if "Wattage" not in df.columns and "wattage" in df.columns:
        df = df.rename(columns={"wattage": "Wattage"})
    if "PSU Name" not in df.columns:
        return pd.DataFrame(columns=["PSU Name", "Wattage"])
    df = df[["PSU Name", "Wattage"]]
    df["PSU Name"] = df["PSU Name"].astype(str).str.strip()
    df["Wattage"] = df["Wattage"].astype(object).where(pd.notna(df["Wattage"]), None)
    df = df.drop_duplicates(subset=["PSU Name"], keep="first").reset_index(drop=True)
    return df


def parse_psus_optimized(start_page: int = 1,
                         end_page: int = 120,
                         base_url: str = "https://www.cybenetics.com/index.php?option=psu-performance-database") -> pd.DataFrame:
    """
    Парсинг данных о блоках питания (PSU)

    Args:
        start_page: Начальная страница для парсинга
        end_page: Конечная страница для парсинга
        base_url: Базовый URL для парсинга

    Returns:
        DataFrame с колонками "PSU Name" и "Wattage"
    """
    session = _requests_session()
    logger.info("Начинаю парсинг PSU...")
    rows = _try_requests_fastpath(base_url, start_page, end_page, session)

    if not rows:
        logger.warning("Не удалось получить данные PSU")
        return pd.DataFrame(columns=["PSU Name", "Wattage"])

    df = _rows_to_df(rows)
    logger.info(f"Парсинг PSU завершен. Получено {len(df)} записей")
    return df

