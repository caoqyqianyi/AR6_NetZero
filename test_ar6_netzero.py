"""Tests for the analysis logic. They use synthetic data only (no internet needed)."""

import math
import tempfile
import unittest
from pathlib import Path

import pandas as pd

import ar6_netzero as nz


class CrossingYearTests(unittest.TestCase):
    def test_interpolates_between_time_steps(self):
        # +10 in 2040, -10 in 2050 -> crosses zero halfway, in 2045
        self.assertAlmostEqual(nz.crossing_year([2040, 2050], [10, -10]), 2045.0)

    def test_unequal_values_interpolate_proportionally(self):
        # +30 -> -10 over 2040..2050: zero at 2040 + 10 * 30/40 = 2047.5
        self.assertAlmostEqual(nz.crossing_year([2040, 2050], [30, -10]), 2047.5)

    def test_exactly_zero_counts_as_net_zero(self):
        self.assertAlmostEqual(nz.crossing_year([2040, 2050, 2060], [20, 0, -5]), 2050.0)

    def test_never_reaching_zero_gives_nan(self):
        self.assertTrue(math.isnan(nz.crossing_year([2020, 2050, 2100], [40, 30, 20])))

    def test_already_negative_returns_first_year(self):
        self.assertEqual(nz.crossing_year([2020, 2030], [-1, -2]), 2020.0)

    def test_unsorted_input_is_handled(self):
        self.assertAlmostEqual(nz.crossing_year([2050, 2040], [-10, 10]), 2045.0)


class PrepareTests(unittest.TestCase):
    def test_keeps_only_known_categories_and_converts_units(self):
        raw = pd.DataFrame(
            {
                "model": ["M"] * 3,
                "scenario": ["a", "b", "c"],
                "year": [2050, 2050, 2050],
                "value": [-2000.0, 1000.0, 500.0],  # Mt CO2/yr
                "category": ["C1: limited overshoot", "C8: above 4C", "C3: likely 2C"],
            }
        )
        out = nz.prepare(raw)
        self.assertEqual(sorted(out["category"]), ["C1", "C3"])
        self.assertAlmostEqual(out.loc[out["category"] == "C1", "value_gt"].iloc[0], -2.0)


class SummaryTests(unittest.TestCase):
    def test_summary_counts_and_median(self):
        table = pd.DataFrame(
            {
                "model": ["M"] * 4,
                "scenario": ["a", "b", "c", "d"],
                "category": ["C1", "C1", "C1", "C2"],
                "net_zero_year": [2050.0, 2060.0, float("nan"), 2070.0],
            }
        )
        summary = nz.summarise(table).set_index("category")
        self.assertEqual(summary.loc["C1", "scenarios"], 3)
        self.assertEqual(summary.loc["C1", "reaching_net_zero"], 2)
        self.assertAlmostEqual(summary.loc["C1", "median_year"], 2055.0)
        self.assertEqual(summary.loc["C3", "scenarios"], 0)


class EndToEndDemoTests(unittest.TestCase):
    def test_demo_run_writes_all_outputs_and_is_ordered_sensibly(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = nz.run(demo=True, out_dir=Path(tmp))
            for name in [
                "demo_summary.csv",
                "demo_net_zero_years.csv",
                "demo_net_co2_pathways.png",
                "demo_net_zero_timing.png",
            ]:
                self.assertTrue((Path(tmp) / name).exists(), name)
        medians = summary.set_index("category")["median_year"]
        # Stricter temperature goals should reach net zero earlier in the demo data
        self.assertLess(medians["C1"], medians["C2"])
        self.assertLess(medians["C2"], medians["C3"])


if __name__ == "__main__":
    unittest.main()
