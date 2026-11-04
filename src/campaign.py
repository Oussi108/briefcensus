"""The experiment of protocol v2 on one fleet: choose k monitors from a campaign window, score them on later periods.
Every campaign selector sees only the campaign's systems, and the evaluation group is never metered or selected.
"""
import numpy as np
import pandas as pd
from scipy.optimize import nnls

from kill_test import fleet_ratio, greedy, rows_of
from kill_test2 import day_rule

SEEDS = (11, 23, 37, 51, 73)
BUDGETS = (1, 2, 3, 5, 10, 20, 50)
LENGTHS = {'1w': 7, '2w': 14, '4w': 28, '3m': 91}
SIZES, SIZE_LENGTHS, SIZE_DRAWS = (25, 50, 100), ('4w', '3m'), 5
START_MONTHS = (1, 4, 7, 10)
DRAWS = 40


def windows_of(dates):
    """(length, start month, first day, days) for every campaign window of a selection year, plus the one-year reference."""
    out = []
    for length, days in LENGTHS.items():
        for month in START_MONTHS:
            first = next(i for i, d in enumerate(dates) if d.month == month and d.day == 1)
            out.append((length, month, first, days))
    out.append(('1y', dates[0].month, 0, 365))
    return out


def distances(x):
    g = x.T @ x
    d = np.diag(g)
    return np.sqrt(np.maximum(d[:, None] + d[None, :] - 2 * g, 0))


def medoids(dist, k):
    """Greedy build, then alternating refinement, on a distance matrix. The result is not nested in k."""
    near = np.full(len(dist), np.inf)
    chosen = []
    for _ in range(k):
        gain = np.minimum(near[:, None], dist).sum(0)
        gain[chosen] = np.inf
        j = int(np.argmin(gain))
        chosen.append(j)
        near = np.minimum(near, dist[:, j])
    for _ in range(20):
        label = np.argmin(dist[:, chosen], axis=1)
        new = []
        for c in range(k):
            members = np.flatnonzero(label == c)
            new.append(int(members[np.argmin(dist[np.ix_(members, members)].sum(1))]) if len(members) else chosen[c])
        if new == chosen or len(set(new)) < k:
            break
        chosen = new
    return chosen


def spatial_order(coords, capacity, candidates, kmax):
    """Greedy on equation 6.2 of Saint-Drenan et al. 2016: the capacity-weighted distance from each fleet system to its nearest chosen system."""
    dist = np.sqrt(((coords[:, None, :] - coords[candidates][None, :, :]) ** 2).sum(-1))
    near = np.full(len(coords), np.inf)
    chosen = []
    for _ in range(kmax):
        cost = capacity @ np.minimum(near[:, None], dist)
        cost[chosen] = np.inf
        j = int(np.argmin(cost))
        chosen.append(j)
        near = np.minimum(near, dist[:, j])
    return [int(candidates[j]) for j in chosen]


def max_difference(view, members, coords, kmax):
    """Zhu et al. 2025, without their clusters: scaled mean power and location, start at the system most different from the rest,
    then add the one farthest from those already chosen. Their equation 11 prints a minimum, but their stated aim and figures need the maximum."""
    parts = [np.nanmean(view[:, members], axis=0)[:, None]]
    if coords is not None:
        parts.append(coords[members])
    f = np.nan_to_num(np.hstack(parts))
    f = (f - f.min(0)) / np.maximum(f.max(0) - f.min(0), 1e-9)
    dist = distances(f.T)
    chosen = [int(np.argmax(dist.sum(1)))]
    near = dist[chosen[0]].copy()
    for _ in range(kmax - 1):
        near[chosen] = -1
        j = int(np.argmax(near))
        chosen.append(j)
        near = np.minimum(near, dist[j])
    return chosen


def rank_corr(a):
    r = np.argsort(np.argsort(a, axis=0), axis=0).astype(float)
    return (r - r.mean(0)) / np.maximum(r.std(0), 1e-9)


def mrmr(x, target, kmax):
    """Incremental minimum-redundancy maximum-relevance, with mutual information from rank correlation under a Gaussian copula."""
    z, t = rank_corr(x), rank_corr(target[:, None])
    n = len(x)

    def info(rho):
        return -0.5 * np.log(np.maximum(1 - np.minimum(rho ** 2, 1 - 1e-9), 1e-9))

    relevance = info((z.T @ t)[:, 0] / n)
    redundancy = info(z.T @ z / n)
    chosen = [int(np.argmax(relevance))]
    for _ in range(kmax - 1):
        score = relevance - redundancy[:, chosen].mean(1)
        score[chosen] = -np.inf
        chosen.append(int(np.argmax(score)))
    return chosen


def gp_mi(x, kmax):
    """Greedy mutual information of Krause et al. 2008 on the campaign covariance: largest var(y | chosen) / var(y | all others)."""
    cov = np.cov(x, rowvar=False)
    cov = cov + 1e-3 * np.trace(cov) / len(cov) * np.eye(len(cov))
    residual = cov.copy()
    free = list(range(len(cov)))
    chosen = []
    for _ in range(kmax):
        precision = np.linalg.inv(cov[np.ix_(free, free)])
        delta = np.diag(residual)[free] * np.diag(precision)
        j = free[int(np.argmax(delta))]
        chosen.append(j)
        free.remove(j)
        r = residual[:, j].copy()
        residual = residual - np.outer(r, r) / max(residual[j, j], 1e-12)
    return chosen


def closest_first(x, target, members):
    """Systems ordered by their own distance from the campaign's ratio, with no search over combinations."""
    return np.asarray(members)[np.argsort(np.mean((x - target[:, None]) ** 2, axis=0), kind='stable')]


def fitted_weights(view, target, homes, n):
    """Non-negative weights on the chosen systems, fitted to the campaign's ratio on the campaign rows, as the source papers fit theirs."""
    w, _ = nnls(np.nan_to_num(view[:, homes]).astype(float), target)
    full = np.zeros(n)
    full[homes] = w
    return full, float(w.sum())


def select_all(view, capacity, members, use_gp, coords=None):
    """Every campaign selector on one window. Each returns (arm, {k: homes})."""
    kmax = min(max(BUDGETS), len(members))
    budgets = [k for k in BUDGETS if k <= len(members)]
    target = fleet_ratio(view, capacity, members)
    x = np.nan_to_num(view[:, members]).astype(float)
    dist = distances(x)
    corr = (x - x.mean(0)).T @ (target - target.mean()) / np.maximum(x.std(0) * target.std() * len(x), 1e-9)
    orders = dict(method=greedy(view, capacity, members, kmax, target),
                  maxdiff=[int(members[j]) for j in max_difference(view, members, coords, kmax)],
                  mrmr=[int(members[j]) for j in mrmr(x, target, kmax)],
                  closest=[int(j) for j in closest_first(x, target, members)[:kmax]],
                  correlated=[int(members[j]) for j in np.argsort(-corr, kind='stable')[:kmax]])
    if use_gp:
        orders['gp_mi'] = [int(members[j]) for j in gp_mi(x, kmax)]
    out = {arm: {k: order[:k] for k in budgets} for arm, order in orders.items()}
    out['medoids'] = {k: [int(members[j]) for j in medoids(dist, k)] for k in budgets}
    return out


def run_fleet(pv, mask, dates, capacity, features, scoring, hold_out, use_gp=True, log=None, coords=None):
    """pv and mask are the selection year. scoring maps a name to (pv, mask), with the primary period first. Returns a long table of errors."""
    n = len(capacity)
    primary = next(iter(scoring))
    rows = []
    windows = windows_of(dates)
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        order = rng.permutation(n)
        held, candidates = np.sort(order[:hold_out]), np.sort(order[hold_out:])
        truth = {name: fleet_ratio(rows_of(p, m), capacity, held) for name, (p, m) in scoring.items()}

        def error(pred, name):
            y = truth[name]
            return float(np.sqrt(np.mean((pred - y) ** 2)) / y.mean() * 100), float((pred - y).mean() / y.mean() * 100)

        def record(arm, length, start, homes, k, size=0, draw=0, names=None, factor=1.0, weights=None):
            for name in names or scoring:
                p, m = scoring[name]
                e, b = error(day_rule(p, m, capacity if weights is None else weights, homes) * factor, name)
                rows.append((seed, arm, length, start, size, draw, name, k, e, b))

        draws = {k: [rng.choice(candidates, k, replace=False) for _ in range(DRAWS)] for k in BUDGETS if k <= len(candidates)}
        preds = {name: {k: [day_rule(p, m, capacity, d) for d in ds] for k, ds in draws.items()} for name, (p, m) in scoring.items()}
        for name in scoring:
            for k in draws:
                es = [error(q, name) for q in preds[name][k]]
                rows.append((seed, 'random', '', 0, 0, 0, name, k, float(np.median([e[0] for e in es])), float(np.median([e[1] for e in es]))))

        by_capacity = candidates[np.argsort(-capacity[candidates], kind='stable')]
        by_metadata = greedy(features, capacity, candidates, max(draws), fleet_ratio(features, capacity, np.arange(n)))
        by_space = None if coords is None else spatial_order(coords, capacity, candidates, max(draws))
        for k in draws:
            record('largest', '', 0, by_capacity[:k], k)
            record('metadata', '', 0, by_metadata[:k], k)
            if by_space is not None:
                record('spatial', '', 0, by_space[:k], k)
        for name, (p, m) in scoring.items():                        # best possible k from hindsight, a floor and not a method
            best = greedy(rows_of(p, m), capacity, candidates, max(draws), truth[name])
            for k in draws:
                record('oracle', '', 0, best[:k], k, names=[name])

        for length, start, first, days in windows:
            p_w, m_w = pv[:, first:first + days], mask[first:first + days]
            view = rows_of(p_w, m_w)
            level_target = fleet_ratio(view, capacity, candidates).mean()

            def level(homes):
                return level_target / max(float(day_rule(p_w, m_w, capacity, homes).mean()), 1e-9)

            picked = select_all(view, capacity, candidates, use_gp, coords)
            target = fleet_ratio(view, capacity, candidates)
            for arm, by_k in picked.items():
                for k, homes in by_k.items():
                    record(arm, length, start, homes, k)
                    weights, total = fitted_weights(view, target, homes, n)
                    record(arm + '_fit', length, start, homes, k, names=[primary], factor=total, weights=weights)
            typical = closest_first(np.nan_to_num(view[:, candidates]).astype(float), target, candidates)[:len(candidates) // 2]
            screen_rng = np.random.default_rng([seed, start, days])
            for k in draws:
                if k <= len(typical):
                    es = [error(day_rule(*scoring[primary], capacity, screen_rng.choice(typical, k, replace=False)), primary) for _ in range(DRAWS)]
                    rows.append((seed, 'screened', length, start, 0, 0, primary, k, float(np.median([e[0] for e in es])), float(np.median([e[1] for e in es]))))
            for k, homes in picked['method'].items():
                record('GC', length, start, homes, k, names=[primary], factor=level(homes))
                factors = [level(d) for d in draws[k]]
                es = [error(q * f, primary) for q, f in zip(preds[primary][k], factors)]
                rows.append((seed, 'RC', length, start, 0, 0, primary, k, float(np.median([e[0] for e in es])), float(np.median([e[1] for e in es]))))

            if length in SIZE_LENGTHS:
                size_rng = np.random.default_rng([seed, start, 7])
                for size in SIZES:
                    if size >= len(candidates):
                        continue
                    for draw in range(SIZE_DRAWS):
                        members = np.sort(size_rng.choice(candidates, size, replace=False))
                        chosen = greedy(view, capacity, members, min(max(BUDGETS), size), fleet_ratio(view, capacity, members))
                        for k in BUDGETS:
                            if k <= size:
                                record('method', length, start, chosen[:k], k, size=size, draw=draw, names=[primary])
        if log:
            log(f'partition {seed} done')
    return pd.DataFrame(rows, columns=['seed', 'arm', 'length', 'start', 'size', 'draw', 'scoring', 'k', 'nrmse', 'bias'])
