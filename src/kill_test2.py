"""Second, bounded kill round fixed in RUN_LOG.md: a day-level rule for failed monitors and three more net-only signals.
Development split only: select from Y1, score on Y2. Y3 is never read. Writes results/kill_test2.json.
"""
import json
import time
from pathlib import Path

import numpy as np

import ausgrid
from kill_test import BUDGETS, DRAWS, HOLD_OUT, KILL, SEEDS, fleet_ratio, greedy, net_signal, rows_of, signature

OUT = Path(__file__).resolve().parents[1] / 'results'
DROP_BELOW, MIN_KEPT, RANK, HIGH_SUN = 0.25, 3, 10, 25.0
ARMS = ('N1', 'N2', 'N3', 'N4', 'N5')


def common_response(net, mask, dates):
    """Each home's response to the fleet's common net-load anomaly, by month and slot, as a row signal."""
    months = np.array([d.month for d in dates])
    fleet = np.nanmean(net, axis=0)
    out = np.zeros(net.shape, dtype=np.float32)
    for m in np.unique(months):
        days = months == m
        anomaly = np.nan_to_num(fleet[days] - np.nanmean(fleet[days], axis=0, keepdims=True))
        spread = (anomaly ** 2).sum(axis=0)
        for s in np.flatnonzero(mask[days].any(axis=0)):
            x = np.nan_to_num(net[:, days, s] - np.nanmean(net[:, days, s], axis=1, keepdims=True))
            beta = x @ anomaly[:, s] / max(spread[s], 1e-9)
            out[:, days, s] = -beta[:, None] * anomaly[:, s][None, :]
    return out


def low_rank(rows):
    """Rank-limited rebuild of a (rows, homes) signal, which keeps what homes share and removes load of one home."""
    filled = np.nan_to_num(rows)
    centre = filled.mean(axis=0, keepdims=True)
    u, s, vt = np.linalg.svd(filled - centre, full_matrices=False)
    return (u[:, :RANK] * s[:RANK]) @ vt[:RANK] + centre


def day_rule(pv, mask, capacity, homes):
    """Capacity-weighted ratio on daylight rows, leaving out a chosen home for any day it looks failed.
    The rule reads only the chosen homes, so it needs no census, and it applies to every arm."""
    homes = np.asarray(homes)
    sub = pv[homes]
    w = capacity[homes][:, None, None]
    keep = np.isfinite(sub)
    if len(homes) >= MIN_KEPT:
        energy = np.where(mask[None], np.nan_to_num(sub), 0).sum(axis=2)
        keep = keep & (energy >= DROP_BELOW * np.median(energy, axis=0, keepdims=True))[:, :, None]
    ratio = (np.where(keep, sub, 0) * w).sum(axis=0) / np.maximum((keep * w).sum(axis=0), 1e-9)
    return ratio[mask]


def recovery(mean, arm):
    per_k = {k: float((mean['random'][k] - mean[arm][k]) / (mean['random'][k] - mean['census'][k])) for k in KILL}
    return per_k, float(np.median(list(per_k.values())))


def averaged(table, use):
    return {n: {k: float(np.mean(np.asarray(v)[use])) for k, v in t.items()} for n, t in table.items()}


def main():
    t0 = time.time()
    sel, scored = ausgrid.load(['Y1']), ausgrid.load(['Y2'])
    capacity = sel['capacity']
    every = np.arange(ausgrid.HOMES)
    day_sel, day_score = ausgrid.daylight(sel['dates']), ausgrid.daylight(scored['dates'])
    high = ausgrid.daylight(sel['dates'], HIGH_SUN)
    signal = net_signal(sel['net'])
    n1 = rows_of(signal, day_sel)
    views = dict(census=rows_of(sel['pv'], day_sel), N1=n1, N2=rows_of(signature(signal, sel['dates']), day_sel), N3=rows_of(signal, high),
                 N4=rows_of(common_response(sel['net'], day_sel, sel['dates']), day_sel), N5=low_rank(n1))
    targets = {n: fleet_ratio(v, capacity, every) for n, v in views.items()}
    true_high = fleet_ratio(rows_of(sel['pv'], high), capacity, every)
    agreement = {n: round(float(np.corrcoef(targets[n], true_high if n == 'N3' else targets['census'])[0, 1]), 3) for n in ARMS}
    print('fleet signal against true fleet PV in Y1, correlation', agreement, '|', round(time.time() - t0), 's', flush=True)

    y_rows = rows_of(scored['pv'], day_score)
    names = ('random', *views)
    table = {n: {k: [] for k in BUDGETS} for n in names}
    plain = {n: {k: [] for k in BUDGETS} for n in names}
    picks = {n: {} for n in views}
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        order = rng.permutation(ausgrid.HOMES)
        held, candidates = np.sort(order[:HOLD_OUT]), np.sort(order[HOLD_OUT:])
        y = fleet_ratio(y_rows, capacity, held)

        def score(homes):
            return float(np.sqrt(np.mean((day_rule(scored['pv'], day_score, capacity, homes) - y) ** 2)) / y.mean() * 100)

        def score_plain(homes):
            return float(np.sqrt(np.mean((fleet_ratio(y_rows, capacity, np.asarray(homes)) - y) ** 2)) / y.mean() * 100)

        for name, view in views.items():
            chosen = greedy(view, capacity, candidates, max(BUDGETS), targets[name])
            picks[name][seed] = chosen
            for k in BUDGETS:
                table[name][k].append(score(chosen[:k]))
                plain[name][k].append(score_plain(chosen[:k]))
        for k in BUDGETS:
            draws = [rng.choice(candidates, k, replace=False) for _ in range(DRAWS)]
            table['random'][k].append(float(np.median([score(d) for d in draws])))
            plain['random'][k].append(float(np.median([score_plain(d) for d in draws])))
        print('partition', seed, {n: round(table[n][10][-1], 2) for n in table}, round(time.time() - t0), 's', flush=True)

    every_part = np.arange(len(SEEDS))
    mean, mean_plain = averaged(table, every_part), averaged(plain, every_part)
    result = {}
    for arm in ARMS:
        per_k, median = recovery(mean, arm)
        left_out = {s: recovery(averaged(table, np.delete(every_part, i)), arm)[1] for i, s in enumerate(SEEDS)}
        within = {s: recovery(averaged(table, np.array([i])), arm)[1] for i, s in enumerate(SEEDS)}
        result[arm] = dict(per_k=per_k, median=median, left_out=left_out, worst_left_out=min(left_out.values()), within=within)
    gain = all(mean['census'][k] < mean['random'][k] for k in KILL)
    best = max(ARMS, key=lambda a: result[a]['median'])
    passed = [a for a in ARMS if result[a]['median'] >= 0.5 and result[a]['worst_left_out'] >= 0.5]
    verdict = 'NO GAIN TO RECOVER' if not gain else 'PASS: ' + ', '.join(passed) if passed else 'FAIL'

    # Run 2 used the same seeds, picks and draws, so the plain estimator must give back its numbers
    run2 = json.loads((OUT / 'runs' / 'kill_test_run2.json').read_text())['nrmse']
    drift = max(abs(run2[n][str(k)] - mean_plain[n][k]) for n in ('random', 'census', 'N1', 'N2') for k in BUDGETS)
    print('largest difference from Run 2 with the plain estimator', round(drift, 6))

    print('\nnRMSE % on Y2, day rule for failed monitors, mean of five partitions')
    print('k     ' + ''.join(f'{n:>9}' for n in names))
    for k in BUDGETS:
        print(f'{k:<6}' + ''.join(f'{mean[n][k]:9.2f}' for n in names))
    print('\nnRMSE % on Y2, plain estimator, for reference')
    for k in BUDGETS:
        print(f'{k:<6}' + ''.join(f'{mean_plain[n][k]:9.2f}' for n in names))
    print()
    for arm in ARMS:
        r = result[arm]
        print(arm, 'recovery', {k: round(v, 3) for k, v in r['per_k'].items()}, 'median', round(r['median'], 3), 'worst left out', round(r['worst_left_out'], 3),
              'within', {s: round(v, 3) for s, v in r['within'].items()})
    print('k=10 by partition')
    for n in names:
        print(' ', n, [round(x, 2) for x in table[n][10]])
    print('verdict', verdict, '| best', best, '| seconds', round(time.time() - t0))
    (OUT / 'kill_test2.json').write_text(json.dumps(dict(split='select Y1, score Y2', estimator='day rule', seeds=SEEDS, nrmse=mean, nrmse_plain=mean_plain, per_partition=table,
                                                        recovery=result, census_gain=gain, verdict=verdict, best=best, picks=picks, signal_correlation=agreement,
                                                        run2_drift=drift, seconds=round(time.time() - t0)), indent=1))


if __name__ == '__main__':
    main()
