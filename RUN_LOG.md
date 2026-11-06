# NetPick run log

## 4 November 2026, day 1

**Protocol.** `PROTOCOL_v1.md` SHA-256 e47ef0bb6f56c61aff315a978195373fa85b759a962c18cef803a0203f40bcbc, fixed before any net-only result.
Code for the kill test: `src/ausgrid.py` c8ee8094cb625ebda4439418d2b3032a315e407f51f20b695d2ac2be9c530840, `src/kill_test.py` a29862f776914c3076960ed75492a24b47fa07d3f0e264e9108e2e8af7c96614.

**Kaggle link.** Signed in as oussielhoucine. The private no-GPU test `p3-link-test` ran for about 5 minutes and pushed, ran, streamed
live logs with `kaggle kernels logs -f`, and returned its output and log. Session: Python 3.13, 4 cores, 19.5 GB free in the working folder.

**Papers read for the gap check.**
- Zheng, Xiao and Pei 2025, Applied Energy 380, 125058: abstract and introduction only (paywall). Uses given reference stations and transfers to the rest, with no selection method in what was read. Its introduction cites budget findings: error rises below about 20 reference stations in a 336-station study, and at least three reference systems are advised. The originals still have to be traced.
- Xie et al. 2026, IET GTD: abstract only, because the full text could not be accessed. Cluster forecasting at 21 sites, with neighbours filling missing data. No selection in the abstract.
- Bu et al. 2021 (arXiv 2009.00734, full text): three exemplars picked by panel direction, no selection procedure. The "three are enough" line cites earlier work. Scored per customer.
- Chen, Moghimi Haji and Ardakanian 2021 (arXiv 2105.08122, full text): proxies picked at random, or from the same cluster on Ausgrid. No sweep over proxy count. Scored per home, with aggregates left as future work.
- Ge et al. 2022, Energies 15, 8783 (encyclopedia version): calls reference-station selection the most critical step of virtual collection, and describes selection after all stations' data have been collected, so a census is assumed.
- Saint-Drenan et al. (Fraunhofer, 366 plants) and an mRMR method (Energies 12, 3817): seen in search results only. They must be read before writing.

**Finding.** Selection from gross PV is prior art, so a census arm cannot be a contribution. Selection from net load has not been found. This raises the stakes of the kill test.

**Data audit, counts only.** Each of the three files has 300 homes, 100 postcodes, capacity 1.0 to 9.99 kWp, with no change in capacity or postcode across files. 139 homes have a CL channel in Y1 and Y2, and 138 in Y3. Y3 GG day-rows run from 284 to 365 per home, which may explain the 299-home cohorts elsewhere, but this is unchecked. Y2 capacity factors show likely outages (home 92 at 0.014, home 220 at 0.053, median 0.143).

**Name.** A search found no "NetPick" in PV or smart-meter work. That is one search only.

**Open.** Licence: Ausgrid is CC BY per the older project audit and search listings, but the live Data.NSW and Research Data Australia pages returned 404 today, so confirm by hand before submission.

## 4 November 2026, kill test

**Run 1: FAIL, median recovery 0.474 for N1 and 0.224 for N2, against a pass mark of 0.5.** Kept in `results/runs/kill_test_run1_clock_error.*`.

The clock check printed by this same run shows an error in the code. The fleet's output centroid is near 11.9 h from April to September and near 12.6 to 13.1 h from October to March, which matches solar noon on a civil clock with daylight saving. `daylight()` assumed AEST all year, so from October to March the daylight rows sat about one hour early. The protocol defines the mask by solar elevation, so this is a mistake in the code, not a change of plan. The fix applies the NSW rule (first Sunday of October to first Sunday of April). The same run is repeated with the pass mark, arms and seeds unchanged.

**Run 2, after the clock fix: formal PASS, median recovery 0.541 for N1 (k = 5: 0.445, k = 10: 0.541, k = 20: 0.664) and 0.428 for N2.** Kept in `results/runs/kill_test_run2.json`. The share of homes in common with census greedy is only 0.04, 0.06 and 0.10 at k = 5, 10 and 20.

| k | random | census | N1 | N2 |
|---|---|---|---|---|
| 1 | 41.90 | 31.71 | 42.04 | 40.16 |
| 2 | 31.20 | 20.65 | 29.73 | 28.99 |
| 3 | 25.69 | 17.53 | 23.93 | 22.79 |
| 5 | 21.16 | 13.20 | 17.62 | 17.32 |
| 10 | 15.16 | 9.69 | 12.20 | 13.32 |
| 20 | 11.69 | 7.30 | 8.77 | 9.81 |
| 50 | 8.28 | 5.92 | 6.39 | 8.00 |

**This pass is not accepted as evidence.** `src/kill_sensitivity.py` (`results/kill_sensitivity.json`) shows why:
- Leaving out one partition gives 0.639, 0.529, 0.564, 0.424 and 0.592 for N1. Leaving out partition 51 fails the mark.
- Within single partitions the median is 0.282, 0.344, 0.485, 2.257 and 0.501.
- In partition 51, census greedy chose homes that partly failed in Y2. Its k = 10 error is 15.91 against 7.11 to 9.77 elsewhere. That shrinks the census gap and flatters recovery.
- The fleet net-load signal correlates only 0.522 with true fleet PV in Y1, so the signal is weak.
- A row-level rule for dropping failed monitors was also tried. It made error worse at high k for every arm (random at k = 50 went from 8.28 to 10.98, census from 5.92 to 8.68), probably because it drops real low values and biases upward. It is rejected as an estimator, so its recovery figures (N1 0.213, N2 0.328) are not a clean estimate. With that rule, census error at k = 10 is 8.48 to 10.85 across partitions, which suggests that failed monitors caused the outlier.

**Solid so far:** the census selection gain is real. **Not shown:** that net-only selection recovers enough of it.

**Bounded second round, fixed before it runs.** Y3 stays unread. Code: `src/kill_test2.py`.
- Estimator for all arms from here on: the capacity-weighted ratio, leaving a chosen home out for a whole day if its daylight energy that day is below a quarter of the chosen homes' median, or for any row where it is missing. The day test needs k of at least 3 and uses only the chosen homes' data.
- New net-only arms, added to N1 and N2: N3 = N1 using only rows with solar elevation of at least 25 degrees. N4 = each home's response to the fleet's common net-load anomaly, by month and slot. N5 = N1 after a rank-10 rebuild of the signal matrix, which removes load of a single home.
- Stricter pass rule: for the best of N1 to N5, median recovery over k = 5, 10, 20 is at least 0.5, and it stays at least 0.5 with any one partition left out.
- Five net-only arms have now been tried, and the paper must say so.
- **If no arm passes, no more signal tuning.** The net-only claim is dropped and the plan moves to the protocol's census-length question.

**Code hashes (SHA-256).** The `src/ausgrid.py` hash logged on day 1 predates the clock fix, so these replace it.
- `src/ausgrid.py`: 3557bb73262b1d4e4e938782de0ada0483cc9878813ec279b47d25001c19bb67
- `src/kill_test.py`: a29862f776914c3076960ed75492a24b47fa07d3f0e264e9108e2e8af7c96614
- `src/kill_sensitivity.py`: 9efd513b65cbfcac88ea2b4b8f5a2f7b08b373182660c01a8aeee76c558b8566
- `src/kill_test2.py`: b30ee57802a6c0d2cca2ce4933465e96b9b3ab9e19a255582b01e9894099106f

**Second round: FAIL by the stricter rule.** `results/kill_test2.json`, `results/kill_test2.log`. With the plain estimator the run gives back Run 2 exactly (largest difference 0.0).

| Arm | Recovery k = 5, 10, 20 | Median | Worst with one partition left out | Fleet signal correlation |
|---|---|---|---|---|
| N1 | 0.218, 0.321, 0.392 | 0.321 | 0.272 | 0.522 |
| N2 | 0.313, 0.268, 0.290 | 0.290 | 0.255 | 0.247 |
| N3 | 0.190, 0.068, -0.098 | 0.068 | -0.050 | 0.659 |
| N4 | 0.366, 0.350, 0.285 | 0.350 | 0.231 | 0.445 |
| N5 | 0.054, 0.263, 0.317 | 0.263 | 0.169 | 0.494 |

nRMSE % on Y2 with the day rule, mean of five partitions:

| k | random | census | N1 | N2 | N3 | N4 | N5 |
|---|---|---|---|---|---|---|---|
| 5 | 20.46 | 10.98 | 18.39 | 17.50 | 18.67 | 16.99 | 19.95 |
| 10 | 14.69 | 8.11 | 12.58 | 12.92 | 14.24 | 12.39 | 12.96 |
| 20 | 11.31 | 6.44 | 9.40 | 9.90 | 11.79 | 9.92 | 9.77 |
| 50 | 8.41 | 5.70 | 7.36 | 8.00 | 8.19 | 7.32 | 7.34 |

- The day rule works for census: partition 51 at k = 10 falls from 15.91 to 8.96, and the range across partitions is now 6.89 to 9.42.
- The day rule hurts N1 at every k from 5 up (k = 10: 12.20 to 12.58). The cause is not checked.
- The verdict does not rest on the rule alone. With the plain estimator N1 also fails the left-out test, at 0.424.
- N3 has the best signal correlation and the worst recovery, so a better fleet signal did not give better picks.

**Decision, following the stop rule fixed above.** No more signal tuning. The claim that net-only selection nearly matches a census is dropped. Y3 stays unread for net-only arms. Net-only beat random at k = 10 in all five partitions for N1, so "about a third of the gain" may be reported as a secondary result, with all five arms disclosed.

**Census-length question, fixed before it runs.** Code: `src/census_length.py`. Development split only.
- Question: if an operator meters every home for a short campaign and then keeps k monitors, how much of the one-year census gain survives?
- Lengths: 4 weeks and 3 months (91 days), each starting on 1 July, 1 October, 1 January and 1 April of Y1. Reference: all of Y1, which is the census arm above.
- Everything else matches the census arm: same greedy search on gross PV, same five partitions, same random medians, scored on all of Y2 with the day rule.
- Gain kept: G = (E_random - E_length) / (E_random - E_census), and its median over k = 5, 10, 20.
- **Clear gain** needs all three, at 3 months: the median G, averaged over start months, is at least 0.5. It stays at least 0.5 with any one partition left out. At least 3 of the 4 start months reach 0.5 on their own.
- **If there is no clear gain, the plan moves to a different study question.**
- Hash of `src/census_length.py`: cd3c986bd5e4b3603dc018be2ca63a92661aa1ca0f77decc89803ba0984bee13

**Census-length result: CLEAR GAIN by the rule above.** `results/census_length.json`, `results/census_length.log`. One-year picks reproduce the census arm in every partition.

Share of the one-year gain kept, median over k = 5, 10, 20:

| Length | Jul | Oct | Jan | Apr | Average | Worst with one partition left out |
|---|---|---|---|---|---|---|
| 4 weeks | 0.765 | 0.883 | 0.617 | 0.912 | 0.794 | 0.774 |
| 3 months | 0.884 | 0.895 | 0.826 | 0.960 | 0.891 | 0.877 |

At k = 10: random 14.69, one-year census 8.11, 4 weeks 8.68 to 10.74, 3 months 8.28 to 9.10.

**This is not yet accepted as a selection result.** A short census may only reveal which homes have a typical level, and that level may persist from year to year. If so, k random homes with one level factor from the same census could do as well, and greedy selection adds little.

**Explanation test, fixed before it runs.** Code: `src/explain_gain.py`. Development split only.
- Windows: the eight above, plus all of Y1.
- Level factor: the fleet's mean ratio in the census window over the chosen homes' mean ratio in that window, one number, applied to the Y2 estimate. It uses census data only.
- Arms: RC = the same random draws with the factor. GC = census greedy with the factor. B = census greedy whose target leaves out the evaluation homes, with no factor, to see if the evaluation homes' census data help.
- Advantage: A = (E_RC - E_GC) / E_RC, median over k = 5, 10, 20, on errors averaged over partitions and start months.
- **Selection adds value** if A is at least 0.10 for both 4 weeks and 3 months, and stays at least 0.10 with any one partition left out. **Otherwise the level factor explains most of the gain**, and the paper must report calibration as the main finding, not selection.
- B counts as harmless if its share of the gain is within 0.10 of the plain census-greedy share for that length.
- Hash of `src/explain_gain.py`: 74833f2ce551f668b09c096178416b48a821b4fdac3be81adfa8c4a56652bf36

**Explanation test: SELECTION ADDS VALUE by the rule above.** `results/explain_gain.json`, `results/explain_gain.log`. The random medians match the second round exactly.

nRMSE % on Y2 at k = 10, mean over partitions and start months (random 14.69, one-year census 8.11):

| Length | greedy | GC | RC | B | A | Worst A, one partition left out | Share of gain: greedy, RC, B |
|---|---|---|---|---|---|---|---|
| 4 weeks | 9.48 | 9.59 | 14.00 | 10.04 | 0.315 | 0.289 | 0.792, 0.098, 0.707 |
| 3 months | 8.63 | 8.93 | 13.96 | 9.39 | 0.354 | 0.340 | 0.876, 0.110, 0.804 |
| 1 year | 8.11 | 8.17 | 13.52 | 8.76 | 0.396 | 0.376 | 1.000, 0.164, 0.901 |

- One level factor on random homes keeps only about a tenth of the gain, so the gain is not just level.
- The factor adds nothing to greedy (GC is no better than greedy).
- Leaving the evaluation homes out of the target is harmless by the rule (0.707 against 0.792, 0.804 against 0.876), though it does cost some gain.

**Still open before this can be the paper's result.**
- All of this is one city and one pair of years, on the development split.
- Y3 is not blind for gross-PV arms, because the 3 November pilot read it for greedy with a full census. UK PV is therefore the real confirmation.
- Simple selectors (largest capacity, medoids, maximum difference, mRMR) have not been run on short windows. If they match greedy, the finding is about census length, not about the search.
- A census of every home is the costly part. The size of the campaign (metering a sample, not the whole fleet) has not been tested.
- No forecast result exists yet. The paper needs one to stay a forecasting paper.
- Check how the publisher screened Y1. Not yet verified: Ratnam et al. 2017 may describe quality filtering on the first year. That could make Y1 look cleaner than Y2 and would matter here.

**Novelty, weak evidence only.** Three searches on 4 November found no study that varies the length of the data used to choose reference PV systems. The Saint-Drenan page (HAL) and preprints.org 202606.1547 could not be accessed at this point, so both remain unread. Yao, Tang and Ayyanar 2014 (ECCE) estimate feeder PV from a few inverters, and the page does not say how those are chosen.

**The main claim has changed**, so `PROTOCOL_v1.md` no longer describes the paper. A `PROTOCOL_v2.md` must be fixed and hashed before UK PV or Y3 is scored for these arms. The change is recorded here because the protocol fixed on 4 November was for net-only selection.

**Open items closed, 4 November.**
- Ausgrid licence: data.gov.au (https://data.gov.au/data/dataset/nsw-solar-home-electricty-data, read in a browser) lists Creative Commons Attribution 3.0 Australia, publisher Ausgrid, from DataNSW, created and updated 24/06/2025. The older Ausgrid and Data.NSW pages return 404, so Ausgrid's own terms could not be read. Cite the catalogue listing with its access date.

**UK PV facts, from the Hugging Face page and API.** `openclimatefix/uk_pv`, CC-BY-4.0, access granted automatically once the conditions are accepted. Over 30,000 systems, 2010 to 2025. Metadata has capacity, tilt, orientation and rounded location, and `bad_data.csv` lists periods to drop. 30-minute Parquet files total 4.65 GB, about 0.4 GB per year since 2016. The earlier plan of 1,000 to 2,000 systems should be reviewed in `PROTOCOL_v2.md`.

## 4 November 2026, protocol v2

**Main claim changed, with the first author's confirmation.** `PROTOCOL_v2.md` fixed before any UK PV generation value was read. SHA-256: 508da4283ae2dda20bf48370e7a853ed426320b83686ed18d6379802702f69b4

**UK PV counts from metadata only.** 30,757 systems. 21,274 span 2018 to 2021, and 16 one-degree cells hold at least 300 of those. The v2 cohort rule does not condition on later years, so its counts will differ and are logged when the code runs.

**Name.** Working name BriefCensus. One search found no clash in PV work, which is one search only.

**First Ausgrid development run of `src/campaign.py`.** It matches the earlier results exactly: random 20.46, 14.69, 11.31 at k = 5, 10, 20, and the method at 13.18, 10.04, 8.20 (4 weeks), 12.27, 9.39, 7.63 (3 months), 11.70, 8.76, 7.28 (1 year).

At k = 10 and 4 weeks, nRMSE % is: method 10.04, mRMR 13.95, random 14.69, GP mutual information 15.24, medoids 15.75, farthest-first 19.73. One week gives 10.68. A campaign of 100, 50 or 25 candidates gives 10.40, 11.57 or 12.70.

**Departures from sources, so far.** Fu et al. 2019 (Energies 12, 3817, read in a browser; 22 plants, 16 May to 30 July 2018, no later year): sub-regions dropped, and mutual information from rank correlation in place of their density estimate. Their equation images did not come through in the page text, so the standard difference form of incremental mRMR is assumed. Zhu et al. 2025: full text not yet accessed, so the farthest-first arm is only in the style of their maximum-difference rule and must be labelled that way or dropped. Saint-Drenan 2016 was not yet accessed either.

**Protocol change, made before any UK PV generation value was read.** The method's lead may be unfair or may have a simpler cause, so these are added to `PROTOCOL_v2.md`'s competitors:
- `_fit` versions of every campaign arm: non-negative weights fitted on the campaign rows, because the source papers fit weights and the method's greedy search directly optimises the unweighted estimator.
- Closest: the k systems individually closest to the campaign's ratio, with no search over combinations.
- Correlated: the k systems with the highest correlation to the campaign's ratio, the traditional rule that Fu et al. describe.
- Screened: random draws from the closest half of candidates, which tests whether the gain is only from removing odd systems.
- Oracle: greedy with hindsight on the scoring period, as a floor and not a method.

**Rule for these, fixed now.** If the best of closest, correlated and screened gets within 10% of the method's error at the median of k = 5, 10, 20 on UK PV in 2019, the paper must say that a simple rule is enough, and the search is not the finding. If any `_fit` competitor beats the method without weights, the paper must say that too.

**Paper read in full, 4 November.** Saint-Drenan, Good, Braun and Freisinger 2016, Solar Energy 135, 536-550, DOI 10.1016/j.solener.2016.05.052, preprint read in full. 366 plants from one German operator, 15 min, July 2013 to August 2014, mean 262 kWp, so mostly medium to large.
- Reference sets are drawn at random 1,000 times, and the estimate is inverse-distance weighting. There is no selection method, no variation in data length and no later scoring year.
- The error depends strongly on which plants are chosen: 0.009 to 0.022 kW/kWp above 70 references. Error falls steeply up to about 20 references and saturates after about 70.
- Average distance to the nearest reference predicts the error when characteristics match (their equation 6.2), and they suggest it could be used to choose a set.
- They say the match in plant characteristics could not be quantified with their data, and they call for a larger set that includes small rooftop plants. UK PV has tilt and orientation for rooftop systems, so it speaks to that gap.
- They suggest choosing large plants as references. On Ausgrid the largest-capacity arm is worse than random (19.26 against 14.69 at k = 10). Their fleet has a much wider capacity spread, so the two results may not conflict, and the UK result should be read with that in mind.

**Protocol change, made before any UK PV generation value was read.** Added a no-campaign competitor, `spatial`: greedy on their equation 6.2, using rounded locations, on UK PV only because Ausgrid has no coordinates. The rule "Is a campaign needed at all?" now applies to the better of metadata only and spatial.

**Paper read, 4 November.** Zhu, Zhang, Wang and Ding 2025, Energy Science & Engineering 13, 4314-4329, DOI 10.1002/ese3.70171, open access. Pages 1 to 14 of 16 were read, which cover the method and results. 109 plants of 0.62 to 38.1 MW in one region of China, 15 min, one year of data (35,040 points).
- Selection uses a full year of data from every plant, with DBSCAN clusters and then a maximum-difference rule on mean power and location. The data length is not varied.
- There is no comparison against random selection or other selectors, and no selection and scoring in separate years. Its own "fewer representatives" arm uses fewer plants from the same method.
- The forecast is trained with total cluster power as its target, so it assumes the operator keeps measuring the whole cluster.
- Its equation 11 prints a minimum of the minimum distances, which would choose the nearest plant. Its stated aim and its figures need the farthest plant, so the maximum is used. This must be said in the paper.

**Correction to the code, made before any UK PV generation value was read.** The `farthest` arm is replaced by `maxdiff`, which follows their steps: scaled mean power from the campaign window and location, a start at the plant most different from the rest, and then the farthest plant. Departures: no DBSCAN clusters, the mean power comes from the campaign window and not a full year, and Ausgrid has no coordinates so it uses mean power only. Earlier `farthest` numbers, including 19.73 at k = 10, describe the old arm and must not be reported as Zhu's method.

**Kaggle.** The local machine ran out of memory, so this CPU work moves to a private Kaggle kernel with no GPU. Private dataset `oussielhoucine/p3-solar-fleets` holds the UK PV 2018 to 2021 files, the UK metadata and Ausgrid Y1 and Y2. It does not hold Ausgrid Y3.

**Debug run, 4 November.** Kernel `oussielhoucine/p3-campaign-debug` finished with exit 0 on both runs (Ausgrid dev 160 s, UK debug cell 50N-5E 278 s). The debug cell tests the code and is not evidence, so its errors are not reported as results.
- UK clock on the debug cell, 2018: output centroid by month runs from 11.99 to 12.50 UTC, with solar noon near 12.29, and there is no one-hour step at the March or October clock change. Timestamps are UTC as the publisher states. The audit line printed NaN because some night slots are all missing, so this check was redone on the laptop and the audit line was fixed.
- Energy outside the daylight mask is 0.004. Missing share is 0.131 overall and 0.121 in daylight. 11 of 224 systems miss over half of daylight readings, and the day rule treats them as missing. No error in the table is empty for any year.

**Fairer arms on Ausgrid dev (selection Y1, scored Y2), nRMSE % at k = 5, 10, 20, at 4 weeks.**
- Method 13.18, 10.04, 8.20. Same picks with fitted weights 12.75, 9.71, 8.04.
- GP MI with fitted weights 14.03, 10.49, 8.26. mRMR with fitted weights 13.98, 11.09, 9.25.
- Closest 18.59, 14.84, 12.32. Screened 18.74, 13.80, 10.71. Correlated 25.40, 20.68, 16.60. Maxdiff 22.16, 17.48, 13.33. Random 20.46, 14.69, 11.31. Oracle 10.41, 6.95, 5.20.
- Reading: the simple rules are far behind, so the search matters. Fitted weights rescue the other selectors a lot (GP MI from 15.24 to 10.49 at k = 10), so the fair lead over the best competitor is about 4% at k = 10 and under 1% at k = 20 on this fleet. Fitted weights on the method's own picks are about 3% better than no weights here.
- Fitted weights can also fail badly on short windows: medoids at 1 week and k = 10 reach 45.33, and maxdiff at 4 weeks and k = 5 reach 134.74.
- No change follows from this. The method stays unweighted as fixed in protocol v2, `method_fit` stays a reported arm, and the rule on `_fit` competitors stands.

**Code frozen for the confirmation run.** SHA-256 of each file:
- `campaign.py` 6e4ac21309b387ae07fd05791b5be4dd4acefecb8f59adb8c72e200f96871b7b
- `ukpv.py` b337c577bf566fef944e9cbfb962a20d922aaf5241bb83bbcf5633e337b8b8bc
- `run_campaign.py` 6e8a706ec069838ee11c9fa395f53017e69e2f75d51c7d685dcb54c6522ab4be
- `kill_test.py` a29862f776914c3076960ed75492a24b47fa07d3f0e264e9108e2e8af7c96614
- `kill_test2.py` b30ee57802a6c0d2cca2ce4933465e96b9b3ab9e19a255582b01e9894099106f
- `ausgrid.py` 3557bb73262b1d4e4e938782de0ada0483cc9878813ec279b47d25001c19bb67

**Scoring script fixed before any confirmation value was read.** `src/summarise.py` SHA-256 6ec154ae9c4e07d952d853660982dd4f29c375f796e708c35bdae0c27eb79c75, tested on the open Ausgrid development table only. It applies the main rule, decay, A, the no-campaign rule, the simple-rule test, the fitted competitors, season, campaign size and bias. One departure: for smaller campaign sets, S uses the one-year error of all candidates as its reference, because the frozen run has no one-year arm for m = 25, 50 and 100. This makes S at those sizes lower than a same-set reference would.

**Ausgrid hold-out scope.** The frozen code takes hold-out campaign windows from Y2 only, the year next to the scoring year Y3, and it loads Y1 only to keep the same homes. This narrows "Windows of Y1 and Y2" in `PROTOCOL_v2.md`, and it is logged here before Y3 is read for any short window.

**Bug fix before the Ausgrid hold-out, 4 November.** The frozen `ausgrid-holdout` branch cut the last 365 days of Y1 and Y2. Y2 has 366 days because 2012 is a leap year, so the cut started on 2 July and `windows_of` would have failed on the missing 1 July. The fix passes `['Y2']` alone and drops the cut, which also loads no Y1 data. Capacity is the same for all 300 homes across Y1, Y2 and Y3. The `uk-confirm` branch does not change, and the confirmation kernel carries its own copy with the earlier hash. New SHA-256 of `run_campaign.py`: 4f274ba0b91a5842e215cebcf6417e81c05285f8a083557f6d100edf56af590f. Y3 generation was cached and uploaded as private dataset `oussielhoucine/p3-ausgrid-y3`, and no Y3 value has been read or scored yet.

**Literature check, 4 November.**
- Ratnam, Weller, Kellett and Murray, International Journal of Sustainable Energy 36(8), 787-806, DOI 10.1080/14786451.2015.1100196, checked on Crossref. An earlier author list was wrong. Its anomaly screening is not read yet, because only the search summary was seen.
- Wu, Lai, Huang, Phuong and Tan 2022, Energies 15(4), 1312, read on the MDPI page. 169 plants of 40 kW to 13 MW in Taiwan. Half are assumed visible throughout, and three plants per cluster are picked by correlation with the cluster total. A model trains on one month and estimates the next. This is the nearest thing found to a short window, but half the fleet stays metered, there is no later year and the length is not varied.
- Shaker, Zareipour and Wood 2016, IEEE Transactions on Smart Grid 7(5), 2466-2476, DOI 10.1109/tsg.2015.2502140: reference checked on Crossref, paper not read.
- Zheng et al. 2024, IET Renewable Power Generation, DOI 10.1049/rpg2.13003: not accessible, not read. preprints.org 202606.1547: not accessible, not read. Neither can be cited for a claim until read.
- Two further extended searches found no study varying the length of data used to choose reference systems. This remains weak evidence.

**Second code freeze, 4 November, before any confirmation or hold-out value was seen.** Test kernel `oussielhoucine/p3-campaign-test2` finished with exit 0 on open data and the debug cell. Rebuilt picks gave back the campaign tables with a largest difference of 0.0 on both fleets, net-only on development gave back N1 .321 and N4 .350 from the second kill round, and the forecast geometry matches both daylight masks exactly.
- Forecast settings, fixed with no tuning: ridge alpha 1.0 on standardised features. LightGBM 300 trees, learning rate 0.05, 31 leaves, at least 20 rows per leaf, subsample and column sample 0.8. Five random draws per budget. Ausgrid selects in Y1, trains on Y2 and tests on Y3. UK PV selects in 2018, trains on 2019 and tests on 2020.
- Monitor loss removes monitors for the whole scoring year, with 20 random choices of who is lost. Random sets use 40 draws.
- SHA-256: `extras.py` 01215d67afb1d38e70256659647a99e23fa768407342f2258a0a7064008e6b06, `forecast.py` 492833007ec5eeca8df2f6f801b876534bc7c84545b9d44f144390ec46aa2d1a.

**Confirmation result, 4 November, frozen code, unchanged.** Kernel `oussielhoucine/p3-campaign-confirm`, all 17 fleets exit 0. At 4 weeks on UK PV in 2019, median S across 16 regions is 0.675, range 0.405 to 1.019, and 13 of 16 regions (0.812) reach 0.5. The rule is met: CONFIRMED. Wilcoxon on E_random - E_L gives p = 3.1e-05 at each of k = 5, 10, 20, which is the smallest value possible with 16 regions. Full output: `results/campaign/uk_summary.txt`.

**Problem found on reading the decay years.** Year errors swing, and 53N-3E in 2020 has random at 62.4 against 18 to 27 in other regions. The cause is an outage: in April and May 2020 only 1 to 4% of that fleet's systems report for weeks, so the evaluation group's ratio rests on one or two systems and many random sets have none reporting. No wrong-scale systems were found in the three regions checked. The fault is in what is scored, not in the method.

**Sensitivity added after seeing the confirmation result, so it does not replace it.** `src/sensitivity.py` reruns the frozen experiment, scoring only rows where at least half of the fleet's capacity reports. The mark of one half was chosen from the outage's size (1 to 4% against about 90% in normal months), not from any error. Selection windows do not change.

**Forecast arm changed before any forecast value was read.** Forecast train and test rows now need the same coverage, because UK PV 2020 is the forecast test year and contains these outages. The earlier forecast kernel `p3-campaign-forecast`, still running when this was written, used no coverage rule, and its output is kept as a record. The new kernel is `p3-campaign-forecast2`. Ausgrid is not affected if no rows fall under the mark, which is checked below.
- SHA-256: `sensitivity.py` ba7a8617d8901a6a6f624028ab640ee30804547c749e73d24834ed0889bbf544, `forecast.py` decac3134ee09276406d19f28ee7d6aba7c1f523bca8610928a82f437c81fbe1.

**Ausgrid coverage check.** No daylight row of Y1, Y2 or Y3 falls under the half-reporting mark, so the coverage rule changes nothing on Ausgrid, and the forecast run in the hold-out kernel stands.

**Coverage sensitivity result, 4 November.** Kernel `p3-campaign-coverage`. The rule still passes at 4 weeks on 2019, with median S 0.855 and 14 of 16 regions at 0.5, but the range is -0.468 to 1.815 because E_random - E_1y is small or negative in some regions. S is not a stable measure on this scoring, so errors are reported beside it.
- k = 10, median across regions, in %: random 16.85, method at 1 week 12.16, 2 weeks 12.27, 4 weeks 12.45, 3 months 12.97, 1 year 12.67, oracle 8.60. The length effect in the frozen result is gone. 4 weeks beats random in 16 of 16 regions at k = 10, with a median error cut of 30%, 24% and 16% at k = 5, 10, 20.
- Rivals at 4 weeks and k = 10: medoids 13.15, GP MI with fitted weights 14.07, mRMR with fitted weights 15.00, screened 17.45, spatial 17.62, metadata 17.85, closest 19.00. The large lead in the frozen table shrinks to about 5% over medoids at k = 10 and 1% at k = 20. Spatial's share of the gain falls from 0.431 to -0.054.

**Why the frozen result differs.** Checked on 51N-1E, partition 11. Outages are whole days, 5 in 2018 and 12 in 2019 for that fleet, with a median of 3.3% of capacity reporting. In the frozen score those rows hold 51% of one random set's squared error and 21% of the one-year picks' error. The one-year picks report on 99.2% of those rows against 66.8% for random sets, while on covered rows the two have similar error in this one case (14.9 and 14.4). Greedy treats a missing reading as zero, and in an outage row the target comes from the few systems still reporting, so long windows pick systems that survive outages. So the frozen length effect in UK PV mostly measures outage survival, not how well the picks represent the fleet. This rests on one fleet and one partition so far. It is a finding about the data and the method, and the paper must state it. Ausgrid has no such rows, and its hold-out still shows a length effect: at k = 10, random 14.14, 1 week 10.16, 4 weeks 9.79, 3 months 9.33, 1 year 8.68.

**Ausgrid hold-out, frozen code.** At 4 weeks S = 0.796, with 1 week 0.694, 2 weeks 0.703 and 3 months 0.876. A is 0.270. Scored on Y3, which is not blind for gross arms.

**Net-only on the hold-out.** N1 keeps a median 0.073 of the census gain and N4 -0.359, against 0.321 and 0.350 on development. The development result did not hold. The paper reports net-only as a failed approach, not as "about a third of the gain".

**Added now, after seeing the above, so these are exploratory for fleets already read.** `src/clean_run.py` removes rows under the half-reporting mark from selection as well as scoring, which an operator can do from its own campaign data. Coverage here is computed on the whole fleet, because the frozen `run_fleet` has no partition at that point. Outages appear to hit whole data feeds, so the effect should be small, but it is a departure.

**Second sample, rule fixed before reading any of it.** Fleets of up to 300 cohort systems from the same cells that no earlier run has read, excluding the confirmation and national samples, with at least 150 systems. Same weather and same outages, so this tests new systems and not new years. Scored on 2019 with outage rows removed from selection and scoring:
- The main rule as before: at 4 weeks, median S at least 0.5 and at least two thirds of regions at 0.5.
- A length is called enough if its error is within 10% of the one-year error, at the median of k = 5, 10, 20 and the median across regions.
- The method is called ahead of a rival only if its error is lower in at least two thirds of regions at the median of k = 5, 10, 20. This applies to medoids, GP MI with fitted weights and mRMR with fitted weights at the same length.
- SHA-256: `clean_run.py` 9195aa897a000ef40977a71b593bc93eb6b404e595e89f88ca75d319c11a96dc.

**Second sample result, 4 November.** Kernel `p3-campaign-second`, rule fixed above before reading. 12 of 16 cells had at least 150 unread systems. 50N-2E, 55N-3E, 56N-4E and 57N-3E had 28 to 120 and are left out, as the rule says. Outage rows are removed from selection and scoring, on 2019. Full output: `results/campaign/uk_summary_second.txt`.
- Main rule: PASSED. At 4 weeks, median S 0.815, range 0.737 to 1.416, 12 of 12 regions at 0.5.
- Length within 10% of the one-year error: 1 week 1.133 no, 2 weeks 1.119 no, 4 weeks 1.093 yes, 3 months 1.048 yes.
- Method ahead of rivals at 4 weeks, regions lower out of 12 with 8 needed: medoids 10, GP MI with fitted weights 11, mRMR with fitted weights 12. So the method is ahead of all three at 4 weeks under the rule. At 1 year: 9, 8 and 9.
- k = 5, 10, 20 at 4 weeks: method 17.31, 12.73, 9.95. Random 23.75, 17.23, 13.04. Medoids 19.34, 13.68, 11.64. GP MI fitted 19.91, 14.07, 11.05. mRMR fitted 18.93, 15.46, 12.42. Spatial 21.27, 16.25, 14.17. Metadata 23.76, 17.83, 14.39. Oracle 12.80, 9.12, 6.82. Method at 1 year 15.57, 11.80, 9.60.
- Error cut against random at 4 weeks: 30%, 27%, 22%. 4 weeks beats random in 12 of 12 at each of k = 5, 10, 20.
- Simple rule: best is 37.9% above the method, none of 12 within 10%. No campaign: better of metadata and spatial keeps 0.296. A at 4 weeks is 0.254.
- Fitted weights on the method's own picks are better than no weights at 4 weeks in 11 of 12 regions (k = 10: 12.14 against 12.73), and at 1 week no weights are better in 8 of 12. The paper must say this. The method stays unweighted because that is what the rule tested.
- Campaign size at 4 weeks and k = 10: m = 100 12.82, m = 50 14.02, m = 25 15.58.

**Clean run on the same fleets, exploratory.** Kernel `p3-campaign-clean`. At 4 weeks median S 0.790, range 0.650 to 0.905, 16 of 16 at 0.5. 1 week 0.690, 2 weeks 0.752, 3 months 0.891. The length effect returns once selection also drops outage rows, and S is stable again, which supports the outage explanation. 4 weeks is 1.131 times the one-year error here, so it misses the 10% mark on these fleets. Only one window in all fleets had to keep its outage rows.

**What the record now shows at 4 weeks.** S: Ausgrid development 0.784, Ausgrid hold-out 0.796, UK clean 0.790, UK second sample 0.815, and UK frozen 0.675 with outage rows in. The frozen confirmation stays the preregistered result. The outage rule is a change made after seeing it, and only the second sample tests it on systems not already read, in the same years and weather.

**Follow-up, fixed before reading.** `src/clean_followup.py` repeats monitor loss and the forecast arm on the second-sample fleets with clean selection, because kernel `p3-campaign-forecast2` still used picks selected with outage rows. It also measures, on all 16 confirmation fleets and all partitions, how far raw picks, clean picks and random sets keep reporting on 2019 outage rows, because the explanation so far rests on one fleet and one partition. The explanation holds if raw one-year picks report on clearly more outage rows than random sets and clean picks, and it is withdrawn otherwise.
- SHA-256: `clean_followup.py` 6b8ee305c8e3c9b19a90f3061523b8f69549e19c93973674ff7a6d9c68235c01.

**Follow-up result, 4 November.** Kernel `p3-campaign-followup`, all three jobs exit 0. Full output: `results/campaign/followup_summary.txt`, from `src/summarise_followup.py` (SHA-256 250e9e293b57540c61836759b6869103d04defa8535333fb683be485d0e5a49f). Rebuilt picks gave back all 12 second-sample tables with a largest difference of 0.0.

- Survival rule: HOLDS. The logged rule said "clearly more" with no number, so the values are given here. Median across the 16 confirmation fleets, k = 10, share of systems reporting on 2019 outage rows: raw one-year picks 0.520, clean one-year picks 0.195, random sets 0.147. Share of outage rows with any pick reporting: 0.995, 0.902, 0.629. Raw one-year share is above random and above clean in 16 of 16 fleets at each k. Raw 4-week picks sit between at 0.298. Outage rows are 3% to 9% of 2019 daylight rows by fleet. Clean one-year picks still report a little more than random, so the outage step removes most of the effect and not all of it.
- Monitor loss, second sample, 4 weeks. k = 10: none lost 12.73, one 13.35, two 14.44, three 15.88. k = 20: 9.95, 10.11, 10.44, 10.79. Random with none lost 17.61 and 13.00, as a median of 40 draws. After losing three, the picks stay below random with none lost in 12 of 12 at k = 10 and 20. Ausgrid hold-out at k = 10: 9.79, 10.39, 11.11, 11.87, against random 14.42.
- Overlap, k = 10, second sample: picks shared across windows 0.140, with the one-year picks 0.190, by chance 0.026. Ausgrid 0.142 and 0.208. The picks are far from unique, so many different small sets do about as well.
- Panel mix: the "why it works" idea from the protocol is NOT supported. At 4 weeks the picks are no closer to the evaluation group's mix than random sets. Orientation at k = 10: 0.265 against 0.244, closer in 4 of 12. Tilt at k = 10: 0.226 against 0.166, closer in 2 of 12. The method matches the fleet's output and does not match its hardware.
- Forecast, second sample, clean selection, select 2018, train 2019, test 2020. Ridge at k = 10, 4 weeks against random, by horizon 0.5, 1, 2, 3, 6 h: 21.81 against 24.96, 30.01 against 31.81, 39.05 against 40.30, 43.91 against 45.11, 51.54 against 52.09. Median error cut at 4 weeks by k = 5, 10, 20: 0.5 h 16%, 12%, 7%. 1 h 11%, 6%, 3%. 2 h 6%, 3%, 1%. 6 h 3%, 1%, 1%. So the benefit is real at 0.5 and 1 h and has mostly gone by 3 h. 4 weeks against one year at 0.5 h: 1.028, 1.016, 1.009 with ridge, so a short campaign costs little in the forecast. All candidates at 0.5 h 18.47.
- Forecast, Ausgrid hold-out, ridge at k = 10: 13.63 against 18.18 at 0.5 h, 18.20 against 21.34 at 1 h, 30.84 against 32.13 at 3 h. Cut by k at 0.5 h: 34%, 25%, 19%. 4 weeks over one year at 0.5 h: 1.078, 1.056, 1.052. All candidates 10.75.
- Models against persistence: at 0.5 h on UK PV, ridge and LightGBM do not clearly beat smart persistence from the same monitors (k = 10: ridge 21.81, LightGBM 21.56, persistence 21.71). The gain over persistence grows with horizon, about 11% at 6 h with the better model. LightGBM at 6 h is worse than ridge and worse than the profile on UK PV (59.64, 51.54, 56.90). No tuning was done, as logged, so this stands as found.
- Kernel `p3-campaign-forecast2`, picks selected with outage rows on the 16 confirmation fleets, agrees: 4-week cut against random with ridge at 0.5 h 18%, 12%, 6%, and 4 weeks over one year 1.024, 1.026, 1.007. Kernel `p3-campaign-forecast` has no coverage rule and is kept only as a record.

**Numbers for the paper, 4 November.** Tables come from `paper/numbers.json` and figures from `paper/build_figures.py`, and the numbers in the text were checked against the summaries and this log. Later-year errors at k = 10 were recomputed from the second-sample tables: 2020 12.98 against 16.91, 2021 14.98 against 19.04. Software versions come from private kernel `p3-versions`. References were checked on Crossref and abstracts read through OpenAlex, except the Zheng 2025 and Yang entries: Zheng 2025 rests on abstract and introduction read earlier, and Yang 2022 was dropped because its abstract could not be read. LightGBM was checked on the NeurIPS proceedings page. Still unread in full: Shaker 2016, Zheng 2024, Ratnam 2017, preprints.org 202606.1547. Whether the public Ausgrid files carry the screening that Ratnam describes is unchecked.

Also from `paper/numbers.json`: k = 10 error at one week and one year, 21.88 and 14.63 with outage rows, 12.16 and 10.46 without.

**Reference upgrade, 4 November.** A search of 2022 onward in listed venues, and of papers citing Saint-Drenan, Shaker, Fu, Wu, Pierro and Bu, found closer work missed earlier: Yue et al. 2024 (k-medoids pilot units for fleet forecasting), Meng et al. 2024 (reference plant selection), and Nguyen et al. 2022 (representative subset). Added on read abstracts: these three, Sultana 2025, Botello 2026, Perera 2024, Majumder 2025, Meng 2022. Dropped: Hong 2020, Clark 2019, Zheng 2024. Kept though older or lower in rank: Saint-Drenan 2016, Shaker 2016, Fu 2019, Wu 2022, Zhu 2025, Peng 2005, Guestrin 2005, Ke 2017, Ratnam 2017, because each is the source of a method, rival, dataset, or the closest earlier case. Quartiles were not checked on a current list. Yue, Meng 2024, and Nguyen were read only in abstract, so whether they vary the length of selection data is still open.

**Full-text checks, 4 November.** Shaker 2016, Zheng 2024, and Zheng 2025 were read in full. Shaker corrects the draft. It already proposes measuring all sites for a limited period, such as four months, and then monitoring a small subset. It states that three to four months were sufficient. Its tests use four months and score the other eight months of the same year on 405 California sites, with no result for another length and no later year. It also assumes clean measurements. The temporary campaign is therefore not new, and the claim is narrowed to how short the campaign can be, later-year holding, and outages. Zheng 2025 designates reference stations by data availability and capacity, so that wording is now firm. Zheng 2024 stays uncited. It advises avoiding small reference stations from a hand comparison of sets. Still abstract-only: Yue 2024, Meng 2024, Nguyen 2022. Ratnam 2017 is still outstanding.

**Full-text checks, second batch, 4 November.** Read Yue 2024, Meng 2024, Nguyen 2022. Yue applies k-medoids to locations only, so an earlier draft sentence calling the k-medoids arm their rule was wrong and is corrected. Our spatial arm (capacity-weighted distance on rounded locations, no deep network) is the nearer test. Yue uses 91 days from 99 Boston units, tests on the last tenth, varies k, and does not vary data length. Meng uses three months from 15 plants with forecasts shown for 21 to 31 May. Nguyen trains on one month and estimates the next over four periods, and reports that the best cluster count changes by month. None varies selection data length, so that claim stands, with Shaker as the closest idea. Ratnam 2017 could not be accessed. The text now cites its abstract for removing anomalous records and states that the screening of the public files was not checked. The licence was read in a browser on the date logged above.
