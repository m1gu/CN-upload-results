"""Thin client wrapper for QBench API calls."""
from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from cn_upload_results.domain.models import RunMetadata, SampleQuantification



class QBenchClient:
    """Handles authenticated requests against QBench."""

    def __init__(self, *, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        base = base_url.rstrip("/")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self._client = httpx.Client(base_url=base, headers=headers, timeout=timeout)

    def __enter__(self) -> "QBenchClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        """Release the underlying HTTP connection pool."""

        self._client.close()

    def fetch_sample(self, sample_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve sample info if it exists."""

        response = self._client.get(f"/samples/{sample_id}")
        if response.status_code == httpx.codes.NOT_FOUND:
            return None
        response.raise_for_status()
        return response.json()

    def upsert_results(self, sample: SampleQuantification, run: RunMetadata) -> Dict[str, Any]:
        """Create or update analytical results for a sample."""

        payload = _build_payload(sample, run)
        response = self._client.post("/sample-results", json=payload)
        response.raise_for_status()
        return response.json()



def _build_payload(sample: SampleQuantification, run: RunMetadata) -> Dict[str, Any]:
    components = [
        {
            "analyte": name,
            "value": value,
        }
        for name, value in sample.components.items()
        if value is not None
]
    return {
        "sample_id": sample.sample_id,
        "run_date": run.run_date.isoformat(),
        "batch_numbers": sample.batch_numbers or run.batch_numbers,
        "measurements": components,
        "metadata": {
            "sample_mass_mg": sample.sample_mass_mg,
            "dilution": sample.dilution,
            "serving_mass_g": sample.serving_mass_g,
            "servings_per_package": sample.servings_per_package,
            "source_file": run.source_filename,
        },
    }
