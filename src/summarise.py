"""Applies the rules of protocol v2 and its logged additions to campaign tables, and prints every outcome whatever it shows.

python summarise.py <folder> <file pattern> <primary period> [L for the main rule]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

MAIN_K = (5, 10, 20)
FIT_COMPETITORS = ('gp_mi_fit', 'mrmr_fit', 'medoids_fit', 'closest_fit', 'correlated_fit', 'maxdiff_fit')
SIMPLE = ('closest', 'correlated', 'screened')
NO_CAMPAIGN = ('metadata', 'spatial')


def read(folder, pattern):
    t = pd.concat([pd.read_csv(p, keep_default_na=False) for p in sorted(Path(folder).glob(pattern))], ignore_index=True)
    t['scoring'] = t.scoring.astype(str)
    return t


def errors(t, arm, length, period, value='nrmse', start=None, size=0):
    """Error of one arm per fleet and k, averaged over partitions, start months and any drawn campaign sets."""
    s = t[(t.arm == arm) & (t.length == length) & (t.scoring == period) & (t['size'] == size)]
    if start is not None:
        s = s[s.start == start]
    return s.groupby(['fleet', 'k'])[value].mean().unstack('k')


def kept(top, bottom, value):
    """Median over the main budgets of the share of the gain from top down to bottom that value keeps, per fleet."""
    keys = list(MAIN_K)
    return ((top[keys] - value[keys]) / (top[keys] - bottom[keys])).median(axis=1)


def signed_rank(diff):
    d = diff.dropna().to_numpy()
    if len(d) < 6 or np.all(d == 0):
        return float('nan')
    return float(wilcoxon(d).pvalue)


def line(name, s):
    print(f'{name:<28} median {s.median():7.3f} | range {s.min():7.3f} to {s.max():7.3f} | share at .5 or more {(s >= .5).mean():.3f} | fleets {len(s)}')


def main():
    folder, pattern, primary = sys.argv[1:4]
    main_length = sys.argv[4] if len(sys.argv) > 4 else '4w'
    pd.set_option('display.width', 220, 'display.max_columns', 40, 'display.max_rows', 200)
    all_fleets = read(folder, pattern)
    t = all_fleets[all_fleets.fleet != 'national']
    print('fleets', sorted(t.fleet.unique()), '| rows', len(t), '| empty errors', int(pd.to_numeric(t.nrmse, errors='coerce').isna().sum()))
    periods = sorted(t.scoring.unique(), key=lambda p: p != primary)

    random = {p: errors(t, 'random', '', p) for p in periods}
    year = {p: errors(t, 'method', '1y', p) for p in periods}
    method = errors(t, 'method', main_length, primary)

    print('\n== Main rule: S by length, then decay ==')
    for p in periods:
        for length in ('1w', '2w', '4w', '3m'):
            line(f'S {length} scored {p}', kept(random[p], year[p], errors(t, 'method', length, p)))
    s = kept(random[primary], year[primary], method)
    print('per fleet at the main length\n', s.round(3).to_string())
    print('CONFIRMED' if s.median() >= .5 and (s >= .5).mean() >= 2 / 3 else 'NOT CONFIRMED', f'at {main_length} on {primary}: median S {s.median():.3f}, share {(s >= .5).mean():.3f}')
    gain = (random[primary] - method)[list(MAIN_K)]
    print('Wilcoxon on E_random - E_L: ' + ', '.join(f'k={k} p={signed_rank(gain[k]):.2g}, median {gain[k].median():.2f}' for k in MAIN_K) + f' | median over k p={signed_rank(gain.median(axis=1)):.2g}')

    print('\n== Errors by arm, median across fleets, %d period %s ==' % (len(t.fleet.unique()), primary))
    arms = sorted(a for a in t[t.scoring == primary].arm.unique())
    table = {}
    for arm in arms:
        for length in ('', main_length, '3m', '1y'):
            e = errors(t, arm, length, primary)
            if len(e):
                table[(arm, length or 'none')] = e[list(MAIN_K)].median()
    print(pd.DataFrame(table).T.round(2).sort_index().to_string())

    print('\n== Selection or level: A = (E_RC - E_GC) / E_RC, rule at .10 ==')
    for length in ('1w', '2w', '4w', '3m', '1y'):
        rc, gc = errors(t, 'RC', length, primary), errors(t, 'GC', length, primary)
        a = ((rc - gc) / rc)[list(MAIN_K)].median(axis=1)
        print(f'{length} median A {a.median():.3f}, range {a.min():.3f} to {a.max():.3f}, share at .10 or more {(a >= .10).mean():.3f}')

    print('\n== Is a campaign needed? Share of the method gain kept with no campaign, rule at .8 ==')
    better = None
    for arm in NO_CAMPAIGN:
        e = errors(t, arm, '', primary)
        if len(e):
            k = kept(random[primary], method, e)
            line(arm, k)
            better = k if better is None else np.maximum(better, k)
    if better is not None:
        line('better of the two, per fleet', better)

    print('\n== Is a simple rule enough? Excess error over the method, rule at .10 ==')
    best = None
    for arm in SIMPLE:
        e = errors(t, arm, main_length, primary)
        excess = (e[list(MAIN_K)] / method[list(MAIN_K)] - 1).median(axis=1)
        print(f'{arm:<12} median excess {excess.median():.3f}, range {excess.min():.3f} to {excess.max():.3f}')
        best = excess if best is None else np.minimum(best, excess)
    print(f'best simple, per fleet: median excess {best.median():.3f}, fleets within .10 {(best <= .10).sum()} of {len(best)}')

    print('\n== Fitted competitors against the method without weights: positive means the competitor is better ==')
    for length in ('1w', '2w', '4w', '3m', '1y'):
        base = errors(t, 'method', length, primary)
        for arm in ('method_fit',) + FIT_COMPETITORS:
            e = errors(t, arm, length, primary)
            if len(e):
                d = (base - e)[list(MAIN_K)]
                print(f'{length} {arm:<16} ' + ' | '.join(f'k={k} median {d[k].median():6.2f}, fleets better {(d[k] > 0).sum():2d}, p={signed_rank(d[k]):.2g}' for k in MAIN_K))

    print('\n== Season: S by start month ==')
    for length in ('1w', '2w', '4w', '3m'):
        for start in sorted(int(x) for x in t[(t.length == length)].start.unique()):
            line(f'{length} start month {start}', kept(random[primary], year[primary], errors(t, 'method', length, primary, start=start)))

    print('\n== Campaign size: S against m, with cost in meter-months ==')
    for length, months in (('4w', 28 / 30.44), ('3m', 91 / 30.44)):
        for size in sorted(int(x) for x in t[t['size'] > 0]['size'].unique()):
            e = errors(t, 'method', length, primary, size=size)
            keys = [k for k in MAIN_K if k <= size]
            d = (random[primary] - e)[keys] / (random[primary] - year[primary])[keys]
            print(f'{length} m={size:<4d} meter-months {size * months:6.1f} | median S {d.median(axis=1).median():.3f} | median error at k=10 {e[10].median() if 10 in e else float("nan"):.2f}')

    print('\n== Bias, %, median across fleets ==')
    for arm, length in (('method', main_length), ('method', '1y'), ('GC', main_length), ('random', ''), ('RC', main_length)):
        print(arm, length or 'none', errors(t, arm, length, primary, value='bias')[list(MAIN_K)].median().round(2).to_dict())

    national = all_fleets[all_fleets.fleet == 'national']
    if len(national):
        print('\n== National fleet, sensitivity ==')
        r, y = errors(national, 'random', '', primary), errors(national, 'method', '1y', primary)
        for length in ('1w', '2w', '4w', '3m'):
            e = errors(national, 'method', length, primary)
            print(length, 'S', round(float(kept(r, y, e).iloc[0]), 3), e[list(MAIN_K)].round(2).to_dict('records')[0])
        print('random', r[list(MAIN_K)].round(2).to_dict('records')[0], '| 1y', y[list(MAIN_K)].round(2).to_dict('records')[0])


if __name__ == '__main__':
    main()
