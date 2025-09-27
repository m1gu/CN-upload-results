"""Supabase client helpers for authentication and audit logging."""
from __future__ import annotations

from typing import Any, Dict, Optional

from supabase import Client, create_client

from cn_upload_results.domain.models import RunMetadata, SampleQuantification


class SupabaseClient:
    """Light wrapper around supabase-py for project-specific operations."""

    def __init__(self, *, url: str, service_role_key: str) -> None:
        self._client: Client = create_client(url, service_role_key)

    def __enter__(self) -> "SupabaseClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        """Placeholder for parity with other clients."""

    @property
    def raw(self) -> Client:
        """Expose the underlying client when advanced calls are needed."""

        return self._client

    def authenticate(self, *, email: str, password: str) -> Dict[str, Any]:
        """Authenticate a user and return the session object."""

        response = self._client.auth.sign_in_with_password(
            {
                "email": email,
                "password": password,
            }
        )
        return response.model_dump() if hasattr(response, "model_dump") else response

    def store_run_record(self, record: Dict[str, Any]) -> None:
        """Persist a full run record into the cn_upload_results table."""

        self._client.table("cn_upload_results").insert(record).execute()

    def log_sample_upload(
        self,
        *,
        sample: SampleQuantification,
        run: RunMetadata,
        qbench_response: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record upload metadata for auditing purposes."""

        payload = {
            "sample_id": sample.sample_id,
            "base_sample_id": sample.base_sample_id,
            "test_index": sample.test_index,
            "column_header": sample.column_header,
            "run_date": run.run_date.isoformat(),
            "batch_numbers": sample.batch_numbers or run.batch_numbers,
            "components": sample.components,
            "area_results": sample.area_results,
            "sample_mass_mg": sample.sample_mass_mg,
            "dilution": sample.dilution,
            "serving_mass_g": sample.serving_mass_g,
            "servings_per_package": sample.servings_per_package,
            "source_file": run.source_filename,
            "qbench_payload": qbench_response or {},
        }
        self._client.table("qbench_uploads").insert(payload).execute()
