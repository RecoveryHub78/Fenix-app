#!/usr/bin/env python3
"""Превращает выгрузку garmin_fetch.py в три таблицы для дашборда.

Запуск:  python3 scripts/garmin_dashboard_data.py garmin_raw.json [папка]
Создаёт activities.json, daily.json и hr_zones.json.
"""
import json
import os
import sys


def r(x, n=1):
    return None if x is None else round(x, n)


def activities(raw):
    rows = []
    for a in raw.get("activities") or []:
        speed = a.get("averageSpeed")
        rows.append({
            "id": str(a["activityId"]),
            "date": a["startTimeLocal"][:10],
            "start": a["startTimeLocal"][11:16],
            "type": a["activityType"]["typeKey"],
            "name": a.get("activityName"),
            "distance_km": r((a.get("distance") or 0) / 1000, 2),
            "duration_min": r((a.get("duration") or 0) / 60),
            "pace_sec_km": r(1000 / speed, 0) if speed else None,
            "avg_hr": a.get("averageHR"),
            "max_hr": a.get("maxHR"),
            "cadence": r(a.get("averageRunningCadenceInStepsPerMinute"), 0),
            "aerobic_te": r(a.get("aerobicTrainingEffect")),
            "anaerobic_te": r(a.get("anaerobicTrainingEffect")),
            "te_label": a.get("trainingEffectLabel"),
            "elev_gain_m": r(a.get("elevationGain"), 0),
            "calories": r(a.get("calories"), 0),
            **{f"z{i}_min": r((a.get(f"hrTimeInZone_{i}") or 0) / 60) for i in range(1, 6)},
        })
    return sorted(rows, key=lambda x: (x["date"], x["start"]))


def daily(raw):
    hrv = {h["calendarDate"]: h for h in (raw.get("hrv") or {}).get("hrvSummaries", [])}
    bb = {b["date"]: b for b in raw.get("bodyBattery") or []}
    steps = {s["calendarDate"]: s for s in raw.get("steps") or []}
    rows = []
    for day in sorted(raw["summary"]):
        s = raw["summary"].get(day) or {}
        sl = raw["sleep"].get(day) or {}
        h = hrv.get(day) or {}
        base = h.get("baseline") or {}
        score = ((sl.get("sleepScores") or {}).get("overall") or {})
        sec = lambda k: r((sl.get(k) or 0) / 3600, 2) if sl.get("sleepTimeSeconds") else None
        rows.append({
            "date": day,
            "rhr": s.get("restingHeartRate"),
            "rhr_7d": s.get("lastSevenDaysAvgRestingHeartRate"),
            "hrv_night": h.get("lastNightAvg"),
            "hrv_week": h.get("weeklyAvg"),
            "hrv_status": h.get("status"),
            "hrv_bal_low": base.get("balancedLow"),
            "hrv_bal_up": base.get("balancedUpper"),
            "sleep_h": sec("sleepTimeSeconds"),
            "deep_h": sec("deepSleepSeconds"),
            "light_h": sec("lightSleepSeconds"),
            "rem_h": sec("remSleepSeconds"),
            "awake_h": sec("awakeSleepSeconds"),
            "sleep_score": score.get("value"),
            "bb_wake": s.get("bodyBatteryAtWakeTime"),
            "bb_high": s.get("bodyBatteryHighestValue"),
            "bb_low": s.get("bodyBatteryLowestValue"),
            "bb_charged": (bb.get(day) or {}).get("charged"),
            "bb_drained": (bb.get(day) or {}).get("drained"),
            "stress_avg": s.get("averageStressLevel"),
            "steps": (steps.get(day) or {}).get("totalSteps"),
        })
    return rows


def zones(raw):
    z = next((z for z in raw.get("hrZones") or [] if z.get("sport") == "DEFAULT"), None)
    if not z:
        return []
    floors = [z[f"zone{i}Floor"] for i in range(1, 6)] + [z["maxHeartRateUsed"]]
    return [{"zone": f"Z{i + 1}", "from_bpm": floors[i], "to_bpm": floors[i + 1] - (i < 4)}
            for i in range(5)]


if __name__ == "__main__":
    raw = json.load(open(sys.argv[1], encoding="utf-8"))
    out = sys.argv[2] if len(sys.argv) > 2 else "."
    for name, rows in (("activities", activities(raw)), ("daily", daily(raw)),
                       ("hr_zones", zones(raw))):
        with open(os.path.join(out, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
        print(name, len(rows))
