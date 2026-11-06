# BriefCensus

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23950664.svg)](https://doi.org/10.5281/zenodo.23950664)

Code, run log, and result tables for the paper "BriefCensus: A short metering campaign that chooses permanent monitors for rooftop photovoltaic fleet estimation and forecasting".

BriefCensus meters candidate rooftop systems for a short temporary campaign, removes outage rows, and keeps k permanent monitors chosen by a forward greedy search. A day-rule estimator with no fitted weights then estimates the fleet from those monitors alone, and forecast models train on that estimate.

## Main results

| Run | Share of the one-year gain kept at four weeks |
|---|---|
| UK frozen confirmation, no outage filter, 16 regions | 0.675 |
| UK same fleets, with filter (exploratory) | 0.790 |
| UK second sample of unread systems, with filter, 12 regions | 0.815 |
| Ausgrid hold-out | 0.796 |

The outage filter was added after the frozen run, and `RUN_LOG.md` records that change. The second sample tests the filter on systems that no earlier run had read. All selection windows are cut from full records, so the study simulates a campaign and does not run one in the field.

## Contents

| Path | What it holds |
|---|---|
| `PROTOCOL_v1.md`, `PROTOCOL_v2.md` | The protocols fixed before the runs. These public copies leave out rules about the authors' own workspace, which do not concern the study, so their hashes differ from those in `RUN_LOG.md`. The hashed originals are in the Zenodo archive of version 1.0.0. |
| `RUN_LOG.md` | Dated log of decisions, failed claims, rule changes, and file hashes. This public copy leaves out personal and manuscript-editing notes and has light wording edits. No result, rule, or code hash changed. |
| `src/` | Method, rival selectors, forecast models, and scoring |
| `kaggle/campaign/` | Kaggle run scripts, logs, and output tables of each run |
| `results/` | Kill tests, development questions, and printed summaries |
| `paper/build_figures.py` | Builds all figures and `numbers.json` from the output tables |
| `paper/figures/` | Figures of the paper |

The first claim of this project, choosing monitors from net load alone, failed its kill test. Its code and results stay here on purpose.

## Rebuild the figures and numbers

This step needs no raw data, because it reads the output tables in this repository.

```bash
pip install -r requirements.txt
python paper/build_figures.py
```

The result should match `paper/numbers.json` and `paper/figures/`.

`build_figures.py` draws Figure 1 in Arial and the other figures in DejaVu Sans. A machine without Arial uses a fallback font for Figure 1.

## Rerun the experiments

The raw data are not in this repository, so download them from their sources first.

| Dataset | Source | Licence | Expected folder |
|---|---|---|---|
| UK PV | [openclimatefix/uk_pv](https://doi.org/10.57967/hf/0878) | CC BY 4.0 | `data_external/uk_pv/` |
| Ausgrid Solar Home | [data.gov.au](https://data.gov.au/data/dataset/nsw-solar-home-electricty-data) | CC BY 3.0 Australia | `../paper3/data_external/ausgrid/extracted/`, beside this repository |

The Ausgrid path is unusual because the code stays byte-identical to the versions hashed in `RUN_LOG.md`.

The docstring at the top of each script gives its commands. For example:

```bash
python src/run_campaign.py ausgrid-dev
python src/summarise.py <folder> <file pattern> <primary period>
```

The full runs used Kaggle CPU sessions with Python 3.13.18. `kaggle/campaign/build.py` builds those kernels, and each kernel stops itself when it ends, fails, or nears its time limit. The kernels and their private dataset copies stay private under the first author's Kaggle account, so a rerun needs a copy of the data under your own account.

## Not included

- Raw data, which remain with their publishers.
- The manuscript text, until the paper is published.
- Full-text papers and their abstracts, which remain under copyright.

## Licence

The code is under the MIT License. Result tables and figures are under CC BY 4.0. Tables derived from UK PV and Ausgrid Solar Home also carry the attribution terms of those datasets.

## Citation

Cite all versions as [10.5281/zenodo.23950664](https://doi.org/10.5281/zenodo.23950664), which always resolves to the latest version. Version 1.0.0 is [10.5281/zenodo.23950665](https://doi.org/10.5281/zenodo.23950665). See `CITATION.cff` for the full entry. The paper reference will be added here once it exists.
