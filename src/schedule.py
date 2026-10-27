"""Schedule loading, weather overlap, and severity thresholds."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DAY_MAP = {
    "Mon": 0,
    "Tue": 1,
    "Wed": 2,
    "Thu": 3,
    "Fri": 4,
    "Sat": 5,
    "Sun": 6,
}

# Severity: info < watch < warning < emergency
SEVERITY_RANK = {"none": 0, "info": 1, "watch": 2, "warning": 3, "emergency": 4}


def load_json(name: str) -> dict[str, Any]:
    with (DATA_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)


def load_buildings() -> dict[str, Any]:
    return load_json("buildings.json")


def load_student_schedule() -> dict[str, Any]:
    return load_json("sample_student_schedule.json")


def load_professor_schedule() -> dict[str, Any]:
    return load_json("sample_professor_schedule.json")


def building_lookup() -> dict[str, dict[str, Any]]:
    buildings = load_buildings()["buildings"]
    return {b["id"]: b for b in buildings}


def parse_hhmm(value: str) -> tuple[int, int]:
    h, m = value.split(":")
    return int(h), int(m)


def class_datetimes_for_week(
    classes: list[dict[str, Any]],
    week_start: datetime | None = None,
) -> list[dict[str, Any]]:
    """Expand recurring class rows into concrete sessions for the demo week."""
    if week_start is None:
        # Anchor demo week to Mon 2026-10-26 (Hack Day) so sample weather aligns
        week_start = datetime(2026, 10, 26, 0, 0, 0)
    # Normalize to Monday
    week_start = week_start - timedelta(days=week_start.weekday())

    sessions: list[dict[str, Any]] = []
    for cls in classes:
        for day in cls.get("days", []):
            offset = DAY_MAP.get(day)
            if offset is None:
                continue
            sh, sm = parse_hhmm(cls["start"])
            eh, em = parse_hhmm(cls["end"])
            start_dt = week_start + timedelta(days=offset, hours=sh, minutes=sm)
            end_dt = week_start + timedelta(days=offset, hours=eh, minutes=em)
            sessions.append(
                {
                    **cls,
                    "day": day,
                    "start_dt": start_dt,
                    "end_dt": end_dt,
                    "start_iso": start_dt.strftime("%Y-%m-%dT%H:%M:%S-05:00"),
                    "end_iso": end_dt.strftime("%Y-%m-%dT%H:%M:%S-05:00"),
                }
            )
    sessions.sort(key=lambda s: s["start_dt"])
    return sessions


def classify_hour_severity(hour: dict[str, Any]) -> str:
    alerts = [a.upper() for a in hour.get("alerts") or []]
    gust = float(hour.get("gust_mph") or 0)
    precip_prob = float(hour.get("precip_prob") or 0)
    precip_in = float(hour.get("precip_in") or 0)
    condition = (hour.get("condition") or "").lower()

    if any("TORNADO WARNING" in a for a in alerts):
        return "emergency"
    if any("WARNING" in a for a in alerts) or gust >= 55 or "severe" in condition:
        return "warning"
    if any("WATCH" in a for a in alerts) or gust >= 40 or precip_in >= 0.25 or precip_prob >= 80:
        return "watch"
    if precip_prob >= 40 or precip_in >= 0.05 or gust >= 25 or "rain" in condition or "shower" in condition:
        return "info"
    return "none"


def session_weather_summary(session: dict[str, Any], weather: dict[str, Any]) -> dict[str, Any]:
    # Include ~90 min lead-in for commute overlap
    lead = session["start_dt"] - timedelta(minutes=90)
    lead_iso = lead.strftime("%Y-%m-%dT%H:%M:%S-05:00")
    points = []
    for h in weather.get("hourly", []):
        t = h.get("time", "")
        if lead_iso <= t <= session["end_iso"]:
            points.append(h)

    if not points:
        # Fallback: same calendar date only (avoid cross-day false storms)
        day = session["start_dt"].strftime("%Y-%m-%d")
        points = [h for h in weather.get("hourly", []) if h.get("time", "").startswith(day)][:4]

    severities = [classify_hour_severity(h) for h in points]
    max_sev = max(severities, key=lambda s: SEVERITY_RANK[s]) if severities else "none"
    worst = points[severities.index(max_sev)] if points else {}

    return {
        "severity": max_sev,
        "hours": points,
        "worst": worst,
        "alerts": sorted({a for h in points for a in (h.get("alerts") or [])}),
    }


def recommend_mode(severity: str, walk_min: int, precip_prob: float, gust: float) -> str:
    if severity in ("warning", "emergency"):
        return "wait"
    if severity == "watch" or precip_prob >= 60 or gust >= 30:
        return "drive"
    if walk_min <= 12 and precip_prob < 35 and gust < 20:
        return "walk"
    if walk_min <= 20 and precip_prob < 50:
        return "bike"
    return "drive"


def leave_by_time(session: dict[str, Any], mode: str, walk_min: int) -> datetime:
    buffers = {"walk": walk_min, "bike": max(5, walk_min // 3), "drive": 12, "wait": 0}
    buffer = buffers.get(mode, 12)
    return session["start_dt"] - timedelta(minutes=buffer)


def bring_list(severity: str, hour: dict[str, Any]) -> list[str]:
    items: list[str] = ["student ID", "laptop"]
    precip = float(hour.get("precip_prob") or 0)
    temp = float(hour.get("temp_f") or 70)
    if precip >= 30 or severity in ("info", "watch", "warning"):
        items.append("umbrella / rain jacket")
    if temp <= 55:
        items.append("light jacket")
    if severity in ("watch", "warning", "emergency"):
        items.append("phone charged (weather alerts)")
    if severity in ("warning", "emergency"):
        items.append("delay commute until warning expires")
    return items


def build_student_plans(schedule: dict[str, Any], weather: dict[str, Any]) -> list[dict[str, Any]]:
    buildings = building_lookup()
    sessions = class_datetimes_for_week(schedule.get("classes", []))
    plans = []
    for session in sessions:
        b = buildings.get(session.get("building"), {"name": session.get("building"), "walk_min_from_campus_core": 10})
        summary = session_weather_summary(session, weather)
        worst = summary.get("worst") or {}
        walk_min = int(b.get("walk_min_from_campus_core") or 10)
        mode = recommend_mode(
            summary["severity"],
            walk_min,
            float(worst.get("precip_prob") or 0),
            float(worst.get("gust_mph") or 0),
        )
        leave = leave_by_time(session, mode, walk_min)
        plans.append(
            {
                "course": session["course"],
                "title": session.get("title"),
                "building_id": session.get("building"),
                "building_name": b.get("name", session.get("building")),
                "day": session["day"],
                "start": session["start"],
                "end": session["end"],
                "start_iso": session["start_iso"],
                "severity": summary["severity"],
                "alerts": summary["alerts"],
                "mode": mode,
                "leave_by": leave.strftime("%Y-%m-%d %H:%M"),
                "bring": bring_list(summary["severity"], worst),
                "weather_snapshot": {
                    "temp_f": worst.get("temp_f"),
                    "precip_prob": worst.get("precip_prob"),
                    "wind_mph": worst.get("wind_mph"),
                    "gust_mph": worst.get("gust_mph"),
                    "condition": worst.get("condition"),
                },
            }
        )
    return plans


def build_professor_alerts(schedule: dict[str, Any], weather: dict[str, Any]) -> list[dict[str, Any]]:
    buildings = building_lookup()
    sessions = class_datetimes_for_week(schedule.get("classes", []))
    alerts = []
    for session in sessions:
        b = buildings.get(session.get("building"), {"name": session.get("building")})
        summary = session_weather_summary(session, weather)
        if summary["severity"] in ("none", "info"):
            # Still list mild items for demo transparency, but mark as clear
            action = "No cancel-watch needed; proceed as scheduled."
        elif summary["severity"] == "watch":
            action = "WATCH: Monitor radar and university alerts; prepare a cancel/remote contingency."
        elif summary["severity"] == "warning":
            action = "CANCEL-WATCH: Severe weather overlaps class — strongly consider canceling or moving online. Advise only; you decide."
        else:
            action = "EMERGENCY OVERLAP: Do not require in-person attendance. Follow OU emergency guidance."

        alerts.append(
            {
                "course": session["course"],
                "title": session.get("title"),
                "building_name": b.get("name", session.get("building")),
                "day": session["day"],
                "start": session["start"],
                "end": session["end"],
                "severity": summary["severity"],
                "alerts": summary["alerts"],
                "action": action,
                "weather_snapshot": summary.get("worst") or {},
            }
        )
    return alerts
