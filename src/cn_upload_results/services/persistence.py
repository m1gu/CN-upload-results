"""Helpers to persist run data into Supabase."""
from __future__ import annotations

import getpass
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from cn_upload_results.clients.supabase import SupabaseClient
from cn_upload_results.config.settings import AppSettings
from cn_upload_results.domain.models import WorkbookExtraction


def _compute_file_hash(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique(values: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def build_excel_payload(extraction: WorkbookExtraction) -> Dict[str, Any]:
    metadata = extraction.metadata
    samples_payload: List[Dict[str, Any]] = []
    for sample in extraction.samples:
        samples_payload.append(
            {
                "sample_id": sample.sample_id,
                "base_sample_id": sample.base_sample_id,
                "test_index": sample.test_index,
                "column_header": sample.column_header,
                "batch_numbers": sample.batch_numbers,
                "components": sample.components,
                "area_results": sample.area_results,
                "sample_mass_mg": sample.sample_mass_mg,
                "dilution": sample.dilution,
                "serving_mass_g": sample.serving_mass_g,
                "servings_per_package": sample.servings_per_package,
            }
        )

    return {
        "metadata": {
            "run_date": metadata.run_date.isoformat(),
            "source_filename": metadata.source_filename,
            "batch_numbers": metadata.batch_numbers,
            "batch_sample_map": metadata.batch_sample_map,
        },
        "samples": samples_payload,
    }


def build_default_qbench_payload(extraction: WorkbookExtraction) -> Dict[str, Any]:
    sample_ids = sorted({sample.base_sample_id for sample in extraction.samples})
    return {
        "status": "completed",
        "synced_samples": sample_ids,
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }


def persist_run_to_supabase(
    *,
    settings: AppSettings,
    extraction: WorkbookExtraction,
    excel_path: Path,
    qbench_payload: Dict[str, Any] | None = None,
    created_by: str | None = None,
    instrument: str | None = None,
) -> None:
    metadata = extraction.metadata
    record = {
        "run_date": metadata.run_date.isoformat(),
        "instrument": instrument,
        "file_name": excel_path.name,
        "workbook_hash": _compute_file_hash(excel_path),
        "batch_codes": metadata.batch_numbers,
        "sample_ids": _unique([sample.base_sample_id for sample in extraction.samples]),
        "created_by": created_by or getpass.getuser(),
        "excel_payload": build_excel_payload(extraction),
        "qbench_payload": qbench_payload or build_default_qbench_payload(extraction),
    }

    with SupabaseClient(
        url=str(settings.supabase_url),
        service_role_key=settings.supabase_service_role_key,
    ) as client:
        client.store_run_record(record)
