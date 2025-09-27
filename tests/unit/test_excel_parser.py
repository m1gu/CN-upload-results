from __future__ import annotations

from datetime import date

import pandas as pd

from cn_upload_results.domain.models import COMPONENT_ORDER
from cn_upload_results.parsers.excel import (
    AREA_RESULT_ROW_OFFSET,
    COMPONENT_ROW_OFFSET,
    DILUTION_ROW,
    SAMPLE_MASS_ROW,
    SERVING_MASS_ROW,
    SERVINGS_PER_PACKAGE_ROW,
    parse_workbook,
)


def test_parse_workbook_extracts_metadata_and_samples(tmp_path):
    path = tmp_path / "20250101_8561_8545 run.xlsx"

    column_values: dict[int, object] = {0: "14956"}

    for offset, component in enumerate(COMPONENT_ORDER):
        column_values[COMPONENT_ROW_OFFSET + offset] = float(offset)
        column_values[AREA_RESULT_ROW_OFFSET + offset] = float(offset * 10)

    column_values[SAMPLE_MASS_ROW] = 100.0
    column_values[DILUTION_ROW] = 2.0
    column_values[SERVING_MASS_ROW] = 5.0
    column_values[SERVINGS_PER_PACKAGE_ROW] = 10.0

    max_row_index = max(column_values) + 1
    sample_column = [column_values.get(index) for index in range(max_row_index)]
    bs_column = ["BS-Con-8398"] + [None] * (len(sample_column) - 1)

    dup_column = ["Dup 14956"] + [None] * (len(sample_column) - 1)

    results_df = pd.DataFrame({
        "A": bs_column,
        "B": sample_column,
        "C": dup_column,
    })

    batch_df = pd.DataFrame([["1234", None, "5678"]])

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        results_df.to_excel(writer, sheet_name="Results Transfer", header=False, index=False)
        batch_df.to_excel(writer, sheet_name="Blank Spike Recovery", header=False, index=False)

    extraction = parse_workbook(path)

    assert extraction.metadata.run_date == date(2025, 1, 1)
    assert extraction.metadata.batch_numbers == ["8561", "8545", "1234", "5678", "8398"]
    assert extraction.metadata.batch_sample_map == {"8398": ["14956"]}

    assert len(extraction.samples) == 1
    sample = extraction.samples[0]
    assert sample.sample_id == "14956"
    assert sample.base_sample_id == "14956"
    assert sample.test_index == 0
    assert sample.column_header == "14956"
    assert sample.batch_numbers == ["8398"]

    for index, component in enumerate(COMPONENT_ORDER):
        assert sample.components[component] == float(index)
        assert sample.area_results[component] == float(index * 10)
    assert sample.sample_mass_mg == 100.0
    assert sample.dilution == 2.0
    assert sample.serving_mass_g == 5.0
    assert sample.servings_per_package == 10.0
