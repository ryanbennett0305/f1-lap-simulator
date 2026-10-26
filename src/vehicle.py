"""Point-mass vehicle model: cornering-limit speed."""

import numpy as np
from src.params import G


def critical_radius(m, mu_y, rho, ClA):
    """Radius above which aero grip outgrows cornering demand [m].

    r_crit = 2m / (mu_y * rho * ClA). For r >= r_crit the corner
    is not grip-limited at any speed.
    """
    return 2 * m / (mu_y * rho * ClA)


def v_apex(r, m, mu_y, rho, ClA, g=G):
    """Cornering-limit speed from m v^2/r = mu_y (m g + 0.5 rho v^2 ClA).

    Closed form: v^2 = mu_y g r / (1 - mu_y k r), where k = rho ClA / (2m).

    Parameters
    ----------
    r : float or array of radii [m]
    m, mu_y, rho, ClA : vehicle and air parameters (SI units)

    Returns
    -------
    v : array [m/s]. np.inf where r >= r_crit (cornering does not limit speed;
        Stage 4's power/drag limit decides there).
    """
    r = np.asarray(r, dtype=float)
    k = rho * ClA / (2 * m)
    denom = 1 - mu_y * k * r

    v = np.full_like(r, np.inf)          # default: no cornering limit
    ok = denom > 0                       # boolean mask: grip-limited points
    v[ok] = np.sqrt(mu_y * g * r[ok] / denom[ok])
    return v


def normal_accel(v, m, rho, ClA, g=G):
    """Normal load per unit mass, n = g + rho*ClA*v^2/(2m)  [m/s^2].

    Weight plus downforce, divided by mass. Both tyre limits scale with this.
    """
    v = np.asarray(v, dtype=float)
    return g + rho * ClA * v**2 / (2 * m)


def a_long_tyre(v, kappa, m, mu_x, mu_y, rho, ClA, g=G):
    """Longitudinal acceleration the tyres can still supply [m/s^2] (friction ellipse).

    Lateral demand a_y = v^2*|kappa| uses part of the grip budget; this returns
    mu_x*n*sqrt(1 - (a_y/a_y_max)^2), the longitudinal grip left over.
    Returns 0 where the corner already uses all the grip (or more).
    """
    v = np.asarray(v, dtype=float)
    kappa = np.asarray(kappa, dtype=float)
    n = normal_accel(v, m, rho, ClA, g)
    a_y = v**2 * np.abs(kappa)
    a_y_max = mu_y * n
    remaining = np.clip(1.0 - (a_y / a_y_max)**2, 0.0, None)
    return mu_x * n * np.sqrt(remaining)


def a_power(v, m, P_max, v_min=1.0):
    """Power-limited acceleration P_max/(m*v) [m/s^2].

    v is floored at v_min to avoid dividing by zero at standstill (the tyre
    limit is far lower than this at low speed, so the floor never sets the answer).
    """
    v = np.asarray(v, dtype=float)
    return P_max / (m * np.maximum(v, v_min))


def a_drag(v, m, rho, CdA):
    """Aerodynamic drag deceleration 0.5*rho*CdA*v^2/m [m/s^2] (positive)."""
    v = np.asarray(v, dtype=float)
    return 0.5 * rho * CdA * v**2 / m


def rear_share(v, car, rho, g=G):
    """Fraction of total normal load on the rear (driven) axle: static
    weight share plus aero balance. No longitudinal load transfer."""
    k = rho * car['ClA'] / (2 * car['m'])
    return (car['w_rear'] * g + car['aero_rear'] * k * v**2) / (g + k * v**2)


def a_accel(v, kappa, car, rho, g=G):
    """Net forward acceleration available when accelerating [m/s^2].

    min(tyre ellipse, power) - drag. Can be negative above terminal speed.
    `car` is a parameter dict such as CAR_2022 or CAR_2022_FIT.
    """
    tyre = a_long_tyre(v, kappa, car['m'], car['mu_x'], car['mu_y'],
                       rho, car['ClA'], g)
    if 'w_rear' in car:                    # RWD traction (Stage 5 diagnostic)
        tyre = tyre * rear_share(v, car, rho, g)
    power = a_power(v, car['m'], car['P_max'])
    return np.minimum(tyre, power) - a_drag(v, car['m'], rho, car['CdA'])


def a_brake(v, kappa, car, rho, g=G):
    """Deceleration available when braking [m/s^2] (positive number).

    Tyre ellipse plus drag (drag helps braking). No power limit on brakes.
    """
    tyre = a_long_tyre(v, kappa, car['m'], car['mu_x'], car['mu_y'],
                       rho, car['ClA'], g)
    return tyre + a_drag(v, car['m'], rho, car['CdA'])