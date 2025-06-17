"""CTTI entity definitions."""

from typing import Any, Dict, List

from pydantic import Field

from airweave.platform.entities._base import Breadcrumb, WebEntity


class CTTIWebEntity(WebEntity):
    """Web entity for CTTI clinical trials.

    Represents a clinical trial study from ClinicalTrials.gov with an NCT ID.
        "WebFileEntity",
        "WebFileEntity",
    This entity will be processed by the web_fetcher transformer to download
    the actual clinical trial content from ClinicalTrials.gov.
    """

    # CTTI-specific fields
    nct_id: str = Field(..., description="The NCT ID of the clinical trial study")
    study_url: str = Field(
        ..., description="The full URL to the clinical trial study on ClinicalTrials.gov"
    )
    data_source: str = Field(
        default="ClinicalTrials.gov", description="The source of the clinical trial data"
    )

    # Override metadata with proper typing
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about the clinical trial"
    )

    # Ensure breadcrumbs is properly typed
    breadcrumbs: List[Breadcrumb] = Field(
        default_factory=list, description="List of breadcrumbs for this clinical trial entity"
    )
