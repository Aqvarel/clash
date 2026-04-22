import requests
from bs4 import BeautifulSoup
import json
import re

BASE_URL = "https://clashofclans.fandom.com"
PAGES = [
    "/ru/wiki/Башня_лучниц",
    "/ru/wiki/Казна",
    # Добавь нужные страницы зданий, которые хочешь распарсить
]

def parse_upgrade_times(page_url):
    result = []
    resp = requests.get(BASE_URL + page_url)
    if not resp.ok:
        print(f"Ошибка при загрузке {page_url}")
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="wikitable")
    if not table:
        print(f"Таблица не найдена на {page_url}")
        return []
    headers = [th.text.strip() for th in table.find_all("th")]
    try:
        level_idx = headers.index("Уровень")
        time_idx = [i for i, h in enumerate(headers) if "время улучшения" in h.lower()][0]
    except Exception:
        print(f"Не удалось найти нужные столбцы на {page_url}")
        return []
    for row in table.find_all("tr")[1:]:
        columns = row.find_all(["td", "th"])
        if len(columns) <= max(level_idx, time_idx):
            continue
        level = columns[level_idx].text.strip()
        upgrade_time = columns[time_idx].text.strip()
        upgrade_time = re.sub(r"\[\d+\]", "", upgrade_time)
        result.append({"level": level, "upgrade_time": upgrade_time})
    return result

all_data = {}
for page in PAGES:
    building_name = page.split("/")[-1]
    print(f"Обрабатывается: {building_name}")
    all_data[building_name] = parse_upgrade_times(page)

with open("clash_upgrade_times.json", "w", encoding="utf-8") as f:
    json.dump(all_data, f, ensure_ascii=False, indent=2)

print("Готово! Все данные собраны в clash_upgrade_times.json")
