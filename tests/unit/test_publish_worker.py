from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from cn_upload_results.domain.models import RunMetadata, SampleQuantification, WorkbookExtraction
from cn_upload_results.ui.publish_worker import PublishWorker
from cn_upload_results.workflows.upload import UploadOutcome


def _make_extraction(sample_count: int = 2) -> WorkbookExtraction:
    metadata = RunMetadata(
        run_date=date(2025, 9, 5),
        batch_numbers=["8398"],
        batch_sample_map={"8398": ["14691"]},
        source_filename="dummy.xlsx",
    )
    samples = []
    for index in range(sample_count):
        sid = f"14691-{index}" if index else "14691"
        samples.append(
            SampleQuantification(
                sample_id=sid,
                base_sample_id="14691",
                test_index=index,
                column_header=f"{sid} Inj. 1",
                components={},
                area_results={},
                sample_mass_mg=None,
                dilution=None,
                serving_mass_g=None,
                servings_per_package=None,
                batch_numbers=["8398"],
            )
        )
    return WorkbookExtraction(metadata=metadata, samples=samples)


class _Settings:
    environment = "sandbox"
    dry_run = False


@pytest.fixture(autouse=True)
def _qt_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def test_publish_worker_success(monkeypatch, tmp_path):
    excel_path = tmp_path / "input.xlsx"
    excel_path.write_text("dummy")

    extraction = _make_extraction(sample_count=3)
    captured = {}

    def fake_run_upload(path: Path):  # noqa: ANN001
        captured["run_upload_path"] = Path(path)
        return extraction, UploadOutcome(processed=[], skipped=[], dry_run=False)

    def fake_persist(**kwargs):  # noqa: ANN003
        captured["persist_kwargs"] = kwargs

    monkeypatch.setattr("cn_upload_results.ui.publish_worker.run_upload", fake_run_upload)
    monkeypatch.setattr("cn_upload_results.ui.publish_worker.persist_run_to_supabase", fake_persist)
    monkeypatch.setattr("cn_upload_results.ui.publish_worker.build_default_qbench_payload", lambda extraction: {"status": "ok"})

    worker = PublishWorker(settings=_Settings(), excel_path=excel_path, user_email="user@example.com")

    progress_messages = []
    successes = []
    errors = []

    worker.progress.connect(progress_messages.append)
    worker.success.connect(successes.append)
    worker.error.connect(errors.append)

    worker.run()

    assert not errors
    assert len(successes) == 1
    assert isinstance(successes[0], UploadOutcome)
    assert not successes[0].dry_run
    assert successes[0].total_processed_samples() == 0
    assert successes[0].total_skipped_samples() == 0
    assert progress_messages[:2] == ["Guardando en QBench...", "Guardando datos en Supabase..."]
    assert progress_messages[-1] == "Proceso completado"
    assert captured["run_upload_path"] == excel_path
    assert captured["persist_kwargs"]["created_by"] == "user@example.com"


def test_publish_worker_handles_qbench_error(monkeypatch, tmp_path):
    excel_path = tmp_path / "input.xlsx"
    excel_path.write_text("dummy")

    def fake_run_upload(path: Path):  # noqa: ANN001
        raise RuntimeError("network down")

    monkeypatch.setattr("cn_upload_results.ui.publish_worker.run_upload", fake_run_upload)

    worker = PublishWorker(settings=_Settings(), excel_path=excel_path, user_email=None)
    errors = []
    worker.error.connect(errors.append)

    worker.run()

    assert errors
    assert "network down" in errors[0]


def test_publish_worker_handles_supabase_error(monkeypatch, tmp_path):
    excel_path = tmp_path / "input.xlsx"
    excel_path.write_text("dummy")

    extraction = _make_extraction()

    monkeypatch.setattr(
        "cn_upload_results.ui.publish_worker.run_upload",
        lambda path: (extraction, UploadOutcome(processed=[], skipped=[], dry_run=False)),
    )
    monkeypatch.setattr(
        "cn_upload_results.ui.publish_worker.build_default_qbench_payload", lambda extraction: {"status": "ok"}
    )

    def fake_persist(**kwargs):  # noqa: ANN003
        raise RuntimeError("supabase fail")

    monkeypatch.setattr("cn_upload_results.ui.publish_worker.persist_run_to_supabase", fake_persist)

    worker = PublishWorker(settings=_Settings(), excel_path=excel_path, user_email=None)
    errors = []
    worker.error.connect(errors.append)

    worker.run()

    assert errors
    assert "supabase fail" in errors[0]
