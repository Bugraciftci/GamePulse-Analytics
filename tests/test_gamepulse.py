import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from gamepulse import (
    AnalyticsStore,
    LevelEvent,
    PlayerProfile,
    RevenueEvent,
    SessionEvent,
    analyze_ab_test,
    compute_cohort_retention,
    compute_funnel_report,
    compute_ltv_summary,
    seed_synthetic_dataset,
)
from gamepulse.api import create_app


class TestGamePulseAnalytics(unittest.TestCase):
    def test_exact_sql_cohort_retention_math(self):
        store = AnalyticsStore(":memory:")
        store.insert_players([
            PlayerProfile("p1", "2026-10-01", "apple_search_ads", "US", "control", 2.0),
            PlayerProfile("p2", "2026-10-01", "apple_search_ads", "US", "control", 2.0),
            PlayerProfile("p3", "2026-10-01", "organic", "TR", "treatment", 0.0),
            PlayerProfile("p4", "2026-10-01", "organic", "TR", "treatment", 0.0),
        ])
        store.insert_sessions([
            SessionEvent("s1", "p1", "2026-10-01", 300),
            SessionEvent("s2", "p1", "2026-10-02", 300),  # D1
            SessionEvent("s3", "p1", "2026-10-08", 300),  # D7
            SessionEvent("s4", "p2", "2026-10-02", 300),  # D1
            SessionEvent("s5", "p3", "2026-10-04", 300),  # D3
        ])

        cohorts = compute_cohort_retention(store)
        self.assertEqual(len(cohorts), 1)
        row = cohorts[0]
        self.assertEqual(row.cohort_size, 4)
        self.assertEqual(row.d1_pct, 50.0)
        self.assertEqual(row.d3_pct, 25.0)
        self.assertEqual(row.d7_pct, 25.0)

        asa_only = compute_cohort_retention(store, channel="apple_search_ads")
        self.assertEqual(asa_only[0].cohort_size, 2)
        self.assertEqual(asa_only[0].d1_pct, 100.0)
        store.close()

    def test_ltv_arpu_arppu_roas_and_payback(self):
        store = AnalyticsStore(":memory:")
        store.insert_players([
            PlayerProfile("p1", "2026-10-01", "meta_ua", "US", "control", 2.0),
            PlayerProfile("p2", "2026-10-01", "meta_ua", "US", "control", 2.0),
        ])
        store.insert_sessions([
            SessionEvent("s1", "p1", "2026-10-01", 500),
            SessionEvent("s2", "p1", "2026-10-02", 500),
            SessionEvent("s3", "p2", "2026-10-01", 500),
            SessionEvent("s4", "p2", "2026-10-02", 500),
        ])
        store.insert_revenue([
            RevenueEvent("r1", "p1", "2026-10-01", "iap", 8.0),
        ])

        ltv = compute_ltv_summary(store, channel="meta_ua")
        self.assertEqual(ltv.total_players, 2)
        self.assertEqual(ltv.paying_players, 1)
        self.assertEqual(ltv.payer_conversion_pct, 50.0)
        self.assertEqual(ltv.arpu_usd, 4.0)
        self.assertEqual(ltv.arppu_usd, 8.0)
        self.assertEqual(ltv.arpdau_usd, 2.0)
        self.assertEqual(ltv.roas_pct, 200.0)
        self.assertEqual(ltv.estimated_payback_days, 1.0)
        store.close()

    def test_funnel_dropoff_and_bottleneck_detection(self):
        store = AnalyticsStore(":memory:")
        store.insert_players([PlayerProfile(f"p{i}", "2026-10-01", "organic", "US") for i in range(10)])
        events = []
        for i in range(10):
            events.append(LevelEvent(f"e1_{i}", f"p{i}", "install", 1, "2026-10-01"))
        for i in range(8):
            events.append(LevelEvent(f"e2_{i}", f"p{i}", "tutorial", 2, "2026-10-01"))
        for i in range(2):
            events.append(LevelEvent(f"e3_{i}", f"p{i}", "level_5", 3, "2026-10-01"))
        store.insert_level_events(events)

        funnel = compute_funnel_report(store)
        self.assertEqual(len(funnel.steps), 3)
        self.assertEqual(funnel.biggest_bottleneck_step, "level_5")
        self.assertEqual(funnel.biggest_drop_off_pct, 75.0)
        store.close()

    def test_ab_z_test_detects_significant_winner_and_srm_mismatch(self):
        sig = analyze_ab_test("paywall_v2", 1000, 100, 1000, 160)
        self.assertTrue(sig.is_statistically_significant)
        self.assertFalse(sig.srm_warning)
        self.assertAlmostEqual(sig.relative_uplift_pct, 60.0, places=1)
        self.assertLess(sig.p_value, 0.001)

        # Severe 70/30 traffic imbalance triggers SRM warning and invalidates significance
        srm = analyze_ab_test("broken_split", 1400, 140, 600, 120, expected_treatment_ratio=0.5)
        self.assertTrue(srm.srm_warning)
        self.assertFalse(srm.is_statistically_significant)

    def test_synthetic_generator_and_fastapi_routes(self):
        store = AnalyticsStore(":memory:")
        counts = seed_synthetic_dataset(store, player_count=400, cohort_days=5, seed=7)
        self.assertEqual(counts["players"], 400)
        self.assertGreater(counts["sessions"], 500)
        self.assertGreater(counts["level_events"], 800)
        store.close()

        # Verify FastAPI app routes cleanly
        app = create_app(db_path=":memory:", auto_seed=True)
        route_paths = {r.path for r in app.routes}
        self.assertIn("/health", route_paths)
        self.assertIn("/api/retention", route_paths)
        self.assertIn("/api/monetization", route_paths)
        self.assertIn("/api/funnel", route_paths)
        self.assertIn("/api/experiments/paywall", route_paths)


if __name__ == "__main__":
    unittest.main()
