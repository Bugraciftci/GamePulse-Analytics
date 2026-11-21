from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from .analytics import (
    analyze_ab_test,
    compute_cohort_retention,
    compute_funnel_report,
    compute_ltv_summary,
)
from .generator import seed_synthetic_dataset
from .segmentation import compute_rfm_segmentation
from .storage import AnalyticsStore


def create_app(db_path: str = ":memory:", auto_seed: bool = True) -> FastAPI:
    app = FastAPI(
        title="GamePulse-Analytics API",
        version="1.0.0",
        description="Mobile game & consumer app cohort retention, LTV/ROAS, funnel, and A/B testing engine.",
    )
    store = AnalyticsStore(db_path=db_path)
    if auto_seed:
        seed_synthetic_dataset(store, player_count=1200, cohort_days=7, seed=42)

    app.state.store = store

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "gamepulse-analytics"}

    @app.get("/api/retention")
    def get_retention(channel: str | None = Query(default=None)) -> list[dict[str, Any]]:
        return [asdict(r) for r in compute_cohort_retention(store, channel=channel)]

    @app.get("/api/monetization")
    def get_monetization(channel: str | None = Query(default=None)) -> dict[str, Any]:
        return asdict(compute_ltv_summary(store, channel=channel))

    @app.get("/api/funnel")
    def get_funnel() -> dict[str, Any]:
        return asdict(compute_funnel_report(store))

    @app.get("/api/segmentation")
    def get_segmentation() -> dict[str, Any]:
        return asdict(compute_rfm_segmentation(store))

    @app.get("/api/experiments/paywall")
    def get_paywall_experiment() -> dict[str, Any]:
        rows = store.connection.execute(
            """
            SELECT
                p.experiment_group,
                COUNT(DISTINCT p.player_id) AS users,
                COUNT(DISTINCT CASE WHEN l.step_name = 'first_purchase' THEN p.player_id END) AS buyers
            FROM players p
            LEFT JOIN level_events l ON l.player_id = p.player_id
            GROUP BY p.experiment_group
            """
        ).fetchall()
        stats = {r["experiment_group"]: (int(r["users"]), int(r["buyers"])) for r in rows}
        c_u, c_b = stats.get("control", (1, 0))
        t_u, t_b = stats.get("treatment", (1, 0))
        result = analyze_ab_test("paywall_trial_timeline_v2", c_u, c_b, t_u, t_b)
        return asdict(result)

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        ltv = compute_ltv_summary(store)
        cohorts = compute_cohort_retention(store)
        funnel = compute_funnel_report(store)
        exp = get_paywall_experiment()

        cohort_rows = "".join(
            f"<tr><td>{c.install_date}</td><td>{c.cohort_size}</td>"
            f"<td>{c.d1_pct}%</td><td>{c.d3_pct}%</td><td>{c.d7_pct}%</td>"
            f"<td>{c.d14_pct}%</td><td>{c.d30_pct}%</td></tr>"
            for c in cohorts
        )
        funnel_rows = "".join(
            f"<tr><td>{s.step_order}. {s.step_name}</td><td>{s.users}</td>"
            f"<td>{s.conversion_from_start_pct}%</td><td>{s.step_conversion_pct}%</td>"
            f"<td>{s.drop_off_pct}%</td></tr>"
            for s in funnel.steps
        )
        verdict = "SIGNIFICANT WINNER" if exp["is_statistically_significant"] else "INCONCLUSIVE"
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>GamePulse Analytics Dashboard</title>
<style>
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#090814; color:#E2E8F0; padding:32px; }}
  .wrap {{ max-width:1080px; margin:0 auto; }}
  h1 {{ margin:0 0 6px; color:#F8FAFC; }}
  .sub {{ color:#94A3B8; margin-bottom:24px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; margin-bottom:24px; }}
  .card {{ background:#14112B; border:1px solid #2A2452; border-radius:14px; padding:16px; }}
  .lbl {{ font-size:11px; color:#A5B4FC; text-transform:uppercase; letter-spacing:0.8px; }}
  .val {{ font-size:26px; font-weight:800; color:#F472B6; margin-top:6px; }}
  table {{ width:100%; border-collapse:collapse; background:#14112B; border:1px solid #2A2452; border-radius:12px; overflow:hidden; margin-bottom:24px; }}
  th, td {{ padding:10px 14px; text-align:left; border-bottom:1px solid #2A2452; font-size:13.5px; }}
  th {{ background:#1C173B; color:#C4B5FD; font-size:12px; text-transform:uppercase; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>GamePulse Product Analytics</h1>
  <div class="sub">Live SQLite Telemetry • Cohort Retention • LTV/ROAS • A/B Z-Test Engine</div>
  <div class="grid">
    <div class="card"><div class="lbl">Players</div><div class="val">{ltv.total_players:,}</div></div>
    <div class="card"><div class="lbl">Total Revenue</div><div class="val">${ltv.total_revenue_usd:,.2f}</div></div>
    <div class="card"><div class="lbl">ARPU / ARPPU</div><div class="val">${ltv.arpu_usd:.2f} / ${ltv.arppu_usd:.2f}</div></div>
    <div class="card"><div class="lbl">ROAS</div><div class="val">{ltv.roas_pct:.1f}%</div></div>
    <div class="card"><div class="lbl">A/B Uplift ({verdict})</div><div class="val">{exp['relative_uplift_pct']:+.1f}%</div></div>
  </div>
  <h2>Cohort Retention Matrix</h2>
  <table><thead><tr><th>Install Date</th><th>Size</th><th>D1</th><th>D3</th><th>D7</th><th>D14</th><th>D30</th></tr></thead><tbody>{cohort_rows}</tbody></table>
  <h2>Onboarding &amp; Progression Funnel (Bottleneck: {funnel.biggest_bottleneck_step})</h2>
  <table><thead><tr><th>Step</th><th>Users</th><th>Cumulative</th><th>Step Conv.</th><th>Drop-Off</th></tr></thead><tbody>{funnel_rows}</tbody></table>
</div>
</body>
</html>"""

    return app


app = create_app()
