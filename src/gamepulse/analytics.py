from __future__ import annotations

import math

from .models import (
    ABTestResult,
    CohortRetentionRow,
    FunnelReport,
    FunnelStepMetric,
    LTVSummary,
)
from .storage import AnalyticsStore


def compute_cohort_retention(
    store: AnalyticsStore,
    channel: str | None = None,
) -> list[CohortRetentionRow]:
    """Computes D1/D3/D7/D14/D30 cohort retention percentages using pure SQLite date math."""
    where_clause = "WHERE p.channel = ?" if channel else ""
    params: tuple[str, ...] = (channel,) if channel else ()

    query = f"""
        WITH cohort_base AS (
            SELECT player_id, install_date
            FROM players p
            {where_clause}
        ),
        active_offsets AS (
            SELECT DISTINCT
                c.player_id,
                c.install_date,
                CAST(julianday(s.session_date) - julianday(c.install_date) AS INTEGER) AS day_offset
            FROM cohort_base c
            LEFT JOIN sessions s ON s.player_id = c.player_id
        )
        SELECT
            c.install_date,
            COUNT(DISTINCT c.player_id) AS cohort_size,
            COUNT(DISTINCT CASE WHEN a.day_offset = 1 THEN a.player_id END) AS d1_users,
            COUNT(DISTINCT CASE WHEN a.day_offset = 3 THEN a.player_id END) AS d3_users,
            COUNT(DISTINCT CASE WHEN a.day_offset = 7 THEN a.player_id END) AS d7_users,
            COUNT(DISTINCT CASE WHEN a.day_offset = 14 THEN a.player_id END) AS d14_users,
            COUNT(DISTINCT CASE WHEN a.day_offset = 30 THEN a.player_id END) AS d30_users
        FROM cohort_base c
        LEFT JOIN active_offsets a ON a.player_id = c.player_id
        GROUP BY c.install_date
        ORDER BY c.install_date ASC
    """

    rows = store.connection.execute(query, params).fetchall()
    result: list[CohortRetentionRow] = []
    for row in rows:
        size = int(row["cohort_size"]) or 1
        result.append(
            CohortRetentionRow(
                install_date=str(row["install_date"]),
                cohort_size=int(row["cohort_size"]),
                d1_pct=round((int(row["d1_users"]) / size) * 100.0, 2),
                d3_pct=round((int(row["d3_users"]) / size) * 100.0, 2),
                d7_pct=round((int(row["d7_users"]) / size) * 100.0, 2),
                d14_pct=round((int(row["d14_users"]) / size) * 100.0, 2),
                d30_pct=round((int(row["d30_users"]) / size) * 100.0, 2),
            )
        )
    return result


def compute_ltv_summary(
    store: AnalyticsStore,
    channel: str | None = None,
) -> LTVSummary:
    """Computes ARPU, ARPPU, ARPDAU, payer conversion, ROAS, and estimated CPI payback days."""
    where_clause = "WHERE channel = ?" if channel else ""
    params: tuple[str, ...] = (channel,) if channel else ()

    player_stats = store.connection.execute(
        f"""
        SELECT COUNT(*) AS total_players, COALESCE(AVG(cpi_usd), 0.0) AS avg_cpi
        FROM players
        {where_clause}
        """,
        params,
    ).fetchone()

    total_players = int(player_stats["total_players"])
    avg_cpi = float(player_stats["avg_cpi"])

    rev_stats = store.connection.execute(
        f"""
        SELECT
            COUNT(DISTINCT r.player_id) AS paying_players,
            COALESCE(SUM(r.amount_usd), 0.0) AS total_revenue
        FROM revenue_events r
        JOIN players p ON p.player_id = r.player_id
        {("WHERE p.channel = ?" if channel else "")}
        """,
        params,
    ).fetchone()

    dau_stats = store.connection.execute(
        f"""
        SELECT COUNT(*) AS total_dau_days
        FROM (
            SELECT DISTINCT s.player_id, s.session_date
            FROM sessions s
            JOIN players p ON p.player_id = s.player_id
            {("WHERE p.channel = ?" if channel else "")}
        )
        """,
        params,
    ).fetchone()

    paying_players = int(rev_stats["paying_players"])
    total_revenue = float(rev_stats["total_revenue"])
    total_dau_days = int(dau_stats["total_dau_days"])

    payer_conv = (paying_players / total_players * 100.0) if total_players else 0.0
    arpu = (total_revenue / total_players) if total_players else 0.0
    arppu = (total_revenue / paying_players) if paying_players else 0.0
    arpdau = (total_revenue / total_dau_days) if total_dau_days else 0.0
    total_spend = avg_cpi * total_players
    roas_pct = (total_revenue / total_spend * 100.0) if total_spend > 0 else 0.0
    payback_days = round(avg_cpi / arpdau, 1) if (avg_cpi > 0 and arpdau > 0) else None

    return LTVSummary(
        segment=channel or "all_channels",
        total_players=total_players,
        paying_players=paying_players,
        payer_conversion_pct=round(payer_conv, 2),
        total_revenue_usd=round(total_revenue, 2),
        arpu_usd=round(arpu, 4),
        arppu_usd=round(arppu, 2),
        arpdau_usd=round(arpdau, 4),
        average_cpi_usd=round(avg_cpi, 2),
        roas_pct=round(roas_pct, 2),
        estimated_payback_days=payback_days,
    )


def compute_funnel_report(store: AnalyticsStore) -> FunnelReport:
    """Calculates step-by-step onboarding/level conversion rates and flags the steepest drop-off."""
    rows = store.connection.execute(
        """
        SELECT step_name, step_order, COUNT(DISTINCT player_id) AS users
        FROM level_events
        GROUP BY step_name, step_order
        ORDER BY step_order ASC
        """
    ).fetchall()

    if not rows:
        return FunnelReport(steps=(), biggest_bottleneck_step=None, biggest_drop_off_pct=0.0)

    start_users = int(rows[0]["users"]) or 1
    prev_users = start_users
    steps: list[FunnelStepMetric] = []
    worst_step: str | None = None
    worst_drop = -1.0

    for idx, row in enumerate(rows):
        users = int(row["users"])
        from_start = (users / start_users) * 100.0
        step_conv = 100.0 if idx == 0 else ((users / prev_users) * 100.0 if prev_users else 0.0)
        drop_off = 0.0 if idx == 0 else max(0.0, 100.0 - step_conv)

        if idx > 0 and drop_off > worst_drop:
            worst_drop = drop_off
            worst_step = str(row["step_name"])

        steps.append(
            FunnelStepMetric(
                step_name=str(row["step_name"]),
                step_order=int(row["step_order"]),
                users=users,
                conversion_from_start_pct=round(from_start, 2),
                step_conversion_pct=round(step_conv, 2),
                drop_off_pct=round(drop_off, 2),
            )
        )
        prev_users = users

    return FunnelReport(
        steps=tuple(steps),
        biggest_bottleneck_step=worst_step,
        biggest_drop_off_pct=round(max(worst_drop, 0.0), 2),
    )


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def analyze_ab_test(
    experiment_name: str,
    control_users: int,
    control_conversions: int,
    treatment_users: int,
    treatment_conversions: int,
    expected_treatment_ratio: float = 0.5,
    alpha: float = 0.05,
) -> ABTestResult:
    """
    Frequentist two-proportion Z-test with 95% Wald confidence interval and
    Chi-Square Sample Ratio Mismatch (SRM) integrity check — zero SciPy dependency.
    """
    if control_users <= 0 or treatment_users <= 0:
        raise ValueError("Both control_users and treatment_users must be positive.")

    p_ctrl = control_conversions / control_users
    p_treat = treatment_conversions / treatment_users
    diff = p_treat - p_ctrl
    uplift = ((p_treat - p_ctrl) / p_ctrl * 100.0) if p_ctrl > 0 else 0.0

    pooled_p = (control_conversions + treatment_conversions) / (control_users + treatment_users)
    pooled_se = math.sqrt(max(pooled_p * (1.0 - pooled_p) * (1.0 / control_users + 1.0 / treatment_users), 1e-12))
    z_score = diff / pooled_se
    p_value = 2.0 * (1.0 - _normal_cdf(abs(z_score)))

    unpooled_se = math.sqrt(
        max((p_ctrl * (1.0 - p_ctrl) / control_users) + (p_treat * (1.0 - p_treat) / treatment_users), 0.0)
    )
    margin = 1.959963984540054 * unpooled_se
    ci_low = (diff - margin) * 100.0
    ci_high = (diff + margin) * 100.0

    # Chi-Square Sample Ratio Mismatch (SRM) check (df=1, critical value at p=0.001 is 10.828)
    total_n = control_users + treatment_users
    expected_treat = total_n * expected_treatment_ratio
    expected_ctrl = total_n * (1.0 - expected_treatment_ratio)
    srm_chi_sq = ((control_users - expected_ctrl) ** 2 / max(expected_ctrl, 1e-9)) + (
        (treatment_users - expected_treat) ** 2 / max(expected_treat, 1e-9)
    )
    srm_warning = srm_chi_sq > 10.828

    return ABTestResult(
        experiment_name=experiment_name,
        control_users=control_users,
        control_conversions=control_conversions,
        control_rate=round(p_ctrl, 4),
        treatment_users=treatment_users,
        treatment_conversions=treatment_conversions,
        treatment_rate=round(p_treat, 4),
        relative_uplift_pct=round(uplift, 2),
        z_score=round(z_score, 4),
        p_value=round(p_value, 6),
        ci95_low_pct=round(ci_low, 2),
        ci95_high_pct=round(ci_high, 2),
        is_statistically_significant=(p_value < alpha and not srm_warning),
        srm_chi_square=round(srm_chi_sq, 4),
        srm_warning=srm_warning,
    )
