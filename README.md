# When does net-zero CO2 happen in IPCC AR6 scenarios?

A small, reproducible Python example that works with the public
[IPCC AR6 Scenario Database](https://data.ece.iiasa.ac.at/ar6/) (hosted by IIASA).

For every scenario in the 1.5°C and 2°C categories (C1, C2, C3) it finds the year in which
global net CO2 emissions first reach zero, summarises the timing per category and draws two figures.

| Category | Meaning |
|----------|---------|
| C1 | Limit warming to 1.5°C (>50% chance) with no or limited overshoot |
| C2 | Return warming to 1.5°C (>50%) after a high overshoot |
| C3 | Limit warming to 2°C (>67% chance) |

I wrote it as a first look at how integrated assessment scenarios are structured, with
the question of residual emissions in mind.

## Quick start

```bash
pip install -r requirements.txt
python ar6_netzero.py            # downloads the public AR6 data and writes outputs/
python ar6_netzero.py --demo     # synthetic data, no internet needed
python -m unittest -v            # tests for the analysis logic
```

## Outputs (in `outputs/`)

| File | Content |
|---|---|
| `net_co2_pathways.png` | Net CO2 pathways, thin lines per scenario, thick line the median per category |
| `net_zero_timing.png` | Spread of net-zero years per category |
| `net_zero_years.csv` | Net-zero year for each scenario |
| `summary.csv` | Scenario counts, median and quartiles per category |

Runs with `--demo` write files with a `demo_` prefix and a "synthetic demo data" label on the figures.
They are for testing only and are not AR6 results.

## Method

- Variable `Emissions|CO2`, region `World`, loaded with `pyam.read_iiasa("ar6-public")`.
- Categories C1, C2, C3 come from the database's `Category` meta indicator.
- The net-zero year is the first time step with emissions at or below zero, linearly interpolated
  between the two surrounding time steps. Scenarios that never reach zero are counted but have no year.
- Values are converted from Mt CO2/yr to Gt CO2/yr.

## Limits

- Net CO2 only. Gross and residual emissions are not covered.
- Linear interpolation between model time steps (mostly 5 or 10 years) is a simplification.
- Scenarios from different models are treated equally, with no weighting for model or scenario family.

## Possible next steps

- Add the other categories and compare with the reported `Year of netzero CO2 emissions` meta indicators.
- Look at carbon dioxide removal variables and what they imply for residual emissions.
- Break results down by model family.
