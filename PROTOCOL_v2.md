# Short-census protocol v2

Fixed on 4 November 2026, before any UK PV generation value has been read. It replaces `PROTOCOL_v1.md` as the description of
the paper, and v1 stays unchanged as the record of what was tried first. Anything that changes after this file is hashed goes
in `RUN_LOG.md` with its reason and date. The user confirmed the change of main claim on 4 November.

## Question

How short and how small can a temporary gross-PV metering campaign be, and still choose k permanent monitors that estimate and
forecast a rooftop PV fleet in later years?

## Why this is the claim

Net-only selection failed its logged kill test on Ausgrid, with the best of five arms keeping 0.35 of the census gain against a
mark of 0.5. On the same development split, a 4-week census kept about 0.79 of the one-year gain and 3 months about 0.89. One
level factor on random homes kept about 0.10, so the gain is not just level. Three searches found no study that varies the length
of the data used to choose reference systems. That is weak evidence, and the literature check must be finished before writing.

## What must be disclosed

- All five net-only arms, the stop rule and the failed result, which is reported as a secondary finding.
- The clock error in Run 1 and its fix.
- Ausgrid Y3 is not blind for gross-PV selection, because the 3 November pilot read it for greedy, medoid, largest-capacity and
  random arms with a full census. It has not been read for any short window or net-only arm.
- The design came from Ausgrid Y1 and Y2, so Ausgrid cannot confirm it. UK PV is the confirmation.

## Data

**Ausgrid Solar Home.** As in v1. 300 gross-metered homes, 30 min, 2010 to 2013.

**UK PV.** `openclimatefix/uk_pv` (DOI 10.57967/hf/0878, CC-BY-4.0), 30-minute files, 2018 to 2021. Timestamps are UTC and mark the
end of each period. Power is `generation_Wh * 2 / (kWp * 1000)` in kW per kWp.

- Cleaning, the publisher's physical checks only: drop the periods in `bad_data.csv`, negative values, and values above 750 x kWp.
  Nothing else is removed, because a failing monitor is a real risk the study should see.
- Cohort, from `metadata.csv` only: 0 < kWp <= 10, first reading on or before 1 January 2018, last reading on or after 31 December
  2018. No condition is placed on later years, so systems may die after the campaign, as they would in practice.
- Regions: floor of latitude and longitude, one-degree cells. Every cell with at least 300 cohort systems is a region, each with a
  fixed random sample of 300 systems. The rule and the list use metadata only.
- Debug cell: the largest cell with 100 to 299 cohort systems. It is used to test code and is never reported as evidence. Confirmation
  regions are not read until the code is frozen and its hash is logged.
- National fleet, sensitivity only: a fixed sample of 1,000 cohort systems from all of Great Britain, with 333 held out.

## Splits

| Dataset | Campaign | Scored on | Status |
|---|---|---|---|
| Ausgrid, development | Windows of Y1 | Y2 | Open, used to design this protocol |
| Ausgrid, hold-out | Windows of Y1 and Y2 | Y3 | Read once, not blind for gross arms (see above) |
| UK PV, confirmation | Windows of 2018 | 2019 is primary, 2020 and 2021 show decay | Read once after the code is frozen |

## Evaluation group and score

Five partitions per fleet, seeds 11, 23, 37, 51 and 73. Each holds out one third of the systems, which are never selected and never
metered in the campaign. The rest are candidates. Target: the evaluation group's capacity-weighted ratio. Daylight: solar elevation
above 5 degrees at the fleet's centre. Score: nRMSE in percent of the mean daylight target, with bias reported beside it.

## Estimator

The chosen systems' capacity-weighted ratio with no fitted weights, leaving a chosen system out for a day if its daylight energy that
day is below a quarter of the chosen systems' median, and for any row where it is missing. The day test needs k of at least 3. It
reads only the chosen systems.

## The method

Meter a campaign set of m candidates for L days. Run forward greedy search for the k systems whose capacity-weighted ratio is closest to
the ratio of the whole campaign set in that window. Keep those k and stop metering the rest.

This target is stricter than the census arm in v1, because it never sees the evaluation group.

## Factors

- Budget k: 1, 2, 3, 5, 10, 20, 50. The main results use k = 5, 10, 20.
- Length L: 1 week, 2 weeks, 4 weeks, 3 months (91 days), with starts on 1 January, 1 April, 1 July and 1 October. Reference: one year.
- Campaign size m: all candidates is the default. Also 25, 50 and 100, drawn at random, at L = 4 weeks and 3 months, for k not above m.

## Competitors

All use the same estimator and the same scoring.

- **No campaign needed:** random (40 draws, median), largest capacity, and metadata only, which is the same greedy search matching the
  fleet's capacity-weighted distribution of tilt, orientation and location.
- **Same campaign data:** random with one level factor, k-medoids, maximum difference (Zhu), mRMR, and greedy mutual information on a
  Gaussian process. Each source paper is read before coding, and any departure from it goes in `RUN_LOG.md`.
- **Ausgrid only, from net load:** N1 and N4, on the hold-out, as the secondary result.

## Main outcome and rules

Gain kept in a fleet: S = (E_random - E_L) / (E_random - E_1y), the median over k = 5, 10, 20, on errors averaged over partitions and
start months. E_1y uses the same campaign set.

- **Confirmed** at L = 4 weeks on UK PV in 2019 if the median S across regions is at least 0.5, and at least two thirds of regions reach
  0.5. A Wilcoxon signed-rank test across regions on E_random - E_L is reported beside it.
- **Not confirmed:** the paper says so, and reports the result as specific to Ausgrid. The next step is then for the user to decide.

Secondary, all reported whatever they show:

- Decay: S with the 2018 campaign scored on 2020 and 2021.
- Selection or level: A = (E_RC - E_GC) / E_RC as in `RUN_LOG.md`, with selection adding value at A of at least 0.10.
- **Is a campaign needed at all?** If metadata only keeps at least 0.8 of the 4-week greedy gain, the campaign is not worth its cost, and
  the paper must say that as its main practical message.
- Season: S by start month. Weak winter windows are expected to matter more in the UK, and are reported either way.
- Campaign size: S against m. Cost is given in meter-months only, with no invented prices.
- Monitor loss: error at k = 10 and 20 when 1 to 3 chosen monitors are removed at random in the scoring year.
- Why it works: overlap of picks across windows, and how far the chosen set matches the fleet's tilt and orientation mix.

## Forecast arm

Horizons 0.5 and 1 h are primary, with 2, 3 and 6 h reported to show the decay. Training uses only the chosen monitors' estimate, because an
operator has no fleet truth, and scoring uses the true evaluation group.

- Train and test: UK PV 2019 and 2020. Ausgrid Y2 and Y3.
- Models: ridge and LightGBM on lags of the monitor estimate, solar geometry and a month-slot profile from training. A neural model on Kaggle
  T4 is optional, at most 10 GPU hours, and only if the simple models show a gap worth explaining.
- Arms: random k, the method at 4 weeks and 3 months, one-year reference, and all candidates as the bound.
- Baselines: smart persistence from the monitors, and the month-slot profile with no live monitor.
- The zero-monitor weather model in v1 is optional now, because it is not needed for the main claim.
- There is no pass mark. The arm reports whether a better monitor set still helps at each horizon.

## Rules

- Compute: laptop first. Kaggle runs carry a time limit, stay private and stop themselves when they end or fail.
- The Hugging Face token stays on the laptop. If Kaggle needs UK PV, the files go up as a private Kaggle dataset.
- Do not read PVDAQ 2107 or 9068 values from 2022 onward for this paper until Paper 1 is scored.
- Do not edit `paper1/`, `paper2`, `paper3/` or `paper4/`.
- Git commits only when the user asks, authored by the user only.
