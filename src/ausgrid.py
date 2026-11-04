"""Reads Ausgrid Solar Home into arrays. Asks for named years only, so Y3 values stay unread until the hold-out.

Power is in kW per kWp. Net load is GC + CL - GG, so it is constructed, not observed: these homes are gross metered.
"""
import csv
import datetime as dt
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RAW = ROOT / 'paper3' / 'data_external' / 'ausgrid' / 'extracted'
CACHE = HERE.parent / 'cache'
FILES = {'Y1': '2010-2011 Solar home electricity data.csv',
         'Y2': '2011-2012 Solar home electricity data v2.csv',
         'Y3': '2012-2013 Solar home electricity data v2.csv'}
STARTS = {'Y1': dt.date(2010, 7, 1), 'Y2': dt.date(2011, 7, 1), 'Y3': dt.date(2012, 7, 1)}
ENDS = {'Y1': dt.date(2011, 6, 30), 'Y2': dt.date(2012, 6, 30), 'Y3': dt.date(2013, 6, 30)}
HOMES, SLOTS = 300, 48
LAT, LON = -33.87, 151.21


def parse_day(text):
    for fmt in ('%d/%m/%Y', '%d-%b-%y', '%d/%m/%y'):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(text)


def read_year(year):
    cached = CACHE / f'ausgrid_{year}.npz'
    if cached.exists():
        with np.load(cached) as z:
            return {k: z[k] for k in z.files}
    days = (ENDS[year] - STARTS[year]).days + 1
    gc, cl, gg = (np.full((HOMES, days, SLOTS), np.nan, dtype=np.float32) for _ in range(3))
    capacity, postcode, has_cl = np.zeros(HOMES), np.zeros(HOMES, dtype=int), np.zeros(HOMES, dtype=bool)
    target = dict(GC=gc, CL=cl, GG=gg)
    with open(RAW / FILES[year], newline='', encoding='utf-8', errors='replace') as f:
        rows = csv.reader(f)
        next(rows)
        head = next(rows)
        flag = head.index('Row Quality') if 'Row Quality' in head else None
        for row in rows:
            home, day = int(row[0]) - 1, (parse_day(row[4]) - STARTS[year]).days
            capacity[home], postcode[home] = float(row[1]), int(row[2])
            has_cl[home] |= row[3] == 'CL'
            if 0 <= day < days and row[3] in target and not (flag is not None and row[flag].strip() == 'NA'):
                target[row[3]][home, day] = np.array(row[5:5 + SLOTS], dtype=np.float32)
    cl[~has_cl] = 0                                                 # a home with no CL channel has no controlled load
    out = dict(gc=gc, cl=cl, gg=gg, capacity=capacity, postcode=postcode, has_cl=has_cl)
    CACHE.mkdir(exist_ok=True)
    np.savez_compressed(cached, **out)
    return out


def load(years):
    """kW-per-kWp arrays for the named years, joined in time: pv and net have shape (homes, days, slots)."""
    parts = [read_year(y) for y in years]
    capacity = parts[0]['capacity']
    scale = 1 / (capacity[:, None, None] * 0.5)                     # kWh in 30 min to kW, then per kWp
    pv = np.concatenate([p['gg'] for p in parts], axis=1) * scale
    net = np.concatenate([p['gc'] + p['cl'] - p['gg'] for p in parts], axis=1) * scale
    start, days = STARTS[years[0]], pv.shape[1]
    return dict(pv=pv.astype('float32'), net=net.astype('float32'), capacity=capacity, postcode=parts[0]['postcode'],
                dates=[start + dt.timedelta(days=d) for d in range(days)])


def first_sunday(year, month):
    d = dt.date(year, month, 1)
    return d + dt.timedelta(days=(6 - d.weekday()) % 7)


def daylight_saving(d):
    """NSW rule since 2008: clocks run one hour ahead from the first Sunday of October to the first Sunday of April."""
    return d >= first_sunday(d.year, 10) or d < first_sunday(d.year, 4)


def daylight(dates, min_elevation=5.0):
    """Solar elevation above min_elevation at Sydney for each date and slot, from geometry only.
    Slot i ends at (i + 1) * 30 min on the clock, so its midpoint is used. The clock is NSW civil time, as the
    fleet's output centroid shows, and the change of clock is applied by whole days because it happens at night."""
    doy = np.array([d.timetuple().tm_yday for d in dates])
    gamma = 2 * np.pi * (doy - 1) / 365
    decl = 0.006918 - 0.399912 * np.cos(gamma) + 0.070257 * np.sin(gamma) - 0.006758 * np.cos(2 * gamma) + 0.000907 * np.sin(2 * gamma)
    eqt = 229.18 * (0.000075 + 0.001868 * np.cos(gamma) - 0.032077 * np.sin(gamma) - 0.014615 * np.cos(2 * gamma) - 0.040849 * np.sin(2 * gamma))
    clock = (np.arange(SLOTS) + 0.5) * 30                           # minutes after midnight, slot midpoint
    ahead = 60 * np.array([daylight_saving(x) for x in dates])
    solar = clock[None, :] + 4 * (LON - 150) + (eqt - ahead)[:, None]
    hour = np.deg2rad(solar / 4 - 180)
    lat = np.deg2rad(LAT)
    sin_e = np.sin(lat) * np.sin(decl)[:, None] + np.cos(lat) * np.cos(decl)[:, None] * np.cos(hour)
    return np.rad2deg(np.arcsin(sin_e)) > min_elevation
