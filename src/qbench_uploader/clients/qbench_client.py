"""HTTP client wrapper for QBench API."""
from __future__ import annotations

from typing import Any

import httpx


class QBenchClient:
    """Small wrapper around the QBench REST API."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip('/')
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._default_headers(),
            timeout=30.0,
        )

    def _default_headers(self) -> dict[str, str]:
        return {
            'Authorization': f'Bearer {self._api_key}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

    async def fetch_sample(self, sample_id: str) -> dict[str, Any]:
        """Fetch metadata for a sample identifier."""
        response = await self._client.get(f'/samples/{sample_id}')
        response.raise_for_status()
        return response.json()

    async def upload_result(self, sample_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Upload a result payload."""
        response = await self._client.post(f'/samples/{sample_id}/results', json=payload)
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the HTTP client session."""
        await self._client.aclose()
