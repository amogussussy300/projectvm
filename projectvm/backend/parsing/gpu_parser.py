"""
Модуль для парсинга данных о видеокартах (GPU)
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
        "User-Agent": "Mozilla/5.0 (compatible; GPU-Scraper/1.0; +https://example.local)",
        "Accept": "text/html,application/json,application/xhtml+xml,*/*;q=0.9",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
    })
    return s


def _parse_table_html(html: str) -> List[Dict[str, Optional[str]]]:
    """Парсинг HTML таблицы для извлечения данных GPU"""
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
        return find_idx(["gpu", "name"]), find_idx(["tdp", "power", "watt", "watts"])

    best = []
    for table in tables:
        gidx, tidx = header_index_map(table)
        if gidx is None:
            gidx = 0
        if tidx is None:
            colcount = len(table.find_all("tr")[0].find_all(["td", "th"])) if table.find("tr") else 2
            tidx = max(1, colcount - 1)
        body_trs = table.select("tbody tr") or table.find_all("tr")
        out = []
        for tr in body_trs:
            cells = tr.find_all("td")
            if not cells:
                continue
            if gidx >= len(cells):
                continue
            name = cells[gidx].get_text(strip=True)
            tdp = cells[tidx].get_text(strip=True) if tidx < len(cells) else None
            if name:
                out.append({"GPU Name": " ".join(name.split()), "TDP": (" ".join(tdp.split()) if tdp else None)})
        if len(out) > len(best):
            best = out

    return best


def _try_requests_fastpath(base_url: str, start_page: int, end_page: int, session: requests.Session) -> Optional[List[Dict[str, Optional[str]]]]:
    """Попытка быстрого парсинга через requests"""
    params = {"page": start_page, "q": "", "sort": "name", "manufacturer": "", "architecture": "",
              "generation": "", "memory_type": "", "bus_interface": "", "directx_version": ""}
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
                                tdp = None
                                if isinstance(item, dict):
                                    for k in ("tdp", "power", "watt", "watts"):
                                        if k in item:
                                            tdp = item[k]
                                            break
                                if name:
                                    rows.append({"GPU Name": name, "TDP": str(tdp) if tdp is not None else None})
                elif isinstance(payload, list):
                    for item in payload:
                        if isinstance(item, dict):
                            name = item.get("name") or item.get("title") or item.get("gpu")
                            tdp = None
                            for k in ("tdp", "power", "watt", "watts"):
                                if k in item:
                                    tdp = item[k]
                                    break
                            if name:
                                rows.append({"GPU Name": name, "TDP": str(tdp) if tdp is not None else None})
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
                                                name = item.get("name") or item.get("title") or item.get("gpu")
                                                tdp = None
                                                for k in ("tdp", "power", "watt", "watts"):
                                                    if k in item:
                                                        tdp = item[k]
                                                        break
                                                if name:
                                                    sub.append({"GPU Name": name, "TDP": str(tdp) if tdp is not None else None})
                            elif isinstance(pl, list):
                                for item in pl:
                                    if isinstance(item, dict):
                                        name = item.get("name") or item.get("title") or item.get("gpu")
                                        tdp = None
                                        for k in ("tdp", "power", "watt", "watts"):
                                            if k in item:
                                                tdp = item[k]
                                                break
                                        if name:
                                            sub.append({"GPU Name": name, "TDP": str(tdp) if tdp is not None else None})
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
        return pd.DataFrame(columns=["GPU Name", "TDP"])
    
    df = pd.DataFrame(rows)
    if "GPU Name" not in df.columns:
        if "name" in df.columns:
            df = df.rename(columns={"name": "GPU Name", "tdp": "TDP"})
    if "TDP" not in df.columns and "tdp" in df.columns:
        df = df.rename(columns={"tdp": "TDP"})
    if "GPU Name" not in df.columns:
        return pd.DataFrame(columns=["GPU Name", "TDP"])
    df = df[["GPU Name", "TDP"]]
    df["GPU Name"] = df["GPU Name"].astype(str).str.strip()
    df["TDP"] = df["TDP"].astype(object).where(pd.notna(df["TDP"]), None)
    df = df.drop_duplicates(subset=["GPU Name"], keep="first").reset_index(drop=True)
    return df


def parse_gpus_optimized(start_page: int = 1,
                         end_page: int = 120,
                         base_url: str = "https://gpus.axiomgaming.net/search") -> pd.DataFrame:
    """
    Парсинг данных о видеокартах (GPU)
    
    Args:
        start_page: Начальная страница для парсинга
        end_page: Конечная страница для парсинга
        base_url: Базовый URL для парсинга
        
    Returns:
        DataFrame с колонками "GPU Name" и "TDP"
    """
    session = _requests_session()
    logger.info("Начинаю парсинг GPU...")
    rows = _try_requests_fastpath(base_url, start_page, end_page, session)
    
    if not rows:
        logger.warning("Не удалось получить данные GPU")
        return pd.DataFrame(columns=["GPU Name", "TDP"])
    
    df = _rows_to_df(rows)
    logger.info(f"Парсинг GPU завершен. Получено {len(df)} записей")
    return df

