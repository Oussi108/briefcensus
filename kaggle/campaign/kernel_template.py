"""Kaggle CPU run of protocol v2. Built by build.py, which embeds the source files. It uses no GPU hours.

It stops itself when it ends or fails, and a watchdog stops it before the time limit. Results go to /kaggle/working/results.
"""
import base64
import hashlib
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

MODE = '__MODE__'
LIMIT_HOURS = __LIMIT_HOURS__
SOURCES = __SOURCES__

JOBS = dict(debug=[('run_campaign.py', 'ausgrid-dev'), ('run_campaign.py', 'uk-debug')], confirm=[('run_campaign.py', 'uk-confirm')],
            test2=[('extras.py', 'ausgrid-dev'), ('extras.py', 'uk-debug'), ('forecast.py', 'uk-debug')],
            holdout=[('run_campaign.py', 'ausgrid-holdout'), ('extras.py', 'ausgrid-holdout'), ('forecast.py', 'ausgrid')],
            extras=[('extras.py', 'uk-confirm')], forecast=[('forecast.py', 'uk-confirm')],
            coverage=[('sensitivity.py', 'uk')], forecast2=[('forecast.py', 'uk-confirm')],
            clean=[('clean_run.py', 'same')], second=[('clean_run.py', 'second')],
            followup=[('clean_followup.py', 'survival'), ('clean_followup.py', 'extras'), ('clean_followup.py', 'forecast')])

ROOT = Path('/tmp/p3')
WORK = Path('/kaggle/working')
INPUT = Path('/kaggle/input')


def watchdog():
    time.sleep(LIMIT_HOURS * 3600)
    print('watchdog: time limit reached, stopping', flush=True)
    os._exit(3)


def setup():
    """Rebuilds the folder layout the code expects, from the flat private dataset."""
    (ROOT / 'src').mkdir(parents=True)
    for name, text in SOURCES.items():
        data = base64.b64decode(text)
        (ROOT / name).write_bytes(data)
        print('source', name, hashlib.sha256(data).hexdigest(), flush=True)
    (WORK / 'results').mkdir(exist_ok=True)
    (ROOT / 'results').symlink_to(WORK / 'results')
    data = next(p.parent for p in INPUT.rglob('metadata.csv'))
    print('dataset at', data, flush=True)
    uk = ROOT / 'data_external' / 'uk_pv'
    uk.mkdir(parents=True)
    for name in ('metadata.csv', 'bad_data.csv'):
        (uk / name).symlink_to(data / name)
    for part in data.glob('y*_m*.parquet'):
        year, month = part.stem[1:5], part.stem[-2:]
        folder = uk / '30_minutely' / f'year={year}' / f'month={month}'
        folder.mkdir(parents=True)
        (folder / 'data.parquet').symlink_to(part)
    (ROOT / 'cache').mkdir()
    for part in INPUT.rglob('ausgrid_*.npz'):
        (ROOT / 'cache' / part.name).symlink_to(part)


def audit():
    """Debug cell only: the clock check and data counts that caught the error in Ausgrid Run 1."""
    sys.path.insert(0, str(ROOT / 'src'))
    import numpy as np
    import ukpv
    m = ukpv.cohort()
    confirm, debug = ukpv.regions(m)
    print('cohort', len(m), '| regions', len(confirm), confirm, '| debug cell', debug, flush=True)
    meta = ukpv.fleet_of(m, debug)
    pv, dates = ukpv.load(debug, meta, ukpv.CAMPAIGN_YEAR)
    print('debug fleet', pv.shape, '| missing share', round(float(np.isnan(pv).mean()), 3), flush=True)
    months = np.array([d.month for d in dates])
    fleet = np.nanmean(pv, axis=0)
    lon = float(meta.longitude_rounded.mean())
    noon = 12 - 4 * lon / 60
    profile = {int(k): np.nan_to_num(np.nanmean(fleet[months == k], axis=0)) for k in np.unique(months)}
    centroid = {k: round(float(((np.arange(48) + .5) / 2 * p).sum() / p.sum()), 2) for k, p in profile.items()}
    print('output centroid in UTC hours by month', centroid, '| solar noon near', round(noon, 2), flush=True)
    mask = ukpv.solar_mask(dates, float(meta.latitude_rounded.mean()), lon)
    print('energy share outside the daylight mask', round(float(np.nansum(fleet[~mask]) / np.nansum(fleet)), 4), flush=True)


def run(script, argument):
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    code = subprocess.call([sys.executable, '-W', 'ignore', script, argument], cwd=ROOT / 'src', env=env)
    print(script, argument, 'exit code', code, flush=True)
    return code


def main():
    threading.Thread(target=watchdog, daemon=True).start()
    setup()
    if MODE == 'debug':
        audit()
    code = 0
    for script, argument in JOBS[MODE]:
        code = run(script, argument)
        if code:
            break
    sys.exit(code)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
