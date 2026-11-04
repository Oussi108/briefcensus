"""Census-length question fixed in RUN_LOG.md: how much of the one-year census gain survives a short metering campaign?
Development split only: select from a window of Y1, score on all of Y2. Y3 is never read. Writes results/census_length.json.
"""
import datetime as dt
import json
import time
from pathlib import Path

import numpy as np

import ausgrid
from kill_test import BUDGETS, HOLD_OUT, KILL, SEEDS, fleet_ratio, greedy, rows_of
from kill_test2 import day_rule

OUT = Path(__file__).resolve().parents[1] / 'results'
LENGTHS = {'4w': 28, '3m': 91}
STARTS = {'Jul': dt.date(2010, 7, 1), 'Oct': dt.date(2010, 10, 1), 'Jan': dt.date(2011, 1, 1), 'Apr': dt.date(2011, 4, 1)}
PASS = 0.5


def kept(table, reference, use):
    """Median over the kill budgets of the share of the census gain kept, on the partitions in use."""
    random, census = reference['random'], reference['census']
    shares = []
    for k in KILL:
        r, c, e = (float(np.mean(np.asarray(t[str(k)] if t is not table else t[k])[use])) for t in (random, census, table))
        shares.append((r - e) / (r - c))
    return float(np.median(shares))


def main():
    t0 = time.time()
    sel, scored = ausgrid.load(['Y1']), ausgrid.load(['Y2'])
    capacity = sel['capacity']
    every = np.arange(ausgrid.HOMES)
    day_sel, day_score = ausgrid.daylight(sel['dates']), ausgrid.daylight(scored['dates'])
    y_rows = rows_of(scored['pv'], day_score)
    previous = json.loads((OUT / 'kill_test2.json').read_text())
    reference = previous['per_partition']

    windows = {(length, name): (start - sel['dates'][0]).days for length in LENGTHS for name, start in STARTS.items()}
    table = {key: {k: [] for k in BUDGETS} for key in windows}
    picks = {f'{a}_{b}': {} for a, b in windows}
    whole = []
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        order = rng.permutation(ausgrid.HOMES)
        held, candidates = np.sort(order[:HOLD_OUT]), np.sort(order[HOLD_OUT:])
        y = fleet_ratio(y_rows, capacity, held)

        def score(homes):
            return float(np.sqrt(np.mean((day_rule(scored['pv'], day_score, capacity, homes) - y) ** 2)) / y.mean() * 100)

        full = rows_of(sel['pv'], day_sel)
        whole.append(greedy(full, capacity, candidates, max(BUDGETS), fleet_ratio(full, capacity, every)) == previous['picks']['census'][str(seed)])
        for (length, name), first in windows.items():
            last = first + LENGTHS[length]
            view = rows_of(sel['pv'][:, first:last], day_sel[first:last])
            chosen = greedy(view, capacity, candidates, max(BUDGETS), fleet_ratio(view, capacity, every))
            picks[f'{length}_{name}'][seed] = chosen
            for k in BUDGETS:
                table[(length, name)][k].append(score(chosen[:k]))
        print('partition', seed, round(time.time() - t0), 's', flush=True)
    print('one-year picks reproduce the census arm in every partition:', all(whole))

    parts = np.arange(len(SEEDS))
    mean = {f'{a}_{b}': {k: float(np.mean(v)) for k, v in t.items()} for (a, b), t in table.items()}
    shares = {f'{a}_{b}': kept(t, reference, parts) for (a, b), t in table.items()}
    summary = {}
    for length in LENGTHS:
        by_start = {name: shares[f'{length}_{name}'] for name in STARTS}
        left_out = {s: float(np.mean([kept(table[(length, name)], reference, np.delete(parts, i)) for name in STARTS])) for i, s in enumerate(SEEDS)}
        summary[length] = dict(by_start=by_start, average=float(np.mean(list(by_start.values()))), left_out=left_out, worst_left_out=min(left_out.values()),
                               starts_passing=int(sum(v >= PASS for v in by_start.values())))
    three = summary['3m']
    verdict = 'CLEAR GAIN' if three['average'] >= PASS and three['worst_left_out'] >= PASS and three['starts_passing'] >= 3 else 'NO CLEAR GAIN'

    print('\nnRMSE % on Y2 with the day rule, mean of five partitions')
    head = list(mean)
    print('k    ' + ' random census ' + ''.join(f'{n:>8}' for n in head))
    for k in BUDGETS:
        print(f"{k:<4} {previous['nrmse']['random'][str(k)]:7.2f}{previous['nrmse']['census'][str(k)]:7.2f} " + ''.join(f'{mean[n][k]:8.2f}' for n in head))
    print()
    for length, s in summary.items():
        print(length, 'share of gain kept by start', {n: round(v, 3) for n, v in s['by_start'].items()}, 'average', round(s['average'], 3),
              'worst left out', round(s['worst_left_out'], 3), 'starts passing', s['starts_passing'])
    print('verdict', verdict, '| seconds', round(time.time() - t0))
    (OUT / 'census_length.json').write_text(json.dumps(dict(split='select window of Y1, score Y2', estimator='day rule', seeds=SEEDS, nrmse=mean, shares=shares, summary=summary,
                                                            verdict=verdict, picks=picks, per_partition={f'{a}_{b}': t for (a, b), t in table.items()},
                                                            one_year_reproduced=all(whole), seconds=round(time.time() - t0)), indent=1))


if __name__ == '__main__':
    main()
