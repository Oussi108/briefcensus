"""Secondary outcomes with outage rows removed from selection and scoring, as logged in RUN_LOG.md. Monitor loss and the forecast arm use the second-sample fleets.

python clean_followup.py extras | forecast | survival
"""
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import campaign
import clean_run
import extras
import forecast
import run_campaign
import ukpv
from sensitivity import covered

OUT = Path(__file__).resolve().parents[1] / 'results' / 'survival'


def clean_selection(meta, label):
    lat, lon = float(meta.latitude_rounded.mean()), float(meta.longitude_rounded.mean())
    pv, dates = ukpv.load(label, meta, ukpv.CAMPAIGN_YEAR)
    raw = ukpv.solar_mask(dates, lat, lon)
    return pv, dates, raw, clean_run.selection_mask(pv, meta.kWp.to_numpy(), raw, dates)[0], lat, lon


def extras_job(job):
    name, label, meta = job
    t0 = time.time()
    capacity = meta.kWp.to_numpy()
    pv, dates, _, mask, lat, lon = clean_selection(meta, label)
    scored, later = ukpv.load(label, meta, 2019)
    extras.run_fleet(label, pv, mask, dates, capacity, scored, ukpv.solar_mask(later, lat, lon) & covered(scored, capacity), round(len(meta) / 3), labels=extras.uk_labels(meta))
    print(label, 'extras seconds', round(time.time() - t0), flush=True)


def forecast_job(job):
    name, label, meta = job
    capacity = meta.kWp.to_numpy()
    pv, dates, _, mask, lat, lon = clean_selection(meta, label)

    def year(y):
        p, d = ukpv.load(label, meta, y)
        return p, d, ukpv.solar_mask(d, lat, lon) & covered(p, capacity), forecast.sun(d, lat, np.full(len(d), 4 * lon))

    forecast.run_fleet(f'uk_{label}', pv, mask, dates, capacity, year(2019), year(2020), round(len(meta) / 3), log=forecast.say)


def survival_job(job):
    """How far each kind of pick keeps reporting on the 2019 rows where under half of the fleet reports, and its error on the other rows."""
    name, label, meta = job
    t0 = time.time()
    capacity = meta.kWp.to_numpy()
    pv, dates, raw, mask, lat, lon = clean_selection(meta, label)
    scored, later = ukpv.load(label, meta, 2019)
    day = ukpv.solar_mask(later, lat, lon)
    keep = covered(scored, capacity)
    outage = day & ~keep
    rows = []
    for seed in campaign.SEEDS:
        order = np.random.default_rng(seed).permutation(len(meta))
        held, candidates = np.sort(order[:round(len(meta) / 3)]), np.sort(order[round(len(meta) / 3):])
        draws = np.random.default_rng([seed, 55])

        def record(kind, length, start, k, homes):
            homes = np.asarray(homes)
            rows.append((name, seed, kind, length, start, k, float(np.isfinite(scored[homes][:, outage]).any(axis=0).mean()), float(np.isfinite(scored[homes][:, outage]).mean())))

        for kind, m in (('raw', raw), ('clean', mask)):
            for (length, start), chosen in extras.picks_of(pv, m, dates, capacity, candidates).items():
                for k in (5, 10, 20):
                    record(kind, length, start, k, chosen[:k])
        for k in (5, 10, 20):
            for _ in range(campaign.DRAWS):
                record('random', '', 0, k, draws.choice(candidates, k, replace=False))
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=['fleet', 'seed', 'kind', 'length', 'start', 'k', 'any_reporting', 'share_reporting']).to_csv(OUT / f'{label}.csv', index=False)
    print(label, 'outage rows in 2019', int(outage.sum()), 'of', int(day.sum()), 'seconds', round(time.time() - t0), flush=True)


def second_jobs(m):
    seconds = {f: clean_run.second_fleet(m, f) for f in ukpv.regions(m)[0]}
    return [(f, f + 'b', s) for f, s in seconds.items() if len(s) >= clean_run.MIN_SECOND]


def main():
    run_campaign.FROZEN += ('sensitivity.py', 'clean_run.py', 'clean_followup.py')
    run_campaign.require_frozen()
    what = sys.argv[1]
    m = ukpv.cohort()
    if what == 'survival':
        jobs, work = [(f, f, ukpv.fleet_of(m, f)) for f in ukpv.regions(m)[0]], survival_job
    else:
        jobs, work = second_jobs(m), dict(extras=extras_job, forecast=forecast_job)[what]
    with mp.Pool(run_campaign.PROCESSES) as pool:
        pool.map(work, jobs, chunksize=1)


if __name__ == '__main__':
    main()
