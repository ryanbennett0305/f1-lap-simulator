"""Quasi-steady-state lap solver: forward/backward passes and lap time.

Integrates d(v^2)/ds = 2a with forward Euler in distance (ME22011, Lecture 7),
using v^2 as the state so there is no division by v.
"""
import numpy as np
from src.vehicle import v_apex, a_accel, a_brake


def _march(ds, kappa, v_lim, a_func, car, rho, v0):
    """Step v^2 along the track, capped at v_lim at every point.

    ds     : step lengths, len(kappa) - 1  [m]
    kappa  : curvature at each point       [1/m]
    v_lim  : speed ceiling at each point (v_apex; may contain inf) [m/s]
    a_func : function(v, kappa, car, rho) -> acceleration available [m/s^2]
    v0     : speed at the first point      [m/s]
    """
    n = len(kappa)
    v = np.empty(n)
    v[0] = min(v0, v_lim[0])
    for i in range(n - 1):
        a = float(a_func(v[i], kappa[i], car, rho))
        v2 = v[i]**2 + 2 * a * ds[i]
        v[i + 1] = min(np.sqrt(max(v2, 0.0)), v_lim[i + 1])
    return v


def forward_pass(s, kappa, v_lim, car, rho, v_start):
    """Fastest speed reachable from v_start without braking [m/s]."""
    return _march(np.diff(s), kappa, v_lim, a_accel, car, rho, v_start)


def backward_pass(s, kappa, v_lim, car, rho, v_end):
    """Fastest speed from which every corner ahead can still be made [m/s].

    Braking run in reverse is acceleration, so march the reversed track
    with a_brake, then reverse the result back.
    """
    v_rev = _march(np.diff(s)[::-1], kappa[::-1], v_lim[::-1],
                   a_brake, car, rho, v_end)
    return v_rev[::-1]


def lap_time(s, v):
    """Lap time [s]: sum of ds / v over segments, v = mean of the end speeds."""
    ds = np.diff(s)
    v_mid = 0.5 * (v[:-1] + v[1:])
    return np.sum(ds / v_mid)


def solve_lap(geo, car, rho, v_start, v_end):
    """Full QSS solution on a track_geometry() DataFrame.

    Returns a dict of arrays (v_apex, v_fwd, v_bwd, v) and the lap time t [s].
    """
    s = geo['s'].to_numpy()
    kappa = geo['kappa'].to_numpy()
    va = v_apex(geo['r'].to_numpy(), car['m'], car['mu_y'], rho, car['ClA'])
    vf = forward_pass(s, kappa, va, car, rho, v_start)
    vb = backward_pass(s, kappa, va, car, rho, v_end)
    v = np.minimum(np.minimum(va, vf), vb)
    return {'v_apex': va, 'v_fwd': vf, 'v_bwd': vb, 'v': v, 't': lap_time(s, v)}


