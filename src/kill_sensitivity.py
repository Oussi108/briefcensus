"""How firm is the kill-test verdict? Development split only, and it does not change the verdict.

1. Recovery with each partition left out, because one partition's census picks hit homes that failed in Y2.
2. Recovery when a failed monitor is dropped: in each row, a chosen home below a quarter of the chosen homes' median
   is left out. The rule uses the chosen homes' own data, so it needs no census, and it applies to every arm.
Writes results/kill_sensitivity.json.
"""
import json
from pathlib import Path

import numpy as np

import ausgrid
from kill_test import BUDGETS, DRAWS, HOLD_OUT, KILL, SEEDS, fleet_ratio

OUT = Path(__file__).resolve().parents[1] / 'results'
DROP_BELOW, MIN_KEPT = 0.25, 3


def robust_ratio(x, capacity, homes):
    sub, w = x[:, homes], capacity[homes]
    if len(homes) < MIN_KEPT:
        return fleet_ratio(x, capacity, homes)
    median = np.nanmedian(sub, axis=1, keepdims=True)
    ok = np.isfinite(sub) & (sub >= DROP_BELOW * median)
    return np.where(ok, sub * w, 0).sum(1) / np.maximum((ok * w).sum(1), 1e-9)


def recovery(table, seeds, arm='N1'):
    mean = {n: {k: np.mean([t[k][seeds.index(s)] for s in seeds]) for k in KILL} for n, t in table.items()}
    per_k = {k: float((mean['random'][k] - mean[arm][k]) / (mean['random'][k] - mean['census'][k])) for k in KILL}
    return per_k, float(np.median(list(per_k.values())))


def main():
    run = json.loads((OUT / 'kill_test.json').read_text())
    plain = {n: {int(k): v for k, v in t.items()} for n, t in run['per_partition'].items()}
    seeds = list(SEEDS)
    out = {'signal_correlation': run['signal_correlation'], 'all': recovery(plain, seeds), 'leave_one_out': {}, 'per_partition': {}}
    for s in seeds:
        rest = [x for x in seeds if x != s]
        kept = {n: {k: [t[k][seeds.index(x)] for x in rest] for k in KILL} for n, t in plain.items()}
        out['leave_one_out'][s] = recovery(kept, rest)
        one = {n: {k: [t[k][seeds.index(s)]] for k in KILL} for n, t in plain.items()}
        out['per_partition'][s] = recovery(one, [s])

    data = ausgrid.load(['Y2'])
    capacity = data['capacity']
    truth = data['pv'][:, ausgrid.daylight(data['dates'])].T
    robust = {n: {k: [] for k in BUDGETS} for n in plain}
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        order = rng.permutation(ausgrid.HOMES)
        held, candidates = np.sort(order[:HOLD_OUT]), np.sort(order[HOLD_OUT:])
        y = fleet_ratio(truth, capacity, held)

        def score(homes):
            return float(np.sqrt(np.mean((robust_ratio(truth, capacity, np.asarray(homes)) - y) ** 2)) / y.mean() * 100)

        for name in ('census', 'N1', 'N2'):
            for k in BUDGETS:
                robust[name][k].append(score(run['picks'][name][str(seed)][:k]))
        for k in BUDGETS:
            robust['random'][k].append(float(np.median([score(rng.choice(candidates, k, replace=False)) for _ in range(DRAWS)])))
    out['drop_failed'] = dict(N1=recovery(robust, seeds, 'N1'), N2=recovery(robust, seeds, 'N2'),
                              nrmse={n: {k: round(float(np.mean(v[k])), 2) for k in BUDGETS} for n, v in robust.items()},
                              per_partition_k10={n: [round(x, 2) for x in v[10]] for n, v in robust.items()})
    (OUT / 'kill_sensitivity.json').write_text(json.dumps(out, indent=1))
    print('signal correlation with true fleet PV', round(out['signal_correlation'], 3))
    print('N1 all five', out['all'])
    print('N1 leave one out', {s: round(v[1], 3) for s, v in out['leave_one_out'].items()})
    print('N1 within each partition', {s: round(v[1], 3) for s, v in out['per_partition'].items()})
    print('drop-failed N1', out['drop_failed']['N1'])
    print('drop-failed N2', out['drop_failed']['N2'])
    print('drop-failed nRMSE'); [print(' ', n, v) for n, v in out['drop_failed']['nrmse'].items()]
    print('drop-failed k=10 by partition'); [print(' ', n, v) for n, v in out['drop_failed']['per_partition_k10'].items()]


if __name__ == '__main__':
    main()
