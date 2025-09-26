"""Thin client wrapper for QBench API calls."""
from __future__ import annotations

import base64
import hmac
import json
import logging
import time
from hashlib import sha256
from typing import Any, Dict, Optional

import httpx

LOGGER = logging.getLogger(__name__)


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

    def fetch_sample(self, sample_id: str, include_tests: bool = False) -> Optional[Dict[str, Any]]:
        """Retrieve a sample, optionally including its tests."""

        params = {"include": "tests"} if include_tests else None
        response = self._request("GET", f"/qbench/api/v1/sample/{sample_id}", params=params)
        if response.status_code == httpx.codes.NOT_FOUND:
            return None
        response.raise_for_status()
        return response.json()

    def update_test_worksheet(
        self,
        test_id: str | int,
        *,
        data: Optional[Dict[str, Any]] = None,
        worksheet_processed: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update worksheet fields for a given test."""

        if data is None and worksheet_processed is None:
            raise ValueError("At least one of data or worksheet_processed must be provided")

        payload: Dict[str, Any] = {}
        if data:
            payload["data"] = data
        if worksheet_processed is not None:
            payload["worksheet_processed"] = worksheet_processed

        response = self._request(
            "PATCH",
            f"/qbench/api/v1/test/{test_id}/worksheet",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        response = self._client.request(method, url, **kwargs)
        if response.status_code == httpx.codes.UNAUTHORIZED:
            self._authenticate()
            response = self._client.request(method, url, **kwargs)
        return response

    def _authenticate(self) -> None:
        """Obtain an access token using the JWT bearer grant flow."""

        token_endpoint = self._resolve_token_endpoint()
        assertion = _build_jwt_assertion(self._client_id, self._client_secret)
        payload = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        }

        response = httpx.post(
            token_endpoint,
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=self._timeout,
        )
        if response.status_code >= 400:
            LOGGER.error(
                "Failed to obtain token from %s: %s", token_endpoint, response.text
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
        return f"{host}/oauth/token"


def _build_jwt_assertion(client_id: str, client_secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "sub": client_id,
        "iat": now,
        "exp": now + 3600,
    }

    header_segment = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = b".".join([header_segment, payload_segment])
    signature = hmac.new(client_secret.encode("utf-8"), signing_input, sha256).digest()
    signature_segment = _base64url_encode(signature)
    return b".".join([header_segment, payload_segment, signature_segment]).decode("ascii")


def _base64url_encode(value: bytes) -> bytes:
    return base64.urlsafe_b64encode(value).rstrip(b"=")
