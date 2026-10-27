# Snowflake CoCo notes — Campus Weather Guard

Hacklahoma Hacktoberfest Hack Day (2026-10-26). Work started at the event on Colby's Windows laptop.

## What CoCo helped with

- Explored Snowflake's free / trial **weather & environment** marketplace-style data for **Norman, OK**.
- Drafted the hourly forecast + alert overlap query committed at [`sql/norman_weather.sql`](../sql/norman_weather.sql).
- Confirmed column shapes (temp °F, precip inches / probability, wind / gust, condition text, alert event types) that the app normalizes in `src/weather.py`.

## Dataset named in the demo

**WEATHER__ENVIRONMENT** (Snowflake free weather dataset family) — Norman / Cleveland County hourly forecast observations with optional alert overlay.

When Snowflake credentials are not present, the app loads [`data/sample_weather.json`](../data/sample_weather.json), a committed cache shaped like that pull so judges can run the demo offline.

## How to wire live Snowflake

1. Create a trial account and note account locator, user, password, warehouse.
2. Copy `.env.example` → `.env` and fill `SNOWFLAKE_*` values (never commit `.env`).
3. Uncheck **Force sample weather** in the Streamlit sidebar.
4. If the marketplace schema names differ, edit `sql/norman_weather.sql` to match — CoCo is useful for discovering the exact `DATABASE.SCHEMA.TABLE` identifiers.

## Dual-challenge checklist

| Requirement | Where it lives |
| --- | --- |
| Public GitHub + MIT | `LICENSE`, this repo |
| Open-weight model plans/alerts | `src/llm.py` (Ollama Gemma GPU default; `LLM_PROVIDER=api` fallback) |
| Document free weather dataset + CoCo | this file + README |
| Work starts at the event | Hack Day timestamps / commit history |
