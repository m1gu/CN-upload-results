"""Workflows to orchestrate sandbox uploads before production rollout."""
from __future__ import annotations

from pathlib import Path

from qbench_uploader.clients.qbench_client import QBenchClient
from qbench_uploader.parsers.excel_parser import load_samples_from_excel


async def load_results_from_file(excel_path: Path, client: QBenchClient) -> None:
    """Iterate samples parsed from Excel and push them to QBench."""
    for sample in load_samples_from_excel(excel_path):
        sample_id = str(sample.get('SampleID', '')).strip()
        if not sample_id:
            continue
        payload = {'results': sample}
        await client.upload_result(sample_id, payload)
