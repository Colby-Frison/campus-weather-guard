# Campus Weather Guard — live demo script (~90s)

1. **Student tab** — Load sample week for Alex Sooner. Point at Tue 15:30 PHYS / Fri afternoon: leave-by time, mode (walk/bike/drive/wait), bring list. Call out storm hours → **wait** or **drive**.
2. **Professor tab** — Dr. Reed schedule. Highlight Tue synoptic / Wed late lab overlapping Severe Thunderstorm Warning → **CANCEL-WATCH** (advise only).
3. **Dataset** — “Norman hourly from Snowflake free WEATHER__ENVIRONMENT, explored with CoCo; SQL in `sql/norman_weather.sql`. Offline demo uses sample JSON.”
4. **Open source + open weight** — MIT LICENSE on public GitHub; briefing from Ollama Gemma on RTX GPU (`LLM_PROVIDER=ollama`), API fallback if needed.
