"""Kill test of protocol v1, on the development split only: select from Y1, score on Y2. Y3 is never read here.

Every arm uses the same estimator, the chosen homes' capacity-weighted ratio with no fitted weights.
Writes results/kill_test.json.
"""
import json
import time
from pathlib import Path

import numpy as np

import ausgrid

OUT = Path(__file__).resolve().parents[1] / 'results'
SEEDS, BUDGETS, KILL = (11, 23, 37, 51, 73), (1, 2, 3, 5, 10, 20, 50), (5, 10, 20)
DRAWS, HOLD_OUT = 40, 100
WINDOW, QUANTILE = 14, 0.9                                          # days each side, for the net-load baseline


def fleet_ratio(x, capacity, homes):
    """x has shape (rows, homes). A missing home drops out of both the sum and the capacity for that row."""
    sub, w = x[:, homes], capacity[homes]
    ok = np.isfinite(sub)
    return np.where(ok, sub * w, 0).sum(1) / np.maximum((ok * w).sum(1), 1e-9)


def net_signal(net):
    """PV signal for each home: a rolling upper quantile of its net load in the same slot, minus its net load, floored at 0."""
    homes, days, slots = net.shape
    out = np.full(net.shape, np.nan, dtype=np.float32)
    span = 2 * WINDOW + 1
    for h in range(homes):
        padded = np.pad(net[h], ((WINDOW, WINDOW), (0, 0)), mode='reflect')
        windows = np.lib.stride_tricks.sliding_window_view(padded, span, axis=0)
        ordered = np.sort(windows, axis=-1)                         # missing values sort to the end
        count = np.isfinite(windows).sum(-1)
        pick = np.maximum((count - 1) * QUANTILE, 0).astype(int)
        base = np.take_along_axis(ordered, pick[..., None], axis=-1)[..., 0]
        out[h] = np.maximum(base - net[h], 0)
    return out


def signature(signal, dates):
    """Each home's signal averaged by month and slot, then repeated on its rows, which reduces load noise."""
    months = np.array([d.month for d in dates])
    out = signal.copy()
    for m in np.unique(months):
        out[:, months == m] = np.nanmean(signal[:, months == m], axis=1, keepdims=True)
    return out


def greedy(x, capacity, candidates, kmax, target):
    """Forward search: add the candidate that brings the chosen homes' capacity-weighted ratio closest to target."""
    filled = np.nan_to_num(x[:, candidates]) * capacity[candidates]
    sum_, weight, chosen, free = np.zeros(len(x)), 0.0, [], np.ones(len(candidates), dtype=bool)
    for _ in range(kmax):
        ratio = (sum_[:, None] + filled) / (weight + capacity[candidates])[None, :]
        err = np.mean((ratio - target[:, None]) ** 2, axis=0)
        err[~free] = np.inf
        j = int(np.argmin(err))
        free[j] = False
        chosen.append(int(candidates[j]))
        sum_ = sum_ + filled[:, j]
        weight += capacity[candidates[j]]
    return chosen


def rows_of(cube, mask):
    return cube[:, mask].T                                          # (rows, homes)


def main():
    t0 = time.time()
    OUT.mkdir(exist_ok=True)
    dev_sel, dev_score = ausgrid.load(['Y1']), ausgrid.load(['Y2'])
    capacity = dev_sel['capacity']
    every = np.arange(ausgrid.HOMES)
    sel_day, score_day = ausgrid.daylight(dev_sel['dates']), ausgrid.daylight(dev_score['dates'])
    print('loaded', round(time.time() - t0), 's | daylight rows', sel_day.sum(), score_day.sum(), flush=True)

    # clock check: the fleet's output centroid by month should sit near solar noon all year if the clock has no daylight saving
    fleet = np.nanmean(dev_sel['pv'], axis=0)
    months = np.array([d.month for d in dev_sel['dates']])
    centroid = {int(m): round(float(((np.arange(48) + .5) / 2 * fleet[months == m].mean(0)).sum() / fleet[months == m].mean(0).sum()), 2) for m in np.unique(months)}
    print('fleet output centroid, clock hours, by month', centroid, flush=True)

    signal = net_signal(dev_sel['net'])
    print('net signal built', round(time.time() - t0), 's', flush=True)
    views = dict(census=rows_of(dev_sel['pv'], sel_day), N1=rows_of(signal, sel_day), N2=rows_of(signature(signal, dev_sel['dates']), sel_day))
    truth = rows_of(dev_score['pv'], score_day)
    agreement = np.corrcoef(fleet_ratio(views['census'], capacity, every), fleet_ratio(views['N1'], capacity, every))[0, 1]
    print('fleet signal against true fleet PV in Y1, correlation', round(float(agreement), 4), flush=True)
    targets = {name: fleet_ratio(v, capacity, every) for name, v in views.items()}
    picks = {name: {} for name in views}
    table = {name: {k: [] for k in BUDGETS} for name in ('random', *views)}
    bias = {name: {k: [] for k in BUDGETS} for name in table}

    def score(homes, y, mean_y):
        pred = fleet_ratio(truth, capacity, np.asarray(homes))
        return float(np.sqrt(np.mean((pred - y) ** 2)) / mean_y * 100), float((pred - y).mean() / mean_y * 100)

    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        order = rng.permutation(ausgrid.HOMES)
        held, candidates = np.sort(order[:HOLD_OUT]), np.sort(order[HOLD_OUT:])
        y = fleet_ratio(truth, capacity, held)
        mean_y = float(y.mean())
        for name, view in views.items():
            chosen = greedy(view, capacity, candidates, max(BUDGETS), targets[name])
            picks[name][seed] = chosen
            for k in BUDGETS:
                e, b = score(chosen[:k], y, mean_y)
                table[name][k].append(e)
                bias[name][k].append(b)
        for k in BUDGETS:
            draws = [score(rng.choice(candidates, k, replace=False), y, mean_y) for _ in range(DRAWS)]
            table['random'][k].append(float(np.median([d[0] for d in draws])))
            bias['random'][k].append(float(np.median([d[1] for d in draws])))
        print('partition', seed, {n: round(table[n][10][-1], 2) for n in table}, flush=True)

    mean = {n: {k: float(np.mean(v)) for k, v in t.items()} for n, t in table.items()}
    recovery = {n: {k: (mean['random'][k] - mean[n][k]) / (mean['random'][k] - mean['census'][k]) for k in KILL} for n in ('N1', 'N2')}
    median = {n: float(np.median(list(r.values()))) for n, r in recovery.items()}
    gain = all(mean['census'][k] < mean['random'][k] for k in KILL)
    best = max(median, key=median.get)
    verdict = 'NO GAIN TO RECOVER' if not gain else 'PASS' if median[best] >= 0.5 else 'FAIL'

    print('\nnRMSE % on Y2, mean of five partitions')
    print('k     random  census      N1      N2')
    for k in BUDGETS:
        print(f"{k:<4}{mean['random'][k]:8.2f}{mean['census'][k]:8.2f}{mean['N1'][k]:8.2f}{mean['N2'][k]:8.2f}")
    print('recovery', {n: {k: round(v, 3) for k, v in r.items()} for n, r in recovery.items()})
    print('median recovery', {n: round(v, 3) for n, v in median.items()}, '| better arm', best, '| verdict', verdict)
    overlap = {k: float(np.mean([len(set(picks[best][s][:k]) & set(picks['census'][s][:k])) / k for s in SEEDS])) for k in KILL}
    print('share of homes in common with census greedy', {k: round(v, 3) for k, v in overlap.items()})
    (OUT / 'kill_test.json').write_text(json.dumps(dict(split='select Y1, score Y2', seeds=SEEDS, nrmse=mean, per_partition=table, bias=bias, recovery=recovery,
                                                        median_recovery=median, better_arm=best, verdict=verdict, census_gain=gain, overlap_with_census=overlap,
                                                        picks=picks, clock_centroid=centroid, signal_correlation=float(agreement), seconds=round(time.time() - t0)), indent=1))
    print('seconds', round(time.time() - t0))


if __name__ == '__main__':
    main()
