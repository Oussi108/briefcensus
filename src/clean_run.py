"""Runs logged in RUN_LOG.md after the coverage sensitivity: rows where under half of the fleet's capacity reports are removed from both selection and scoring.

python clean_run.py same      the same fleets as the confirmation run
python clean_run.py second    fleets of cohort systems no earlier run has read, in the same cells
"""
import multiprocessing as mp
import sys
import time
import zlib
from pathlib import Path

import numpy as np

import campaign
import run_campaign
import ukpv
from sensitivity import covered

OUT = Path(__file__).resolve().parents[1] / 'results' / 'clean'
MIN_ROWS, MIN_SECOND = 0.25, 150


def second_fleet(m, name):
    """Up to 300 systems of a cell that neither its confirmation fleet nor the national fleet holds."""
    used = set(ukpv.fleet_of(m, name).ss_id) | set(ukpv.fleet_of(m, 'national').ss_id)
    pool = m[(m.cell == name) & ~m.ss_id.isin(used)]
    size = min(ukpv.FLEET, len(pool))
    rng = np.random.default_rng(zlib.crc32((name + '-second').encode()))
    return pool.iloc[np.sort(rng.choice(len(pool), size, replace=False))].reset_index(drop=True) if size else pool


def selection_mask(pv, capacity, raw, dates):
    """Daylight rows with coverage. A window left with under a quarter of its rows keeps them all, because it would have nothing to select on."""
    mask = raw & covered(pv, capacity)
    restored = 0
    for _, _, first, days in campaign.windows_of(dates):
        if mask[first:first + days].sum() < MIN_ROWS * raw[first:first + days].sum():
            mask[first:first + days] = raw[first:first + days]
            restored += 1
    return mask, restored


def run_fleet(job):
    name, label, meta = job
    t0 = time.time()
    lat, lon = float(meta.latitude_rounded.mean()), float(meta.longitude_rounded.mean())
    capacity = meta.kWp.to_numpy()
    pv, dates = ukpv.load(label, meta, ukpv.CAMPAIGN_YEAR)
    raw = ukpv.solar_mask(dates, lat, lon)
    mask, restored = selection_mask(pv, capacity, raw, dates)
    scoring = {}
    for year in (2019, 2020, 2021):
        p, d = ukpv.load(label, meta, year)
        scoring[str(year)] = (p, ukpv.solar_mask(d, lat, lon) & covered(p, capacity))
    table = campaign.run_fleet(pv, mask, dates, capacity, ukpv.features(meta), scoring, round(len(meta) / 3), use_gp=name != 'national', coords=ukpv.coords(meta))
    table.insert(0, 'fleet', name)
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT / f'{label}.csv', index=False)
    print(name, label, 'systems', len(meta), 'selection rows removed', round(float(1 - mask[raw].mean()), 4), 'windows restored', restored, 'seconds', round(time.time() - t0), flush=True)


def main():
    run_campaign.FROZEN += ('sensitivity.py', 'clean_run.py')
    run_campaign.require_frozen()
    m = ukpv.cohort()
    fleets = ukpv.regions(m)[0]
    if sys.argv[1] == 'same':
        jobs = [(f, f, ukpv.fleet_of(m, f)) for f in fleets + ['national']]
    else:
        seconds = {f: second_fleet(m, f) for f in fleets}
        print('unread systems by cell', {f: len(s) for f, s in seconds.items()}, flush=True)
        jobs = [(f, f + 'b', s) for f, s in seconds.items() if len(s) >= MIN_SECOND]
    with mp.Pool(run_campaign.PROCESSES) as pool:
        pool.map(run_fleet, jobs, chunksize=1)


if __name__ == '__main__':
    main()
