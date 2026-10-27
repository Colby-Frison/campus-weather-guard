# Campus Weather Guard

Schedule-aware weather guidance for **University of Oklahoma** students and professors in Norman.

- **Students:** weekly class schedule → Norman weather → leave-by time, travel mode (walk / bike / drive / wait), what to bring.
- **Professors:** teaching schedule → severe-weather overlap → alert severity + cancel-watch advice (advise only; never auto-cancel).

Built at **Hacklahoma Hacktoberfest Hack Day** as a dual-challenge open-source + open-weight AI prototype.

## Quick start

```powershell
cd C:\Users\colby\Documents\campus-weather-guard
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
streamlit run app.py
```

Optional GPU LLM (default):

```powershell
# Install Ollama, then:
ollama pull gemma2:2b
$env:LLM_PROVIDER = "ollama"
$env:OLLAMA_MODEL = "gemma2:2b"
streamlit run app.py
```

OpenAI-compatible API fallback (still an open-weight model host):

```powershell
$env:LLM_PROVIDER = "api"
$env:LLM_API_BASE = "https://your-open-weight-host/v1"
$env:LLM_API_KEY = "..."
$env:LLM_API_MODEL = "gemma-2-2b-it"
streamlit run app.py
```

## Repo layout

| Path | Role |
| --- | --- |
| `app.py` | Streamlit entry (Student / Professor / About) |
| `src/weather.py` | Snowflake connector + sample JSON fallback |
| `src/schedule.py` | Schedule expand, severity thresholds, mode / leave-by |
| `src/llm.py` | Ollama GPU default + `LLM_PROVIDER=api` fallback |
| `data/*.json` | Sample schedules, buildings, weather cache |
| `sql/norman_weather.sql` | CoCo-explored Norman weather SQL |
| `docs/coco_notes.md` | Snowflake CoCo + dataset notes |
| `docs/demo_script.md` | Live demo talking points |
| `docs/campus-weather-guard-demo.png` | Demo screenshot |

## Demo script (90 seconds)

1. **Student** tab → sample week → show leave-by + mode (storm hours → drive/wait).
2. **Professor** tab → severe overlap → cancel-watch advisory.
3. Name dataset: Snowflake **WEATHER__ENVIRONMENT** Norman hourly (+ alerts); CoCo wrote the SQL.
4. Point at **MIT** `LICENSE` + open-weight provider label (`ollama:gemma2:2b` or API).

## Weather path

1. If `SNOWFLAKE_*` env vars (or sidebar session creds) are set → run `sql/norman_weather.sql` against **Snowflake Public Data (Free)** NOAA Norman tables, then expand daily → daytime hourly.
2. Else → `data/sample_weather.json` (committed demo storm week), or `data/cache_weather.json` from the last successful pull.

```powershell
python scripts/test_integrations.py
```

In the app sidebar: **Warm GPU model**, **Test Snowflake connection**, paste trial credentials.

## Measured LLM latency (Hack Day laptop, RTX 4060)

| Call | Provider | Latency |
| --- | --- | --- |
| Cold probe (`gemma2:2b`) | `ollama:gemma2:2b` | ~139 s (model load) |
| Student briefing (warm) | `ollama:gemma2:2b` | ~10.8 s |
| Professor briefing (warm) | `ollama:gemma2:2b` | ~2.5 s |

`LLM_PROVIDER=api` is wired for OpenAI-compatible open-weight hosts when local inference is too slow. Re-measure with `python scripts/measure_llm.py`.

## License

MIT — see [`LICENSE`](LICENSE).
