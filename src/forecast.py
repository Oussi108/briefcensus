"""Forecast arm of protocol v2. Models train on the chosen monitors' estimate only, because an operator has no fleet truth, and are scored on the true evaluation group.
There is no tuning: every model setting is fixed here, so the test year plays no part in choosing one.

python forecast.py uk-debug                       open at any time
python forecast.py uk-confirm | ausgrid           refuse to run until the hash of this file is in RUN_LOG.md
"""
import multiprocessing as mp
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

import ausgrid
import campaign
import run_campaign
import ukpv
from extras import picks_of
from kill_test import fleet_ratio, rows_of
from kill_test2 import day_rule
from sensitivity import covered

OUT = Path(__file__).resolve().parents[1] / 'results' / 'forecast'
HORIZONS = (1, 2, 4, 6, 12)                                         # slots of 30 min: 0.5, 1, 2, 3 and 6 h
BUDGETS = (5, 10, 20)
LENGTHS = ('4w', '3m', '1y')
DRAWS = 5
SLOTS = 48
RIDGE_ALPHA = 1.0
GBM = dict(n_estimators=300, learning_rate=0.05, num_leaves=31, min_child_samples=20, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, n_jobs=1, verbose=-1)


def sun(dates, lat, shift):
    """Sine of solar elevation, shape (days, slots). shift holds minutes per date from clock time to mean solar time."""
    doy = np.array([d.timetuple().tm_yday for d in dates])
    gamma = 2 * np.pi * (doy - 1) / 365
    decl = 0.006918 - 0.399912 * np.cos(gamma) + 0.070257 * np.sin(gamma) - 0.006758 * np.cos(2 * gamma) + 0.000907 * np.sin(2 * gamma)
    eqt = 229.18 * (0.000075 + 0.001868 * np.cos(gamma) - 0.032077 * np.sin(gamma) - 0.014615 * np.cos(2 * gamma) - 0.040849 * np.sin(2 * gamma))
    solar = ((np.arange(SLOTS) + 0.5) * 30)[None, :] + (shift + eqt)[:, None]
    hour = np.deg2rad(solar / 4 - 180)
    phi = np.deg2rad(lat)
    return np.sin(phi) * np.sin(decl)[:, None] + np.cos(phi) * np.cos(decl)[:, None] * np.cos(hour)


def grid_estimate(pv, capacity, homes):
    """The monitors' estimate on every slot of the year. The failed-day test sees all slots, which differ from daylight by about 0.4% of energy."""
    return day_rule(pv, np.ones(pv.shape[1:], dtype=bool), capacity, np.asarray(homes)).reshape(pv.shape[1], SLOTS)


def month_profile(y, months_of):
    """Mean by month and slot from a training year, as an array of (12, slots)."""
    out = np.zeros((12, SLOTS))
    for m in range(12):
        days = months_of == m + 1
        if days.any():
            out[m] = y[days].mean(axis=0)
    return out


def features(y, profile, months_of, sine, h):
    """One row per origin t, for a target at t + h. Rows start after a full day of lags."""
    series = y.reshape(-1)
    p = profile[months_of - 1].reshape(-1)
    s = sine.reshape(-1)
    t = np.arange(SLOTS, len(series) - h)
    index = np.clip(series[t] / np.maximum(p[t], 0.02), 0, 3)
    recent = np.stack([series[t - i] for i in range(6)]).mean(axis=0)
    day = (t + h) / SLOTS % 365 / 365 * 2 * np.pi
    x = np.column_stack([series[t], series[t - 1], series[t - 2], series[t - 3], series[t + h - SLOTS], recent, index, p[t], p[t + h], s[t], s[t + h], np.sin(day), np.cos(day)])
    return x, t + h, series[t + h]


def persistence(y, profile, months_of, h):
    """Smart persistence on the month-slot profile: the latest ratio to the profile carries forward."""
    series, p = y.reshape(-1), profile[months_of - 1].reshape(-1)
    t = np.arange(SLOTS, len(series) - h)
    ratio = np.where(p[t] > 0.02, np.clip(series[t] / np.maximum(p[t], 0.02), 0, 3), 1.0)
    return ratio * p[t + h]


def ridge(x, y, test):
    mean, scale = x.mean(0), np.maximum(x.std(0), 1e-9)
    a = (x - mean) / scale
    w = np.linalg.solve(a.T @ a + RIDGE_ALPHA * np.eye(a.shape[1]), a.T @ (y - y.mean()))
    return ((test - mean) / scale) @ w + y.mean()


def boosted(x, y, test):
    return lgb.LGBMRegressor(random_state=0, **GBM).fit(x, y).predict(test)


MODELS = dict(ridge=ridge, lightgbm=boosted)


def score_set(homes, data):
    """Every model and baseline at every horizon for one set of monitors. Returns (model, horizon, nrmse, bias) rows."""
    train = grid_estimate(data['train_pv'], data['capacity'], homes)
    test = grid_estimate(data['test_pv'], data['capacity'], homes)
    profile = month_profile(train, data['train_months'])
    rows = []
    for h in HORIZONS:
        x, target_t, y = features(train, profile, data['train_months'], data['train_sine'], h)
        use = data['train_mask'].reshape(-1)[target_t]
        x_test, target_test, _ = features(test, profile, data['test_months'], data['test_sine'], h)
        keep = data['test_mask'].reshape(-1)[target_test]
        truth = data['truth'].reshape(-1)[target_test][keep]
        preds = dict(persistence=persistence(test, profile, data['test_months'], h)[keep], profile=profile[data['test_months'] - 1].reshape(-1)[target_test][keep])
        for name, model in MODELS.items():
            preds[name] = np.clip(model(x[use], y[use], x_test[keep]), 0, None)
        for name, pred in preds.items():
            rows.append((name, h, float(np.sqrt(np.mean((pred - truth) ** 2)) / truth.mean() * 100), float((pred - truth).mean() / truth.mean() * 100)))
    return rows


def run_fleet(name, sel_pv, sel_mask, sel_dates, capacity, train, test, hold_out, log=None):
    """train and test are (pv, dates, mask, sine)."""
    n = len(capacity)
    data = dict(capacity=capacity, train_pv=train[0], test_pv=test[0], train_months=np.array([d.month for d in train[1]]), test_months=np.array([d.month for d in test[1]]),
                train_mask=train[2], test_mask=test[2], train_sine=train[3], test_sine=test[3])
    rows = []
    t0 = time.time()
    for seed in campaign.SEEDS:
        rng = np.random.default_rng(seed)
        order = rng.permutation(n)
        held, candidates = np.sort(order[:hold_out]), np.sort(order[hold_out:])
        truth = np.zeros(test[2].shape)
        truth[test[2]] = fleet_ratio(rows_of(test[0], test[2]), capacity, held)
        data['truth'] = truth

        def record(arm, length, start, k, draw, homes):
            for model, h, e, b in score_set(homes, data):
                rows.append((name, seed, arm, length, start, k, draw, model, h, e, b))

        picked = picks_of(sel_pv, sel_mask, sel_dates, capacity, candidates)
        for (length, start), chosen in picked.items():
            if length in LENGTHS:
                for k in BUDGETS:
                    record('method', length, start, k, 0, chosen[:k])
        draw_rng = np.random.default_rng([seed, 77])
        for k in BUDGETS:
            for draw in range(DRAWS):
                record('random', '', 0, k, draw, draw_rng.choice(candidates, k, replace=False))
        record('all', '', 0, len(candidates), 0, candidates)
        if log:
            log(f'{name} partition {seed} done, {round(time.time() - t0)} s')
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=['fleet', 'seed', 'arm', 'length', 'start', 'k', 'draw', 'model', 'horizon', 'nrmse', 'bias']).to_csv(OUT / f'{name}.csv', index=False)


def say(message):
    print(message, flush=True)


def run_uk(name):
    meta = ukpv.fleet_of(ukpv.cohort(), name)
    lat, lon = float(meta.latitude_rounded.mean()), float(meta.longitude_rounded.mean())

    capacity = meta.kWp.to_numpy()

    def year(y):
        pv, dates = ukpv.load(name, meta, y)
        return pv, dates, ukpv.solar_mask(dates, lat, lon) & covered(pv, capacity), sun(dates, lat, np.full(len(dates), 4 * lon))

    sel_pv, sel_dates = ukpv.load(name, meta, ukpv.CAMPAIGN_YEAR)
    run_fleet(f'uk_{name}', sel_pv, ukpv.solar_mask(sel_dates, lat, lon), sel_dates, capacity, year(2019), year(2020), round(len(meta) / 3), log=say)


def run_ausgrid():
    sel = ausgrid.load(['Y1'])

    def year(y):
        d = ausgrid.load([y])
        shift = 4 * (ausgrid.LON - 150) - 60 * np.array([ausgrid.daylight_saving(x) for x in d['dates']])
        return d['pv'], d['dates'], ausgrid.daylight(d['dates']) & covered(d['pv'], d['capacity']), sun(d['dates'], ausgrid.LAT, shift)

    run_fleet('ausgrid', sel['pv'], ausgrid.daylight(sel['dates']), sel['dates'], sel['capacity'], year('Y2'), year('Y3'), 100, log=say)


def require_frozen():
    run_campaign.FROZEN += ('extras.py', 'forecast.py', 'sensitivity.py')
    run_campaign.require_frozen()


def main():
    what = sys.argv[1]
    if what == 'uk-debug':
        run_uk(ukpv.regions(ukpv.cohort())[1])
    elif what == 'ausgrid':
        require_frozen()
        run_ausgrid()
    elif what == 'uk-confirm':
        require_frozen()
        with mp.Pool(run_campaign.PROCESSES) as pool:
            pool.map(run_uk, ukpv.regions(ukpv.cohort())[0], chunksize=1)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
