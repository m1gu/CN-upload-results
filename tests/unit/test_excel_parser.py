from __future__ import annotations

from datetime import date

import pandas as pd

from cn_upload_results.domain.models import COMPONENT_ORDER
from cn_upload_results.parsers.excel import parse_workbook


def test_parse_workbook_extracts_metadata_and_samples(tmp_path):
    path = tmp_path / "20250101_8561_8545 run.xlsx"

    sample_column = ["14956"]
    for index, _component in enumerate(COMPONENT_ORDER):
        sample_column.append(float(index))

    additional_rows = 26 - len(sample_column)
    sample_column.extend([None] * max(additional_rows, 0))
    sample_column[22] = 100.0
    sample_column[23] = 2.0
    sample_column[24] = 5.0
    sample_column[25] = 10.0

    dup_column = ["Dup 14956"] + [None] * (len(sample_column) - 1)

    results_df = pd.DataFrame({
        "A": sample_column,
        "B": dup_column,
    })

    batch_df = pd.DataFrame([["1234", None, "5678"]])

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        results_df.to_excel(writer, sheet_name="Results Transfer", header=False, index=False)
        batch_df.to_excel(writer, sheet_name="Blank Spike Recovery", header=False, index=False)

    extraction = parse_workbook(path)

    assert extraction.metadata.run_date == date(2025, 1, 1)
    assert extraction.metadata.batch_numbers == ["8561", "8545", "1234", "5678"]

    assert len(extraction.samples) == 1
    sample = extraction.samples[0]
    assert sample.sample_id == "14956"
    for index, component in enumerate(COMPONENT_ORDER):
        assert sample.components[component] == float(index)
    assert sample.sample_mass_mg == 100.0
    assert sample.dilution == 2.0
    assert sample.serving_mass_g == 5.0
    assert sample.servings_per_package == 10.0
