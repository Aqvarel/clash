from bs4 import BeautifulSoup
import json
import re

# Открываем сохранённый html-файл
with open("clash/new.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")
tables = soup.find_all("table", class_="wikitable")

target_table = None
for table in tables:
    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    # В англ. версии могут быть "Build Time" или "Upgrade Time"
    if any("Build Time" in h or "Upgrade Time" in h for h in headers):
        target_table = table
        break

if not target_table:
    print("Таблица с апгрейд-таймингом не найдена.")
else:
    headers = [th.get_text(strip=True) for th in target_table.find_all("th")]
    level_idx = None
    time_idx = None
    for i, header in enumerate(headers):
        if header.lower() in ["level", "уровень"]:
            level_idx = i
        if ("build time" in header.lower() or 
            "upgrade time" in header.lower() or 
            "время постройки" in header.lower() or 
            "время улучшения" in header.lower()):
            time_idx = i
    if level_idx is None or time_idx is None:
        print("Не удалось найти нужные столбцы.")
    else:
        data = []
        for row in target_table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) > max(level_idx, time_idx):
                level = cells[level_idx].get_text(strip=True)
                build_time = cells[time_idx].get_text(strip=True)
                build_time = re.sub(r"\[\d+\]", "", build_time)
                data.append({"level": level, "build_time": build_time})
        with open("clash/cannon_build_times.json", "w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
        print("Готово! Данные сохранены в clash/cannon_build_times.json")
