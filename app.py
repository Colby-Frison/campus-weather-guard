"""Campus Weather Guard — Streamlit entry (Student + Professor tabs)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from src.llm import (  # noqa: E402
    active_provider,
    brief_professor_alerts,
    brief_student_plans,
    ollama_model,
    ollama_status,
    warmup_ollama,
)
from src.schedule import (  # noqa: E402
    build_professor_alerts,
    build_student_plans,
    load_professor_schedule,
    load_student_schedule,
)
from src.weather import (  # noqa: E402
    apply_snowflake_env,
    get_weather,
    snowflake_config_status,
    test_snowflake_connection,
)

st.set_page_config(
    page_title="Campus Weather Guard",
    layout="wide",
)

SEVERITY_COLORS = {
    "none": "#2e7d32",
    "info": "#1565c0",
    "watch": "#ef6c00",
    "warning": "#c62828",
    "emergency": "#6a1b9a",
}


def severity_badge(level: str) -> str:
    color = SEVERITY_COLORS.get(level, "#555")
    return (
        f"<span style='background:{color};color:white;padding:2px 8px;"
        f"border-radius:4px;font-size:0.85rem'>{level.upper()}</span>"
    )


def _apply_session_snowflake() -> None:
    creds = st.session_state.get("sf_creds") or {}
    apply_snowflake_env(creds)


@st.cache_data(ttl=300, show_spinner=False)
def cached_weather(force_sample: bool, cred_fingerprint: str) -> dict:
    _ = cred_fingerprint  # bust cache when credentials change
    return get_weather(force_sample=force_sample)


def render_sidebar() -> tuple[dict, bool]:
    with st.sidebar:
        st.header("Integrations")

        # --- Ollama ---
        st.subheader("Ollama (GPU)")
        status = ollama_status()
        if status["ok"] and status["model_ready"]:
            st.success(f"Online · `{status['preferred_model']}` · {status['latency_ms']} ms")
        elif status["ok"]:
            st.warning(status["error"])
        else:
            st.error(f"Ollama unreachable at `{status['host']}` — {status['error']}")

        st.write(f"**LLM_PROVIDER:** `{active_provider()}`")
        st.write(f"**Model:** `{ollama_model()}`")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Refresh status", key="ollama_refresh"):
                st.rerun()
        with c2:
            if st.button("Warm GPU model", key="ollama_warm"):
                with st.spinner("Loading model onto GPU…"):
                    warm = warmup_ollama()
                if warm["ok"]:
                    st.session_state["ollama_warm"] = warm
                    st.success(f"Warmed in {warm['latency_s']}s via {warm['provider']}")
                else:
                    st.error(warm.get("error") or "Warmup failed")
        if st.session_state.get("ollama_warm"):
            w = st.session_state["ollama_warm"]
            st.caption(f"Last warmup: {w['latency_s']}s · {w['provider']}")

        run_llm = st.checkbox("Enable LLM briefing buttons", value=True)

        st.markdown("---")

        # --- Snowflake ---
        st.subheader("Snowflake")
        with st.expander("Credentials (session)", expanded=not snowflake_config_status()["configured"]):
            st.caption("Stored only in this Streamlit session / optional .env — never committed.")
            account = st.text_input("Account locator", value=os.getenv("SNOWFLAKE_ACCOUNT", ""))
            user = st.text_input("User", value=os.getenv("SNOWFLAKE_USER", ""))
            password = st.text_input("Password", type="password", value=os.getenv("SNOWFLAKE_PASSWORD", ""))
            warehouse = st.text_input("Warehouse", value=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"))
            database = st.text_input(
                "Database",
                value=os.getenv("SNOWFLAKE_DATABASE", "SNOWFLAKE_PUBLIC_DATA_FREE"),
            )
            schema = st.text_input(
                "Schema",
                value=os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC_DATA_FREE"),
            )
            role = st.text_input("Role (optional)", value=os.getenv("SNOWFLAKE_ROLE", ""))
            if st.button("Apply credentials", key="sf_apply"):
                st.session_state["sf_creds"] = {
                    "SNOWFLAKE_ACCOUNT": account,
                    "SNOWFLAKE_USER": user,
                    "SNOWFLAKE_PASSWORD": password,
                    "SNOWFLAKE_WAREHOUSE": warehouse,
                    "SNOWFLAKE_DATABASE": database,
                    "SNOWFLAKE_SCHEMA": schema,
                    "SNOWFLAKE_ROLE": role,
                }
                apply_snowflake_env(st.session_state["sf_creds"])
                st.success("Credentials applied for this session.")
                st.cache_data.clear()

        _apply_session_snowflake()
        cfg = snowflake_config_status()
        if cfg["configured"]:
            st.write(f"Account: `{cfg['account']}` · user `{cfg['user']}`")
        else:
            st.info("No Snowflake credentials yet — using sample weather.")

        if st.button("Test Snowflake connection", key="sf_test"):
            with st.spinner("Connecting…"):
                result = test_snowflake_connection()
            st.session_state["sf_test"] = result
        if st.session_state.get("sf_test"):
            result = st.session_state["sf_test"]
            if result["ok"]:
                st.success(
                    f"Connected · Snowflake {result.get('version')} · "
                    f"role {result.get('role')} · wh {result.get('warehouse')}"
                )
                weather_dbs = result.get("weather_databases") or []
                if weather_dbs:
                    st.caption("Weather-related DBs: " + ", ".join(weather_dbs[:12]))
                else:
                    st.warning(
                        "Connected, but no weather-named database found. "
                        "In Marketplace, Get **Snowflake Public Data (Free)** "
                        "(creates SNOWFLAKE_PUBLIC_DATA_FREE)."
                    )
            else:
                st.error(result.get("error") or "Connection failed")

        force_sample = st.checkbox("Force sample weather (skip Snowflake)", value=not cfg["configured"])
        fingerprint = "|".join(
            [
                os.getenv("SNOWFLAKE_ACCOUNT", ""),
                os.getenv("SNOWFLAKE_USER", ""),
                "x" if os.getenv("SNOWFLAKE_PASSWORD") else "",
                str(force_sample),
            ]
        )
        weather = cached_weather(force_sample, fingerprint)
        st.write(f"**Weather source:** `{weather.get('source')}`")
        if weather.get("station"):
            st.caption(f"Station: {weather['station']}")
        if weather.get("fallback_reason"):
            st.info(weather["fallback_reason"])

        st.markdown("---")
        st.markdown(
            "Demo week anchored to **Mon 2026-10-26** for sample storm overlap. "
            "Live Snowflake NOAA daily data is expanded to daytime hours."
        )
        st.markdown(
            "Dataset: **Snowflake Public Data (Free)** NOAA Norman metrics "
            "(`sql/norman_weather.sql`, `docs/coco_notes.md`)."
        )

    return weather, run_llm


def main() -> None:
    st.title("Campus Weather Guard")
    st.caption(
        "OU Norman · schedule-aware commute plans for students · cancel-watch for professors · "
        "Snowflake weather + open-weight LLM"
    )

    weather, run_llm = render_sidebar()
    student_tab, professor_tab, about_tab = st.tabs(["Student", "Professor", "About"])

    with student_tab:
        schedule = load_student_schedule()
        st.subheader(f"Student commute plan — {schedule.get('name', 'Student')}")
        plans = build_student_plans(schedule, weather)
        for p in plans:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1:
                    st.markdown(
                        f"**{p['course']}** · {p['title']}  \n"
                        f"{p['day']} {p['start']}–{p['end']} · {p['building_name']}"
                    )
                    st.markdown(severity_badge(p["severity"]), unsafe_allow_html=True)
                with c2:
                    st.metric("Leave by", p["leave_by"].split(" ")[-1])
                    st.write(f"Mode: **{p['mode']}**")
                with c3:
                    snap = p.get("weather_snapshot") or {}
                    st.write(
                        f"{snap.get('condition', '—')}  \n"
                        f"{snap.get('temp_f', '—')}°F · precip {snap.get('precip_prob', '—')}%  \n"
                        f"gust {snap.get('gust_mph', '—')} mph"
                    )
                st.write("Bring: " + ", ".join(p["bring"]))
                if p.get("alerts"):
                    st.warning("Alerts: " + ", ".join(p["alerts"]))

        if run_llm and st.button("Generate student briefing", key="student_llm"):
            with st.spinner("Calling open-weight model on GPU…"):
                result = brief_student_plans(plans)
            st.markdown("#### LLM briefing")
            st.write(result["text"])
            st.caption(
                f"provider={result['provider']} · latency={result['latency_s']}s"
                + (f" · note={result['error']}" if result.get("error") else "")
            )

    with professor_tab:
        schedule = load_professor_schedule()
        st.subheader(f"Professor cancel-watch — {schedule.get('name', 'Professor')}")
        st.info("Advisory only — Campus Weather Guard never auto-cancels classes.")
        alerts = build_professor_alerts(schedule, weather)
        for a in alerts:
            with st.container(border=True):
                st.markdown(
                    f"**{a['course']}** · {a['title']}  \n"
                    f"{a['day']} {a['start']}–{a['end']} · {a['building_name']}"
                )
                st.markdown(severity_badge(a["severity"]), unsafe_allow_html=True)
                st.write(a["action"])
                if a.get("alerts"):
                    st.error("NWS-style alerts in window: " + ", ".join(a["alerts"]))
                snap = a.get("weather_snapshot") or {}
                if snap:
                    st.caption(
                        f"Overlap snapshot: {snap.get('condition')} · "
                        f"{snap.get('temp_f')}°F · gust {snap.get('gust_mph')} mph"
                    )

        if run_llm and st.button("Generate cancel-watch briefing", key="prof_llm"):
            with st.spinner("Calling open-weight model on GPU…"):
                result = brief_professor_alerts(alerts)
            st.markdown("#### LLM briefing")
            st.write(result["text"])
            st.caption(
                f"provider={result['provider']} · latency={result['latency_s']}s"
                + (f" · note={result['error']}" if result.get("error") else "")
            )

    with about_tab:
        st.markdown(
            """
### Dual-challenge prototype
- **Public MIT** open-source repo for Hacklahoma Hacktoberfest
- **Open-weight** inference (Ollama + Gemma on GPU by default; `LLM_PROVIDER=api` fallback)
- **Snowflake** Public Data (Free) NOAA Norman via CoCo-authored SQL + sample fallback
- Built at Hacklahoma Hacktoberfest Hack Day on Colby's Windows laptop (RTX 4060)

### Wire live Snowflake
1. Create / open a Snowflake trial.
2. Marketplace → **Snowflake Public Data (Free)** → Get.
3. Paste account / user / password in the sidebar (or `.env`).
4. Click **Test Snowflake connection**, uncheck **Force sample weather**.
            """
        )


if __name__ == "__main__":
    main()
