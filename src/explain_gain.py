"""Is the short-census gain selection, or only level? Test fixed in RUN_LOG.md. Development split only, Y3 is never read.
Arms on each census window: greedy, greedy with one level factor, the same random draws with that factor, and greedy whose
target leaves out the evaluation homes. Writes results/explain_gain.json.
"""
import json
import time
from pathlib import Path

import numpy as np

import ausgrid
from census_length import LENGTHS, STARTS
from kill_test import BUDGETS, DRAWS, HOLD_OUT, KILL, SEEDS, fleet_ratio, greedy, rows_of
from kill_test2 import day_rule

OUT = Path(__file__).resolve().parents[1] / 'results'
ENOUGH, CLOSE = 0.10, 0.10
ARMS = ('greedy', 'GC', 'RC', 'B')


def main():
    t0 = time.time()
    sel, scored = ausgrid.load(['Y1']), ausgrid.load(['Y2'])
    capacity = sel['capacity']
    every = np.arange(ausgrid.HOMES)
    day_sel, day_score = ausgrid.daylight(sel['dates']), ausgrid.daylight(scored['dates'])
    y_rows = rows_of(scored['pv'], day_score)
    previous = json.loads((OUT / 'kill_test2.json').read_text())
    random, census = previous['per_partition']['random'], previous['per_partition']['census']

    windows = {(length, name): ((start - sel['dates'][0]).days, days) for length, days in LENGTHS.items() for name, start in STARTS.items()}
    windows[('1y', 'Jul')] = (0, 365)
    table = {key: {arm: {k: [] for k in BUDGETS} for arm in ARMS} for key in windows}
    same_random = []
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        order = rng.permutation(ausgrid.HOMES)
        held, candidates = np.sort(order[:HOLD_OUT]), np.sort(order[HOLD_OUT:])
        y = fleet_ratio(y_rows, capacity, held)

        def nrmse(pred):
            return float(np.sqrt(np.mean((pred - y) ** 2)) / y.mean() * 100)

        draws = {k: [rng.choice(candidates, k, replace=False) for _ in range(DRAWS)] for k in BUDGETS}
        preds = {k: [day_rule(scored['pv'], day_score, capacity, d) for d in draws[k]] for k in BUDGETS}
        same_random.append(max(abs(float(np.median([nrmse(p) for p in preds[k]])) - random[str(k)][SEEDS.index(seed)]) for k in BUDGETS))
        for key, (first, days) in windows.items():
            pv, mask = sel['pv'][:, first:first + days], day_sel[first:first + days]
            view = rows_of(pv, mask)
            target = fleet_ratio(view, capacity, every)
            chosen = greedy(view, capacity, candidates, max(BUDGETS), target)
            blind = greedy(view, capacity, candidates, max(BUDGETS), fleet_ratio(view, capacity, candidates))

            def level(homes):
                return target.mean() / max(float(day_rule(pv, mask, capacity, homes).mean()), 1e-9)

            for k in BUDGETS:
                pick = day_rule(scored['pv'], day_score, capacity, chosen[:k])
                table[key]['greedy'][k].append(nrmse(pick))
                table[key]['GC'][k].append(nrmse(pick * level(chosen[:k])))
                table[key]['RC'][k].append(float(np.median([nrmse(p * level(d)) for d, p in zip(draws[k], preds[k])])))
                table[key]['B'][k].append(nrmse(day_rule(scored['pv'], day_score, capacity, blind[:k])))
        print('partition', seed, round(time.time() - t0), 's', flush=True)
    print('largest difference from the random medians of the second round', round(max(same_random), 6))

    parts = np.arange(len(SEEDS))

    def error(length, arm, k, use):
        return float(np.mean([np.asarray(table[key][arm][k])[use].mean() for key in windows if key[0] == length]))

    def advantage(length, use):
        return float(np.median([(error(length, 'RC', k, use) - error(length, 'GC', k, use)) / error(length, 'RC', k, use) for k in KILL]))

    def share(length, arm, use):
        out = []
        for k in KILL:
            r, c = np.asarray(random[str(k)])[use].mean(), np.asarray(census[str(k)])[use].mean()
            out.append((r - error(length, arm, k, use)) / (r - c))
        return float(np.median(out))

    summary = {}
    for length in ('4w', '3m', '1y'):
        left_out = {s: advantage(length, np.delete(parts, i)) for i, s in enumerate(SEEDS)}
        summary[length] = dict(advantage=advantage(length, parts), left_out=left_out, worst_left_out=min(left_out.values()), share={arm: share(length, arm, parts) for arm in ARMS},
                               nrmse={arm: {k: error(length, arm, k, parts) for k in BUDGETS} for arm in ARMS})
    adds = all(summary[n]['advantage'] >= ENOUGH and summary[n]['worst_left_out'] >= ENOUGH for n in LENGTHS)
    harmless = {n: abs(summary[n]['share']['B'] - summary[n]['share']['greedy']) <= CLOSE for n in LENGTHS}
    verdict = 'SELECTION ADDS VALUE' if adds else 'LEVEL FACTOR EXPLAINS MOST'

    for length, s in summary.items():
        print(f'\n{length}: nRMSE % on Y2, mean over partitions and start months. random and census are the second-round arms.')
        print('k     random census ' + ''.join(f'{a:>8}' for a in ARMS))
        for k in BUDGETS:
            print(f"{k:<5}{np.mean(random[str(k)]):7.2f}{np.mean(census[str(k)]):7.2f} " + ''.join(f"{s['nrmse'][a][k]:8.2f}" for a in ARMS))
        print('advantage of greedy over random, both with the factor', round(s['advantage'], 3), '| worst left out', round(s['worst_left_out'], 3),
              '| share of gain', {a: round(v, 3) for a, v in s['share'].items()})
    print('\nverdict', verdict, '| target without evaluation homes is harmless', harmless, '| seconds', round(time.time() - t0))
    (OUT / 'explain_gain.json').write_text(json.dumps(dict(split='select window of Y1, score Y2', estimator='day rule', seeds=SEEDS, summary=summary, verdict=verdict, blind_target_harmless=harmless,
                                                          per_window={f'{a}_{b}': t for (a, b), t in table.items()}, random_drift=max(same_random), seconds=round(time.time() - t0)), indent=1))


if __name__ == '__main__':
    main()
