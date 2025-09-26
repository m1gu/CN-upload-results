"""Entry points for orchestrating the upload workflow."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import httpx

from cn_upload_results.clients.qbench import QBenchClient
from cn_upload_results.clients.supabase import SupabaseClient
from cn_upload_results.config.settings import get_settings
from cn_upload_results.domain.models import WorkbookExtraction
from cn_upload_results.parsers.excel import parse_workbook

LOGGER = logging.getLogger(__name__)


def run_upload(excel_path: Path) -> WorkbookExtraction:
    """Execute the end-to-end upload pipeline."""

    settings = get_settings()
    extraction = parse_workbook(excel_path)

    with QBenchClient(
        base_url=str(settings.qbench_base_url),
        client_id=settings.qbench_client_id,
        client_secret=settings.qbench_client_secret,
        token_url=settings.qbench_token_endpoint,
    ) as qbench, SupabaseClient(
        url=str(settings.supabase_url),
        service_role_key=settings.supabase_service_role_key,
    ) as supabase:
        for sample in extraction.samples:
            qbench_response: Optional[dict] = None
            try:
                qbench_response = qbench.upsert_results(sample, extraction.metadata)
            except httpx.HTTPError as exc:
                LOGGER.exception("Failed to push sample %s to QBench", sample.sample_id)
                raise
            finally:
                supabase.log_sample_upload(
                    sample=sample,
                    run=extraction.metadata,
                    qbench_response=qbench_response,
                )

    return extraction
