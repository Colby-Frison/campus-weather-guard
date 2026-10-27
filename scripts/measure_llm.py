"""Measure Ollama / API latency for demo notes."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from src.llm import time_ollama_generate  # noqa: E402


def main() -> None:
    result = time_ollama_generate("Reply with exactly: Campus Weather Guard ready.")
    print(result)


if __name__ == "__main__":
    main()
