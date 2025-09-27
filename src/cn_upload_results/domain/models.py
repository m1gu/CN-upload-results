"""Domain models shared across the application."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional


COMPONENT_ORDER = [
    "cbdva",
    "cbdv",
    "cbda",
    "cbga",
    "cbg",
    "cbd",
    "thcv",
    "thcva",
    "cbcv",
    "cbn",
    "d9_thc",
    "d8_thc",
    "cbl",
    "thca",
    "cbc",
    "cbca",
    "cbla",
    "cbt",
]

AREA_RESULT_SUFFIX = "_area_result"


@dataclass(slots=True)
class RunMetadata:
    """Details about the analytical run represented by an Excel workbook."""

    run_date: date
    batch_numbers: List[str]
    batch_sample_map: Dict[str, List[str]]
    source_filename: str


@dataclass(slots=True)
class SampleQuantification:
    """Quantitative results for a specific test of a sample."""

    sample_id: str
    base_sample_id: str
    test_index: int
    column_header: str
    components: Dict[str, Optional[float]]
    area_results: Dict[str, Optional[float]]
    sample_mass_mg: Optional[float]
    dilution: Optional[float]
    serving_mass_g: Optional[float]
    servings_per_package: Optional[float]
    batch_numbers: List[str] = field(default_factory=list)

    def suffixed_components(self) -> Dict[str, Optional[float]]:
        """Return component values keyed with the test index suffix."""

        return {
            f"{component}_{self.test_index}": value
            for component, value in self.components.items()
        }

    def suffixed_metadata(self) -> Dict[str, Optional[float]]:
        """Return sample-level metadata keyed with the test index suffix."""

        return {
            f"sample_mass_{self.test_index}": self.sample_mass_mg,
            f"dilution_{self.test_index}": self.dilution,
            f"serving_mass_g_{self.test_index}": self.serving_mass_g,
            f"servings_per_package_{self.test_index}": self.servings_per_package,
        }

    def suffixed_area_results(self) -> Dict[str, Optional[float]]:
        """Return area results keyed with the test index suffix."""

        return {
            f"{component}{AREA_RESULT_SUFFIX}_{self.test_index}": value
            for component, value in self.area_results.items()
        }


@dataclass(slots=True)
class WorkbookExtraction:
    """Container for parsed workbook data."""

    metadata: RunMetadata
    samples: List[SampleQuantification]
