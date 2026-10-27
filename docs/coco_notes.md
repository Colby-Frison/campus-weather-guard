# Snowflake CoCo notes — Campus Weather Guard

Hacklahoma Hacktoberfest Hack Day (2026-10-26). Work started at the event on Colby's Windows laptop.

## What CoCo helped with

- Explored **Snowflake Public Data (Free)** weather & environment tables for **Norman, OK**.
- Drafted the NOAA Norman daily query committed at [`sql/norman_weather.sql`](../sql/norman_weather.sql).
- Mapped free-tier column shapes (station index + metrics timeseries variables) that `src/weather.py` normalizes into daytime hourly points for schedule overlap.

## Dataset named in the demo

**Snowflake Public Data (Free)** → shared database `SNOWFLAKE_PUBLIC_DATA_FREE.PUBLIC_DATA_FREE`

Primary tables used:

| Table | Role |
| --- | --- |
| `NOAA_WEATHER_STATION_INDEX` | Find Norman / Oklahoma stations |
| `NOAA_WEATHER_METRICS_TIMESERIES` | Daily temp / precip / wind values |

Notes:

- Free NOAA history can lag (~months). That still proves the Snowflake path for judges.
- NWS hourly forecasts / alerts live in broader Weather & Environment products; if your trial includes them, adapt SQL column names and the app will accept a `temp_f` + `time` shaped result directly.
- When credentials are absent or the query fails, the app loads [`data/sample_weather.json`](../data/sample_weather.json) (or `data/cache_weather.json` from the last successful pull).

## How to wire live Snowflake

1. Open a Snowflake trial (or event-provided account).
2. Marketplace → search **Snowflake Public Data (Free)** → **Get** (do not rename).
3. Copy `.env.example` → `.env` and fill `SNOWFLAKE_ACCOUNT` / `USER` / `PASSWORD` (never commit `.env`).
   - Or paste the same values in the Streamlit sidebar **Credentials (session)** form.
4. Run `python scripts/test_integrations.py` or click **Test Snowflake connection**.
5. Uncheck **Force sample weather**.

## Dual-challenge checklist

| Requirement | Where it lives |
| --- | --- |
| Public GitHub + MIT | `LICENSE`, this repo |
| Open-weight model plans/alerts | `src/llm.py` (Ollama Gemma GPU default; `LLM_PROVIDER=api` fallback) |
| Document free weather dataset + CoCo | this file + README |
| Work starts at the event | Hack Day timestamps / commit history |
