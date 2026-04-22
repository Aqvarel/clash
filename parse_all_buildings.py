#!/usr/bin/env python3
"""
parse_all_buildings.py
Собирает таблицы (Level / Build Cost / Build Time) для всех страниц в категории Fandom (Clash of Clans).
Использует MediaWiki API для списка страниц категории, затем парсит HTML каждой страницы.

Запуск:
    python clash/parse_all_buildings.py --category Buildings --output clash/all_buildings.json

По умолчанию категория = Buildings, сайт = clashofclans.fandom.com
"""
from bs4 import BeautifulSoup
import requests
import time
import json
import re
import argparse
from urllib.parse import quote

BASE_SITE = "https://clashofclans.fandom.com"

# Таймауты/ограничения
REQUEST_DELAY = 0.8  # секунда между запросами, не перегружаем сайт
API_SLEEP_ON_ERROR = 3

# Возможные заголовки столбцов (англ/рус)
LEVEL_NAMES = ["Level", "Уровень"]
COST_NAMES = ["Build Cost", "Cost", "Стоимость постройки", "Стоимость"]
BUILD_TIME_NAMES = ["Build Time", "Upgrade Time", "Время постройки", "Время улучшения"]

# Регекс для нормализации чисел в с��оимостях
DIGIT_RE = re.compile(r"[\d\s,]+")

# Конвертер времени в секунды
TIME_UNITS = {
    's': 1, 'sec': 1, 'secs': 1, 'second': 1, 'seconds': 1,
    'm': 60, 'min': 60, 'mins': 60, 'minute': 60, 'minutes': 60,
    'h': 3600, 'hr': 3600, 'hrs': 3600, 'hour': 3600, 'hours': 3600,
    'd': 86400, 'day': 86400, 'days': 86400,
    'w': 7*86400, 'week': 7*86400, 'weeks': 7*86400,
    # русские
    'с': 1, 'сек': 1, 'секунд': 1, 'секунда': 1,
    'м': 60, 'мин': 60, 'минута': 60, 'минут': 60,
    'ч': 3600, 'час': 3600, 'часов': 3600,
    'д': 86400, 'дн': 86400, 'день': 86400, 'дней': 86400
}

def parse_time_to_seconds(s: str):
    """Попытка распарсить строку времени в секунды. Возвращает int seconds или None."""
    if not s:
        return None
    s = s.strip()
    # Заменим длинные слова и запятые
    s = s.replace('\u00A0', ' ')  # nbsp
    s = s.replace(',', ' ')
    # Общие шаблоны: "4h 30m", "3d 4h 20m", "5s", "4ч 30м"
    total = 0
    found = False
    # Найти все пары (число, юнит)
    # поддержим форматы: "4h", "30m", "3 ч", "4ч 30м", "1 day", "3d"
    parts = re.findall(r'(\d+)\s*([a-zA-Zа-яА-Яµ]+)?', s)
    if not parts:
        # Иногда формат "3h30m" без пробела: попробуем добавить пробел между цифрой и буквой
        parts = re.findall(r'(\d+)([a-zA-Zа-яА-Яµ]+)', s)
    for number, unit in parts:
        try:
            n = int(number)
        except:
            continue
        unit = (unit or '').lower()
        # у некоторых значений нет юнита — в таком случае интерпретируем как секунды? нет — пропускаем
        if not unit:
            # если строка всего одно число — возможно секунды или минуты, но хитро угадать плохо
            # пропускаем этот фрагмент
            continue
        # укорачивание русских/англ вариантов: оставим первые 1-3 символа чтобы матчить словарь
        u = unit
        if u in TIME_UNITS:
            factor = TIME_UNITS[u]
        else:
            # try to map by prefix
            matched = None
            for k in TIME_UNITS:
                if u.startswith(k):
                    matched = TIME_UNITS[k]
                    break
            if matched is None:
                # не опознали юнит — пропустить
                continue
            factor = matched
        total += n * factor
        found = True
    return total if found else None

def normalize_cost(cost_str: str):
    """Возвращает (int or None, raw_str). Убирает запятые/пробелы."""
    if not cost_str:
        return None, cost_str
    # убираем заметки [1], non-digits
    s = re.sub(r'\[\d+\]', '', cost_str)
    # Найдём подряд идущие цифры, пробелы и запятые
    m = DIGIT_RE.search(s)
    if not m:
        return None, cost_str.strip()
    num_str = m.group(0)
    # убираем пробелы и запятые
    num = int(re.sub(r'[^\d]', '', num_str))
    return num, cost_str.strip()

def get_category_members(category: str, site_base: str = BASE_SITE):
    """Возвращает список заголовков страниц в категории (получаем через API)."""
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
    cont = None
    while True:
        if cont:
            params.update(cont)
        try:
            r = requests.get(api, params=params, timeout=15)
        except Exception as e:
            print("Ошибка запроса API:", e)
            time.sleep(API_SLEEP_ON_ERROR)
            continue
        if r.status_code != 200:
            print("API вернул статус", r.status_code)
            time.sleep(API_SLEEP_ON_ERROR)
            continue
        data = r.json()
        cm = data.get('query', {}).get('categorymembers', [])
        for item in cm:
            # получаем title
            title = item.get('title')
            # фильтруем Subcategories/Files и т.д. Оставим только нормальные страницы (ns=0) - API возвращает ns
            if item.get('ns') == 0:
                members.append(title)
        if 'continue' in data:
            cont = data['continue']
            # заменить None хранение
            time.sleep(0.25)
            continue
        break
    return members

def parse_page_table(title: str, site_base: str = BASE_SITE):
    """Парсит страницу по title, ищет таблицу с Level/Build Cost/Build Time, возвращает список записей."""
    # build page url
    title_url = quote(title.replace(' ', '_'), safe='/:%?=&')
    url = site_base.rstrip('/') + '/wiki/' + title_url
    try:
        r = requests.get(url, timeout=20)
    except Exception as e:
        print(f"Ошибка загрузки {title}: {e}")
        return None
    if r.status_code != 200:
        print(f"{title}: HTTP {r.status_code}")
        return None
    soup = BeautifulSoup(r.text, 'html.parser')
    tables = soup.find_all("table", class_="wikitable")
    # Попробовать найти таблицу, где точно есть заголовки Level + Build Cost + Build Time
    for table in tables:
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        # Проверим наличие нужных колонок
        def has_any(hlist, headers):
            return any(any(h.lower() == head.lower() or h.lower() in head.lower() for head in headers) for h in hlist)
        if has_any(LEVEL_NAMES, headers) and has_any(COST_NAMES, headers) and has_any(BUILD_TIME_NAMES, headers):
            # нашли целевую таблицу
            # определим индексы
            def find_index(headers, names):
                for i, head in enumerate(headers):
                    for name in names:
                        if name.lower() == head.lower() or name.lower() in head.lower() or head.lower() in name.lower():
                            return i
                return None
            level_idx = find_index(headers, LEVEL_NAMES)
            cost_idx = find_index(headers, COST_NAMES)
            time_idx = find_index(headers, BUILD_TIME_NAMES)
            if None in (level_idx, cost_idx, time_idx):
                continue
            rows = []
            for tr in table.find_all("tr")[1:]:
                cells = tr.find_all(["td", "th"])
                # пропускаем пустые/заголовочные строки
                if len(cells) <= max(level_idx, cost_idx, time_idx):
                    continue
                level_raw = cells[level_idx].get_text(strip=True)
                cost_raw = cells[cost_idx].get_text(strip=True)
                time_raw = cells[time_idx].get_text(strip=True)
                # нормализация
                level_parsed = None
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
    # если не нашли подходящую таблицу, возвращаем None
    return None

def main():
    parser = argparse.ArgumentParser(description="Парсер таблиц Clash of Clans Wiki по категории")
    parser.add_argument('--category', '-c', default='Buildings', help='Имя категории (без префикса Category:), например Buildings, Troops, Heroes')
    parser.add_argument('--output', '-o', default='clash/all_buildings.json', help='Файл вывода JSON')
    parser.add_argument('--site', default=BASE_SITE, help='Базовый сайт (по умолчанию clashofclans.fandom.com)')
    parser.add_argument('--limit', '-l', type=int, default=0, help='Макс. количество страниц для обработки (0 = все)')
    args = parser.parse_args()

    print("Получаем список страниц категории:", args.category)
    members = get_category_members(args.category, site_base=args.site)
    print("Найдено страниц:", len(members))
    if args.limit and args.limit > 0:
        members = members[:args.limit]

    result = {}
    for idx, title in enumerate(members, 1):
        print(f"[{idx}/{len(members)}] Парсим: {title} ...")
        data = parse_page_table(title, site_base=args.site)
        if data:
            result[title] = data
            print(f"  -> найдено {len(data)} строк")
        else:
            print("  -> таблица не найдена или не содержит нужных столбцов")
        time.sleep(REQUEST_DELAY)

    # Сохраняем результат
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("Готово. Результат сохранён в", args.output)

if __name__ == "__main__":
    main()
