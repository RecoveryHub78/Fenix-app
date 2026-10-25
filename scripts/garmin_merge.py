#!/usr/bin/env python3
"""Добавляет свежую выгрузку к данным, которые уже лежат на дашборде.

Запуск:  python3 scripts/garmin_merge.py <старая_папка> <новая_папка> <папка_результата> [дней]

В каждой папке — activities.json, daily.json, hr_zones.json (как их делает
garmin_dashboard_data.py). Новые записи заменяют старые с тем же ключом
(тренировка — по id, день — по дате). Остаются только последние N дней
(по умолчанию 28), считая от самой свежей даты. Зоны берутся из новой выгрузки.
"""
import datetime as dt
import json
import os
import sys


def load(folder, name):
    path = os.path.join(folder, name + ".json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def merge(old, new, key):
    rows = {r[key]: r for r in old}
    rows.update({r[key]: r for r in new})
    return list(rows.values())


def main(old_dir, new_dir, out_dir, days=28):
    daily = merge(load(old_dir, "daily"), load(new_dir, "daily"), "date")
    acts = merge(load(old_dir, "activities"), load(new_dir, "activities"), "id")
    zones = load(new_dir, "hr_zones") or load(old_dir, "hr_zones")

    last = max(r["date"] for r in daily)
    start = (dt.date.fromisoformat(last) - dt.timedelta(days=days - 1)).isoformat()
    daily = sorted((r for r in daily if r["date"] >= start), key=lambda r: r["date"])
    acts = sorted((a for a in acts if a["date"] >= start), key=lambda a: (a["date"], a["start"]))

    os.makedirs(out_dir, exist_ok=True)
    for name, rows in (("activities", acts), ("daily", daily), ("hr_zones", zones)):
        with open(os.path.join(out_dir, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
    print(f"Период {start} — {last}: дней {len(daily)}, тренировок {len(acts)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 28)
