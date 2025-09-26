from __future__ import annotations

from cn_upload_results.domain.models import SampleQuantification
from cn_upload_results.workflows import upload as workflow_upload
from cn_upload_results.workflows.upload import (
    AREA_RESULT_SUFFIX,
    COMPONENT_ORDER,
    _build_cannabinoid_payload,
    _build_homogeneity_payload,
    _group_by_base_sample,
)


def make_sample(
    index: int,
    components: dict[str, float | None],
    area_results: dict[str, float | None],
    **kwargs,
) -> SampleQuantification:
    merged_components = {component: None for component in COMPONENT_ORDER}
    merged_components.update(components)
    merged_area_results = {component: None for component in COMPONENT_ORDER}
    merged_area_results.update(area_results)
    return SampleQuantification(
        sample_id=f"15042-{index}" if index else "15042",
        base_sample_id="15042",
        test_index=index,
        column_header=f"15042 Inj {index}",
        components=merged_components,
        area_results=merged_area_results,
        sample_mass_mg=kwargs.get("sample_mass_mg"),
        dilution=kwargs.get("dilution"),
        serving_mass_g=kwargs.get("serving_mass_g"),
        servings_per_package=kwargs.get("servings_per_package"),
        batch_numbers=[],
    )


def test_build_cannabinoid_payload_formats_values() -> None:
    sample = make_sample(
        0,
        components={"cbg": 0.1213, "d9_thc": 3.135},
        area_results={"cbg": 27.31, "d9_thc": 634.4},
        sample_mass_mg=1021.0,
        dilution=40.0,
        serving_mass_g=3.1,
        servings_per_package=10,
    )

    payload = _build_cannabinoid_payload(sample)

    assert payload["sample_mass"] == "1021"
    assert payload["dilution"] == "40"
    assert payload["serving_mass_g"] == "3.1"
    assert payload["unit_weight"] == "3.1"
    assert payload["servings_per_package"] == "10"
    assert payload["units_per_package"] == "10"
    assert payload["cbg"] == "0.1213"
    assert payload["d9_thc"] == "3.135"
    assert payload["cbg" + AREA_RESULT_SUFFIX] == "27.31"
    assert payload["d9_thc" + AREA_RESULT_SUFFIX] == "634.4"


def test_build_homogeneity_payload_combines_indexes() -> None:
    samples = [
        make_sample(0, {"cbg": 0.12}, {}, sample_mass_mg=100.0, dilution=10.0),
        make_sample(1, {"cbg": 0.13}, {}, sample_mass_mg=101.0, dilution=11.0),
    ]

    payload = _build_homogeneity_payload(samples)

    assert payload["sample_mass_0"] == "100"
    assert payload["sample_mass_1"] == "101"
    assert payload["dilution_0"] == "10"
    assert payload["dilution_1"] == "11"
    assert payload["cbg_0"] == "0.12"
    assert payload["cbg_1"] == "0.13"


def test_group_by_base_sample_orders_by_index() -> None:
    samples = [
        make_sample(2, {}, {}),
        make_sample(0, {}, {}),
        make_sample(1, {}, {}),
    ]

    grouped = _group_by_base_sample(samples)

    assert list(grouped.keys()) == ["15042"]
    assert [sample.test_index for sample in grouped["15042"]] == [0, 1, 2]


def test_apply_cannabinoid_updates_uses_expected_subset() -> None:
    samples = [
        make_sample(0, {"cbg": 0.1}, {"cbg": 10.0}),
        make_sample(1, {"cbg": 0.2}, {"cbg": 20.0}),
        make_sample(2, {"cbg": 0.3}, {"cbg": 30.0}),
    ]
    qbench_tests = [{"id": "cn-1"}, {"id": "cn-2"}]
    calls: list[tuple[str, dict[str, str]]] = []

    original_sender = workflow_upload._send_worksheet_update

    def fake_sender(qbench, qbench_test, data):
        calls.append((qbench_test["id"], data))

    workflow_upload._send_worksheet_update = fake_sender
    try:
        workflow_upload._apply_cannabinoid_updates(
            qbench=object(),
            base_sample_id="15042",
            sample_tests=samples,
            qbench_tests=qbench_tests,
        )
    finally:
        workflow_upload._send_worksheet_update = original_sender

    assert [test_id for test_id, _ in calls] == ["cn-1", "cn-2"]
    assert all("cbg" in data for _, data in calls)


def test_apply_homogeneity_update_includes_all_replicates() -> None:
    samples = [
        make_sample(0, {"cbg": 0.1}, {}, sample_mass_mg=100.0),
        make_sample(1, {"cbg": 0.2}, {}, sample_mass_mg=101.0),
        make_sample(2, {"cbg": 0.3}, {}, sample_mass_mg=102.0),
    ]
    qbench_tests = [{"id": "ho-1"}]
    calls: list[dict[str, str]] = []

    original_sender = workflow_upload._send_worksheet_update

    def fake_sender(qbench, qbench_test, data):
        calls.append(data)

    workflow_upload._send_worksheet_update = fake_sender
    try:
        workflow_upload._apply_homogeneity_update(
            qbench=object(),
            base_sample_id="15042",
            sample_tests=samples,
            qbench_tests=qbench_tests,
        )
    finally:
        workflow_upload._send_worksheet_update = original_sender

    assert len(calls) == 1
    data = calls[0]
    assert data["cbg_0"] == "0.1"
    assert data["cbg_1"] == "0.2"
    assert data["cbg_2"] == "0.3"
