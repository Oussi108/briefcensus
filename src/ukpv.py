"""Reads UK PV into arrays, one fleet at a time. Only the named systems and years are read, so a region stays unread until it is asked for.

Power is in kW per kWp. Timestamps are UTC and mark the end of each 30-minute period, so slot i ends at (i + 1) * 30 min, as in ausgrid.py.
"""
import datetime as dt
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
RAW = HERE.parent / 'data_external' / 'uk_pv'
CACHE = HERE.parent / 'cache'
SLOTS, FLEET, MIN_REGION, MIN_DEBUG, NATIONAL = 48, 300, 300, 100, 1000
CAMPAIGN_YEAR = 2018
MAX_RATIO = 1.5                                                     # publisher's limit of 750 Wh per kWp in 30 min


def cohort():
    """Protocol v2 cohort, from metadata only. It places no condition on years after the campaign."""
    m = pd.read_csv(RAW / 'metadata.csv', parse_dates=['start_datetime_GMT', 'end_datetime_GMT'])
    first = pd.Timestamp(f'{CAMPAIGN_YEAR}-01-01', tz='UTC')
    last = pd.Timestamp(f'{CAMPAIGN_YEAR}-12-31', tz='UTC')
    m = m[(m.kWp > 0) & (m.kWp <= 10) & (m.start_datetime_GMT <= first) & (m.end_datetime_GMT >= last)].copy()
    m['cell'] = np.floor(m.latitude_rounded).astype(int).astype(str) + 'N' + np.floor(m.longitude_rounded).astype(int).astype(str) + 'E'
    return m.sort_values('ss_id').reset_index(drop=True)


def regions(m):
    """Confirmation regions, and the debug cell, chosen by counts alone."""
    counts = m.cell.value_counts()
    return sorted(counts[counts >= MIN_REGION].index), counts[(counts >= MIN_DEBUG) & (counts < MIN_REGION)].index[0]


def fleet_of(m, name):
    """Fixed random sample for a fleet. The national fleet samples all of Great Britain."""
    pool = m if name == 'national' else m[m.cell == name]
    size = min(NATIONAL if name == 'national' else FLEET, len(pool))
    rng = np.random.default_rng(zlib.crc32(name.encode()))
    return pool.iloc[np.sort(rng.choice(len(pool), size, replace=False))].reset_index(drop=True)


def read_year(meta, year):
    """Cube of kW per kWp with shape (systems, days, slots), after the publisher's physical checks. Missing readings stay NaN."""
    ids = meta.ss_id.to_numpy()
    position = pd.Series(np.arange(len(ids)), index=ids)
    start = dt.date(year, 1, 1)
    days = (dt.date(year + 1, 1, 1) - start).days
    cube = np.full((len(ids), days, SLOTS), np.nan, dtype=np.float32)
    for month in range(1, 14):
        y, mo = (year, month) if month <= 12 else (year + 1, 1)             # a period ending at midnight on the 1st may sit in the next file
        path = RAW / '30_minutely' / f'year={y}' / f'month={mo:02d}' / 'data.parquet'
        if not path.exists():
            continue
        t = pq.read_table(path, columns=['ss_id', 'datetime_GMT', 'generation_Wh'], filters=[('ss_id', 'in', ids.tolist())]).to_pandas()
        began = pd.to_datetime(t.datetime_GMT, utc=True) - pd.Timedelta(minutes=30)
        day = (began.dt.tz_localize(None).dt.floor('D') - pd.Timestamp(start)).dt.days.to_numpy()
        slot = (began.dt.hour * 2 + began.dt.minute // 30).to_numpy()
        keep = (day >= 0) & (day < days) & (began.dt.minute.to_numpy() % 30 == 0)
        cube[position[t.ss_id.to_numpy()[keep]].to_numpy(), day[keep], slot[keep]] = t.generation_Wh.to_numpy()[keep]
    cube = cube * 2 / (meta.kWp.to_numpy()[:, None, None] * 1000)
    cube[(cube < 0) | (cube > MAX_RATIO)] = np.nan
    bad = pd.read_csv(RAW / 'bad_data.csv', parse_dates=['start_datetime_GMT', 'end_datetime_GMT'])
    base = pd.Timestamp(start, tz='UTC')
    ends = base + pd.to_timedelta((np.arange(days * SLOTS) + 1) * 30, unit='min')
    for row in bad[bad.ss_id.isin(ids)].itertuples():
        stop = row.end_datetime_GMT if pd.notna(row.end_datetime_GMT) else ends[-1]
        hit = (ends >= row.start_datetime_GMT) & (ends <= stop)
        if hit.any():
            cube[position[row.ss_id]].reshape(-1)[hit] = np.nan
    return cube, [start + dt.timedelta(days=d) for d in range(days)]


def load(name, meta, year):
    cached = CACHE / f'ukpv_{name}_{year}.npz'
    if cached.exists():
        with np.load(cached) as z:
            return z['pv'], [dt.date.fromordinal(int(d)) for d in z['dates']]
    pv, dates = read_year(meta, year)
    CACHE.mkdir(exist_ok=True)
    np.savez_compressed(cached, pv=pv, dates=np.array([d.toordinal() for d in dates]))
    return pv, dates


def solar_mask(dates, lat, lon, min_elevation=5.0):
    """Solar elevation above min_elevation for each date and slot, from geometry only, on a UTC clock."""
    doy = np.array([d.timetuple().tm_yday for d in dates])
    gamma = 2 * np.pi * (doy - 1) / 365
    decl = 0.006918 - 0.399912 * np.cos(gamma) + 0.070257 * np.sin(gamma) - 0.006758 * np.cos(2 * gamma) + 0.000907 * np.sin(2 * gamma)
    eqt = 229.18 * (0.000075 + 0.001868 * np.cos(gamma) - 0.032077 * np.sin(gamma) - 0.014615 * np.cos(2 * gamma) - 0.040849 * np.sin(2 * gamma))
    clock = (np.arange(SLOTS) + 0.5) * 30
    solar = clock[None, :] + 4 * lon + eqt[:, None]
    hour = np.deg2rad(solar / 4 - 180)
    phi = np.deg2rad(lat)
    sin_e = np.sin(phi) * np.sin(decl)[:, None] + np.cos(phi) * np.cos(decl)[:, None] * np.cos(hour)
    return np.rad2deg(np.arcsin(sin_e)) > min_elevation


def coords(meta):
    """Rounded locations in km on a local flat grid."""
    lat, lon = meta.latitude_rounded.to_numpy(), meta.longitude_rounded.to_numpy()
    return np.column_stack([(lon - lon.mean()) * 111.32 * np.cos(np.deg2rad(lat.mean())), (lat - lat.mean()) * 110.57])


def features(meta):
    """Metadata an operator holds without a campaign, as a (features, systems) matrix: orientation sector, tilt band and scaled location."""
    sector = (np.floor(((meta.orientation.to_numpy() + 22.5) % 360) / 45)).astype(int)
    band = np.digitize(meta.tilt.to_numpy(), [25, 35, 45])
    lat = meta.latitude_rounded.to_numpy()
    lon = meta.longitude_rounded.to_numpy()
    scale = max(lat.std(), lon.std(), 1e-6)
    return np.vstack([np.eye(8)[sector].T, np.eye(4)[band].T, (lat - lat.mean()) / scale, (lon - lon.mean()) / scale])
