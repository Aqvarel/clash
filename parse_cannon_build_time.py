from bs4 import BeautifulSoup
import json
import re

with open("clash/new.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")
tables = soup.find_all("table", class_="wikitable")

target_table = None
for table in tables:
    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    # Ищем основную таблицу по ключевым колонкам
    if (
        any(h in ["Build Time", "Время постройки", "Upgrade Time", "Время улучшения"] for h in headers)
        and any(h in ["Cost", "Стоимость постройки"] for h in headers)
        and any(h in ["Level", "Уровень"] for h in headers)
    ):
        target_table = table
        break

if not target_table:
    print("Не удалось найти таблицу с нужными столбцами.")
else:
    headers = [th.get_text(strip=True) for th in target_table.find_all("th")]
    # Выведем заголовки для отладки
    print("Заголовки:", headers)

    def find_index(possible_names):
        for idx, name in enumerate(headers):
            for key in possible_names:
                if key.lower() in name.lower():
                    return idx
        return None

    level_idx = find_index(["level", "уровень"])
    build_time_idx = find_index(["build time", "upgrade time", "время постройки", "время улучшения"])
    cost_idx = find_index(["cost", "стоимость постройки"])    

    if None in (level_idx, build_time_idx, cost_idx):
        print("Не удалось определить индексы нужных столбцов.")
    else:
        data = []
        for row in target_table.find_all("tr")[1:]:
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
        print("Готово! Результат: clash/cannon_table.json")
