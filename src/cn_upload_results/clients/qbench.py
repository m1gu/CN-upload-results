"""Thin client wrapper for QBench API calls."""
from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from cn_upload_results.domain.models import RunMetadata, SampleQuantification


class QBenchClient:
    """Handles authenticated requests against QBench."""

    def __init__(
        self,
        *,
        base_url: str,
        client_id: str,
        client_secret: str,
        token_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_base = base_url.rstrip("/")
        if not client_id or not client_secret:
            raise ValueError("QBench client_id and client_secret are required")
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._timeout = timeout
        self._client = httpx.Client(
            base_url=self._api_base,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
        self._authenticate()

    def __enter__(self) -> "QBenchClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        """Release the underlying HTTP connection pool."""

        self._client.close()

    def fetch_sample(self, sample_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve sample info if it exists."""

        response = self._request("GET", f"/samples/{sample_id}")
        if response.status_code == httpx.codes.NOT_FOUND:
            return None
        response.raise_for_status()
        return response.json()

    def upsert_results(self, sample: SampleQuantification, run: RunMetadata) -> Dict[str, Any]:
        """Create or update analytical results for a sample."""

        payload = _build_payload(sample, run)
        response = self._request("POST", "/sample-results", json=payload)
        response.raise_for_status()
        return response.json()

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        response = self._client.request(method, url, **kwargs)
        if response.status_code == httpx.codes.UNAUTHORIZED:
            self._authenticate()
            response = self._client.request(method, url, **kwargs)
        return response

    def _authenticate(self) -> None:
        """Obtain an access token using the client credentials grant."""

        token_endpoint = self._resolve_token_endpoint()
        auth = httpx.BasicAuth(self._client_id, self._client_secret)
        response = httpx.post(
            token_endpoint,
            data={"grant_type": "client_credentials"},
            auth=auth,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        token_payload = response.json()
        access_token = token_payload.get("access_token")
        if not access_token:
            raise RuntimeError("QBench token response did not include an access token")
        token_type = token_payload.get("token_type", "Bearer")
        self._client.headers["Authorization"] = f"{token_type} {access_token}"

    def _resolve_token_endpoint(self) -> str:
        if self._token_url:
            return self._token_url

        base = self._api_base.rstrip("/")
        if base.endswith("/api"):
            host = base[: -len("/api")]
        else:
            host = base
        return f"{host.rstrip('/')}/oauth/token"


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
