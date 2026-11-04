"""Secondary outcomes of protocol v2 that the campaign run does not hold: monitor loss, why it works, and net-only on the Ausgrid hold-out.
Picks are rebuilt from the same seeds and windows as campaign.py, and each fleet checks that it gives back the campaign table's method errors.

python extras.py uk-debug | ausgrid-dev           open at any time
python extras.py uk-confirm | ausgrid-holdout     refuse to run until the hash of this file is in RUN_LOG.md
"""
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import ausgrid
import campaign
import run_campaign
import ukpv
from kill_test import fleet_ratio, greedy, net_signal, rows_of
from kill_test2 import common_response, day_rule

OUT = Path(__file__).resolve().parents[1] / 'results' / 'extras'
LOSS_BUDGETS, LOSSES, LOSS_DRAWS = (10, 20), (0, 1, 2, 3), 20
MAIN_K = (5, 10, 20)
LOSS_LENGTHS = ('4w', '3m', '1y')
NET_ARMS = ('N1', 'N4')


def nrmse(pred, y):
    return float(np.sqrt(np.mean((pred - y) ** 2)) / y.mean() * 100)


def picks_of(pv, mask, dates, capacity, candidates):
    """The method's order for every campaign window, as in campaign.select_all."""
    out = {}
    for length, start, first, days in campaign.windows_of(dates):
        view = rows_of(pv[:, first:first + days], mask[first:first + days])
        out[length, start] = greedy(view, capacity, candidates, min(max(campaign.BUDGETS), len(candidates)), fleet_ratio(view, capacity, candidates))
    return out


def loss_rows(score, chosen, k, rng):
    """Error after a whole scoring year without 0 to 3 of the chosen monitors, the median over random choices of who is lost."""
    out = []
    for lost in LOSSES:
        if lost == 0:
            out.append((lost, score(chosen)))
        else:
            out.append((lost, float(np.median([score(rng.choice(chosen, k - lost, replace=False)) for _ in range(LOSS_DRAWS)]))))
    return out


def mix_distance(a, b, capacity, labels):
    """Total variation between two sets' capacity-weighted shares of a label such as orientation sector."""
    def share(homes):
        s = np.bincount(labels[homes], weights=capacity[homes], minlength=labels.max() + 1)
        return s / s.sum()
    return float(np.abs(share(a) - share(b)).sum() / 2)


def run_fleet(name, pv, mask, dates, capacity, scored, score_mask, hold_out, labels=None, reference=None):
    n = len(capacity)
    loss, overlap, mix = [], [], []
    y_rows = rows_of(scored, score_mask)
    for seed in campaign.SEEDS:
        rng = np.random.default_rng(seed)
        order = rng.permutation(n)
        held, candidates = np.sort(order[:hold_out]), np.sort(order[hold_out:])
        y = fleet_ratio(y_rows, capacity, held)

        def score(homes):
            return nrmse(day_rule(scored, score_mask, capacity, np.asarray(homes)), y)

        picked = picks_of(pv, mask, dates, capacity, candidates)
        draw_rng = np.random.default_rng([seed, 99])
        for k in LOSS_BUDGETS:
            for (length, start), chosen in picked.items():
                if length in LOSS_LENGTHS:
                    for lost, e in loss_rows(score, chosen[:k], k, draw_rng):
                        loss.append((name, seed, 'method', length, start, k, lost, e))
            by_lost = {}
            for _ in range(campaign.DRAWS):
                for lost, e in loss_rows(score, draw_rng.choice(candidates, k, replace=False), k, draw_rng):
                    by_lost.setdefault(lost, []).append(e)
            for lost, es in by_lost.items():
                loss.append((name, seed, 'random', '', 0, k, lost, float(np.median(es))))

        whole = picked['1y', dates[0].month]
        for k in MAIN_K:
            for length in campaign.LENGTHS:
                sets = [set(chosen[:k]) for (ln, _), chosen in picked.items() if ln == length]
                pairs = [len(a & b) / len(a | b) for i, a in enumerate(sets) for b in sets[i + 1:]]
                with_year = [len(a & set(whole[:k])) / len(a | set(whole[:k])) for a in sets]
                overlap.append((name, seed, length, k, float(np.mean(pairs)), float(np.mean(with_year)), k / (2 * len(candidates) - k)))
        if labels:
            for label, codes in labels.items():
                for k in MAIN_K:
                    for (length, start), chosen in picked.items():
                        mix.append((name, seed, 'method', length, start, k, label, mix_distance(np.asarray(chosen[:k]), held, capacity, codes)))
                    es = [mix_distance(draw_rng.choice(candidates, k, replace=False), held, capacity, codes) for _ in range(campaign.DRAWS)]
                    mix.append((name, seed, 'random', '', 0, k, label, float(np.median(es))))
    if reference is not None and reference.exists():
        check_against(reference, pd.DataFrame(loss, columns=['fleet', 'seed', 'arm', 'length', 'start', 'k', 'lost', 'nrmse']))
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(loss, columns=['fleet', 'seed', 'arm', 'length', 'start', 'k', 'lost', 'nrmse']).to_csv(OUT / f'loss_{name}.csv', index=False)
    pd.DataFrame(overlap, columns=['fleet', 'seed', 'length', 'k', 'across_windows', 'with_year', 'by_chance']).to_csv(OUT / f'overlap_{name}.csv', index=False)
    if mix:
        pd.DataFrame(mix, columns=['fleet', 'seed', 'arm', 'length', 'start', 'k', 'label', 'distance']).to_csv(OUT / f'mix_{name}.csv', index=False)


def check_against(reference, loss):
    """The rebuilt picks must give back the campaign table, or the numbers here describe different monitors."""
    table = pd.read_csv(reference, keep_default_na=False)
    table = table[(table.arm == 'method') & (table['size'] == 0) & (table.scoring.astype(str) == str(table.scoring.iloc[0]))]
    merged = loss[(loss.arm == 'method') & (loss.lost == 0)].merge(table, on=['seed', 'length', 'start', 'k'])
    drift = float((merged.nrmse_x - merged.nrmse_y).abs().max())
    print('check against', reference.name, 'rows', len(merged), 'largest difference', drift, flush=True)
    if not len(merged) or drift > 1e-6:
        sys.exit(f'refused: rebuilt picks differ from {reference}')


def uk_labels(meta):
    return dict(orientation=(np.floor(((meta.orientation.to_numpy() + 22.5) % 360) / 45)).astype(int), tilt=np.digitize(meta.tilt.to_numpy(), [25, 35, 45]))


def run_uk(args):
    name, reference_folder = args
    t0 = time.time()
    meta = ukpv.fleet_of(ukpv.cohort(), name)
    lat, lon = float(meta.latitude_rounded.mean()), float(meta.longitude_rounded.mean())
    pv, dates = ukpv.load(name, meta, ukpv.CAMPAIGN_YEAR)
    scored, later = ukpv.load(name, meta, 2019)
    run_fleet(name, pv, ukpv.solar_mask(dates, lat, lon), dates, meta.kWp.to_numpy(), scored, ukpv.solar_mask(later, lat, lon), round(len(meta) / 3),
              labels=uk_labels(meta), reference=Path(reference_folder) / f'uk_{name}.csv')
    print(name, 'seconds', round(time.time() - t0), flush=True)


def run_net(selection, scored_year):
    """N1 and N4 from a year of net load, scored on the next, as in the second kill round. Net load exists for every home, so their target uses every home."""
    sel, scored = ausgrid.load([selection]), ausgrid.load([scored_year])
    capacity = sel['capacity']
    every = np.arange(ausgrid.HOMES)
    day_sel, day_score = ausgrid.daylight(sel['dates']), ausgrid.daylight(scored['dates'])
    views = dict(census=rows_of(sel['pv'], day_sel), N1=rows_of(net_signal(sel['net']), day_sel), N4=rows_of(common_response(sel['net'], day_sel, sel['dates']), day_sel))
    y_rows = rows_of(scored['pv'], day_score)
    rows = []
    for seed in campaign.SEEDS:
        rng = np.random.default_rng(seed)
        order = rng.permutation(ausgrid.HOMES)
        held, candidates = np.sort(order[:100]), np.sort(order[100:])
        y = fleet_ratio(y_rows, capacity, held)
        for arm, view in views.items():
            chosen = greedy(view, capacity, candidates, max(campaign.BUDGETS), fleet_ratio(view, capacity, every))
            for k in campaign.BUDGETS:
                rows.append((seed, arm, k, nrmse(day_rule(scored['pv'], day_score, capacity, chosen[:k]), y)))
        for k in campaign.BUDGETS:
            es = [nrmse(day_rule(scored['pv'], day_score, capacity, rng.choice(candidates, k, replace=False)), y) for _ in range(campaign.DRAWS)]
            rows.append((seed, 'random', k, float(np.median(es))))
    table = pd.DataFrame(rows, columns=['seed', 'arm', 'k', 'nrmse'])
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT / f'net_{selection}_{scored_year}.csv', index=False)
    mean = table.groupby(['arm', 'k']).nrmse.mean().unstack('arm')
    print(mean.round(2).to_string())
    for arm in NET_ARMS:
        kept = ((mean.random - mean[arm]) / (mean.random - mean.census)).loc[list(MAIN_K)]
        print(arm, 'share of the census gain', kept.round(3).to_dict(), 'median', round(float(kept.median()), 3), flush=True)


def run_ausgrid(name, selection, scored_year, reference):
    t0 = time.time()
    sel, scored = ausgrid.load([selection]), ausgrid.load([scored_year])
    run_fleet(name, sel['pv'], ausgrid.daylight(sel['dates']), sel['dates'], sel['capacity'], scored['pv'], ausgrid.daylight(scored['dates']), 100, reference=reference)
    print(name, 'seconds', round(time.time() - t0), flush=True)


def require_frozen():
    run_campaign.FROZEN += ('extras.py',)
    run_campaign.require_frozen()


def main():
    what = sys.argv[1]
    campaign_tables = Path(sys.argv[2]) if len(sys.argv) > 2 else run_campaign.OUT
    if what == 'ausgrid-dev':
        run_ausgrid('ausgrid_dev', 'Y1', 'Y2', campaign_tables / 'ausgrid_dev.csv')
        run_net('Y1', 'Y2')
    elif what == 'uk-debug':
        run_uk((ukpv.regions(ukpv.cohort())[1], campaign_tables))
    elif what == 'ausgrid-holdout':
        require_frozen()
        run_ausgrid('ausgrid_holdout', 'Y2', 'Y3', campaign_tables / 'ausgrid_holdout.csv')
        run_net('Y2', 'Y3')
    elif what == 'uk-confirm':
        require_frozen()
        fleets = ukpv.regions(ukpv.cohort())[0]
        with mp.Pool(run_campaign.PROCESSES) as pool:
            pool.map(run_uk, [(f, campaign_tables) for f in fleets], chunksize=1)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
