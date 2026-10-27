-- Campus Weather Guard — Norman, OK weather pull
-- Explored with Snowflake CoCo against free WEATHER__ENVIRONMENT-style datasets.
-- Adjust database/schema/table names to match your trial marketplace listing.

-- Example: locate Norman / Cleveland County stations
-- SELECT * FROM WEATHER__ENVIRONMENT.DATA.LOCATION
-- WHERE UPPER(CITY) LIKE '%NORMAN%' OR UPPER(STATE) = 'OK'
-- LIMIT 50;

-- Hourly forecast / observation style query used for the demo path
WITH norman AS (
  SELECT
    DATE_TRUNC('HOUR', OBSERVED_AT) AS hour_ts,
    AVG(TEMP_F) AS temp_f,
    SUM(PRECIP_IN) AS precip_in,
    AVG(PRECIP_PROB) AS precip_prob,
    AVG(WIND_MPH) AS wind_mph,
    MAX(GUST_MPH) AS gust_mph,
    ANY_VALUE(CONDITION_TEXT) AS condition
  FROM WEATHER__ENVIRONMENT.PUBLIC.HOURLY_FORECAST
  WHERE
    UPPER(CITY) = 'NORMAN'
    AND UPPER(STATE) IN ('OK', 'OKLAHOMA')
    AND OBSERVED_AT >= DATEADD('hour', -6, CURRENT_TIMESTAMP())
    AND OBSERVED_AT < DATEADD('day', 5, CURRENT_TIMESTAMP())
  GROUP BY 1
)
SELECT
  hour_ts AS time,
  ROUND(temp_f, 1) AS temp_f,
  ROUND(COALESCE(precip_in, 0), 3) AS precip_in,
  ROUND(COALESCE(precip_prob, 0), 0) AS precip_prob,
  ROUND(COALESCE(wind_mph, 0), 1) AS wind_mph,
  ROUND(COALESCE(gust_mph, 0), 1) AS gust_mph,
  condition
FROM norman
ORDER BY time;

-- Alert overlay (when available in listing)
-- SELECT VALID_FROM, VALID_TO, EVENT_TYPE, SEVERITY, HEADLINE
-- FROM WEATHER__ENVIRONMENT.PUBLIC.ALERTS
-- WHERE UPPER(AREA_DESC) LIKE '%NORMAN%'
--    OR UPPER(AREA_DESC) LIKE '%CLEVELAND%OK%';
