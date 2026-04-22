from bs4 import BeautifulSoup
import json
import re

with open("clash/new.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")
tables = soup.find_all("table", class_="wikitable")

# --------- ВАЖНО: здесь выбираешь ту таблицу, номера смотришь по выводу ---------------
table_index = 0    # если нужна другая таблица, поменяй на её номер (например, 2)

if len(tables) <= table_index:
    print(f"Таблицы с таким индексом нет. Нашлось таблиц: {len(tables)}")
    exit(1)

table = tables[table_index]
headers = [th.get_text(strip=True) for th in table.find_all("th")]
print(f"Использую Таблицу {table_index}: {headers}")

def find_index(headers, possible_names):
    for idx, name in enumerate(headers):
        for key in possible_names:
            if key.lower() == name.lower():
                return idx
    return None

level_idx = find_index(headers, ["Level", "Уровень"])
build_time_idx = find_index(headers, ["Build Time", "Время постройки", "Upgrade Time", "Время улучшения"])
cost_idx = find_index(headers, ["Build Cost", "Стоимость постройки", "Cost"])

if None in (level_idx, build_time_idx, cost_idx):
    print("Не удалось определить индексы нужных столбцов, проверь заголовки:")
    print(f"level_idx={level_idx}, build_time_idx={build_time_idx}, cost_idx={cost_idx}")
    exit(1)

data = []
for row in table.find_all("tr")[1:]:
    cells = row.find_all(["td", "th"])
    if len(cells) > max(level_idx, build_time_idx, cost_idx):
        level = cells[level_idx].get_text(strip=True)
        build_time = cells[build_time_idx].get_text(strip=True)
        cost = cells[cost_idx].get_text(strip=True)
        build_time = re.sub(r"\[\d+\]", "", build_time)
        cost = re.sub(r"\[\d+\]", "", cost)
        data.append({
            "level": level,
            "cost": cost,
            "build_time": build_time
        })

with open("clash/cannon_table.json", "w", encoding="utf-8") as out:
    json.dump(data, out, ensure_ascii=False, indent=2)

print("Готово! Данные сохранены в clash/cannon_table.json")
