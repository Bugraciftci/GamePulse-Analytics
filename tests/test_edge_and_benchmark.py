import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from gamepulse import (
    AnalyticsStore,
    PlayerProfile,
    analyze_ab_test,
    compute_cohort_retention,
    compute_funnel_report,
    compute_ltv_summary,
    compute_rfm_segmentation,
    seed_synthetic_dataset,
)


class TestEdgeCasesAndBenchmarks(unittest.TestCase):
    def test_empty_store_returns_zeroed_reports(self):
        store = AnalyticsStore(":memory:")
        self.assertEqual(compute_cohort_retention(store), [])
        ltv = compute_ltv_summary(store)
        self.assertEqual(ltv.total_players, 0)
        self.assertEqual(ltv.roas_pct, 0.0)
        self.assertIsNone(ltv.estimated_payback_days)

        funnel = compute_funnel_report(store)
        self.assertEqual(funnel.steps, ())
        self.assertIsNone(funnel.biggest_bottleneck_step)

        rfm = compute_rfm_segmentation(store)
        self.assertEqual(rfm.segments, ())
        self.assertEqual(rfm.gini_revenue_coefficient, 0.0)
        store.close()

    def test_ab_test_validation_and_zero_control_conversions(self):
        with self.assertRaises(ValueError):
            analyze_ab_test("invalid", 0, 0, 100, 10)

        res = analyze_ab_test("cold_start", 500, 0, 500, 25)
        self.assertEqual(res.control_rate, 0.0)
        self.assertEqual(res.relative_uplift_pct, 0.0)
        self.assertFalse(res.srm_warning)
        self.assertTrue(res.is_statistically_significant)

    def test_sqlite_cohort_and_rfm_query_benchmark(self):
        store = AnalyticsStore(":memory:")
        seed_synthetic_dataset(store, player_count=2000, cohort_days=14, seed=99)

        start = time.perf_counter()
        cohorts = compute_cohort_retention(store)
        rfm = compute_rfm_segmentation(store)
        ltv = compute_ltv_summary(store)
        funnel = compute_funnel_report(store)
        elapsed = time.perf_counter() - start

        self.assertGreaterEqual(len(cohorts), 1)
        self.assertGreater(ltv.total_players, 0)
        self.assertGreater(len(funnel.steps), 0)
        self.assertGreaterEqual(rfm.gini_revenue_coefficient, 0.0)
        self.assertLess(elapsed, 1.5, f"Full analytical pass over 2k players took {elapsed:.3f}s")
        store.close()


if __name__ == "__main__":
    unittest.main()
