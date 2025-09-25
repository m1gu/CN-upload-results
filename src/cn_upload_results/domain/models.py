"""Domain models shared across the application."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional


COMPONENT_ORDER = [
    "CBDVA",
    "CBDV",
    "CBDA",
    "CBGA",
    "CBG",
    "CBD",
    "THCV",
    "THCVA",
    "CBCV",
    "CBN",
    "D9-THC",
    "D8-THC",
    "CBL",
    "THCA",
    "CBC",
    "CBCA",
    "CBLA",
    "CBT",
]



@dataclass(slots=True)
class RunMetadata:
    """Details about the analytical run represented by an Excel workbook."""

    run_date: date
    batch_numbers: List[str]
    source_filename: str



@dataclass(slots=True)
class SampleQuantification:
    """Quantitative results for a single sample."""

    sample_id: str
    components: Dict[str, float]
    sample_mass_mg: Optional[float]
    dilution: Optional[float]
    serving_mass_g: Optional[float]
    servings_per_package: Optional[float]
    batch_numbers: List[str] = field(default_factory=list)



@dataclass(slots=True)
class WorkbookExtraction:
    """Container for parsed workbook data."""

    metadata: RunMetadata
    samples: List[SampleQuantification]
