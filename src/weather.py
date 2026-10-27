"""Norman weather: Snowflake connector with sample JSON fallback."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SQL_PATH = Path(__file__).resolve().parent.parent / "sql" / "norman_weather.sql"
SAMPLE_WEATHER = DATA_DIR / "sample_weather.json"


def _snowflake_configured() -> bool:
    required = ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD")
    return all(os.getenv(k) for k in required)


def _connect_snowflake():
    import snowflake.connector

    kwargs: dict[str, Any] = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "password": os.environ["SNOWFLAKE_PASSWORD"],
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        "database": os.getenv("SNOWFLAKE_DATABASE", "WEATHER__ENVIRONMENT"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC"),
    }
    role = os.getenv("SNOWFLAKE_ROLE")
    if role:
        kwargs["role"] = role
    return snowflake.connector.connect(**kwargs)


def _rows_to_payload(rows: list[dict[str, Any]], source: str) -> dict[str, Any]:
    hourly = []
    for row in rows:
        # Normalize possibly-uppercased Snowflake column names
        norm = {str(k).lower(): v for k, v in row.items()}
        alerts = norm.get("alerts") or []
        if isinstance(alerts, str):
            alerts = [a.strip() for a in alerts.split(",") if a.strip()]
        hourly.append(
            {
                "time": str(norm.get("time") or ""),
                "temp_f": float(norm.get("temp_f") or 0),
                "precip_in": float(norm.get("precip_in") or 0),
                "precip_prob": float(norm.get("precip_prob") or 0),
                "wind_mph": float(norm.get("wind_mph") or 0),
                "gust_mph": float(norm.get("gust_mph") or 0),
                "condition": str(norm.get("condition") or "Unknown"),
                "alerts": alerts,
            }
        )
    return {
        "source": source,
        "location": "Norman, OK",
        "hourly": hourly,
    }


def _extract_main_select(sql: str) -> str:
    """Return the first executable statement (skip comment-only blocks)."""
    chunks = []
    for block in sql.split(";"):
        lines = [
            ln
            for ln in block.splitlines()
            if ln.strip() and not ln.strip().startswith("--")
        ]
        if lines:
            chunks.append("\n".join(lines))
    return chunks[0] if chunks else sql


def fetch_from_snowflake() -> dict[str, Any]:
    import snowflake.connector

    query = _extract_main_select(SQL_PATH.read_text(encoding="utf-8"))
    conn = _connect_snowflake()
    try:
        cur = conn.cursor(snowflake.connector.DictCursor)
        cur.execute(query)
        rows = cur.fetchall()
        return _rows_to_payload(rows, source="snowflake")
    finally:
        conn.close()


def load_sample_weather() -> dict[str, Any]:
    with SAMPLE_WEATHER.open(encoding="utf-8") as f:
        return json.load(f)


def get_weather(force_sample: bool = False) -> dict[str, Any]:
    """Return Norman hourly weather. Prefers Snowflake; falls back to sample JSON."""
    if force_sample or not _snowflake_configured():
        data = load_sample_weather()
        data["source"] = data.get("source", "sample_fallback")
        if not _snowflake_configured():
            data["fallback_reason"] = (
                "Snowflake credentials not set; using committed sample weather."
            )
        elif force_sample:
            data["fallback_reason"] = "Forced sample weather from sidebar."
        return data

    try:
        return fetch_from_snowflake()
    except Exception as exc:  # noqa: BLE001 — demo path must never hard-fail
        data = load_sample_weather()
        data["source"] = "sample_fallback"
        data["fallback_reason"] = f"Snowflake query failed ({exc}); using sample weather."
        return data


def weather_window(weather: dict[str, Any], start_iso: str, end_iso: str) -> list[dict[str, Any]]:
    """Return hourly points overlapping [start_iso, end_iso]."""
    points = []
    for h in weather.get("hourly", []):
        t = h.get("time", "")
        if start_iso <= t <= end_iso or (t[:13] >= start_iso[:13] and t[:13] <= end_iso[:13]):
            points.append(h)
    return points
