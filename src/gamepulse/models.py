from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerProfile:
    player_id: str
    install_date: str  # YYYY-MM-DD
    channel: str       # e.g. "apple_search_ads", "meta_ua", "organic"
    country: str       # e.g. "US", "TR", "DE"
    experiment_group: str = "control"  # "control" | "treatment"
    cpi_usd: float = 0.0


@dataclass(frozen=True)
class SessionEvent:
    event_id: str
    player_id: str
    session_date: str  # YYYY-MM-DD
    duration_sec: int


@dataclass(frozen=True)
class RevenueEvent:
    event_id: str
    player_id: str
    event_date: str  # YYYY-MM-DD
    source: str      # "iap" | "subscription" | "ad_rewarded"
    amount_usd: float


@dataclass(frozen=True)
class LevelEvent:
    event_id: str
    player_id: str
    step_name: str   # e.g. "install", "tutorial_complete", "level_1", "level_5", "first_purchase"
    step_order: int
    event_date: str


@dataclass(frozen=True)
class CohortRetentionRow:
    install_date: str
    cohort_size: int
    d1_pct: float
    d3_pct: float
    d7_pct: float
    d14_pct: float
    d30_pct: float


@dataclass(frozen=True)
class LTVSummary:
    segment: str
    total_players: int
    paying_players: int
    payer_conversion_pct: float
    total_revenue_usd: float
    arpu_usd: float
    arppu_usd: float
    arpdau_usd: float
    average_cpi_usd: float
    roas_pct: float
    estimated_payback_days: float | None


@dataclass(frozen=True)
class FunnelStepMetric:
    step_name: str
    step_order: int
    users: int
    conversion_from_start_pct: float
    step_conversion_pct: float
    drop_off_pct: float


@dataclass(frozen=True)
class FunnelReport:
    steps: tuple[FunnelStepMetric, ...]
    biggest_bottleneck_step: str | None
    biggest_drop_off_pct: float


@dataclass(frozen=True)
class ABTestResult:
    experiment_name: str
    control_users: int
    control_conversions: int
    control_rate: float
    treatment_users: int
    treatment_conversions: int
    treatment_rate: float
    relative_uplift_pct: float
    z_score: float
    p_value: float
    ci95_low_pct: float
    ci95_high_pct: float
    is_statistically_significant: bool
    srm_chi_square: float
    srm_warning: bool
