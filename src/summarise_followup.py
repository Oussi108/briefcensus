"""Prints the outage survival, monitor loss, overlap, panel mix and forecast results logged in RUN_LOG.md.

python summarise_followup.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import extras

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / 'kaggle' / 'campaign'
FOLLOWUP = CAMPAIGN / 'followup' / 'output' / 'results'
SECOND = CAMPAIGN / 'second' / 'output' / 'results' / 'clean'
HOLDOUT = CAMPAIGN / 'holdout' / 'output' / 'results'
LENGTHS = ['1w', '2w', '4w', '3m', '1y']
SKILLS = ['ridge', 'lightgbm']


def tables(folder, pattern):
    return pd.concat([pd.read_csv(f, keep_default_na=False) for f in sorted(folder.glob(pattern))], ignore_index=True)


def survival():
    d = tables(FOLLOWUP / 'survival', '*.csv')
    print('--- reporting on 2019 outage rows, median over fleets')
    d['group'] = np.where(d.kind == 'random', 'random', d.kind + ' ' + d.length)
    for column in ('any_reporting', 'share_reporting'):
        by_fleet = d.groupby(['fleet', 'group', 'k'])[column].mean().reset_index()
        print(column)
        print(by_fleet.groupby(['group', 'k'])[column].median().unstack('k').round(3).to_string())
    year = d[d.length == '1y'].groupby(['fleet', 'kind', 'k']).share_reporting.mean().unstack('kind')
    year['random'] = d[d.kind == 'random'].groupby(['fleet', 'k']).share_reporting.mean()
    for rival in ('random', 'clean'):
        print('raw 1y share above', rival, 'fleets of', year.index.get_level_values(0).nunique(), (year.raw > year[rival]).groupby('k').sum().to_dict())


def checks():
    print('--- rebuilt picks against the second-sample tables')
    for f in sorted((FOLLOWUP / 'extras').glob('loss_*.csv')):
        label = f.stem.replace('loss_', '')
        extras.check_against(SECOND / f'{label}.csv', pd.read_csv(f, keep_default_na=False))


def loss(table, title):
    print('---', title, 'error by monitors lost, median over fleets')
    table = table.copy()
    table['group'] = np.where(table.arm == 'random', 'random', table.length)
    by_fleet = table.groupby(['fleet', 'group', 'k', 'lost']).nrmse.mean().reset_index()
    print(by_fleet.groupby(['group', 'k', 'lost']).nrmse.median().unstack('lost').round(2).to_string())
    base = by_fleet.pivot_table(index=['fleet', 'k', 'lost'], columns='group', values='nrmse')
    for lost in sorted(table.lost.unique()):
        print('lost', lost, '4w below random, fleets', (base.xs(lost, level='lost')['4w'] < base.xs(lost, level='lost')['random']).groupby('k').agg(['sum', 'size']).to_dict('index'))
    print('4w after 3 lost below random with none lost, fleets', (base.xs(3, level='lost')['4w'] < base.xs(0, level='lost')['random']).groupby('k').agg(['sum', 'size']).to_dict('index'))


def overlap(table, title):
    print('---', title, 'share of picks shared, median over fleets')
    by_fleet = table.groupby(['fleet', 'length', 'k'])[['across_windows', 'with_year', 'by_chance']].mean().reset_index()
    print(by_fleet.groupby(['length', 'k'])[['across_windows', 'with_year', 'by_chance']].median().round(3).to_string())


def mix(table):
    print('--- panel mix distance from the candidates, median over fleets')
    table = table.copy()
    table['group'] = np.where(table.arm == 'random', 'random', table.length)
    by_fleet = table.groupby(['fleet', 'group', 'label', 'k']).distance.mean().reset_index()
    print(by_fleet.groupby(['label', 'group', 'k']).distance.median().unstack('k').round(3).to_string())
    wide = by_fleet.pivot_table(index=['fleet', 'label', 'k'], columns='group', values='distance')
    print('4w closer than random, fleets', (wide['4w'] < wide['random']).groupby(['label', 'k']).agg(['sum', 'size']).to_dict('index'))


def forecast(table, title):
    print('---', title)
    table = table.copy()
    table['group'] = np.where(table.arm == 'method', table.length, table.arm)
    table.loc[table.arm == 'all', 'k'] = 0                          # fleets differ in size, so all candidates sit in one row
    by_fleet = table.groupby(['fleet', 'group', 'k', 'model', 'horizon'])[['nrmse', 'bias']].mean().reset_index()
    for model in ['persistence', 'profile'] + SKILLS:
        part = by_fleet[by_fleet.model == model]
        print(model)
        print(part.groupby(['group', 'k', 'horizon']).nrmse.median().unstack('horizon').round(2).to_string())
    for model in SKILLS:
        part = by_fleet[(by_fleet.model == model) & (by_fleet.group.isin(['4w', 'random', '1y']))]
        wide = part.pivot_table(index=['fleet', 'k', 'horizon'], columns='group', values='nrmse')
        cut = 1 - wide['4w'] / wide['random']
        ratio = wide['4w'] / wide['1y']
        print(model, '4w error cut against random, by k and horizon')
        print(cut.groupby(['k', 'horizon']).median().unstack('horizon').round(3).to_string())
        print(model, '4w below random, fleets of', wide.index.get_level_values(0).nunique())
        print((wide['4w'] < wide['random']).groupby(['k', 'horizon']).sum().unstack('horizon').to_string())
        print(model, '4w over 1y, by k and horizon')
        print(ratio.groupby(['k', 'horizon']).median().unstack('horizon').round(3).to_string())
    best = by_fleet[by_fleet.model.isin(SKILLS)].groupby(['fleet', 'group', 'k', 'horizon']).nrmse.min().unstack('group')
    print('better of ridge and lightgbm, against persistence at 4w')
    persistence = by_fleet[(by_fleet.model == 'persistence') & (by_fleet.group == '4w')].set_index(['fleet', 'k', 'horizon']).nrmse
    print((1 - best['4w'].dropna() / persistence).groupby(['k', 'horizon']).median().unstack('horizon').round(3).to_string())


def main():
    survival()
    checks()
    loss(tables(FOLLOWUP / 'extras', 'loss_*.csv'), 'UK second sample')
    loss(tables(HOLDOUT / 'extras', 'loss_*.csv'), 'Ausgrid hold-out')
    overlap(tables(FOLLOWUP / 'extras', 'overlap_*.csv'), 'UK second sample')
    overlap(tables(HOLDOUT / 'extras', 'overlap_*.csv'), 'Ausgrid hold-out')
    mix(tables(FOLLOWUP / 'extras', 'mix_*.csv'))
    forecast(tables(FOLLOWUP / 'forecast', 'uk_*.csv'), 'UK second sample, select 2018, train 2019, test 2020')
    forecast(tables(HOLDOUT / 'forecast', 'ausgrid*.csv'), 'Ausgrid, select Y1, train Y2, test Y3')
    frozen = tables(CAMPAIGN / 'forecast2' / 'output' / 'results' / 'forecast', 'uk_*.csv')
    forecast(frozen[frozen.fleet != 'uk_national'], 'UK confirmation fleets, picks selected with outage rows, kernel forecast2')


if __name__ == '__main__':
    sys.exit(main())
