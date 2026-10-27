"""LLM provider abstraction: Ollama (GPU) default, OpenAI-compatible API fallback."""

from __future__ import annotations

import json
import os
import time
from typing import Any

import requests

STUDENT_SYSTEM = (
    "You are Campus Weather Guard for University of Oklahoma students in Norman. "
    "Given structured commute plans, write a short plain-language weekly briefing. "
    "Emphasize leave-by times, travel mode, and what to bring. Be concise. No emojis."
)

PROFESSOR_SYSTEM = (
    "You are Campus Weather Guard for OU professors. "
    "Given teaching sessions with weather severity, write a short cancel-watch briefing. "
    "Advise only — never auto-cancel. Flag severe overlaps clearly. No emojis."
)


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def ollama_host() -> str:
    return _env("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")


def ollama_model() -> str:
    return _env("OLLAMA_MODEL", "gemma2:2b")


def api_model() -> str:
    return _env("LLM_API_MODEL", "gemma-2-2b-it")


def api_base() -> str:
    return _env("LLM_API_BASE", "https://api.openai.com/v1").rstrip("/")


def api_key() -> str:
    return _env("LLM_API_KEY", "")


def active_provider() -> str:
    return _env("LLM_PROVIDER", "ollama").lower()


def ollama_status() -> dict[str, Any]:
    """Ping Ollama and report installed models / preferred model readiness."""
    host = ollama_host()
    model = ollama_model()
    started = time.perf_counter()
    try:
        resp = requests.get(f"{host}/api/tags", timeout=5)
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        resp.raise_for_status()
        models = [m.get("name", "") for m in (resp.json().get("models") or [])]
        ready = any(m == model or m.startswith(f"{model}") or model in m for m in models)
        return {
            "ok": True,
            "host": host,
            "latency_ms": latency_ms,
            "models": models,
            "preferred_model": model,
            "model_ready": ready,
            "error": None if ready else f"Model '{model}' not found. Run: ollama pull {model}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "host": host,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "models": [],
            "preferred_model": model,
            "model_ready": False,
            "error": str(exc),
        }


def warmup_ollama(prompt: str = "Reply with exactly: ready") -> dict[str, Any]:
    """Load model onto GPU and keep it warm (keeps cold-start off the demo path)."""
    return generate(prompt, "You are a warmup probe. Reply briefly.", force_provider="ollama")


def _ollama_generate(prompt: str, system: str, model: str | None = None) -> tuple[str, float, str]:
    model = model or ollama_model()
    url = f"{ollama_host()}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "keep_alive": _env("OLLAMA_KEEP_ALIVE", "30m"),
        "options": {
            # 99 = use as many GPU layers as fit (CUDA on RTX machines)
            "num_gpu": int(_env("OLLAMA_NUM_GPU", "99") or "99"),
            "temperature": 0.3,
            "num_predict": int(_env("OLLAMA_NUM_PREDICT", "280") or "280"),
        },
    }
    started = time.perf_counter()
    resp = requests.post(url, json=payload, timeout=int(_env("OLLAMA_TIMEOUT", "180") or "180"))
    latency = time.perf_counter() - started
    resp.raise_for_status()
    data = resp.json()
    text = (data.get("response") or data.get("thinking") or "").strip()
    return text, latency, f"ollama:{model}"


def _api_generate(prompt: str, system: str, model: str | None = None) -> tuple[str, float, str]:
    model = model or api_model()
    key = api_key()
    if not key:
        raise RuntimeError("LLM_API_KEY is required when LLM_PROVIDER=api")
    url = f"{api_base()}/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": 0.3,
        "max_tokens": 400,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }
    started = time.perf_counter()
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    latency = time.perf_counter() - started
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"].strip()
    return text, latency, f"api:{model}"


def generate(
    prompt: str,
    system: str,
    force_provider: str | None = None,
) -> dict[str, Any]:
    """Run generation with provider switch. Returns text, latency_s, provider label."""
    provider = (force_provider or active_provider()).lower()
    try:
        if provider == "api":
            text, latency, label = _api_generate(prompt, system)
        else:
            text, latency, label = _ollama_generate(prompt, system)
        return {
            "ok": True,
            "text": text,
            "latency_s": round(latency, 3),
            "provider": label,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        if provider != "api" and api_key():
            try:
                text, latency, label = _api_generate(prompt, system)
                return {
                    "ok": True,
                    "text": text,
                    "latency_s": round(latency, 3),
                    "provider": label,
                    "error": f"ollama failed ({exc}); used API fallback",
                }
            except Exception as api_exc:  # noqa: BLE001
                return {
                    "ok": False,
                    "text": _heuristic_briefing(prompt, system),
                    "latency_s": 0.0,
                    "provider": "heuristic",
                    "error": f"ollama: {exc}; api: {api_exc}",
                }
        return {
            "ok": False,
            "text": _heuristic_briefing(prompt, system),
            "latency_s": 0.0,
            "provider": "heuristic",
            "error": str(exc),
        }


def _heuristic_briefing(prompt: str, system: str) -> str:
    """Deterministic briefing when no LLM is available (demo still works)."""
    role = "professor" if "cancel-watch" in system.lower() or "professors" in system.lower() else "student"
    try:
        payload = json.loads(prompt.split("JSON:\n", 1)[1]) if "JSON:\n" in prompt else []
    except Exception:  # noqa: BLE001
        payload = []

    if role == "professor":
        lines = ["Professor cancel-watch briefing (heuristic fallback):"]
        for item in payload:
            lines.append(
                f"- {item.get('day')} {item.get('start')} {item.get('course')}: "
                f"{item.get('severity', 'none').upper()} — {item.get('action')}"
            )
        return "\n".join(lines) if len(lines) > 1 else "No teaching sessions in range."

    lines = ["Student commute briefing (heuristic fallback):"]
    for item in payload:
        lines.append(
            f"- {item.get('day')} {item.get('course')}: leave by {item.get('leave_by')}, "
            f"mode={item.get('mode')}, bring {', '.join(item.get('bring') or [])}."
        )
    return "\n".join(lines) if len(lines) > 1 else "No classes in range."


def brief_student_plans(plans: list[dict[str, Any]]) -> dict[str, Any]:
    compact = [
        {
            "day": p["day"],
            "course": p["course"],
            "leave_by": p["leave_by"],
            "mode": p["mode"],
            "severity": p["severity"],
            "bring": p["bring"],
            "condition": (p.get("weather_snapshot") or {}).get("condition"),
        }
        for p in plans
    ]
    prompt = (
        "Write a short weekly commute briefing for an OU student.\n"
        "JSON:\n" + json.dumps(compact, indent=2)
    )
    return generate(prompt, STUDENT_SYSTEM)


def brief_professor_alerts(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    compact = [
        {
            "day": a["day"],
            "course": a["course"],
            "start": a["start"],
            "severity": a["severity"],
            "action": a["action"],
            "alerts": a.get("alerts"),
        }
        for a in alerts
    ]
    prompt = (
        "Write a short cancel-watch briefing for an OU professor.\n"
        "JSON:\n" + json.dumps(compact, indent=2)
    )
    return generate(prompt, PROFESSOR_SYSTEM)


def time_ollama_generate(prompt: str = "Say ready in five words.") -> dict[str, Any]:
    """Utility used at startup / demo to measure GPU Ollama latency."""
    return generate(prompt, "You are a latency probe. Reply briefly.", force_provider="ollama")
