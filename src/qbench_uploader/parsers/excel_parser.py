"""Utilities to parse Excel result files."""
from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd


def load_samples_from_excel(path: Path, *, sheet_name: str | int = 0) -> List[dict]:
    """Load rows from an Excel file and normalise null values."""
    frame = pd.read_excel(path, sheet_name=sheet_name)
    frame = frame.where(pd.notnull(frame), None)
    return frame.to_dict(orient='records')
