"""HTTP client wrapper for QBench API."""
from __future__ import annotations

from typing import Any, Optional

import httpx


class QBenchClient:
    """Small wrapper around the QBench REST API."""

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        token_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_base = base_url.rstrip('/')
        if not client_id or not client_secret:
            raise ValueError('QBench client_id and client_secret are required')
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self._api_base,
            headers=self._default_headers(),
            timeout=timeout,
        )

    def _default_headers(self) -> dict[str, str]:
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

    async def fetch_sample(self, sample_id: str) -> Optional[dict[str, Any]]:
        """Fetch metadata for a sample identifier."""
        response = await self._request('GET', f'/samples/{sample_id}')
        if response.status_code == httpx.codes.NOT_FOUND:
            return None
        response.raise_for_status()
        return response.json()

    async def upload_result(self, sample_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Upload a result payload."""
        response = await self._request('POST', f'/samples/{sample_id}/results', json=payload)
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the HTTP client session."""
        await self._client.aclose()

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        await self._ensure_token()
        response = await self._client.request(method, url, **kwargs)
        if response.status_code == httpx.codes.UNAUTHORIZED:
            await self._authenticate()
            response = await self._client.request(method, url, **kwargs)
        return response

    async def _ensure_token(self) -> None:
        if 'Authorization' not in self._client.headers:
            await self._authenticate()

    async def _authenticate(self) -> None:
        token_endpoint = self._resolve_token_endpoint()
        auth = httpx.BasicAuth(self._client_id, self._client_secret)
        async with httpx.AsyncClient(timeout=self._timeout) as auth_client:
            response = await auth_client.post(
                token_endpoint,
                data={'grant_type': 'client_credentials'},
                auth=auth,
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
            )
        response.raise_for_status()
        token_payload = response.json()
        access_token = token_payload.get('access_token')
        if not access_token:
            raise RuntimeError('QBench token response did not include an access token')
        token_type = token_payload.get('token_type', 'Bearer')
        self._client.headers['Authorization'] = f'{token_type} {access_token}'

    def _resolve_token_endpoint(self) -> str:
        if self._token_url:
            return self._token_url

        base = self._api_base.rstrip('/')
        if base.endswith('/api'):
            host = base[:-len('/api')]
        else:
            host = base
        return f'{host.rstrip('/')}/oauth/token'

