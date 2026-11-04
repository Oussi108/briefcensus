"""Runs protocol v2 on a fleet and writes results/campaign/<fleet>.csv.

python run_campaign.py ausgrid-dev | uk-debug       open at any time
python run_campaign.py ausgrid-holdout | uk-confirm  refuse to run until the hashes of this code are in RUN_LOG.md
"""
import hashlib
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

import ausgrid
import campaign
import ukpv

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / 'results' / 'campaign'
FROZEN = ('campaign.py', 'ukpv.py', 'run_campaign.py', 'kill_test.py', 'kill_test2.py', 'ausgrid.py')
PROCESSES = 4


def require_frozen():
    log = (HERE.parent / 'RUN_LOG.md').read_text(encoding='utf-8')
    missing = [f for f in FROZEN if hashlib.sha256((HERE / f).read_bytes()).hexdigest() not in log]
    if missing:
        sys.exit(f'refused: hash not in RUN_LOG.md for {missing}')


def ausgrid_features(data):
    """Ausgrid gives no tilt, orientation or coordinates, so its metadata arm has only capacity band and postcode district."""
    band = np.digitize(data['capacity'], [1.5, 2, 3, 5])
    district = data['postcode'] // 100
    values = np.unique(district)
    return np.vstack([np.eye(5)[band].T, (district[None, :] == values[:, None]).astype(float)])


def run_ausgrid(name, selection, scored):
    t0 = time.time()
    sel, scores = ausgrid.load(selection), {y: ausgrid.load([y]) for y in scored}
    table = campaign.run_fleet(sel['pv'], ausgrid.daylight(sel['dates']), sel['dates'], sel['capacity'], ausgrid_features(sel),
                               {y: (s['pv'], ausgrid.daylight(s['dates'])) for y, s in scores.items()}, 100, log=lambda m: print(name, m, round(time.time() - t0), 's', flush=True))
    table.insert(0, 'fleet', name)
    table.to_csv(OUT / f'{name}.csv', index=False)
    print(name, 'rows', len(table), 'seconds', round(time.time() - t0), flush=True)


def run_uk(name):
    t0 = time.time()
    meta = ukpv.fleet_of(ukpv.cohort(), name)
    lat, lon = float(meta.latitude_rounded.mean()), float(meta.longitude_rounded.mean())
    pv, dates = ukpv.load(name, meta, ukpv.CAMPAIGN_YEAR)
    scoring = {}
    for year in (2019, 2020, 2021):
        p, d = ukpv.load(name, meta, year)
        scoring[str(year)] = (p, ukpv.solar_mask(d, lat, lon))
    hold_out = round(len(meta) / 3)
    table = campaign.run_fleet(pv, ukpv.solar_mask(dates, lat, lon), dates, meta.kWp.to_numpy(), ukpv.features(meta), scoring, hold_out, use_gp=name != 'national', coords=ukpv.coords(meta))
    table.insert(0, 'fleet', name)
    table.to_csv(OUT / f'uk_{name}.csv', index=False)
    print(name, 'systems', len(meta), 'rows', len(table), 'seconds', round(time.time() - t0), flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    what = sys.argv[1]
    if what == 'ausgrid-dev':
        run_ausgrid('ausgrid_dev', ['Y1'], ['Y2'])
    elif what == 'uk-debug':
        run_uk(ukpv.regions(ukpv.cohort())[1])
    elif what == 'ausgrid-holdout':
        require_frozen()
        run_ausgrid('ausgrid_holdout', ['Y2'], ['Y3'])
    elif what == 'uk-confirm':
        require_frozen()
        fleets = ukpv.regions(ukpv.cohort())[0] + ['national']
        print('fleets', fleets, flush=True)
        with mp.Pool(PROCESSES) as pool:
            pool.map(run_uk, fleets, chunksize=1)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
