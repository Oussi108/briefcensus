# NetPick protocol v1

Fixed on 4 November 2026, before any net-only selection result exists. Anything that changes after this file is hashed
goes in `RUN_LOG.md` with its reason and date.

## Question

Can a grid operator choose which k rooftop PV systems to meter using only net-meter data, so that those k systems
estimate and forecast the whole fleet's PV output nearly as well as systems chosen with a full census of gross PV?

## Why net-only is the claim

Choosing reference stations from gross PV already exists: clustering, mRMR, maximum difference and VECM methods all assume
output data from the candidate stations, and upscaling studies already report error against the number of references.
Selection from net data is the part not found so far. The census arm in this protocol is a reference, not a contribution.

## Data

Ausgrid Solar Home, 300 gross-metered homes, 30 min, read from `paper3/data_external/ausgrid/extracted/` and never written.

- Y1 = July 2010 to June 2011. Y2 = July 2011 to June 2012. Y3 = July 2012 to June 2013.
- Net load is built as GC + CL - GG, so it is constructed, not observed, and the paper must say so.
- A missing CL row counts as 0 for a home with no CL channel, and as missing for a home with one.
- Rows flagged NA under Row Quality count as missing. All 300 homes stay in. Nothing is removed for looking odd, because
  a failing monitor is a real risk that the study should see.
- Allowed without a census: net load, capacity, postcode. Gross PV of a home may be used only after that home is chosen.

## Splits

| Use | Selection data | Scored on | Status |
|---|---|---|---|
| Development and kill test | Y1 | Y2 | Open |
| Hold-out | Y1 + Y2 | Y3 | Read once, after the method is fixed |

The feasibility pilot of 3 November read Y3 of gross PV for random, greedy, medoid and largest-capacity selection, so Y3 is
not blind for those arms. It has never been used for any net-only arm. The paper must disclose this. UK PV is the untouched
confirmation for selectors that do not need net load.

## Evaluation group

Five fixed partitions with seeds 11, 23, 37, 51 and 73. Each holds out 100 random homes that can never be selected, and leaves
200 candidates. The target stays the same for every selector and budget, which fixes the moving target in the pilot.

## Target and score

- Target: the evaluation group's fleet ratio, the sum of its GG power over the sum of its capacity, in kW per kWp.
- Sensitivity: the equal-weighted mean of home ratios.
- Daylight rows: solar elevation above 5 degrees at Sydney (33.87 S, 151.21 E), so the mask does not depend on the target.
- Score: RMSE as a percentage of the mean daylight target (nRMSE). Mean bias is reported beside it.

## Estimators

- Primary, needing no census: the chosen homes' capacity-weighted ratio with no fitted weights.
- Census reference only: OLS weights fitted on the fleet's gross PV, which no net-only operator has. It is reported as a bound.

**Correction to the plan in the topic report.** The report's kill thresholds came from a table using OLS weights. Those weights
need the fleet's gross PV, so a net-only operator cannot fit them, and the comparison would not be like with like. The test
below scores every arm with the primary estimator.

## Budgets and selectors

Budgets: k = 1, 2, 3, 5, 10, 20, 50. The kill test uses k = 5, 10, 20.

Kill-test arms:

- **Random:** 40 draws per partition, using the median.
- **Census greedy:** greedy search that minimises the RMSE between the chosen homes' ratio and the ratio of all 300 homes, on
  gross PV in the selection data.
- **Net-only N1:** the same greedy search on a PV signal built from net load.
- **Net-only N2:** the same greedy search on each home's signal averaged by month and half-hour slot, which reduces load noise.

The PV signal for a home is a baseline minus its net load, in kW per kWp and floored at 0. The baseline is the 90th percentile of
that home's net load in the same half-hour slot over the 29 days centred on that day. The idea is that the least sunny days
in a month show the load with little PV behind it.

Later arms (day 3): largest capacity, medoids, Zhu-style maximum difference, mRMR, greedy mutual information on a Gaussian
process, and metadata only.

## Kill test

Run on the development split only. For each k in 5, 10, 20, averaged over the five partitions:

R_k = (E_random - E_net) / (E_random - E_census)

- **Pass:** for the better of N1 and N2, median R_k is at least 0.5.
- **No gain to recover:** if census greedy does not beat the random median at k = 5, 10, 20, selection itself is not worth a
  paper on this fleet, and the plan moves to the fallback.
- **Fail:** move to the census-length question (4 weeks, 3 months, 1 year). If that shows no clear gain either, move to LeadLock.

Trying two variants and keeping the better one flatters the result, so the kill test only decides whether to continue. The
reported result is the hold-out, with the variant fixed in `RUN_LOG.md` before Y3 is read.

## Forecast arm (outline, fixed before day 5)

Horizons 0.5 and 1 h are primary. 2, 3 and 6 h are reported only to show how the gain decays. Training may use only the chosen
monitors' upscaled series, and scoring uses the true evaluation group. Baselines: fleet persistence from monitors, an all-homes
reference, and a zero-monitor weather model using retrospective weather, which flatters that baseline and must be stated.

## Rules

- Compute: laptop first. Kaggle runs carry a time limit, stay private and stop themselves when they end or fail.
- Do not read PVDAQ 2107 or 9068 values from 2022 onward for this paper until Paper 1 is scored.
- Do not edit `paper1/`, `paper2`, `paper3/` or `paper4/`.
- Git commits only when the user asks, authored by the user only.
