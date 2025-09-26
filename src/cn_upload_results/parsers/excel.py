"""Helpers to extract CN results from Excel files."""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import pandas as pd

from cn_upload_results.domain.models import (
    AREA_RESULT_SUFFIX,
    COMPONENT_ORDER,
    RunMetadata,
    SampleQuantification,
    WorkbookExtraction,
)

LOGGER = logging.getLogger(__name__)

RESULTS_SHEET = "Results Transfer"
BATCH_SHEET = "Blank Spike Recovery"
BATCH_COLUMN_STEP = 2
COMPONENT_ROW_OFFSET = 1  # zero-based index for first component row
AREA_RESULT_ROW_OFFSET = 28  # zero-based index (row 29 in Excel)

SAMPLE_MASS_ROW = 22  # zero-based index (row 23 in Excel)
DILUTION_ROW = 23  # zero-based index (row 24 in Excel)
SERVING_MASS_ROW = 24  # zero-based index (row 25 in Excel)
SERVINGS_PER_PACKAGE_ROW = 25  # zero-based index (row 26 in Excel)


def parse_workbook(path: Path) -> WorkbookExtraction:
    """Parse workbook into structured domain objects."""

    excel = pd.ExcelFile(path)
    metadata = _build_metadata(path, excel)
    results_df = excel.parse(RESULTS_SHEET, header=None)
    samples = _parse_samples(results_df, metadata.batch_numbers)
    return WorkbookExtraction(metadata=metadata, samples=samples)


def _build_metadata(path: Path, excel: pd.ExcelFile) -> RunMetadata:
    run_date, file_batches = _extract_from_filename(path)
    sheet_batches = _extract_batches_from_sheet(excel)
    batch_numbers = _deduplicate_sequence([*file_batches, *sheet_batches])
    return RunMetadata(
        run_date=run_date,
        batch_numbers=batch_numbers,
        source_filename=path.name,
    )


def _extract_from_filename(path: Path) -> tuple[datetime.date, List[str]]:
    """Extract run date and batch numbers from filename."""

    stem = path.stem
    primary_token = stem.split(" ")[0]
    parts = [segment for segment in primary_token.split("_") if segment]
    if not parts:
        raise ValueError(f"Filename {path.name} does not contain expected pattern")

    raw_date = parts[0]
    if not re.fullmatch(r"\d{8}", raw_date):
        raise ValueError(f"Filename {path.name} missing YYYYMMDD date prefix")
    run_date = datetime.strptime(raw_date, "%Y%m%d").date()

    batches = [piece for piece in parts[1:] if piece.isdigit()]
    return run_date, batches


def _extract_batches_from_sheet(excel: pd.ExcelFile) -> List[str]:
    """Collect additional batch numbers from the Blank Spike Recovery tab."""

    try:
        sheet = excel.parse(BATCH_SHEET, header=None)
    except ValueError:
        LOGGER.debug("Sheet %s not found; skipping batch extraction", BATCH_SHEET)
        return []

    if sheet.empty:
        return []

    batches: List[str] = []
    first_row = sheet.iloc[0]

    for column in range(0, len(first_row), BATCH_COLUMN_STEP):
        value = first_row.iloc[column]
        if pd.isna(value):
            break
        token = str(value).strip()
        if not token or token.lower() == "nan":
            break
        sanitized = _sanitize_batch_token(token)
        if sanitized:
            batches.append(sanitized)
    return batches


def _parse_samples(frame: pd.DataFrame, batch_numbers: Sequence[str]) -> List[SampleQuantification]:
    header = frame.iloc[0].astype(str).str.strip()
    samples: List[SampleQuantification] = []
    test_counters: Dict[str, int] = defaultdict(int)

    for column_index, raw_header in enumerate(header):
        if _should_skip_header(raw_header):
            continue

        normalized = _normalize_sample_header(raw_header)
        if not normalized:
            continue

        base_sample_id = _extract_base_sample_id(normalized)
        test_index = test_counters[base_sample_id]
        test_counters[base_sample_id] += 1

        column = frame.iloc[:, column_index]
        components = _extract_components(column)
        area_results = _extract_area_results(column)

        sample = SampleQuantification(
            sample_id=normalized,
            base_sample_id=base_sample_id,
            test_index=test_index,
            column_header=_format_column_header(raw_header),
            components=components,
            area_results=area_results,
            sample_mass_mg=_coerce_number(_safe_get(column, SAMPLE_MASS_ROW)),
            dilution=_coerce_number(_safe_get(column, DILUTION_ROW)),
            serving_mass_g=_coerce_number(_safe_get(column, SERVING_MASS_ROW)),
            servings_per_package=_coerce_number(_safe_get(column, SERVINGS_PER_PACKAGE_ROW)),
            batch_numbers=list(batch_numbers),
        )
        samples.append(sample)
    return samples


def _extract_components(column: pd.Series) -> Dict[str, float | None]:
    return {
        component: _coerce_number(_safe_get(column, COMPONENT_ROW_OFFSET + offset))
        for offset, component in enumerate(COMPONENT_ORDER)
    }


def _extract_area_results(column: pd.Series) -> Dict[str, float | None]:
    return {
        component: _coerce_number(_safe_get(column, AREA_RESULT_ROW_OFFSET + offset))
        for offset, component in enumerate(COMPONENT_ORDER)
    }


def _should_skip_header(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return True
    lowered = text.lower()
    if lowered.startswith(("dup", "blank", "bs", "low")):
        return True
    if not any(char.isdigit() for char in text):
        return True
    return False


def _normalize_sample_header(value: object) -> str | None:
    text = str(value).strip()
    if not text:
        return None

    replacements = text.replace(" ", "")
    match = re.match(r"(\d+(?:-\d+)?)", replacements)
    if match:
        return match.group(1)

    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    if text.replace(".", "", 1).isdigit() and text.count(".") == 1:
        integer, fractional = text.split(".")
        if fractional == "0":
            return integer
    return text


def _format_column_header(value: object) -> str:
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _extract_base_sample_id(sample_id: str) -> str:
    if "-" in sample_id:
        prefix, _, remainder = sample_id.partition("-")
        if prefix.isdigit() and remainder.isdigit():
            return prefix
    return sample_id


def _sanitize_batch_token(token: str) -> str | None:
    numeric = _coerce_number(token)
    if numeric is not None:
        if numeric.is_integer():
            return str(int(numeric))
        return str(numeric)
    digits = re.sub(r"\D", "", token)
    return digits or None


def _coerce_number(value) -> float | None:
    """Convert spreadsheet cell value to float when possible."""

    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    try:
        normalized = text.replace(",", "")
        return float(normalized)
    except ValueError:
        return None


def _safe_get(column: pd.Series, index: int):
    return column.iloc[index] if index < len(column) else None


def _deduplicate_sequence(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


