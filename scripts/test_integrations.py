"""Probe Ollama + Snowflake integrations and print a short status report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from src.llm import ollama_status, warmup_ollama  # noqa: E402
from src.weather import get_weather, snowflake_config_status, test_snowflake_connection  # noqa: E402


def main() -> None:
    print("=== Ollama ===")
    status = ollama_status()
    print(json.dumps(status, indent=2))
    if status.get("ok") and status.get("model_ready"):
        warm = warmup_ollama()
        print("warmup:", json.dumps({k: warm[k] for k in ("ok", "latency_s", "provider", "error")}, indent=2))
        print("warmup_text:", (warm.get("text") or "")[:120])

    print("\n=== Snowflake config ===")
    print(json.dumps(snowflake_config_status(), indent=2))
    print("\n=== Snowflake connection ===")
    conn = test_snowflake_connection()
    # Never print password; connection result is safe
    print(json.dumps(conn, indent=2, default=str))

    print("\n=== Weather fetch ===")
    weather = get_weather(force_sample=False)
    print(
        json.dumps(
            {
                "source": weather.get("source"),
                "location": weather.get("location"),
                "station": weather.get("station"),
                "hourly_points": len(weather.get("hourly") or []),
                "fallback_reason": weather.get("fallback_reason"),
                "first_point": (weather.get("hourly") or [None])[0],
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
