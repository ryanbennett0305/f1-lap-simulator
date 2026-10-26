"""Vehicle parameters for a 2022 F1 car in qualifying trim.

Public estimates only. Each value states its source and assumptions.
Air density is NOT here: it is an environment value, computed per session
from FastF1 weather data.
"""

G = 9.81  # m/s^2

CAR_2022 = {
    # FIA 2022 Tech Regs Art. 4.1: 798 kg min (car + driver, no fuel)
    # + ASSUMED 10 kg qualifying fuel (out-lap, flying lap, in-lap, 1 kg sample)
    'm': 808.0,       # kg
    # Midpoint of range derived from Mercedes-AMG F1 'Downforce explained' (2022):
    # weight at ~150 km/h -> 7.33; 3-4x weight at ASSUMED 320 km/h -> 4.83-6.45
    'ClA': 6.1,       # m^2
    # OptimumG (C. Rouelle): warm slick on dry asphalt, mu = 1.4-1.8
    'mu_y': 1.6,      # -
    # --- Stage 4 values (provisional) ---
    'mu_x': 1.6,      # -   F1 mu_x quoted 1.5-1.7 (BME vehicle dynamics course)
    'CdA': 1.5,       # m^2 Cd 0.7-1.1 x A ~1.4-1.6; to be checked vs top speed
    'P_max': 670e3,   # W   552 kW ICE (Honda, via forum) + 120 kW MGU-K (regs)
}

# Plausible bounds for sensitivity studies: (low, high)
RANGES_2022 = {
    'm': (803, 818),
    'ClA': (4.8, 7.3),
    'mu_y': (1.4, 1.8),
    'CdA': (1.0, 1.8),          # Stage 3/4 sourcing table
    'P_max': (650e3, 750e3),    # W, same units as CAR_2022['P_max']
    'mu_x': (1.5, 1.7),         # Stage 3/4 sourcing table
}

# --- Identified grip set: FITTED, NOT SOURCED -------------------------------
# From notebook 03: least squares of implied a_lat = A + B*v^2 over 9 LEC apexes
#   A = 23.3 +/- 2.2 m/s^2,  B = 0.00696 +/- 0.00108 1/m
#   mu = A/g = 2.38;  ClA = 2*m*B/(mu*rho) = 4.16 m^2 (with rho = 1.135)
# Only A and B are identified; the mu/ClA split is not (corr = -0.83).
# mu_x = mu_y so the solver depends only on A and B.
# CIRCULAR for LEC's lap time (fitted on that lap). VER's lap is the held-out check.
# Note mu_x = 2.38 extrapolates lateral grip to longitudinal (sourced 1.5-1.7).
CAR_2022_FIT = {**CAR_2022, 'mu_y': 2.38, 'mu_x': 2.38, 'ClA': 4.16}


# Rear-wheel-drive traction (Stage 5 diagnostic). Not part of CAR_2022:
# merged in explicitly as {**car, **RWD_2022} so baseline results are unchanged.
RWD_2022 = {
    'w_rear': 0.5475,      # static rear weight share; Art. 4.2 range 0.54-0.555 (The Race, G. Anderson)
    'aero_rear': 0.57,     # rear share of downforce; 0.54 (CoP at CoG, Durham) to 0.60 (G. Anderson)
}
RWD_RANGES_2022 = {'w_rear': (0.54, 0.555), 'aero_rear': (0.54, 0.60)}