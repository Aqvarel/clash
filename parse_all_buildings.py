import requests
from bs4 import BeautifulSoup
import json
import re
import time

BASE = "https://clashofclans.fandom.com"
CATEGORIES = ["/wiki/Category:Buildings"]

def fetch_building_links(category_url):
    resp = requests.get(BASE + category_url)
    soup = BeautifulSoup(resp.text, "html.parser")
    links = []
    for div in soup.find_all("div", class_="category-page__member-left"):
        a = div.find("a")
        if a and a['href'].startswith('/wiki/'):
            links.append(a['href'])
    return links

def parse_table_from_url(url):
    resp = requests.get(BASE + url)
    soup = BeautifulSoup(resp.text, "html.parser")
    tables = soup.find_all("table", class_="wikitable")
    # Пример: как из первой таблицы взять нужные параметры
    if not tables:
        return None
    # Берём первую таблицу — если что, подбери номер как выше
    table = tables[0]
    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    # indices:
    def find_index(names):
        for idx,h in enumerate(headers):
            for n in names:
                if n.lower() == h.lower():
                    return idx
        return None
    level_idx = find_index(["Level", "Уровень"])
    build_time_idx = find_index(["Build Time", "Время постройки", "Upgrade Time", "Время улучшения"])
    cost_idx = find_index(["Build Cost", "Стоимость постройки", "Cost"])
    if None in (level_idx, build_time_idx, cost_idx):
        return None
    data = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) > max(level_idx, build_time_idx, cost_idx):
            level = cells[level_idx].get_text(strip=True)
            build_time = cells[build_time_idx].get_text(strip=True)
            cost = cells[cost_idx].get_text(strip=True)
            data.append({
                "level": level,
                "build_time": build_time,
                "cost": cost
            })
    return data

all_buildings = {}
for cat in CATEGORIES:
    links = fetch_building_links(cat)
    print(f"Нашлось {len(links)} зданий")
    for link in links:
        name = link.split("/")[-1].replace("_"," ")
        print(f"Парсим {name} ...")
        parsed = parse_table_from_url(link)
        if parsed:
            all_buildings[name] = parsed
        # чтобы не заддосить сервер
        time.sleep(1)

with open("all_buildings_tables.json", "w", encoding="utf-8") as f:
    json.dump(all_buildings, f, ensure_ascii=False, indent=2)

print("Готово! Данные всех зданий в all_buildings_tables.json")
