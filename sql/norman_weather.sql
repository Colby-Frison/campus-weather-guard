-- Campus Weather Guard — Norman, OK weather pulls
-- Explored with Snowflake CoCo against Snowflake Public Data (Free).
--
-- 1) Preferred live path after Marketplace → Get "Snowflake Public Data (Free)":
--    Database share is typically SNOWFLAKE_PUBLIC_DATA_FREE.PUBLIC_DATA_FREE
-- 2) NOAA tables are daily historical (free tier may lag ~months).
-- 3) App expands daily Norman rows into daytime hourly points in src/weather.py.
-- 4) If you later add NWS forecast/alert listings, adapt column names below.

-- NOAA daily metrics for Norman / Cleveland County area stations
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
LIMIT 14;

-- Discovery helpers (run in CoCo / Snowsight; commented so the connector skips them)
-- SHOW DATABASES;
-- SHOW TABLES IN SCHEMA SNOWFLAKE_PUBLIC_DATA_FREE.PUBLIC_DATA_FREE;
-- SELECT DISTINCT variable FROM SNOWFLAKE_PUBLIC_DATA_FREE.PUBLIC_DATA_FREE.NOAA_WEATHER_METRICS_TIMESERIES LIMIT 50;
-- SELECT * FROM SNOWFLAKE_PUBLIC_DATA_FREE.PUBLIC_DATA_FREE.NOAA_WEATHER_STATION_INDEX
-- WHERE UPPER(state_name) IN ('OK','OKLAHOMA') AND UPPER(city_name) LIKE '%NORMAN%' LIMIT 20;
