"""Builds the manuscript figures and numbers.json from the result tables, so every number in the paper traces to a kernel output.

python build_figures.py
"""
import json
import sys
from pathlib import Path

import matplotlib
import matplotlib.colors
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from summarise import MAIN_K, errors, kept, read  # noqa: E402

CAMPAIGN = ROOT / 'kaggle' / 'campaign'
FIG = Path(__file__).resolve().parent / 'figures'
INK, MUTED, GRID, BLUE, ORANGE, AQUA, GREY = '#0b0b0b', '#52514e', '#e4e3df', '#2a78d6', '#eb6834', '#1baf7a', '#8c8b86'
RAMP = {5: '#9ec5f0', 10: '#2a78d6', 20: '#123f78'}
LENGTHS = ['1w', '2w', '4w', '3m', '1y']
ARMS = ['oracle', 'method', 'method_fit', 'medoids', 'gp_mi_fit', 'mrmr_fit', 'maxdiff', 'closest', 'screened', 'correlated', 'spatial', 'metadata', 'largest', 'random', 'RC', 'GC']
NAMES = dict(method='BriefCensus', medoids='k-medoids', gp_mi_fit='GP mutual information', mrmr_fit='mRMR', spatial='Spatial, no campaign', metadata='Metadata, no campaign', random='Random', screened='Screened random', closest='Closest', oracle='Hindsight floor')

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8, 'axes.edgecolor': MUTED, 'axes.linewidth': .6, 'axes.labelcolor': INK, 'xtick.color': MUTED, 'ytick.color': MUTED,
                     'xtick.major.size': 0, 'ytick.major.size': 0, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': .5, 'axes.axisbelow': True,
                     'axes.titlesize': 8.5, 'axes.titleweight': 'bold', 'axes.titlelocation': 'left', 'legend.frameon': False, 'savefig.dpi': 600, 'savefig.bbox': 'tight'})


def runs():
    return dict(dev=(read(ROOT / 'results' / 'campaign', 'ausgrid_dev.csv'), 'Y2'),
                holdout=(read(CAMPAIGN / 'holdout' / 'output' / 'results' / 'campaign', 'ausgrid_holdout*.csv'), 'Y3'),
                frozen=(read(CAMPAIGN / 'confirm' / 'output' / 'results' / 'campaign', 'uk_*.csv'), '2019'),
                clean=(read(CAMPAIGN / 'clean' / 'output' / 'results' / 'clean', '*.csv'), '2019'),
                second=(read(CAMPAIGN / 'second' / 'output' / 'results' / 'clean', '*b.csv'), '2019'))


def regional(t):
    return t[t.fleet != 'national']


def length_table(t, period):
    t = regional(t)
    random, year = errors(t, 'random', '', period), errors(t, 'method', '1y', period)
    out = {'random': random[list(MAIN_K)].median().round(2).to_dict()}
    for length in LENGTHS:
        e = errors(t, 'method', length, period)
        out[length] = e[list(MAIN_K)].median().round(2).to_dict()
        if length != '1y':
            s = kept(random, year, e)
            ratio = (e[list(MAIN_K)] / year[list(MAIN_K)]).median(axis=1)
            out[length].update(S=round(float(s.median()), 3), S_min=round(float(s.min()), 3), S_max=round(float(s.max()), 3), share=round(float((s >= .5).mean()), 3), over_year=round(float(ratio.median()), 3))
    return out


def arm_table(t, period, length='4w'):
    t = regional(t)
    out = {}
    for arm in ARMS:
        span = '' if arm in ('random', 'spatial', 'metadata', 'largest', 'oracle') else length
        e = errors(t, arm, span, period)
        if len(e):
            out[arm] = e[list(MAIN_K)].median().round(2).to_dict()
    return out


def framework():
    """One flow figure: blocks are the static framework, panels are the dynamic pipeline. The small plots are schematic drawings, not measured data."""
    navy, slate, ink, soft, frame_ink = '#22324a', '#55667f', '#1f2430', '#5b6472', '#7d8794'
    temp, pick, fail, off = '#2f6db3', '#d9622b', '#b3261e', '#dde0e5'
    style = {'font.family': 'Arial', 'mathtext.fontset': 'custom', 'mathtext.rm': 'Arial', 'mathtext.it': 'Arial:italic', 'mathtext.bf': 'Arial:bold', 'mathtext.bfit': 'Arial:italic:bold'}
    with plt.rc_context(style):
        fig, ax = plt.subplots(figsize=(7.2, 2.55))
        ax.set_xlim(-.5, 201)
        ax.set_ylim(0, 71.3)
        ax.set_aspect('equal')
        ax.axis('off')
        fig.subplots_adjust(0, 0, 1, 1)

        def text(x, y, s, size=7, color=ink, ha='center', va='center', **kw):
            ax.text(x, y, s, fontsize=size, color=color, ha=ha, va=va, **kw)

        def line(xs, ys, color=ink, lw=1.0, ls='-', z=3):
            ax.plot(xs, ys, color=color, lw=lw, ls=ls, zorder=z, solid_capstyle='round')

        def arrow(x0, y0, x1, y1, color=navy, lw=1.1, size=6.5, style='arc3'):
            ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle='-|>', mutation_scale=size, lw=lw, color=color, shrinkA=0, shrinkB=0, zorder=6, connectionstyle=style))

        def panel(x, y, s, fill, cross=False):
            """A tilted PV module on a stand. The colour shows the metering state of the system."""
            w, h, skew = .84 * s, .56 * s, .2 * s
            base = y + .16 * s
            ax.add_patch(plt.Polygon([(x - w / 2, base), (x + w / 2 - skew, base), (x + w / 2, base + h), (x - w / 2 + skew, base + h)], facecolor=fill, edgecolor='none', zorder=4))
            for f in (1 / 3, 2 / 3):
                line([x - w / 2 + f * (w - skew), x - w / 2 + skew + f * (w - skew)], [base, base + h], 'white', .45, z=5)
            line([x - w / 2 + skew / 2, x + w / 2 - skew / 2], [base + h / 2] * 2, 'white', .45, z=5)
            stand = soft if fill != off else off
            line([x - .1 * s] * 2, [y, base], stand, .7, z=3)
            line([x - .28 * s, x + .08 * s], [y, y], stand, .7, z=3)
            if cross:
                line([x - .55 * s, x + .55 * s], [y - .08 * s, y + .82 * s], fail, 1.1, z=6)
                line([x - .55 * s, x + .55 * s], [y + .82 * s, y - .08 * s], fail, 1.1, z=6)

        def block(x0, y0, x1, y1, label, fill=navy, mark=None, size=7):
            ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle='round,pad=0,rounding_size=1.3', facecolor=fill, edgecolor='none', zorder=4))
            text((x0 + x1) / 2, (y0 + y1) / 2 - .1, label, size=size, color='white', weight='bold', zorder=5, linespacing=1.1)
            if mark:
                ax.add_patch(plt.Circle((x0 + .4, y1 - .4), 2.1, facecolor='white', edgecolor=fill, lw=.8, zorder=6))
                text(x0 + .4, y1 - .5, mark, size=6.2, color=fill, weight='bold', zorder=7)

        def function(x, y, label, width):
            ax.add_patch(FancyBboxPatch((x - width / 2, y - 2.4), width, 4.8, boxstyle='round,pad=0,rounding_size=1', facecolor='white', edgecolor=frame_ink, lw=.6, zorder=6))
            text(x, y - .1, label, size=6.6, color=ink, zorder=7)

        def stage(x0, x1, title):
            ax.add_patch(FancyBboxPatch((x0, 13), x1 - x0, 57, boxstyle='round,pad=0,rounding_size=1.6', facecolor='none', edgecolor=frame_ink, lw=.8, ls=(0, (4, 2.4)), zorder=1))
            text((x0 + x1) / 2, 16.8, title, size=8, weight='bold', color=navy)

        def matrix(x0, y0, x1, y1, grid):
            rows, cols = grid.shape
            dx, dy = (x1 - x0) / cols, (y1 - y0) / rows
            for r in range(rows):
                for c in range(cols):
                    value = grid[r, c]
                    colour = '#f1f2f4' if np.isnan(value) else tuple(1 - value * (1 - v) for v in matplotlib.colors.to_rgb(temp))
                    ax.add_patch(plt.Rectangle((x0 + c * dx, y1 - (r + 1) * dy), dx, dy, facecolor=colour, edgecolor='white', lw=.25, zorder=3))

        def daily(x0, x1, y0, height, colour=ink, lw=1.1):
            x = np.linspace(0, 1, 120)
            line([x0, x1], [y0, y0], soft, .6)
            line(x0 + (x1 - x0) * x, y0 + height * np.sin(np.pi * x) ** 1.3, colour, lw)

        def estimate_row(x0, crossed):
            """Monitors feed the day rule, which gives the fleet estimate."""
            ys = (61, 54, 47)
            for i, y in enumerate(ys):
                failed = crossed and i == 1
                panel(x0, y, 4.6, pick, cross=failed)
                if not failed:
                    line([x0 + 2.7, x0 + 7.2], [y + 1.7, 55.4 + (1 - i) * 2.2], pick, .7)
            block(x0 + 7.2, 47.5, x0 + 19.2, 63.3, 'Day\nrule', navy, '3')
            arrow(x0 + 19.2, 55.4, x0 + 22.6, 55.4)
            daily(x0 + 23, x0 + 37.5, 48.5, 11.5)
            text(x0 + 30.2, 62.8, r'$\hat{r}_t$', size=7.5)

        def models(x0, x1):
            ax.add_patch(FancyBboxPatch((x0, 22.2), x1 - x0, 19.6, boxstyle='round,pad=0,rounding_size=1.3', facecolor='#f1f3f6', edgecolor=frame_ink, lw=.7, zorder=2))
            block(x0 + 1.5, 33, x1 - 1.5, 40.3, 'Ridge', slate, size=6.8)
            block(x0 + 1.5, 23.7, x1 - 1.5, 31, 'LightGBM', slate, size=6.8)

        # Campaign
        stage(1, 31, r'Campaign, $\mathbfit{L}$ days')
        spots = [(5.5, 64.3), (11, 65.2), (17, 64), (23, 65), (27, 63.6), (7.5, 59.2), (13.5, 59.8), (20, 59), (25.5, 58.6), (5, 54.4), (10.5, 55), (16.5, 54.4), (22.5, 54.8), (27.3, 54)]
        for x, y in spots:
            panel(x, y, 4.4, temp)
        rng = np.random.default_rng(3)
        grid = np.clip(rng.uniform(.5, 1, 16)[None] * np.array([1, .8, .92, .98, .72, .86])[:, None] + rng.normal(0, .05, (6, 16)), .3, 1)
        grid[2, 1:4] = np.nan
        outage = [8, 9, 10]
        grid[np.ix_([0, 2, 3, 5], outage)] = np.nan
        matrix(5, 29, 27, 49.5, grid)
        arrow(16, 53.6, 16, 50.2, soft, .8, 5)
        text(16, 25.2, r'$p_{i,t},\ c_i$', size=7.5)

        # Selection
        stage(34.5, 102, 'Selection')
        arrow(27.3, 39, 38, 39)
        block(38, 30, 51.5, 48, 'Outage\nfilter', navy, '1')
        arrow(51.5, 39, 55, 39)
        kept = np.delete(grid, outage, axis=1)
        matrix(55, 31, 66, 47, kept)
        text(60.5, 28.4, r'$T$', size=7.5)
        arrow(66, 39, 69.5, 39)
        block(69.5, 30, 83, 48, 'Greedy\nsearch', navy, '2')
        arrow(79.8, 48.2, 72.8, 48.2, navy, .9, 5.5, 'arc3,rad=1.25')
        text(77.5, 55.4, r'$|A| < k$', size=6.6, color=navy)
        arrow(83, 39, 86.5, 39)
        for row in range(4):
            for col in range(3):
                chosen = (col, row) in ((0, 1), (2, 2), (1, 0))
                panel(88.7 + col * 4, 32 + row * 4, 3.5, pick if chosen else off)
        text(92.7, 28.4, r'$A$', size=7.5)
        function(45.5, 25.6, r'capacity $\geq$ 50%', 20)
        function(76.2, 25.6, r'$\mathrm{min}_j\ \mathrm{MSE}(r_{A \cup j},\ r_t)$', 21.5)
        arrow(96, 44, 106.8, 54.5, navy, 1.1, 6.5, 'arc3,rad=-.2')

        # Training year
        stage(105.5, 151.5, 'Training year')
        estimate_row(109.5, False)
        function(121.7, 44.6, r'$E_i \geq \frac{1}{4}\, \mathrm{med}\, E$', 17)
        models(127.5, 146.5)
        arrow(140, 47.8, 140, 42, navy, 1.1, 6)
        text(143, 45, 'fit', size=6.8, color=soft)
        text(115, 32, r'$\mathbf{x}_t$:' + '\nlags\nprofile\nsun', size=6.5, color=soft, linespacing=1.15)
        arrow(121.5, 32, 127.3, 32, soft, .8, 5)

        # Later years
        stage(155, 200, 'Later years')
        estimate_row(158.5, True)
        models(158.5, 177.5)
        arrow(146.5, 32, 158.3, 32)
        text(149, 35, r'$f_h$', size=7, color=navy)
        line([189, 189, 168, 168], [47.8, 44.6, 44.6, 44.6], navy, 1.1, z=5)
        arrow(168, 44.6, 168, 42, navy, 1.1, 6)
        arrow(177.5, 32, 180.5, 32)
        x = np.linspace(0, 1, 120)
        curve = np.sin(np.pi * x) ** 1.3
        split = 68
        plot_x = 181 + 17 * x
        line([181, 198], [24, 24], soft, .6)
        line(plot_x[:split], 24 + 12 * curve[:split], ink, 1.1)
        line(plot_x[split:], 24 + 12 * curve[split:], pick, 1.1, (0, (2.4, 1.6)))
        line([plot_x[split]] * 2, [24, 37], soft, .5, z=2)
        text(193, 38.6, r'$\hat{r}_{t+h}$', size=7, color=pick)
        text(189.5, 21, r'$h \leq 6$ h', size=6.6, color=soft)

        # Legend
        y = 4.6
        items = [(10, temp, False, r'$m$ temporary meters'), (56, pick, False, r'$k$ permanent monitors'), (105, off, False, 'No meter'), (136, pick, True, 'Failed monitor')]
        for x, fill, cross, label in items:
            panel(x, y - 1.7, 4.6, fill, cross=cross)
            text(x + 4.2, y, label, size=7, ha='left')
        line([170, 178], [y, y], pick, 1.1, (0, (2.4, 1.6)))
        text(180, y, 'Forecast', size=7, ha='left')
        fig.savefig(FIG / 'fig1_framework.png')
        plt.close(fig)


def length_figure(r):
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), sharey=True)
    for ax, (key, title) in zip(axes, (('holdout', '(a) Ausgrid hold-out, scored on Y3'), ('second', '(b) UK second sample, scored on 2019'))):
        t, period = r[key]
        t = regional(t)
        random = errors(t, 'random', '', period)
        for k in MAIN_K:
            y = [errors(t, 'method', length, period)[k].median() for length in LENGTHS]
            ax.plot(range(5), y, color=RAMP[k], lw=2, marker='o', ms=4, mec='white', mew=.6, label=f'BriefCensus, k = {k}')
            ax.plot([-.1, 4.1], [random[k].median()] * 2, color=RAMP[k], lw=1, ls=(0, (4, 3)))
            ax.text(4.14, random[k].median(), f'k = {k}', va='center', fontsize=6.4, color=MUTED)
            ax.text(.5, (y[0] + y[1]) / 2 - 1.05, f'k = {k}', ha='center', va='center', fontsize=6.4, color=INK)
        ax.set_xticks(range(5), ['1 week', '2 weeks', '4 weeks', '3 months', '1 year'])
        ax.set_xlim(-.2, 4.75)
        ax.set_title(title)
        ax.set_xlabel('Length of the metering campaign')
        ax.grid(axis='x', visible=False)
    axes[0].set_ylabel('nRMSE of the fleet estimate (%)')
    axes[0].set_ylim(0, None)
    key = [plt.Line2D([], [], color=MUTED, lw=2, marker='o', ms=4, mec='white', mew=.6, label='BriefCensus'), plt.Line2D([], [], color=MUTED, lw=1, ls=(0, (4, 3)), label='Random monitors')]
    axes[0].legend(handles=key, loc='lower left', ncol=2, fontsize=6.6, handlelength=2.4)
    fig.tight_layout(w_pad=1.2)
    fig.savefig(FIG / 'fig2_length.png')
    plt.close(fig)


def comparison_figure(r):
    t, period = r['second']
    t = regional(t)
    order = ['oracle', 'method', 'medoids', 'gp_mi_fit', 'mrmr_fit', 'spatial', 'random', 'screened', 'closest', 'metadata']
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    for i, arm in enumerate(order):
        span = '' if arm in ('random', 'spatial', 'metadata', 'oracle') else '4w'
        e = errors(t, arm, span, period)[10]
        color = BLUE if arm == 'method' else ('#bdbcb6' if arm != 'random' else ORANGE)
        y = len(order) - i
        jitter = np.linspace(-.17, .17, len(e))
        ax.scatter(e.sort_values(), y + jitter, s=11, color=color, alpha=.55, lw=0, zorder=2)
        ax.plot([e.median()] * 2, [y - .33, y + .33], color=INK if arm != 'method' else BLUE, lw=1.8, zorder=3)
        ax.text(e.max() + .35, y, f'{e.median():.2f}', va='center', fontsize=6.6, color=INK)
    ax.set_yticks(range(len(order), 0, -1), [NAMES[a] for a in order])
    ax.set_xlabel('nRMSE of the fleet estimate at k = 10 (%)')
    ax.grid(axis='y', visible=False)
    ax.set_xlim(0, None)
    fig.savefig(FIG / 'fig3_comparison.png')
    plt.close(fig)


def outage_figure(r):
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.7))
    ax = axes[0]
    series = (('frozen', 'Outage rows kept', ORANGE), ('clean', 'Outage rows removed', BLUE))
    ax.set_title('(a) Same 16 UK fleets, k = 10, scored on 2019')
    for key, label, color in series:
        t, period = r[key]
        t = regional(t)
        y = [errors(t, 'method', length, period)[10].median() for length in LENGTHS]
        rand = errors(t, 'random', '', period)[10].median()
        ax.plot(range(5), y, color=color, lw=2, marker='o', ms=4, mec='white', mew=.6)
        ax.plot([-.1, 4.1], [rand, rand], color=color, lw=1, ls=(0, (4, 3)))
        ax.text(4.14, rand, 'random', va='center', fontsize=6.4, color=MUTED)
        ax.text(1.5, y[1] + 1.5 if key == 'frozen' else y[1] - 2.3, label, fontsize=6.8, color=INK, ha='center')
    ax.set_xticks(range(5), ['1 w', '2 w', '4 w', '3 m', '1 y'])
    ax.set_xlim(-.2, 4.9), ax.set_ylim(0, None)
    ax.set_ylabel('nRMSE (%)'), ax.set_xlabel('Campaign length')
    ax.grid(axis='x', visible=False)

    ax = axes[1]
    ax.set_title('(b) Systems reporting on 2019 outage rows, k = 10')
    d = pd.concat([pd.read_csv(f, keep_default_na=False) for f in sorted((CAMPAIGN / 'followup' / 'output' / 'results' / 'survival').glob('*.csv'))], ignore_index=True)
    d = d[d.k == 10]
    for kind, label, color in (('raw', 'Chosen with outage rows', ORANGE), ('clean', 'Chosen without outage rows', BLUE)):
        y = [d[(d.kind == kind) & (d.length == length)].groupby('fleet').share_reporting.mean().median() for length in LENGTHS]
        ax.plot(range(5), y, color=color, lw=2, marker='o', ms=4, mec='white', mew=.6)
        ax.text(4.0, y[-1] + .035, label, fontsize=6.8, color=INK, ha='right')
    rand = d[d.kind == 'random'].groupby('fleet').share_reporting.mean().median()
    ax.plot([-.1, 4.1], [rand, rand], color=GREY, lw=1, ls=(0, (4, 3)))
    ax.text(4.0, rand - .05, 'Random sets', ha='right', fontsize=6.8, color=INK)
    ax.set_xticks(range(5), ['1 w', '2 w', '4 w', '3 m', '1 y'])
    ax.set_ylim(0, .7), ax.set_xlim(-.2, 4.3)
    ax.set_ylabel('Share of chosen systems'), ax.set_xlabel('Campaign length')
    ax.grid(axis='x', visible=False)
    fig.tight_layout(w_pad=1.5)
    fig.savefig(FIG / 'fig6_outage.png')
    plt.close(fig)


def forecast_tables():
    second = pd.concat([pd.read_csv(f, keep_default_na=False) for f in sorted((CAMPAIGN / 'followup' / 'output' / 'results' / 'forecast').glob('uk_*.csv'))], ignore_index=True)
    ausgrid = pd.concat([pd.read_csv(f, keep_default_na=False) for f in sorted((CAMPAIGN / 'holdout' / 'output' / 'results' / 'forecast').glob('ausgrid*.csv'))], ignore_index=True)
    return dict(holdout=ausgrid, second=second)


def forecast_wide(t, model):
    t = t[t.model == model].copy()
    t['group'] = np.where(t.arm == 'method', t.length, t.arm)
    t.loc[t.arm == 'all', 'k'] = 0
    return t.groupby(['fleet', 'group', 'k', 'horizon']).nrmse.mean().unstack('group')


def forecast_figure(tables):
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.6), sharey=True)
    hours = {1: .5, 2: 1, 4: 2, 6: 3, 12: 6}
    for ax, (key, title) in zip(axes, (('holdout', '(a) Ausgrid, test year Y3'), ('second', '(b) UK second sample, test year 2020'))):
        wide = forecast_wide(tables[key], 'ridge')
        cut = (100 * (1 - wide['4w'] / wide['random'])).dropna().groupby(['k', 'horizon']).median().unstack('horizon')
        for k in MAIN_K:
            ax.plot(range(5), cut.loc[k], color=RAMP[k], lw=2, marker='o', ms=4, mec='white', mew=.6)
            if k == 20:
                ax.text(.02, cut.loc[k].iloc[0] * .7, f'k = {k}', va='top', fontsize=6.6, color=INK)
            else:
                ax.text(1.12, cut.loc[k].iloc[1] + .9, f'k = {k}', va='bottom', fontsize=6.6, color=INK)
        ax.set_xticks(range(5), [f'{hours[h]:g} h' for h in cut.columns])
        ax.set_xlim(-.2, 4.2)
        ax.set_title(title), ax.set_xlabel('Forecast horizon')
        ax.grid(axis='x', visible=False)
    axes[0].set_ylabel('Error cut against random monitors (%)')
    axes[0].set_ylim(0, None)
    fig.tight_layout(w_pad=1.2)
    fig.savefig(FIG / 'fig5_forecast.png')
    plt.close(fig)


def loss_table(folder, pattern):
    t = pd.concat([pd.read_csv(f, keep_default_na=False) for f in sorted(folder.glob(pattern))], ignore_index=True)
    t['group'] = np.where(t.arm == 'random', 'random', t.length)
    return t.groupby(['fleet', 'group', 'k', 'lost']).nrmse.mean().reset_index().groupby(['group', 'k', 'lost']).nrmse.median()


def sizes(t, period, length='4w'):
    t = regional(t)
    return {str(m): float(errors(t, 'method', length, period, size=m)[10].median()) for m in (25, 50, 100)} | {'all': float(errors(t, 'method', length, period)[10].median())}


def robustness_figure(r, second_loss, holdout_loss):
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.5))
    ax = axes[0]
    ax.set_title('(a) Campaign size, 4 weeks, k = 10')
    for key, label, color in (('second', 'UK second sample', BLUE), ('holdout', 'Ausgrid hold-out', ORANGE)):
        s = sizes(*r[key])
        ax.plot(range(4), [s[m] for m in ('25', '50', '100', 'all')], color=color, lw=2, marker='o', ms=4, mec='white', mew=.6)
        ax.text(1.55, (s['50'] + s['100']) / 2 + (.9 if color == BLUE else -1.5), label, fontsize=6.8, color=INK, ha='center')
    ax.set_xticks(range(4), ['25', '50', '100', 'all'])
    ax.set_xlabel('Systems metered in the campaign, m'), ax.set_ylabel('nRMSE (%)')
    ax.set_ylim(0, None), ax.grid(axis='x', visible=False)
    ax.set_yticks([0, 5, 10, 15])

    ax = axes[1]
    ax.set_title('(b) Monitors lost in the scoring year, k = 10')
    for table, label, color, nudge in ((second_loss, 'UK', BLUE, (-.5, 0)), (holdout_loss, 'Ausgrid', ORANGE, (0, .4))):
        ax.plot(range(4), [table['4w', 10, i] for i in range(4)], color=color, lw=2, marker='o', ms=4, mec='white', mew=.6)
        ax.plot(range(4), [table['random', 10, i] for i in range(4)], color=color, lw=1, ls=(0, (4, 3)))
        ax.text(3.08, table['4w', 10, 3] + nudge[0], f'{label}, BriefCensus', va='center', fontsize=6.4, color=INK)
        ax.text(3.08, table['random', 10, 3] + nudge[1], f'{label}, random', va='center', fontsize=6.4, color=MUTED)
    ax.set_xticks(range(4), ['0', '1', '2', '3'])
    ax.set_xlim(-.2, 4.5), ax.set_ylim(0, None)
    ax.set_xlabel('Chosen monitors removed at random')
    ax.grid(axis='x', visible=False)
    fig.tight_layout(w_pad=1.5)
    fig.savefig(FIG / 'fig4_robustness.png')
    plt.close(fig)


def main():
    FIG.mkdir(exist_ok=True)
    r = runs()
    numbers = {key: dict(lengths=length_table(t, p), arms=arm_table(t, p), sizes=sizes(t, p) if key != 'dev' else None) for key, (t, p) in r.items()}
    second_loss = loss_table(CAMPAIGN / 'followup' / 'output' / 'results' / 'extras', 'loss_*.csv')
    holdout_loss = loss_table(CAMPAIGN / 'holdout' / 'output' / 'results' / 'extras', 'loss_*.csv')
    tables = forecast_tables()
    numbers['forecast'] = {}
    for key, t in tables.items():
        for model in ('ridge', 'lightgbm', 'persistence'):
            wide = forecast_wide(t, model)
            numbers['forecast'][f'{key}_{model}'] = {g: wide[g].dropna().groupby(['k', 'horizon']).median().unstack('horizon').round(2).to_dict('index') for g in ('4w', '3m', '1y', 'random', 'all')}
    framework()
    length_figure(r)
    comparison_figure(r)
    outage_figure(r)
    forecast_figure(tables)
    robustness_figure(r, second_loss, holdout_loss)
    with open(Path(__file__).resolve().parent / 'numbers.json', 'w') as f:
        json.dump(numbers, f, indent=1, default=str)
    for key in r:
        print(key, json.dumps(numbers[key]['lengths']))
        print('  arms', json.dumps(numbers[key]['arms']))
        print('  sizes', numbers[key]['sizes'])


if __name__ == '__main__':
    main()
