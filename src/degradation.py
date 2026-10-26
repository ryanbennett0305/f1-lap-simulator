"""Stage 6: tyre degradation from race laps.

Cleaning rules (counted), the fixed-effects design matrix and the
least-squares fit, as developed in notebooks/06_tyre_degradation.ipynb.
"""
import numpy as np
import pandas as pd

COMPOUNDS = ['SOFT', 'MEDIUM', 'HARD']
PHYS = ['c_lap', 'k_SOFT', 'k_MEDIUM', 'k_HARD', 'b_MEDIUM', 'b_HARD']


def add_gaps(laps):
    """Copy of FastF1 laps with lap time in s ('t') and the gaps to the
    cars ahead and behind at the line, over all cars on any lap."""
    df = laps.copy()
    df['t'] = df['LapTime'].dt.total_seconds()
    order = df.sort_values('Time')
    df['gap_ahead'] = order['Time'].diff().dt.total_seconds()
    df['gap_behind'] = -order['Time'].diff(-1).dt.total_seconds()
    return df


def keep(d, mask, rule, log):
    """Apply a boolean mask and record the before/after counts in log."""
    out = d[mask]
    log.append({'rule': rule, 'before': len(d), 'after': len(out),
                'dropped': len(d) - len(out)})
    return out


def clean_laps(df, gap_min=1.5, outlier_frac=1.07):
    """Stage 6 cleaning rules, in order. All but the last are independent
    of lap time. outlier_frac=None skips the outlier rule.
    Returns (clean laps, filter log as a DataFrame)."""
    log = []
    c = df
    c = keep(c, c['t'].notna(), 'has a lap time', log)
    c = keep(c, c['Compound'].notna() & c['Stint'].notna(), 'compound and stint known', log)
    c = keep(c, c['LapNumber'] > 1, 'not lap 1', log)
    c = keep(c, c['PitInTime'].isna(), 'not an in-lap', log)
    c = keep(c, c['PitOutTime'].isna(), 'not an out-lap', log)
    c = keep(c, c['TrackStatus'] == '1', 'green all lap', log)
    c = keep(c, c['Deleted'] != True, 'not deleted', log)
    c = keep(c, c['IsAccurate'] == True, 'FastF1 IsAccurate', log)
    c = keep(c, ~(c['gap_ahead'] < gap_min), f'clear air (gap ahead >= {gap_min} s)', log)
    if outlier_frac is not None:
        med = c.groupby('Driver')['t'].transform('median')
        c = keep(c, c['t'] <= outlier_frac * med,
                 f'within {100 * outlier_frac:.0f} % of driver median', log)
    return c, pd.DataFrame(log)


def is_held(d, held_out):
    """Boolean array: True where (Driver, Stint) is in the held_out list."""
    return np.array([(a, b) in held_out for a, b in zip(d['Driver'], d['Stint'])])


def design(d, drivers):
    """Design matrix: driver dummies, Medium/Hard offsets (Soft = baseline),
    lap number, and tyre age in its own compound's column."""
    cols = {}
    for drv in drivers:
        cols[f'd_{drv}'] = (d['Driver'] == drv).astype(float)
    for comp in ['MEDIUM', 'HARD']:
        cols[f'b_{comp}'] = (d['Compound'] == comp).astype(float)
    cols['c_lap'] = d['LapNumber'].astype(float)
    for comp in COMPOUNDS:
        cols[f'k_{comp}'] = d['TyreLife'] * (d['Compound'] == comp)
    return pd.DataFrame(cols)


def fit(d):
    """Least-squares fit of t = d_driver + b_compound + c*L + k_compound*age.
    Returns coefficients with SEs, covariance, residuals, RMS and rank.
    SEs assume independent laps, so they are optimistic."""
    drv = sorted(d['Driver'].unique())
    X = design(d, drv)
    A = X.to_numpy()
    y = d['t'].to_numpy()
    beta, _, rank, sv = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ beta
    n, p = A.shape
    cov = (resid @ resid / (n - p)) * np.linalg.inv(A.T @ A)
    return {'coef': pd.DataFrame({'value': beta, 'se': np.sqrt(np.diag(cov))}, index=X.columns),
            'cov': pd.DataFrame(cov, index=X.columns, columns=X.columns),
            'resid': pd.Series(resid, index=d.index),
            'rms': np.sqrt(resid @ resid / n), 'rank': rank, 'drivers': drv,
            'cond': sv[0] / sv[-1]}