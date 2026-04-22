from bs4 import BeautifulSoup
import json
import re

with open("clash/new.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")
tables = soup.find_all("table", class_="wikitable")

# Сначала выводим заголовки всех wikitable
for idx, table in enumerate(tables):
    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    print(f"Таблица {idx}: {headers}")

# Теперь основная логика: пробуем распарсить по известным названиям
def find_index(headers, possible_names):
    for idx, name in enumerate(headers):
        for key in possible_names:
            if key.lower() in name.lower():
                return idx
    return None

parsed = False
for table in tables:
    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    level_idx = find_index(headers, ["level", "уровень"])
    build_time_idx = find_index(headers, ["build time", "upgrade time", "время постройки", "время улучшения"])
    cost_idx = find_index(headers, ["build cost", "стоимость постройки", "cost"])
    # Если нашли все нужные индексы
    if None not in (level_idx, build_time_idx, cost_idx):
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
                    "build_time": build_time,
                    "cost": cost
                })
        with open("clash/cannon_table.json", "w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
        print("Готово! Найдена нужная таблица. Результат: clash/cannon_table.json")
        parsed = True
        break

if not parsed:
    print("Не удалось найти таблицу с нужными столбцами. Смотри вывод заголовков выше.")
