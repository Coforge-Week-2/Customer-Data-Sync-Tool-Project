"""Shared fixtures: path to saved responses and a loader for the raw capture."""

import json
from pathlib import Path

import pytest

from customer_sync.contracts import RawRecord

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def raw_records() -> list[RawRecord]:
    path = FIXTURES_DIR / "raw" / "seed_team2_r10_p1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = payload["results"]
    if not isinstance(results, list):
        raise TypeError("fixture results must be a list")
    return results
