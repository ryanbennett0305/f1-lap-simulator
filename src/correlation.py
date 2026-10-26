"""Model-vs-measurement helpers: timing, acceleration, regridding,
apex diagnostics and sector times (Stage 5)."""

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

from src.params import G
from src.track import arc_length
from src.vehicle import v_apex, a_long_tyre, a_power, rear_share


def cum_time(s, v):
    """Elapsed time at every point of the grid [s]. Same quadrature as lap_time()."""
    v_mid = 0.5 * (v[:-1] + v[1:])
    return np.concatenate([[0.0], np.cumsum(np.diff(s) / v_mid)])


def accel_profile(s, v):
    """Longitudinal acceleration per segment from d(v^2)/ds = 2a [m/s^2]."""
    return np.diff(v**2) / (2 * np.diff(s))


def regrid(geo, ds_new):
    """Same kappa(s) on a new step size. For integrator tests only."""
    s0, s1 = geo['s'].iloc[0], geo['s'].iloc[-1]
    n_pts = int(round((s1 - s0) / ds_new)) + 1
    s_new = np.linspace(s0, s1, n_pts)
    kap = np.interp(s_new, geo['s'], geo['kappa'])
    with np.errstate(divide='ignore'):
        r_new = 1.0 / np.abs(kap)
    return pd.DataFrame({'s': s_new, 'kappa': kap, 'r': r_new})


def apex_table(geo, rho, car, prominence_kmh=20.0, half=10):
    """Per-corner apex diagnostics from a track_geometry DataFrame.

    Apexes are minima of the MEASURED speed. v_apex is computed here from
    car, so geo needs no extra columns. mu_req is the friction coefficient
    needed to explain the measured apex speed, given car['ClA'].
    """
    s = geo['s'].to_numpy()
    r = geo['r'].to_numpy()
    v = geo['v'].to_numpy()
    va = v_apex(r, car['m'], car['mu_y'], rho, car['ClA'])
    idx, _ = find_peaks(-v, prominence=prominence_kmh / 3.6)

    rows = []
    for i in idx:
        win = slice(max(i - half, 0), i + half + 1)
        r_min = r[win].min()
        v_meas = v[i]
        a_lat = v_meas**2 / r_min
        rows.append({
            's': s[i],
            'r_min': r_min,
            'v_meas_kmh': v_meas * 3.6,
            'v_apex_kmh': va[win].min() * 3.6,
            'v2': v_meas**2,
            'a_lat': a_lat,
            'a_lat_g': a_lat / G,
            'mu_req': a_lat / (G + 0.5 * rho * v_meas**2 * car['ClA'] / car['m']),
        })
    return pd.DataFrame(rows)


def s_at_session_time(lap, session_times):
    """Arc length s [m], as defined by track_geometry, at given session times [s]."""
    pos = lap.get_pos_data()
    s = arc_length(pos['X'].to_numpy() / 10.0, pos['Y'].to_numpy() / 10.0)
    t = pos['SessionTime'].dt.total_seconds().to_numpy()
    return np.interp(session_times, t, s)


def sector_boundaries(lap):
    """Positions in s [m] of the official timing lines for this lap."""
    fields = ['LapStartTime', 'Sector1SessionTime', 'Sector2SessionTime', 'Time']
    times = np.array([lap[f].total_seconds() for f in fields])
    s_b = s_at_session_time(lap, times)
    return dict(zip(['start', 's12', 's23', 'end'], s_b))


def sector_times(s, v, bounds):
    """Time in S1, S2, S3 [s] on the s grid.

    Boundaries outside the grid are clamped to its ends by np.interp, so
    S1 and S3 cover only the part of each sector the grid contains.
    """
    t = cum_time(s, v)
    t_b = np.interp([bounds['start'], bounds['s12'], bounds['s23'], bounds['end']], s, t)
    return np.diff(t_b)


ZONES = ['cornering', 'braking', 'accel_grip', 'accel_power']


def classify_zones(geo, res, car, rho, rtol=1e-6):
    """Active constraint at every grid point of a solve_lap() result.

    Priority: cornering (v at v_apex), then braking (backward pass is the
    minimum), then acceleration split by whichever limit is lower,
    power P_max/(m v) or the friction ellipse.

    If car contains 'w_rear', the tyre limit is scaled by rear_share (RWD traction).    
    """
    v = res['v']
    kappa = geo['kappa'].to_numpy()
    tyre = a_long_tyre(v, kappa, car['m'], car['mu_x'], car['mu_y'], rho, car['ClA'])
    if 'w_rear' in car:
        tyre = tyre * rear_share(v, car, rho)    
    power = a_power(v, car['m'], car['P_max'])
    conditions = [
        np.isclose(v, res['v_apex'], rtol=rtol),
        res['v_bwd'] < res['v_fwd'],
        power < tyre,
    ]
    return np.select(conditions, ['cornering', 'braking', 'accel_power'], default='accel_grip')


def segment_table(s, v_model, v_meas, zone, bounds):
    """One row per grid segment: start position, length, model zone (at the
    segment start), sector, and model - measured time [s]."""
    dt = np.diff(cum_time(s, v_model)) - np.diff(cum_time(s, v_meas))
    s_seg = s[:-1]
    sector = np.select([s_seg < bounds['s12'], s_seg < bounds['s23']],
                       ['S1', 'S2'], default='S3')
    return pd.DataFrame({'s': s_seg, 'ds': np.diff(s), 'zone': zone[:-1],
                         'zone_end': zone[1:], 'sector': sector, 'dt': dt})


def zone_totals(seg):
    """Zone time deltas [s], each segment split half to its start-point label
    and half to its end-point label. 'spread' is half the start-vs-end
    difference: the discretisation uncertainty of the attribution."""
    start = seg.groupby('zone')['dt'].sum().reindex(ZONES, fill_value=0.0)
    end = seg.groupby('zone_end')['dt'].sum().reindex(ZONES, fill_value=0.0)
    return pd.DataFrame({'dt': 0.5 * (start + end),
                         'spread': 0.5 * (end - start).abs()})


def channel_on_grid(lap, s_grid, channel):
    """A telemetry channel resampled onto the s grid, aligned by timestamp
    exactly as track_geometry aligns Speed."""
    pos = lap.get_pos_data()
    s_raw = arc_length(pos['X'].to_numpy() / 10.0, pos['Y'].to_numpy() / 10.0)
    t_pos = pos['Time'].dt.total_seconds().to_numpy()
    tel = lap.get_telemetry()
    t_tel = tel['Time'].dt.total_seconds().to_numpy()
    c_raw = np.interp(t_pos, t_tel, tel[channel].to_numpy().astype(float))
    return np.interp(s_grid, s_raw, c_raw)