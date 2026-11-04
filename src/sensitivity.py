"""Sensitivity logged in RUN_LOG.md after the confirmation run: the same frozen experiment, scored only on rows where at least half of the fleet's capacity reports.
An outage can leave one or two systems reporting for weeks, and then the evaluation group's ratio is not a fleet's output. Selection windows are not changed.
"""
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

import campaign
import run_campaign
import ukpv

OUT = Path(__file__).resolve().parents[1] / 'results' / 'coverage'
MIN_REPORTING = 0.5


def covered(pv, capacity):
    """True on rows where the reporting systems hold at least MIN_REPORTING of the fleet's capacity."""
    return (np.isfinite(pv) * capacity[:, None, None]).sum(axis=0) >= MIN_REPORTING * capacity.sum()


def run_uk(name):
    t0 = time.time()
    meta = ukpv.fleet_of(ukpv.cohort(), name)
    lat, lon = float(meta.latitude_rounded.mean()), float(meta.longitude_rounded.mean())
    capacity = meta.kWp.to_numpy()
    pv, dates = ukpv.load(name, meta, ukpv.CAMPAIGN_YEAR)
    mask = ukpv.solar_mask(dates, lat, lon)
    print(name, '2018 daylight rows under the mark, share', round(float(1 - covered(pv, capacity)[mask].mean()), 4), flush=True)
    scoring = {}
    for year in (2019, 2020, 2021):
        p, d = ukpv.load(name, meta, year)
        m = ukpv.solar_mask(d, lat, lon)
        keep = covered(p, capacity)
        print(name, year, 'daylight rows under the mark, share', round(float(1 - keep[m].mean()), 4), flush=True)
        scoring[str(year)] = (p, m & keep)
    table = campaign.run_fleet(pv, mask, dates, capacity, ukpv.features(meta), scoring, round(len(meta) / 3), use_gp=name != 'national', coords=ukpv.coords(meta))
    table.insert(0, 'fleet', name)
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT / f'uk_{name}.csv', index=False)
    print(name, 'rows', len(table), 'seconds', round(time.time() - t0), flush=True)


def main():
    run_campaign.FROZEN += ('sensitivity.py',)
    run_campaign.require_frozen()
    with mp.Pool(run_campaign.PROCESSES) as pool:
        pool.map(run_uk, ukpv.regions(ukpv.cohort())[0] + ['national'], chunksize=1)


if __name__ == '__main__':
    main()
