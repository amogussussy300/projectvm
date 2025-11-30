from __future__ import annotations
import logging
import re
import lxml
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from bs4 import BeautifulSoup
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_MAX_WORKERS = 8
REQUESTS_TIMEOUT = 15.0
DEFAULT_DELAY = 0.1


def main():
    def _requests_session(max_retries: int = 3, pool_connections: int = 100,
                          pool_maxsize: int = 100) -> requests.Session:
        s = requests.Session()
        retries = Retry(total=max_retries, backoff_factor=0.3,
                        status_forcelist=(429, 500, 502, 503, 504),
                        allowed_methods=frozenset(["GET", "POST"]))
        adapter = HTTPAdapter(max_retries=retries, pool_connections=pool_connections, pool_maxsize=pool_maxsize)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; CPU-Scraper/1.0; +https://example.local)",
            "Accept": "text/html,application/json,application/xhtml+xml,*/*;q=0.9",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
        })
        return s

    def _parse_cpu_table(html: str, brand_name: str) -> List[Dict[str, Optional[str]]]:
        soup = BeautifulSoup(html, "lxml")
        rows = []
        tables = soup.find_all("table")
        for table in tables:
            thead = table.find("thead")
            if not thead:
                continue
            headers = [th.get_text(strip=True) for th in thead.find_all("th")]
            header_idx = {name: i for i, name in enumerate(headers)}
            tbody = table.find("tbody")
            if not tbody:
                continue
            for tr in tbody.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) != len(headers):
                    continue
                row = {}
                for name, i in header_idx.items():
                    val = tds[i].get_text(strip=True)
                    row[name] = val

                if 'CPU' in row or 'Model' in row or 'Processor' in row:
                    name_columns = ['CPU', 'Model', 'Processor', 'Name']
                    for col in name_columns:
                        if col in row and row[col]:
                            if brand_name.lower() not in row[col].lower():
                                row[col] = f"{brand_name} {row[col]}"
                            break

                rows.append(row)
        return rows

    def parse_cpu_brand(base_url: str, brand_name: str) -> pd.DataFrame:
        session = _requests_session()
        logger.info(f"Getting page count for {brand_name}...")
        max_page = 50
        logger.info(f"{brand_name}: Total pages: {max_page}")

        urls = [f"{base_url}?&pg={i}" for i in range(1, max_page + 1)]
        rows: List[Dict[str, Optional[str]]] = []

        def fetch(url):
            try:
                resp = session.get(url, timeout=REQUESTS_TIMEOUT)
                parsed = _parse_cpu_table(resp.text, brand_name)
                logger.info(f"Fetched {url}, found rows: {len(parsed)}")
                return parsed
            except Exception as e:
                logger.warning(f"Failed to fetch {url}: {e}")
                return []

        with ThreadPoolExecutor(max_workers=DEFAULT_MAX_WORKERS) as ex:
            for rows_chunk in ex.map(fetch, urls):
                if rows_chunk:
                    rows.extend(rows_chunk)

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.loc[:, ~df.columns.duplicated()].copy()
            df['Brand'] = brand_name
            logger.info(f"{brand_name}: Successfully parsed {len(df)} rows")

            name_columns = ['CPU', 'Model', 'Processor', 'Name']
            for col in name_columns:
                if col in df.columns:
                    sample_names = df[col].head(3).tolist()
                    logger.info(f"{brand_name} sample processor names: {sample_names}")
                    break
        else:
            logger.warning(f"{brand_name}: No data found")

        return df

    def parse_all_cpus() -> pd.DataFrame:
        brands = [
            {
                'url': 'https://technical.city/en/cpu/intel-rating',
                'name': 'Intel'
            },
            {
                'url': 'https://technical.city/en/cpu/amd-rating',
                'name': 'AMD'
            }
        ]

        all_dataframes = []

        for brand in brands:
            logger.info(f"=== Starting to parse {brand['name']} CPUs ===")
            try:
                df_brand = parse_cpu_brand(brand['url'], brand['name'])
                if not df_brand.empty:
                    all_dataframes.append(df_brand)
                    logger.info(f"=== {brand['name']} parsing completed: {len(df_brand)} rows ===")
                else:
                    logger.warning(f"=== {brand['name']} parsing failed: no data ===")
            except Exception as e:
                logger.error(f"=== Error parsing {brand['name']}: {e} ===")
                continue

        if all_dataframes:
            combined_df = pd.concat(all_dataframes, ignore_index=True)
            logger.info(f"=== Combined data: {len(combined_df)} total rows ===")
            return combined_df
        else:
            logger.error("=== No data was parsed from any brand ===")
            return pd.DataFrame()

    df = parse_all_cpus()

    if not df.empty:
        filename = "technical_city_all_cpu_ratings.csv"
        df.to_csv(filename, index=False)
        logger.info(f"All data saved to {filename}")

        brand_counts = df['Brand'].value_counts()
        logger.info("=== Final statistics ===")
        for brand, count in brand_counts.items():
            logger.info(f"{brand}: {count} processors")

        name_columns = ['CPU', 'Model', 'Processor', 'Name']
        for col in name_columns:
            if col in df.columns:
                logger.info("=== Sample processor names ===")
                sample_data = df[[col, 'Brand']].head(5)
                for _, row in sample_data.iterrows():
                    logger.info(f"  {row[col]} ({row['Brand']})")
                break
    else:
        logger.warning("No data to save")

    return df


if __name__ == "__main__":
    result = main()
    print(f"Parsing completed. Total processors: {len(result) if hasattr(result, 'shape') else 0}")