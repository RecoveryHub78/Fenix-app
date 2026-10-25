#!/usr/bin/env python3
"""Выгрузка данных из Garmin Connect Personal API.

Ключ берётся из переменной окружения GARMIN_API_KEY (личный API-ключ из
connect.garmin.com → Настройки → Личный API-ключ). Ключ обменивается на
токен доступа (живёт 24 часа), затем скачиваются данные за N дней.

Запуск:  python3 scripts/garmin_fetch.py [дней] [файл.json]
         python3 scripts/garmin_fetch.py <с YYYY-MM-DD> <по YYYY-MM-DD> [файл.json]
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://personal.connectapi.garmin.com"
TOKEN_URL = BASE + "/personalapitoken-service/personal-api/personal-api-key/token"


def get_token(api_key):
    req = urllib.request.Request(TOKEN_URL, method="POST",
                                 headers={"Authorization": "ApiKey " + api_key})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode().strip()


def get(token, path, **params):
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    # Garmin отвечает 429, если запросов слишком много подряд: ждём и повторяем.
    for wait in (5, 15, 30, 60, 120, None):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as e:
            if e.code == 429 and wait:
                time.sleep(wait)
                continue
            print(f"  ! {path}: HTTP {e.code}", file=sys.stderr)
            return None


def get_daily(token, path, dates, param):
    """Посуточный эндпоинт: по запросу на день, с паузой, чтобы не упереться в лимит."""
    rows = {}
    for d in dates:
        rows[d] = get(token, path, **{param: d})
        time.sleep(0.5)
    return rows


def chunks(start, end, size=28):
    """Разбивает период на куски: часть эндпоинтов не отдаёт больше месяца за раз."""
    while start <= end:
        stop = min(end, start + dt.timedelta(days=size - 1))
        yield start.isoformat(), stop.isoformat()
        start = stop + dt.timedelta(days=1)


def get_list(token, path_fn, start, end, **params):
    rows = []
    for s, e in chunks(start, end):
        part = get(token, path_fn(s, e), **{k: v.format(s=s, e=e) for k, v in params.items()})
        rows += part or []
    return rows


def fetch_activities(token, s, e):
    rows, offset = [], 0
    while True:
        page = get(token, "/activitylist-service/activities/search/activities",
                   startDate=s, endDate=e, start=offset, limit=100) or []
        rows += page
        if len(page) < 100:
            return rows
        offset += 100


def fetch_range(start, end):
    api_key = os.environ.get("GARMIN_API_KEY")
    if not api_key:
        sys.exit("GARMIN_API_KEY не задан")
    token = get_token(api_key)

    s, e = start.isoformat(), end.isoformat()
    dates = [(start + dt.timedelta(d)).isoformat() for d in range((end - start).days + 1)]

    data = {"from": s, "to": e, "fetchedAt": dt.datetime.now().isoformat(timespec="seconds")}
    data["profile"] = get(token, "/userprofile-service/userprofile/settings")
    data["hrZones"] = get(token, "/biometric-service/heartRateZones/v2")
    data["activities"] = fetch_activities(token, s, e)
    data["hrv"] = {"hrvSummaries": [h for a, b in chunks(start, end)
                                    for h in (get(token, f"/hrv-service/hrv/daily/{a}/{b}") or {})
                                    .get("hrvSummaries", [])]}
    data["bodyBattery"] = get_list(token, lambda a, b: "/wellness-service/wellness/bodyBattery/reports/daily",
                                   start, end, startDate="{s}", endDate="{e}")
    data["steps"] = get_list(token, lambda a, b: f"/usersummary-service/stats/steps/daily/{a}/{b}", start, end)
    data["stress"] = get_list(token, lambda a, b: f"/usersummary-service/stats/stress/daily/{a}/{b}", start, end)
    data["weight"] = get(token, f"/weight-service/weight/range/{s}/{e}")
    data["fitnessAge"] = get(token, f"/fitnessage-service/fitnessage/v2/{e}")
    data["sleep"] = get_daily(token, "/sleep-service/sleep/dailySleep", dates, "date")
    data["summary"] = get_daily(token, "/usersummary-service/usersummary/daily", dates, "calendarDate")
    return data


def fetch(days=28):
    end = dt.date.today()
    return fetch_range(end - dt.timedelta(days=days - 1), end)


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) >= 2 and "-" in args[0] and "-" in args[1]:
        data = fetch_range(dt.date.fromisoformat(args[0]), dt.date.fromisoformat(args[1]))
        out = args[2] if len(args) > 2 else "garmin_raw.json"
    else:
        data = fetch(int(args[0]) if args else 28)
        out = args[1] if len(args) > 1 else "garmin_raw.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"Сохранено в {out}: тренировок {len(data['activities'] or [])}, "
          f"период {data['from']} — {data['to']}")
