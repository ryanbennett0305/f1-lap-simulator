"""Track geometry from FastF1 position data: arc length, smoothing, curvature."""
import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt


def raw_path(lap):
    """Raw X/Y position [m] and time [s] for one FastF1 lap."""
    pos = lap.get_pos_data()
    x = pos['X'].to_numpy() / 10.0          # FastF1 X/Y are in decimetres
    y = pos['Y'].to_numpy() / 10.0
    t = pos['Time'].dt.total_seconds().to_numpy()
    return x, y, t


def arc_length(x, y):
    """Cumulative distance along a polyline [m], starting at 0."""
    seg = np.hypot(np.diff(x), np.diff(y))
    return np.concatenate(([0.0], np.cumsum(seg)))


def smooth_path(x, y, ds, L, order=4):
    """Zero-phase Butterworth low-pass of a uniformly sampled path, cut-off wavelength L [m]."""
    b, a = butter(order, 1 / L, fs=1 / ds)
    return filtfilt(b, a, x), filtfilt(b, a, y)


def curvature(x, y, ds):
    """Signed curvature [1/m] of a path sampled at uniform spacing ds."""
    dx = np.gradient(x, ds)
    dy = np.gradient(y, ds)
    ddx = np.gradient(dx, ds)
    ddy = np.gradient(dy, ds)
    return (dx * ddy - dy * ddx) / (dx**2 + dy**2)**1.5


def track_geometry(lap, ds=2.0, L=60.0, r_max=1e4):
    """Uniformly sampled track geometry and measured speed for one lap.

    Returns a DataFrame with columns:
    s [m], x [m], y [m], kappa [1/m], r [m], v [m/s], a_lat_g [g].
    """
    x, y, t = raw_path(lap)
    s = arc_length(x, y)
    if np.any(np.diff(s) <= 0):
        raise ValueError('Repeated position samples: arc length is not strictly increasing.')

    s_u = np.arange(0.0, s[-1], ds)
    x_u = np.interp(s_u, s, x)
    y_u = np.interp(s_u, s, y)
    x_s, y_s = smooth_path(x_u, y_u, ds, L)
    kappa = curvature(x_s, y_s, ds)

    # FastF1 Distance runs ~1.13 % (51.7 m) longer than the integrated arc length s over the lap
    tel = lap.get_telemetry()
    t_tel = tel['Time'].dt.total_seconds().to_numpy()
    v_raw = np.interp(t, t_tel, tel['Speed'].to_numpy()) / 3.6
    v = np.interp(s_u, s, v_raw)

    return pd.DataFrame({
        's': s_u,
        'x': x_s,
        'y': y_s,
        'kappa': kappa,
        'r': 1 / np.maximum(np.abs(kappa), 1 / r_max),
        'v': v,
        'a_lat_g': v**2 * np.abs(kappa) / 9.81,
    })