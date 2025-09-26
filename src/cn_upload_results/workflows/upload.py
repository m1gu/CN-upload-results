"""Entry points for orchestrating the upload workflow."""
from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List

import httpx

from cn_upload_results.clients.qbench import QBenchClient
from cn_upload_results.config.settings import get_settings
from cn_upload_results.domain.models import (
    AREA_RESULT_SUFFIX,
    COMPONENT_ORDER,
    SampleQuantification,
    WorkbookExtraction,
)
from cn_upload_results.parsers.excel import parse_workbook

LOGGER = logging.getLogger(__name__)

ASSAY_ID_CN = 16
ASSAY_ID_HO = 34
STATE_PRIORITY = {
    "NOT STARTED": 0,
    "IN PROGRESS": 1,
    "NOT REPORTABLE": 2,
    "IN REVIEW": 3,
    "COMPLETED": 4,
    "REPORTED": 5,
}


def run_upload(excel_path: Path) -> WorkbookExtraction:
    """Execute the end-to-end upload pipeline against QBench."""

    settings = get_settings()
    extraction = parse_workbook(excel_path)
    grouped_samples = _group_by_base_sample(extraction.samples)

    with QBenchClient(
        base_url=str(settings.qbench_base_url),
        client_id=settings.qbench_client_id,
        client_secret=settings.qbench_client_secret,
        token_url=settings.qbench_token_endpoint,
    ) as qbench:
        for base_sample_id, sample_tests in grouped_samples.items():
            _push_sample_tests(qbench, base_sample_id, sample_tests)

    return extraction


def _group_by_base_sample(samples: Iterable[SampleQuantification]) -> Dict[str, List[SampleQuantification]]:
    grouped: Dict[str, List[SampleQuantification]] = defaultdict(list)
    for sample in samples:
        grouped[sample.base_sample_id].append(sample)
    for sample_list in grouped.values():
        sample_list.sort(key=lambda value: value.test_index)
    return dict(grouped)


def _push_sample_tests(
    qbench: QBenchClient,
    base_sample_id: str,
    sample_tests: List[SampleQuantification],
) -> None:
    qbench_sample = qbench.fetch_sample(base_sample_id, include_tests=True)
    if not qbench_sample:
        raise ValueError(f"Sample {base_sample_id} not found in QBench")

    qbench_tests = qbench_sample.get("tests", []) or []
    cn_tests = _select_tests_by_assay(qbench_tests, ASSAY_ID_CN)
    ho_tests = _select_tests_by_assay(qbench_tests, ASSAY_ID_HO)

    _apply_cannabinoid_updates(qbench, base_sample_id, sample_tests, cn_tests)
    _apply_homogeneity_update(qbench, base_sample_id, sample_tests, ho_tests)


def _select_tests_by_assay(tests: List[Dict[str, object]], assay_id: int) -> List[Dict[str, object]]:
    selected = [test for test in tests if test.get("assay_id") == assay_id]
    selected.sort(
        key=lambda test: (
            STATE_PRIORITY.get(str(test.get("state") or "").upper(), 99),
            test.get("id"),
        )
    )
    return selected


def _apply_cannabinoid_updates(
    qbench: QBenchClient,
    base_sample_id: str,
    sample_tests: List[SampleQuantification],
    qbench_tests: List[Dict[str, object]],
) -> None:
    if not qbench_tests:
        return

    cn_samples = [sample for sample in sample_tests if sample.test_index < len(qbench_tests)]
    if len(cn_samples) < len(qbench_tests):
        raise ValueError(
            f"Sample {base_sample_id} has only {len(cn_samples)} CN tests in the workbook but "
            f"{len(qbench_tests)} tests are expected in QBench"
        )

    for sample, qbench_test in zip(cn_samples, qbench_tests):
        data = _build_cannabinoid_payload(sample)
        if not data:
            LOGGER.info(
                "Skipping CN test %s for sample %s because payload is empty",
                qbench_test.get("id"),
                base_sample_id,
            )
            continue
        _send_worksheet_update(qbench, qbench_test, data)


def _apply_homogeneity_update(
    qbench: QBenchClient,
    base_sample_id: str,
    sample_tests: List[SampleQuantification],
    qbench_tests: List[Dict[str, object]],
) -> None:
    if not qbench_tests:
        return

    payload = _build_homogeneity_payload(sample_tests)
    if not payload:
        LOGGER.info("Skipping HO upload for sample %s because payload is empty", base_sample_id)
        return

    _send_worksheet_update(qbench, qbench_tests[0], payload)


def _send_worksheet_update(qbench: QBenchClient, qbench_test: Dict[str, object], data: Dict[str, str]) -> None:
    test_id = qbench_test.get("id")
    try:
        qbench.update_test_worksheet(test_id, data=data)
    except httpx.HTTPError:
        LOGGER.exception("Failed to update worksheet for test %s", test_id)
        raise


def _build_cannabinoid_payload(sample: SampleQuantification) -> Dict[str, str]:
    payload: Dict[str, str] = {}

    if sample.sample_mass_mg is not None:
        payload["sample_mass"] = _format_number(sample.sample_mass_mg)
    if sample.dilution is not None:
        payload["dilution"] = _format_number(sample.dilution)
    if sample.serving_mass_g is not None:
        formatted = _format_number(sample.serving_mass_g)
        payload["serving_mass_g"] = formatted
        payload["unit_weight"] = formatted
    if sample.servings_per_package is not None:
        formatted = _format_number(sample.servings_per_package)
        payload["servings_per_package"] = formatted
        payload["units_per_package"] = formatted

    for component in COMPONENT_ORDER:
        value = sample.components.get(component)
        if value is None:
            continue
        payload[component] = _format_number(value)

    for component, value in sample.area_results.items():
        if value is None:
            continue
        payload[f"{component}{AREA_RESULT_SUFFIX}"] = _format_number(value)

    return payload


def _build_homogeneity_payload(samples: List[SampleQuantification]) -> Dict[str, str]:
    payload: Dict[str, str] = {}
    for sample in samples:
        index = sample.test_index
        if sample.sample_mass_mg is not None:
            payload[f"sample_mass_{index}"] = _format_number(sample.sample_mass_mg)
        if sample.dilution is not None:
            payload[f"dilution_{index}"] = _format_number(sample.dilution)
        for component in COMPONENT_ORDER:
            value = sample.components.get(component)
            if value is None:
                continue
            payload[f"{component}_{index}"] = _format_number(value)
    return payload


def _format_number(value: float) -> str:
    text = f"{value:.6f}"
    return text.rstrip("0").rstrip(".")
