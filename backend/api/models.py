"""Response models (so the OpenAPI schema, and openapi-typescript, carry real types for /api/lakes)."""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class LakeSummary(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    alias: Optional[str] = None
    name: Optional[str] = None
    country: Optional[str] = None
    centre: Optional[list[float]] = None
    group: Literal["turkey", "reference", "custom"]
    validated: bool
    unverified: bool
    years: Optional[list[int]] = None
    latest_area_km2: Optional[float] = None
    latest_area_year: Optional[int] = None
    ref_mean_km2: Optional[float] = None
    ref_years: list[int] = []
    recent_years: list[int] = []
    recent_mean_km2: Optional[float] = None
    total_loss_pct: Optional[float] = None
    total_loss_basis: str
    trend_pct_per_decade: Optional[float] = None
    trend_p: Optional[float] = None
    trend_direction: Optional[str] = None
    emergence_year: Optional[int] = None
    emergence_status: Optional[str] = None
    emergence_censored_at_ref_end: bool = False
    emergence_note: Optional[str] = None
    warming_c_per_decade: Optional[float] = None
    warming_basis: Optional[str] = None
    warming_pooled_c_per_decade: Optional[float] = None
    warming_sensor_break_caveat: str
    climate_explained_share: Optional[float] = None
    climate_explained_ci90: Optional[list[float]] = None
    climate_interpretable: bool = False
    climate_ci_includes_zero: bool = False
    climate_flags: list[str] = []
    climate_wording: Optional[str] = None
    reliability: str
    reliability_note: Optional[str] = None
    status: Optional[str] = None
    why_selected: Optional[str] = None
    mndwi_note: Optional[str] = None
    resolution_m: Optional[int] = None
    cadence_note: Optional[str] = None
    cadence_years: Optional[int] = None
    years_analysed: Optional[list[int]] = None
    window: Optional[list[str]] = None
    literature_direction: Optional[str] = None
    our_direction: Optional[str] = None
    literature_agrees: Optional[bool] = None
    literature_agreement: Optional[str] = None
    validation_basis: Optional[str] = None


class LakesResponse(BaseModel):
    lakes: list[LakeSummary]
