
"""Entry points for orchestrating the upload workflow."""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Optional, Sequence, Tuple

import httpx

from cn_upload_results.clients.qbench import QBenchClient
from cn_upload_results.config.settings import AppSettings, get_settings
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
REQUIRED_STATE = "NEEDS REVIEW (DATA TEAM)"
HO_ALLOWED_INDICES = {0, 1, 2}

STATE_PRIORITY = {
    "NOT STARTED": 0,
    "IN PROGRESS": 1,
    "NOT REPORTABLE": 2,
    "NEEDS REVIEW (DATA TEAM)": 3,
    "IN REVIEW": 4,
    "COMPLETED": 5,
    "REPORTED": 6,
}


@dataclass(slots=True)
class QBenchTestInfo:
    """Minimal representation of a QBench test relevant for uploads."""

    test_id: int
    assay_id: int
    state: str
    batches: set[str]
    worksheet_processed: bool
    raw: Dict[str, object]
    label: str


@dataclass(slots=True)
class ScheduledTestUpdate:
    """Associates Excel columns with a QBench test to update."""

    qbench_test: QBenchTestInfo
    kind: Literal["CN", "HO"]
    samples: List[SampleQuantification]
    indices: List[int]
    column_headers: List[str]


@dataclass(slots=True)
class SampleUploadPlan:
    """Decision tree result for a single base sample."""

    base_sample_id: str
    updates: List[ScheduledTestUpdate]
    skipped_columns: List[str]
    reason: Optional[str]
    available_cn: int
    available_ho: int

    # NOTE: Helper that reports whether the plan contains actionable updates and no
    #       blocking reason, simplifying later success checks.
    def is_successful(self) -> bool:
        return not self.reason and bool(self.updates)


@dataclass(slots=True)
class TestUpdateSummary:
    """What was actually updated for a given test."""

    test_id: int
    kind: Literal["CN", "HO"]
    column_headers: List[str]
    indices: List[int]


@dataclass(slots=True)
class SampleUploadSummary:
    """Aggregated information for reporting per sample."""

    base_sample_id: str
    tests: List[TestUpdateSummary]
    skipped_columns: List[str]
    reason: Optional[str]
    available_cn: int
    available_ho: int


@dataclass
class UploadOutcome:
    """Container for success/skip results across the workbook."""

    processed: List[SampleUploadSummary]
    skipped: List[SampleUploadSummary]
    dry_run: bool

    # NOTE: Returns how many samples were successfully processed in this run.
    def total_processed_samples(self) -> int:
        return len(self.processed)

    # NOTE: Returns how many samples were skipped or aborted during the workflow.
    def total_skipped_samples(self) -> int:
        return len(self.skipped)

    # NOTE: Produces a human-readable report summarizing processed and skipped samples,
    #       including dry-run notices, column assignments, and reasons for omissions.
    def summary_text(self) -> str:
        if not self.processed and not self.skipped:
            return "No se realizaron actualizaciones."

        lines: List[str] = []
        if self.dry_run:
            lines.append("Modo simulacion: no se enviaron cambios a QBench ni Supabase.")
        if self.processed:
            lines.append("Samples actualizados:")
            for sample in self.processed:
                tests_description = []
                for test in sample.tests:
                    columns = ", ".join(test.column_headers)
                    if test.indices:
                        index_text = ", ".join(str(index) for index in test.indices)
                        tests_description.append(f"{test.kind} #{test.test_id} ({columns}) -> indices [{index_text}]")
                    else:
                        tests_description.append(f"{test.kind} #{test.test_id} ({columns})")
                lines.append(
                    f" - {sample.base_sample_id} [CN:{sample.available_cn}, HO:{sample.available_ho}]: "
                    + "; ".join(tests_description)
                )

        if self.skipped:
            lines.append("Samples omitidos:")
            for sample in self.skipped:
                columns = ", ".join(sample.skipped_columns) if sample.skipped_columns else "Sin columnas"
                header = f" - {sample.base_sample_id} [CN:{sample.available_cn}, HO:{sample.available_ho}]"
                if sample.reason:
                    lines.append(f"{header}: {columns} -> {sample.reason}")
                else:
                    lines.append(f"{header}: {columns}")
        return "\n".join(lines)


# -----------------------------------------------------------------------------
# NOTE: Orchestrates the end-to-end workflow. It parses the Excel workbook,
#       fetches candidate tests from QBench, resolves the matching plan, and
#       either simulates or applies the updates while building an outcome summary.
def run_upload(excel_path: Path, *, settings: AppSettings | None = None) -> Tuple[WorkbookExtraction, UploadOutcome]:
    """Execute the end-to-end upload pipeline against QBench."""

    if settings is None:
        settings = get_settings()
    extraction = parse_workbook(excel_path)
    grouped_samples = _group_by_base_sample(extraction.samples)
    outcome = UploadOutcome(processed=[], skipped=[], dry_run=settings.dry_run)

    with QBenchClient(
        base_url=str(settings.qbench_base_url),
        client_id=settings.qbench_client_id,
        client_secret=settings.qbench_client_secret,
        token_url=settings.qbench_token_endpoint,
    ) as qbench:
        for base_sample_id, sample_tests in grouped_samples.items():
            qbench_sample = qbench.fetch_sample(base_sample_id, include_tests=True)
            plan = _resolve_upload_plan(
                base_sample_id=base_sample_id,
                sample_columns=sample_tests,
                qbench_sample=qbench_sample,
            )

            if plan.reason:
                outcome.skipped.append(
                    SampleUploadSummary(
                        base_sample_id=plan.base_sample_id,
                        tests=[],
                        skipped_columns=plan.skipped_columns,
                        reason=plan.reason,
                        available_cn=plan.available_cn,
                        available_ho=plan.available_ho,
                    )
                )
                continue

            applied, payload_skips, skip_reason = _execute_plan(
                qbench, plan, settings.skip_processed_tests, settings.dry_run
            )
            if applied:
                summary = SampleUploadSummary(
                    base_sample_id=plan.base_sample_id,
                    tests=[
                        TestUpdateSummary(
                            test_id=update.qbench_test.test_id,
                            kind=update.kind,
                            column_headers=update.column_headers,
                            indices=update.indices,
                        )
                        for update in applied
                    ],
                    skipped_columns=[*plan.skipped_columns, *payload_skips],
                    reason=None,
                    available_cn=plan.available_cn,
                    available_ho=plan.available_ho,
                )
                outcome.processed.append(summary)
            else:
                reason = skip_reason or "Los tests seleccionados no tenian datos para enviar."
                outcome.skipped.append(
                    SampleUploadSummary(
                        base_sample_id=plan.base_sample_id,
                        tests=[],
                        skipped_columns=[*plan.skipped_columns, *payload_skips],
                        reason=reason,
                        available_cn=plan.available_cn,
                        available_ho=plan.available_ho,
                    )
                )

    return extraction, outcome


# -----------------------------------------------------------------------------
# NOTE: Groups SampleQuantification objects by base sample id and orders each list
#       by test index so later matching logic can rely on a deterministic sequence.
def _group_by_base_sample(samples: Iterable[SampleQuantification]) -> Dict[str, List[SampleQuantification]]:
    grouped: Dict[str, List[SampleQuantification]] = defaultdict(list)
    for sample in samples:
        grouped[sample.base_sample_id].append(sample)
    for sample_list in grouped.values():
        sample_list.sort(key=lambda value: value.test_index)
    return dict(grouped)


# -----------------------------------------------------------------------------
# NOTE: Builds the decision plan for a single sample. It analyses available CN/HO
#       tests, validates Excel columns, determines assignments, and records reasons
#       whenever the sample cannot be uploaded.
def _resolve_upload_plan(
    *,
    base_sample_id: str,
    sample_columns: List[SampleQuantification],
    qbench_sample: Optional[Dict[str, object]],
) -> SampleUploadPlan:
    column_headers = [sample.column_header or sample.sample_id for sample in sample_columns]
    if not qbench_sample:
        reason = f"Sample {base_sample_id} no se encontr? en QBench"
        return SampleUploadPlan(
            base_sample_id=base_sample_id,
            updates=[],
            skipped_columns=column_headers,
            reason=reason,
            available_cn=0,
            available_ho=0,
        )

    excel_batches = _collect_excel_batches(sample_columns)
    available_tests = _collect_available_tests(
        qbench_sample.get("tests", []) or [], excel_batches
    )
    cn_tests = [test for test in available_tests if test.assay_id == ASSAY_ID_CN]
    ho_tests = [test for test in available_tests if test.assay_id == ASSAY_ID_HO]

    plan = SampleUploadPlan(
        base_sample_id=base_sample_id,
        updates=[],
        skipped_columns=[],
        reason=None,
        available_cn=len(cn_tests),
        available_ho=len(ho_tests),
    )

    if not sample_columns:
        plan.reason = "El Excel no contiene columnas para el sample"
        plan.skipped_columns = []
        return plan

    if not cn_tests and not ho_tests:
        plan.reason = "No hay tests elegibles en QBench tras aplicar los filtros"
        plan.skipped_columns = column_headers
        return plan

    if len(ho_tests) > 1:
        plan.reason = "Se encontr? m?s de un test HO elegible, caso no soportado"
        plan.skipped_columns = column_headers
        return plan

    if len(cn_tests) > 3:
        plan.reason = "Se encontraron m?s de tres tests CN elegibles, caso no soportado"
        plan.skipped_columns = column_headers
        return plan

    replicate_map: Dict[int, SampleQuantification] = {}
    duplicate_indices: List[int] = []
    for sample in sample_columns:
        index = _extract_replicate_index(sample, base_sample_id)
        if index in replicate_map:
            duplicate_indices.append(index)
        replicate_map[index] = sample

    if duplicate_indices:
        indices_text = ", ".join(str(index) for index in duplicate_indices)
        plan.reason = f"Se repiten ?ndices de r?plica en el Excel ({indices_text})"
        plan.skipped_columns = column_headers
        return plan

    updates: List[ScheduledTestUpdate] = []

    if len(cn_tests) == 0 and len(ho_tests) == 1:
        ho_indices = sorted(replicate_map.keys())
        if not ho_indices:
            plan.reason = "No hay columnas para actualizar el test HO"
        elif any(index not in HO_ALLOWED_INDICES for index in ho_indices):
            plan.reason = "?ndices de HO fuera del rango permitido (0, 1, 2)"
        else:
            ho_samples = [replicate_map[index] for index in ho_indices]
            updates.append(
                ScheduledTestUpdate(
                    qbench_test=ho_tests[0],
                    kind="HO",
                    samples=ho_samples,
                    indices=ho_indices,
                    column_headers=[sample.column_header or sample.sample_id for sample in ho_samples],
                )
            )
    elif len(cn_tests) == 1 and len(ho_tests) == 1:
        if not sample_columns:
            plan.reason = "No hay columnas en el Excel para asignar a CN/HO"
        else:
            cn_sample = sample_columns[0]
            updates.append(
                ScheduledTestUpdate(
                    qbench_test=cn_tests[0],
                    kind="CN",
                    samples=[cn_sample],
                    indices=[_extract_replicate_index(cn_sample, base_sample_id)],
                    column_headers=[cn_sample.column_header or cn_sample.sample_id],
                )
            )
            ho_indices = sorted(replicate_map.keys())
            if any(index not in HO_ALLOWED_INDICES for index in ho_indices):
                plan.reason = "?ndices de HO fuera del rango permitido (0, 1, 2)"
            else:
                ho_samples = [replicate_map[index] for index in ho_indices]
                updates.append(
                    ScheduledTestUpdate(
                        qbench_test=ho_tests[0],
                        kind="HO",
                        samples=ho_samples,
                        indices=ho_indices,
                        column_headers=[sample.column_header or sample.sample_id for sample in ho_samples],
                    )
                )
    elif len(ho_tests) == 0 and len(cn_tests) in {1, 2, 3}:
        if len(sample_columns) != len(cn_tests):
            plan.reason = (
                "La cantidad de columnas del Excel no coincide con los tests CN disponibles"
            )
        else:
            for sample, qbench_test in zip(sample_columns, cn_tests):
                updates.append(
                    ScheduledTestUpdate(
                        qbench_test=qbench_test,
                        kind="CN",
                        samples=[sample],
                        indices=[_extract_replicate_index(sample, base_sample_id)],
                        column_headers=[sample.column_header or sample.sample_id],
                    )
                )
    else:
        plan.reason = "Combinaci?n de tests CN/HO no soportada"

    if plan.reason:
        plan.skipped_columns = column_headers
        plan.updates = []
        return plan

    used_sample_ids = {sample.sample_id for update in updates for sample in update.samples}
    plan.updates = updates
    plan.skipped_columns = [
        sample.column_header or sample.sample_id
        for sample in sample_columns
        if sample.sample_id not in used_sample_ids
    ]
    return plan







# -----------------------------------------------------------------------------
# NOTE: Filters raw QBench tests by assay and state. CN tests must also share a
#       batch with the Excel data when possible, while HO tests only need the
#       state check. Fallback lists preserve candidates when batches do not match.
def _collect_available_tests(
    raw_tests: Sequence[Dict[str, object]],
    excel_batches: set[str],
) -> List[QBenchTestInfo]:
    selected: Dict[int, List[QBenchTestInfo]] = {ASSAY_ID_CN: [], ASSAY_ID_HO: []}
    fallback: Dict[int, List[QBenchTestInfo]] = {ASSAY_ID_CN: [], ASSAY_ID_HO: []}

    for raw in raw_tests:
        try:
            assay = raw.get("assay") or {}
            assay_id = int(assay.get("id"))
        except (TypeError, ValueError):
            continue

        if assay_id not in {ASSAY_ID_CN, ASSAY_ID_HO}:
            continue

        state_text = str(raw.get("state") or "").strip()
        if state_text.upper() != REQUIRED_STATE:
            continue

        batches = {_normalize_batch(value) for value in raw.get("batches", [])}

        try:
            test_id = int(raw.get("id"))
        except (TypeError, ValueError):
            continue

        label = str(raw.get("name") or raw.get("label") or raw.get("test_name") or "")
        info = QBenchTestInfo(
            test_id=test_id,
            assay_id=assay_id,
            state=state_text,
            batches=batches,
            worksheet_processed=bool(raw.get("worksheet_processed")),
            raw=raw,
            label=label,
        )

        fallback[assay_id].append(info)
        if assay_id == ASSAY_ID_CN and excel_batches and not (batches & excel_batches):
            continue
        selected[assay_id].append(info)

    results: List[QBenchTestInfo] = []
    for assay_id in (ASSAY_ID_CN, ASSAY_ID_HO):
        group = selected[assay_id] if selected[assay_id] else fallback[assay_id]
        group.sort(key=lambda test: (STATE_PRIORITY.get(test.state.upper(), 99), test.test_id))
        results.extend(group)
    return results


# -----------------------------------------------------------------------------
# NOTE: Extracts and normalizes all batch identifiers present in the Excel columns
#       so they can be compared against the batches reported by QBench.
def _collect_excel_batches(samples: Iterable[SampleQuantification]) -> set[str]:
    batches: set[str] = set()
    for sample in samples:
        for value in sample.batch_numbers:
            normalized = _normalize_batch(value)
            if normalized:
                batches.add(normalized)
    return batches


# -----------------------------------------------------------------------------
# NOTE: Converts any batch representation into a trimmed string, ensuring that
#       comparisons between Excel and QBench batches remain consistent.
def _normalize_batch(value: object) -> str:
    return str(value).strip()


# -----------------------------------------------------------------------------
# NOTE: Derives the replicate index for a column using its sample id. Suffixes
#       like "-1" or "-2" override the spreadsheet order so HO indices align.
def _extract_replicate_index(sample: SampleQuantification, base_sample_id: str) -> int:
    sample_id = sample.sample_id
    if sample_id == base_sample_id:
        return 0
    if "-" in sample_id:
        suffix = sample_id.rsplit("-", 1)[-1]
        if suffix.isdigit():
            return int(suffix)
    return sample.test_index


# -----------------------------------------------------------------------------
# NOTE: Interprets a worksheet field value from QBench and decides whether it is
#       effectively empty (None, zero, or blank string), regardless of format.
def _is_blank_worksheet_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, (int, float)):
        return value == 0
    text = str(value).strip()
    if not text:
        return True
    normalized = text.rstrip('%')
    try:
        return float(normalized) == 0.0
    except ValueError:
        return False


# -----------------------------------------------------------------------------
# NOTE: Checks that every field we intend to populate in QBench still contains only
#       blank values, preventing accidental overwrites of previously uploaded data.
def _worksheet_fields_are_empty(worksheet_data: object, keys: Iterable[str]) -> bool:
    if not isinstance(worksheet_data, dict):
        return True
    for key in keys:
        field = worksheet_data.get(key)
        if field is None:
            continue
        if isinstance(field, dict):
            value = field.get('value')
            if value is None:
                value = field.get('default_numeric_value')
        else:
            value = field
        if not _is_blank_worksheet_value(value):
            return False
    return True




# -----------------------------------------------------------------------------
# NOTE: Iterates over the scheduled updates, builds payloads, enforces the
#       worksheet guards, optionally performs QBench PATCH calls, and tracks
#       which columns were applied or skipped.
def _execute_plan(
    qbench: QBenchClient,
    plan: SampleUploadPlan,
    respect_existing_data: bool,
    dry_run: bool,
) -> Tuple[List[ScheduledTestUpdate], List[str], Optional[str]]:
    applied: List[ScheduledTestUpdate] = []
    skipped_columns: List[str] = []
    skip_reason: Optional[str] = None

    for update in plan.updates:
        worksheet_data = update.qbench_test.raw.get("worksheet_data") if update.qbench_test.raw else None
        if update.kind == "CN":
            payload = _build_cannabinoid_payload(update.samples[0])
            if not payload:
                skipped_columns.extend(update.column_headers)
                continue
            if respect_existing_data and not _worksheet_fields_are_empty(worksheet_data, payload.keys()):
                skipped_columns.extend(update.column_headers)
                if skip_reason is None:
                    skip_reason = "Los tests seleccionados ya contienen datos en QBench."
                continue
            if not dry_run:
                _send_worksheet_update(qbench, update.qbench_test.raw, payload)
            applied.append(update)
        else:
            payload = _build_homogeneity_payload_for_indices(update.samples, update.indices)
            if not payload:
                skipped_columns.extend(update.column_headers)
                continue
            if respect_existing_data and not _worksheet_fields_are_empty(worksheet_data, payload.keys()):
                skipped_columns.extend(update.column_headers)
                if skip_reason is None:
                    skip_reason = "Los tests seleccionados ya contienen datos en QBench."
                continue
            if not dry_run:
                _send_worksheet_update(qbench, update.qbench_test.raw, payload)
            applied.append(update)

    return applied, skipped_columns, skip_reason


# -----------------------------------------------------------------------------
# NOTE: Sends the worksheet PATCH request to QBench and logs failures so that the
#       caller can surface the error to the UI.
def _send_worksheet_update(qbench: QBenchClient, qbench_test: Dict[str, object], data: Dict[str, str]) -> None:
    test_id = qbench_test.get("id")
    try:
        qbench.update_test_worksheet(test_id, data=data)
    except httpx.HTTPStatusError as exc:
        response = exc.response
        status = response.status_code if response is not None else None
        body = response.text if response is not None else ""
        if status == httpx.codes.BAD_REQUEST:
            LOGGER.warning(
                "QBench devolvio 400 al actualizar worksheet para test %s; se continua. Detalle: %s",
                test_id,
                body[:500],
            )
            return
        LOGGER.exception(
            "Error HTTP al actualizar worksheet para test %s (status=%s, body=%s)",
            test_id,
            status,
            body[:500],
        )
        raise
    except httpx.HTTPError:
        LOGGER.exception("Error de red al actualizar worksheet para test %s", test_id)
        raise


# -----------------------------------------------------------------------------
# NOTE: Translates a SampleQuantification into the dictionary expected by a CN
#       worksheet, covering metadata, components, and area results.
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


# -----------------------------------------------------------------------------
# NOTE: Assembles the HO worksheet payload only for the indices that will be updated,
#       enabling partial corrections when a subset of injections must be rewritten.
def _build_homogeneity_payload_for_indices(
    samples: List[SampleQuantification],
    indices: List[int],
) -> Dict[str, str]:
    payload: Dict[str, str] = {}
    for sample, index in zip(samples, indices):
        _populate_homogeneity_fields(payload, sample, index)
    return payload


# -----------------------------------------------------------------------------
# NOTE: Adds the per-index HO fields (mass, dilution, components) into the payload
#       using the formatted naming convention expected by QBench.
def _populate_homogeneity_fields(
    payload: Dict[str, str],
    sample: SampleQuantification,
    index: int,
) -> None:
    if sample.sample_mass_mg is not None:
        payload[f"sample_mass_{index}"] = _format_number(sample.sample_mass_mg)
    if sample.dilution is not None:
        payload[f"dilution_{index}"] = _format_number(sample.dilution)
    for component in COMPONENT_ORDER:
        value = sample.components.get(component)
        if value is None:
            continue
        payload[f"{component}_{index}"] = _format_number(value)


# -----------------------------------------------------------------------------
# NOTE: Formats numeric values in a stable way, trimming trailing zeros and decimal
#       points so the worksheet payload matches QBench expectations.
def _format_number(value: float) -> str:
    text = f"{value:.6f}"
    return text.rstrip("0").rstrip(".")
