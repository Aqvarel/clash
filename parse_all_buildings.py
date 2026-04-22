#!/usr/bin/env python3
# clash/parse_all_buildings_api.py
"""
Парсер для Clash of Clans Fandom, использующий MediaWiki API как primary source.
Использование:
    python clash/parse_all_buildings_api.py --category Buildings --output clash/all_buildings.json
"""
import requests
from bs4 import BeautifulSoup
import argparse
import time
import json
import re
from urllib.parse import quote

BASE_SITE_DEFAULT = "https://clashofclans.fandom.com"
REQUEST_DELAY = 0.6
API_SLEEP_ON_ERROR = 2
MAX_RETRIES = 4

LEVEL_NAMES = ["Level", "Уровень"]
COST_NAMES = ["Build Cost", "Cost", "Стоимость постройки", "Стоимость"]
BUILD_TIME_NAMES = ["Build Time", "Upgrade Time", "Время постройки", "Время улучшения"]

DIGIT_RE = re.compile(r"[\d\s,]+")
TIME_UNITS = {
    's': 1, 'sec': 1, 'second': 1, 'seconds': 1,
    'm': 60, 'min': 60, 'minute': 60, 'minutes': 60,
    'h': 3600, 'hr': 3600, 'hour': 3600, 'hours': 3600,
    'd': 86400, 'day': 86400, 'days': 86400,
    # Russian
    'с': 1, 'сек': 1, 'секунд': 1, 'секунда': 1,
    'м': 60, 'мин': 60, 'минута': 60, 'минут': 60,
    'ч': 3600, 'час': 3600, 'часов': 3600,
    'д': 86400, 'дн': 86400, 'день': 86400, 'дней': 86400
}

def parse_time_to_seconds(s: str):
    if not s:
        return None
    s = s.replace('\u00A0', ' ').replace(',', ' ')
    total = 0
    found = False
    parts = re.findall(r'(\d+)\s*([a-zA-Zа-яА-Яµ]+)?', s)
    if not parts:
        parts = re.findall(r'(\d+)([a-zA-Zа-яА-Яµ]+)', s)
    for number, unit in parts:
        try:
            n = int(number)
        except:
            continue
        unit = (unit or '').lower()
        if not unit:
            continue
        factor = None
        if unit in TIME_UNITS:
            factor = TIME_UNITS[unit]
        else:
            for k in TIME_UNITS:
                if unit.startswith(k):
                    factor = TIME_UNITS[k]
                    break
        if factor is None:
            continue
        total += n * factor
        found = True
    return total if found else None

def normalize_cost(cost_str: str):
    if not cost_str:
        return None, cost_str
    s = re.sub(r'\[\d+\]', '', cost_str)
    m = DIGIT_RE.search(s)
    if not m:
        return None, s.strip()
    num_str = m.group(0)
    num = int(re.sub(r'[^\d]', '', num_str))
    return num, s.strip()

def build_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0 Safari/537.36 (compatible; parser/1.0; +https://example.org)",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": BASE_SITE_DEFAULT
    })
    return s

def get_category_members(category: str, site_base: str, session: requests.Session):
    if not category.startswith("Category:"):
        category = "Category:" + category
    api = site_base.rstrip('/') + "/api.php"
    members = []
    params = {
        'action': 'query',
        'list': 'categorymembers',
        'cmtitle': category,
        'cmlimit': '500',
        'format': 'json'
    }
    cont = {}
    while True:
        p = params.copy()
        p.update(cont)
        for attempt in range(MAX_RETRIES):
            try:
                r = session.get(api, params=p, timeout=15)
                break
            except Exception as e:
                print("API request error:", e, "retrying...")
                time.sleep(API_SLEEP_ON_ERROR)
        else:
            print("API unreachable after retries")
            return members
        if r.status_code != 200:
            print("API returned", r.status_code)
            time.sleep(API_SLEEP_ON_ERROR)
            return members
        data = r.json()
        cm = data.get('query', {}).get('categorymembers', [])
        for item in cm:
            if item.get('ns') == 0:
                members.append(item.get('title'))
        if 'continue' in data:
            cont = data['continue']
            time.sleep(0.2)
            continue
        break
    return members

def fetch_page_html_via_api(title: str, site_base: str, session: requests.Session):
    api = site_base.rstrip('/') + "/api.php"
    params = {
        'action': 'parse',
        'page': title,
        'prop': 'text',
        'format': 'json'
    }
    for attempt in range(MAX_RETRIES):
        try:
            r = session.get(api, params=params, timeout=15)
        except Exception as e:
            print(f"API parse error for {title}: {e}")
            time.sleep(API_SLEEP_ON_ERROR * (attempt+1))
            continue
        if r.status_code == 200:
            j = r.json()
            if 'error' in j:
                return None
            html = j.get('parse', {}).get('text', {}).get('*')
            return html
        elif r.status_code in (429, 403):
            # rate limited or blocked, backoff
            time.sleep(API_SLEEP_ON_ERROR * (attempt+1))
            continue
        else:
            time.sleep(0.5)
    return None

def fetch_page_html_direct(title: str, site_base: str, session: requests.Session):
    title_url = quote(title.replace(' ', '_'), safe='/:?=&')
    url = site_base.rstrip('/') + '/wiki/' + title_url
    for attempt in range(MAX_RETRIES):
        try:
            r = session.get(url, timeout=20)
        except Exception as e:
            print(f"Direct fetch error {title}: {e}")
            time.sleep(1.0 * (attempt+1))
            continue
        if r.status_code == 200:
            return r.text
        elif r.status_code in (403, 429):
            # try slower backoff
            time.sleep(1.5 * (attempt+1))
            continue
        else:
            time.sleep(0.5)
    return None

def find_target_table_and_parse(html: str):
    if not html:
        return None
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all("table", class_="wikitable")
    for table in tables:
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        def has_any(names):
            return any(any(name.lower() == head.lower() or name.lower() in head.lower() or head.lower() in name.lower()
                           for head in headers) for name in names)
        if has_any(LEVEL_NAMES) and has_any(COST_NAMES) and has_any(BUILD_TIME_NAMES):
            # find indices
            def find_index(names):
                for i, head in enumerate(headers):
                    for name in names:
                        if name.lower() == head.lower() or name.lower() in head.lower() or head.lower() in name.lower():
                            return i
                return None
            level_idx = find_index(LEVEL_NAMES)
            cost_idx = find_index(COST_NAMES)
            time_idx = find_index(BUILD_TIME_NAMES)
            if None in (level_idx, cost_idx, time_idx):
                continue
            rows = []
            for tr in table.find_all("tr")[1:]:
                cells = tr.find_all(["td", "th"])
                if len(cells) <= max(level_idx, cost_idx, time_idx):
                    continue
                level_raw = cells[level_idx].get_text(strip=True)
                cost_raw = cells[cost_idx].get_text(strip=True)
                time_raw = cells[time_idx].get_text(strip=True)
                try:
                    level_parsed = int(re.sub(r'\D', '', level_raw)) if re.search(r'\d', level_raw) else None
                except:
                    level_parsed = None
                cost_parsed, cost_raw_clean = normalize_cost(cost_raw)
                time_seconds = parse_time_to_seconds(time_raw)
                rows.append({
                    "level_raw": level_raw,
                    "level": level_parsed,
                    "cost_raw": cost_raw_clean,
                    "cost": cost_parsed,
                    "build_time_raw": time_raw,
                    "build_time_seconds": time_seconds
                })
            return rows
    return None

def parse_page(title: str, site_base: str, session: requests.Session):
    # Try API parse first (more reliable)
    html = fetch_page_html_via_api(title, site_base, session)
    if html:
        parsed = find_target_table_and_parse(html)
        if parsed:
            return parsed
    # Fallback: try direct fetch (with headers)
    html2 = fetch_page_html_direct(title, site_base, session)
    if html2:
        parsed2 = find_target_table_and_parse(html2)
        if parsed2:
            return parsed2
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--category', '-c', default='Buildings')
    parser.add_argument('--output', '-o', default='clash/all_buildings.json')
    parser.add_argument('--site', default=BASE_SITE_DEFAULT)
    parser.add_argument('--limit', '-l', type=int, default=0)
    args = parser.parse_args()

    session = build_session()
    members = get_category_members(args.category, args.site, session)
    print("Найдено страниц:", len(members))
    if args.limit and args.limit > 0:
        members = members[:args.limit]

    result = {}
    for idx, title in enumerate(members, 1):
        print(f"[{idx}/{len(members)}] Парсим: {title} ...")
        parsed = parse_page(title, args.site, session)
        if parsed:
            result[title] = parsed
            print(f"  -> найдено {len(parsed)} строк")
        else:
            print("  -> таблица не найдена или 403/ограничение")
        time.sleep(REQUEST_DELAY)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("Готово. Сохранено в", args.output)

if __name__ == "__main__":
    main()
