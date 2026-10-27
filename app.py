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

from src.llm import active_provider, brief_professor_alerts, brief_student_plans  # noqa: E402
from src.schedule import (  # noqa: E402
    build_professor_alerts,
    build_student_plans,
    load_professor_schedule,
    load_student_schedule,
)
from src.weather import get_weather  # noqa: E402

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
    return f"<span style='background:{color};color:white;padding:2px 8px;border-radius:4px;font-size:0.85rem'>{level.upper()}</span>"


@st.cache_data(ttl=300)
def cached_weather(force_sample: bool) -> dict:
    return get_weather(force_sample=force_sample)


def main() -> None:
    st.title("Campus Weather Guard")
    st.caption(
        "OU Norman · schedule-aware commute plans for students · cancel-watch for professors · "
        "Snowflake weather + open-weight LLM"
    )

    with st.sidebar:
        st.header("Data & model")
        force_sample = st.checkbox("Force sample weather (skip Snowflake)", value=True)
        weather = cached_weather(force_sample)
        st.write(f"**Weather source:** `{weather.get('source')}`")
        if weather.get("fallback_reason"):
            st.info(weather["fallback_reason"])
        st.write(f"**LLM_PROVIDER:** `{active_provider()}`")
        st.write(f"**Ollama model:** `{os.getenv('OLLAMA_MODEL', 'gemma2:2b')}`")
        run_llm = st.checkbox("Generate LLM briefing", value=True)
        st.markdown("---")
        st.markdown(
            "Demo week anchored to **Mon 2026-10-26** so sample storm hours "
            "overlap Tue afternoon labs / Wed late classes."
        )
        st.markdown(
            "Dataset: Snowflake free **WEATHER__ENVIRONMENT**-style Norman hourly + alerts "
            "(see `sql/norman_weather.sql` and `docs/coco_notes.md`)."
        )

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
            with st.spinner("Calling open-weight model…"):
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
            with st.spinner("Calling open-weight model…"):
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
- **Open-weight** inference (Ollama + Gemma on GPU by default; `LLM_PROVIDER=api` for OpenAI-compatible hosts)
- **Snowflake** free weather exploration via CoCo → `sql/norman_weather.sql` + sample fallback
- Built at Hacklahoma Hacktoberfest Hack Day on Colby's Windows laptop (RTX 4060)

### Demo script
1. Open **Student** → sample week → note leave-by + mode (Tue afternoon storm → wait/drive).
2. Open **Professor** → Wed late METR lab / Tue synoptic → cancel-watch on severe overlap.
3. Name the dataset: Snowflake WEATHER__ENVIRONMENT Norman hourly (+ alerts).
4. Point at MIT LICENSE + open-weight LLM provider label in the sidebar / briefing caption.
            """
        )


if __name__ == "__main__":
    main()
