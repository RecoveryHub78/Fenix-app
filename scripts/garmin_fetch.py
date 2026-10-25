#!/usr/bin/env python3
"""Выгрузка данных из Garmin Connect Personal API.

Ключ берётся из переменной окружения GARMIN_API_KEY (личный API-ключ из
connect.garmin.com → Настройки → Личный API-ключ). Ключ обменивается на
токен доступа (живёт 24 часа), затем скачиваются данные за N дней.

Запуск:  python3 scripts/garmin_fetch.py [дней] [папка_для_json]
"""
import datetime as dt
import json
import os
import sys
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
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        print(f"  ! {path}: HTTP {e.code}", file=sys.stderr)
        return None


def fetch(days=28):
    api_key = os.environ.get("GARMIN_API_KEY")
    if not api_key:
        sys.exit("GARMIN_API_KEY не задан")
    token = get_token(api_key)

    end = dt.date.today()
    start = end - dt.timedelta(days=days - 1)
    s, e = start.isoformat(), end.isoformat()
    dates = [(start + dt.timedelta(d)).isoformat() for d in range(days)]

    data = {"from": s, "to": e, "fetchedAt": dt.datetime.now().isoformat(timespec="seconds")}
    data["profile"] = get(token, "/userprofile-service/userprofile/settings")
    data["hrZones"] = get(token, "/biometric-service/heartRateZones/v2")
    data["activities"] = get(token, "/activitylist-service/activities/search/activities",
                             startDate=s, endDate=e, limit=200)
    data["hrv"] = get(token, f"/hrv-service/hrv/daily/{s}/{e}")
    data["bodyBattery"] = get(token, "/wellness-service/wellness/bodyBattery/reports/daily",
                              startDate=s, endDate=e)
    data["steps"] = get(token, f"/usersummary-service/stats/steps/daily/{s}/{e}")
    data["stress"] = get(token, f"/usersummary-service/stats/stress/daily/{s}/{e}")
    data["weight"] = get(token, f"/weight-service/weight/range/{s}/{e}")
    data["fitnessAge"] = get(token, f"/fitnessage-service/fitnessage/v2/{e}")
    data["sleep"] = {d: get(token, "/sleep-service/sleep/dailySleep", date=d) for d in dates}
    data["summary"] = {d: get(token, "/usersummary-service/usersummary/daily", calendarDate=d)
                       for d in dates}
    return data


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 28
    out = sys.argv[2] if len(sys.argv) > 2 else "garmin_raw.json"
    data = fetch(days)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"Сохранено в {out}: тренировок {len(data['activities'] or [])}, "
          f"период {data['from']} — {data['to']}")
