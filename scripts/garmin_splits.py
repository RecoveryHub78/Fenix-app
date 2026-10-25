#!/usr/bin/env python3
"""Покилометровые сплиты тренировки из её FIT-файла (Garmin Connect Personal API).

Нужен пакет garmin-fit-sdk (pip install garmin-fit-sdk).
Запуск:  python3 scripts/garmin_splits.py <activityId> [файл.json]

Сплиты берутся из кругов (lap) FIT-файла, поэтому на часах должен быть
включён автокруг на 1 км. GPS-координаты в результат не попадают.
"""
import io
import json
import os
import sys
import urllib.request
import zipfile

from garmin_fit_sdk import Decoder, Stream

sys.path.insert(0, os.path.dirname(__file__))
import garmin_fetch  # noqa: E402


def download_fit(token, activity_id):
    req = urllib.request.Request(
        f"{garmin_fetch.BASE}/download-service/files/activity/{activity_id}",
        headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=120) as r:
        blob = r.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".fit"))
        return z.read(name)


def r(x, n=1):
    return None if x is None else round(x, n)


def splits(fit_bytes):
    messages, errors = Decoder(Stream.from_byte_array(bytearray(fit_bytes))).read()
    if errors:
        raise RuntimeError(f"FIT не разобран: {errors}")
    rows, elapsed, dist = [], 0.0, 0.0
    for i, lap in enumerate(messages.get("lap_mesgs", []), 1):
        sec = lap.get("total_timer_time") or 0
        m = lap.get("total_distance") or 0
        elapsed += sec
        dist += m
        cad = lap.get("avg_running_cadence") or lap.get("avg_cadence")
        frac = lap.get("avg_fractional_cadence") or 0
        rows.append({
            "km": i,
            "distance_m": r(m),
            "time_sec": r(sec),
            "cum_time_sec": r(elapsed),
            "cum_distance_km": r(dist / 1000, 2),
            "pace_sec_km": r(sec / m * 1000, 0) if m else None,
            "avg_hr": lap.get("avg_heart_rate"),
            "max_hr": lap.get("max_heart_rate"),
            # В FIT каденс бега записан на одну ногу: умножаем на 2, чтобы получить шаги/мин.
            "cadence_spm": r((cad + frac) * 2, 0) if cad else None,
            "stride_m": r((lap.get("avg_step_length") or 0) / 1000, 2) or None,
            "gct_ms": r(lap.get("avg_stance_time"), 0),
            "vert_osc_cm": r((lap.get("avg_vertical_oscillation") or 0) / 10) or None,
            "power_w": lap.get("avg_power"),
            "ascent_m": lap.get("total_ascent"),
            "descent_m": lap.get("total_descent"),
            "temp_c": lap.get("avg_temperature"),
        })
    return rows


if __name__ == "__main__":
    activity_id = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else f"splits_{activity_id}.json"
    token = garmin_fetch.get_token(os.environ["GARMIN_API_KEY"])
    rows = splits(download_fit(token, activity_id))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)
    print(f"Сохранено в {out}: кругов {len(rows)}")
