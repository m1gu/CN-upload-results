from __future__ import annotations

import sys
import types
from datetime import date
from pathlib import Path

import pytest

if "supabase" not in sys.modules:
    supabase_stub = types.ModuleType("supabase")

    class _DummySupabaseClient:
        def __init__(self):
            self.auth = types.SimpleNamespace(sign_in_with_password=lambda *args, **kwargs: types.SimpleNamespace(model_dump=lambda: {}))

        def table(self, name):  # noqa: ANN001
            return types.SimpleNamespace(insert=lambda payload: types.SimpleNamespace(execute=lambda: None))

    def _create_client(*args, **kwargs):  # noqa: ANN003
        return _DummySupabaseClient()

    supabase_stub.Client = _DummySupabaseClient
    supabase_stub.create_client = _create_client
    sys.modules["supabase"] = supabase_stub

from cn_upload_results.domain.models import RunMetadata, SampleQuantification, WorkbookExtraction
from cn_upload_results.services import persistence


def _make_extraction() -> WorkbookExtraction:
    metadata = RunMetadata(
        run_date=date(2025, 9, 5),
        batch_numbers=["8398", "8386"],
        batch_sample_map={"8398": ["14691"], "8386": ["14733", "14734"]},
        source_filename="20250905_run.xlsx",
    )
    samples = [
        SampleQuantification(
            sample_id="14691",
            base_sample_id="14691",
            test_index=0,
            column_header="14691 Inj. 1",
            components={"cbd": 0.1},
            area_results={"cbd": 10.0},
            sample_mass_mg=100.0,
            dilution=2.0,
            serving_mass_g=None,
            servings_per_package=None,
            batch_numbers=["8398"],
        ),
        SampleQuantification(
            sample_id="14733",
            base_sample_id="14733",
            test_index=0,
            column_header="14733 Inj. 1",
            components={"cbd": 0.2},
            area_results={"cbd": 12.0},
            sample_mass_mg=101.0,
            dilution=2.5,
            serving_mass_g=None,
            servings_per_package=None,
            batch_numbers=["8386"],
        ),
    ]
    return WorkbookExtraction(metadata=metadata, samples=samples)


class _FakeClient:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def store_run_record(self, record):
        self.records.append(record)


def test_persist_run_to_supabase_inserts_expected_payload(monkeypatch, tmp_path):
    extraction = _make_extraction()
    excel_path = tmp_path / "run.xlsx"
    excel_path.write_text("dummy")

    fake_client = _FakeClient()

    monkeypatch.setattr(persistence, "SupabaseClient", lambda **kwargs: fake_client)

    class _Settings:
        supabase_url = "https://example.supabase.co"
        supabase_service_role_key = "service-key"
        environment = "sandbox"

    persistence.persist_run_to_supabase(
        settings=_Settings(),
        extraction=extraction,
        excel_path=excel_path,
        qbench_payload={"status": "completed"},
        created_by="user@example.com",
        instrument="HPLC-01",
    )

    assert len(fake_client.records) == 1
    record = fake_client.records[0]
    assert record["run_date"] == "2025-09-05"
    assert record["file_name"] == "run.xlsx"
    assert record["created_by"] == "user@example.com"
    assert record["batch_codes"] == ["8398", "8386"]
    assert set(record["sample_ids"]) == {"14691", "14733"}
    assert "excel_payload" in record and "samples" in record["excel_payload"]
    assert record["qbench_payload"]["status"] == "completed"
    assert record["instrument"] == "HPLC-01"


@pytest.mark.parametrize("created_by", [None, "operator@example.com"])
def test_persist_run_to_supabase_sets_created_by(monkeypatch, tmp_path, created_by):
    extraction = _make_extraction()
    excel_path = tmp_path / "run.xlsx"
    excel_path.write_text("dummy")

    captured = {}

    class _FakeClient2:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def store_run_record(self, record):
            captured.update(record)

    monkeypatch.setattr(persistence, "SupabaseClient", lambda **_: _FakeClient2())

    class _Settings:
        supabase_url = "https://example.supabase.co"
        supabase_service_role_key = "service-key"
        environment = "sandbox"

    persistence.persist_run_to_supabase(
        settings=_Settings(),
        extraction=extraction,
        excel_path=excel_path,
        qbench_payload={"status": "completed"},
        created_by=created_by,
    )

    if created_by:
        assert captured["created_by"] == created_by
    else:
        assert captured["created_by"]
