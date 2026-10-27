"""Norman weather: Snowflake connector with sample JSON fallback."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SQL_PATH = Path(__file__).resolve().parent.parent / "sql" / "norman_weather.sql"
SAMPLE_WEATHER = DATA_DIR / "sample_weather.json"
CACHE_WEATHER = DATA_DIR / "cache_weather.json"

# Built-in query against Snowflake Public Data (Free) NOAA tables for Norman, OK.
# Marketplace share is typically named SNOWFLAKE_PUBLIC_DATA_FREE after "Get".
NOAA_NORMAN_SQL = """
SELECT
  DATE_TRUNC('DAY', ts.date) AS obs_date,
  idx.noaa_weather_station_id AS station_id,
  idx.noaa_weather_station_name AS station_name,
  idx.city_name AS city,
  idx.state_name AS state,
  MAX(CASE WHEN LOWER(ts.variable) LIKE '%temp%avg%' OR LOWER(ts.variable) = 'average_temperature'
           THEN ts.value END) AS temp_avg_c,
  MAX(CASE WHEN LOWER(ts.variable) LIKE '%temp%max%' OR LOWER(ts.variable) = 'maximum_temperature'
           THEN ts.value END) AS temp_max_c,
  MAX(CASE WHEN LOWER(ts.variable) LIKE '%temp%min%' OR LOWER(ts.variable) = 'minimum_temperature'
           THEN ts.value END) AS temp_min_c,
  MAX(CASE WHEN LOWER(ts.variable) LIKE '%precip%' THEN ts.value END) AS precip_mm,
  MAX(CASE WHEN LOWER(ts.variable) LIKE '%wind%' THEN ts.value END) AS wind_mps
FROM SNOWFLAKE_PUBLIC_DATA_FREE.PUBLIC_DATA_FREE.NOAA_WEATHER_METRICS_TIMESERIES ts
JOIN SNOWFLAKE_PUBLIC_DATA_FREE.PUBLIC_DATA_FREE.NOAA_WEATHER_STATION_INDEX idx
  ON ts.noaa_weather_station_id = idx.noaa_weather_station_id
WHERE
  UPPER(COALESCE(idx.state_name, '')) IN ('OK', 'OKLAHOMA')
  AND (
    UPPER(COALESCE(idx.city_name, '')) LIKE '%NORMAN%'
    OR UPPER(COALESCE(idx.noaa_weather_station_name, '')) LIKE '%NORMAN%'
  )
  AND ts.date >= DATEADD('day', -14, CURRENT_DATE())
GROUP BY 1, 2, 3, 4, 5
ORDER BY obs_date DESC
LIMIT 14
"""


def apply_snowflake_env(overrides: dict[str, str] | None = None) -> None:
    """Set/override Snowflake env vars for this process (used by Streamlit form)."""
    if not overrides:
        return
    for key, value in overrides.items():
        if value is None:
            continue
        value = str(value).strip()
        if value:
            os.environ[key] = value


def _snowflake_configured() -> bool:
    required = ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD")
    return all(os.getenv(k) for k in required)


def snowflake_config_status() -> dict[str, Any]:
    keys = [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_SCHEMA",
        "SNOWFLAKE_ROLE",
    ]
    present = {k: bool(os.getenv(k)) for k in keys}
    return {
        "configured": _snowflake_configured(),
        "present": present,
        "account": os.getenv("SNOWFLAKE_ACCOUNT") or "",
        "user": os.getenv("SNOWFLAKE_USER") or "",
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        "database": os.getenv("SNOWFLAKE_DATABASE", "SNOWFLAKE_PUBLIC_DATA_FREE"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC_DATA_FREE"),
    }


def _connect_snowflake():
    import snowflake.connector

    kwargs: dict[str, Any] = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "password": os.environ["SNOWFLAKE_PASSWORD"],
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
    }
    # Database/schema optional — NOAA query uses fully-qualified names
    database = os.getenv("SNOWFLAKE_DATABASE")
    schema = os.getenv("SNOWFLAKE_SCHEMA")
    if database:
        kwargs["database"] = database
    if schema:
        kwargs["schema"] = schema
    role = os.getenv("SNOWFLAKE_ROLE")
    if role:
        kwargs["role"] = role
    return snowflake.connector.connect(**kwargs)


def test_snowflake_connection() -> dict[str, Any]:
    """Validate credentials and list weather-related databases if reachable."""
    if not _snowflake_configured():
        return {
            "ok": False,
            "error": "Missing SNOWFLAKE_ACCOUNT / SNOWFLAKE_USER / SNOWFLAKE_PASSWORD",
            "version": None,
            "databases": [],
        }
    try:
        conn = _connect_snowflake()
        try:
            cur = conn.cursor()
            cur.execute("SELECT CURRENT_VERSION(), CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE()")
            version, user, role, wh = cur.fetchone()
            cur.execute("SHOW DATABASES")
            dbs = [row[1] for row in cur.fetchall()]
            weatherish = [
                d
                for d in dbs
                if any(tok in d.upper() for tok in ("WEATHER", "PUBLIC_DATA", "NOAA", "NWS", "ENVIRONMENT"))
            ]
            return {
                "ok": True,
                "error": None,
                "version": version,
                "user": user,
                "role": role,
                "warehouse": wh,
                "databases": dbs,
                "weather_databases": weatherish,
            }
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc),
            "version": None,
            "databases": [],
        }


def _c_to_f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round((float(value) * 9.0 / 5.0) + 32.0, 1)
    except (TypeError, ValueError):
        return None


def _mps_to_mph(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return round(float(value) * 2.23694, 1)
    except (TypeError, ValueError):
        return 0.0


def _mm_to_in(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return round(float(value) / 25.4, 3)
    except (TypeError, ValueError):
        return 0.0


def _rows_to_payload(rows: list[dict[str, Any]], source: str) -> dict[str, Any]:
    hourly = []
    for row in rows:
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
                "gust_mph": float(norm.get("gust_mph") or norm.get("wind_mph") or 0),
                "condition": str(norm.get("condition") or "Unknown"),
                "alerts": alerts,
            }
        )
    return {
        "source": source,
        "location": "Norman, OK",
        "hourly": hourly,
    }


def _noaa_daily_to_hourly(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Expand NOAA daily Norman rows into daytime hourly points the scheduler can match."""
    hourly: list[dict[str, Any]] = []
    for row in rows:
        norm = {str(k).lower(): v for k, v in row.items()}
        raw_date = norm.get("obs_date") or norm.get("date")
        if hasattr(raw_date, "strftime"):
            day = raw_date.strftime("%Y-%m-%d")
        else:
            day = str(raw_date)[:10]
        temp_f = _c_to_f(norm.get("temp_avg_c"))
        if temp_f is None:
            temp_f = _c_to_f(norm.get("temp_max_c")) or 70.0
        precip_in = _mm_to_in(norm.get("precip_mm"))
        wind_mph = _mps_to_mph(norm.get("wind_mps"))
        if precip_in >= 0.5:
            condition = "Heavy rain"
            precip_prob = 90.0
            alerts = ["Flood Watch"] if precip_in >= 1.0 else []
        elif precip_in >= 0.1:
            condition = "Rain"
            precip_prob = 70.0
            alerts = []
        elif precip_in > 0:
            condition = "Light rain possible"
            precip_prob = 40.0
            alerts = []
        else:
            condition = "Clear to partly cloudy"
            precip_prob = 10.0
            alerts = []
        # Emit campus-relevant daytime hours
        for hour in (8, 9, 10, 11, 12, 13, 14, 15, 16, 17):
            # Slight diurnal swing from daily average
            swing = {8: -4, 9: -2, 10: 0, 11: 1, 12: 2, 13: 3, 14: 3, 15: 2, 16: 1, 17: 0}[hour]
            hourly.append(
                {
                    "time": f"{day}T{hour:02d}:00:00-05:00",
                    "temp_f": round(temp_f + swing, 1),
                    "precip_in": precip_in / 10.0,
                    "precip_prob": precip_prob,
                    "wind_mph": wind_mph,
                    "gust_mph": round(wind_mph * 1.35, 1),
                    "condition": condition,
                    "alerts": alerts,
                }
            )
    hourly.sort(key=lambda h: h["time"])
    station = ""
    if rows:
        first = {str(k).lower(): v for k, v in rows[0].items()}
        station = str(first.get("station_name") or first.get("station_id") or "")
    return {
        "source": "snowflake_noaa",
        "location": "Norman, OK",
        "station": station,
        "note": "Expanded from Snowflake Public Data (Free) NOAA daily metrics for Norman.",
        "hourly": hourly,
    }


def _extract_statements(sql: str) -> list[str]:
    chunks = []
    for block in sql.split(";"):
        lines = [
            ln
            for ln in block.splitlines()
            if ln.strip() and not ln.strip().startswith("--")
        ]
        if lines:
            chunks.append("\n".join(lines))
    return chunks


def _run_query(query: str) -> list[dict[str, Any]]:
    import snowflake.connector

    conn = _connect_snowflake()
    try:
        cur = conn.cursor(snowflake.connector.DictCursor)
        cur.execute(query)
        return list(cur.fetchall())
    finally:
        conn.close()


def fetch_from_snowflake() -> dict[str, Any]:
    """Pull Norman weather from Snowflake.

    Prefers committed sql/norman_weather.sql when it returns rows; otherwise runs the
    built-in NOAA Public Data (Free) Norman query and expands daily → hourly.
    """
    statements = _extract_statements(SQL_PATH.read_text(encoding="utf-8"))
    last_error: Exception | None = None

    for query in statements:
        try:
            rows = _run_query(query)
            if not rows:
                continue
            sample = {str(k).lower(): v for k, v in rows[0].items()}
            if "temp_f" in sample or "time" in sample:
                payload = _rows_to_payload(rows, source="snowflake")
                _write_cache(payload)
                return payload
            if "temp_avg_c" in sample or "obs_date" in sample or "precip_mm" in sample:
                payload = _noaa_daily_to_hourly(rows)
                _write_cache(payload)
                return payload
            # Unknown shape — still try generic mapping
            payload = _rows_to_payload(rows, source="snowflake")
            if payload["hourly"]:
                _write_cache(payload)
                return payload
        except Exception as exc:  # noqa: BLE001
            last_error = exc

    # Built-in NOAA fallback query
    try:
        rows = _run_query(NOAA_NORMAN_SQL)
        if rows:
            payload = _noaa_daily_to_hourly(rows)
            _write_cache(payload)
            return payload
        raise RuntimeError("NOAA Norman query returned 0 rows — check Marketplace share is installed.")
    except Exception as exc:  # noqa: BLE001
        if last_error:
            raise RuntimeError(f"SQL file failed ({last_error}); NOAA fallback failed ({exc})") from exc
        raise


def _write_cache(payload: dict[str, Any]) -> None:
    try:
        CACHE_WEATHER.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    except OSError:
        pass


def load_sample_weather() -> dict[str, Any]:
    # Prefer last successful Snowflake cache if present and fresh-ish
    if CACHE_WEATHER.exists():
        try:
            with CACHE_WEATHER.open(encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("hourly"):
                cached = dict(cached)
                cached["source"] = cached.get("source", "cache") + "_cache"
                return cached
        except (OSError, json.JSONDecodeError):
            pass
    with SAMPLE_WEATHER.open(encoding="utf-8") as f:
        return json.load(f)


def get_weather(force_sample: bool = False) -> dict[str, Any]:
    """Return Norman hourly weather. Prefers Snowflake; falls back to sample/cache JSON."""
    if force_sample:
        data = json.loads(SAMPLE_WEATHER.read_text(encoding="utf-8"))
        data["source"] = "sample_fallback"
        data["fallback_reason"] = "Forced sample weather from sidebar."
        return data

    if not _snowflake_configured():
        data = load_sample_weather()
        data["source"] = data.get("source", "sample_fallback")
        data["fallback_reason"] = (
            "Snowflake credentials not set; using committed sample weather "
            "(or last Snowflake cache if present)."
        )
        return data

    try:
        return fetch_from_snowflake()
    except Exception as exc:  # noqa: BLE001 — demo path must never hard-fail
        data = load_sample_weather()
        data["source"] = data.get("source", "sample_fallback")
        data["fallback_reason"] = f"Snowflake query failed ({exc}); using sample/cache weather."
        return data


def weather_window(weather: dict[str, Any], start_iso: str, end_iso: str) -> list[dict[str, Any]]:
    """Return hourly points overlapping [start_iso, end_iso]."""
    points = []
    for h in weather.get("hourly", []):
        t = h.get("time", "")
        if start_iso <= t <= end_iso or (t[:13] >= start_iso[:13] and t[:13] <= end_iso[:13]):
            points.append(h)
    return points
