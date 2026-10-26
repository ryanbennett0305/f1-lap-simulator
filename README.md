# F1 Lap Time and Race Strategy Simulator

A Python model of the 2022 Spanish Grand Prix.
A quasi steady state lap time simulation checked against FastF1 telemetry, 
a tyre degradation fit from race laps  and a pit stop strategy search.

## Where to look
- `src/`: model code (track geometry, vehicle, solver, correlation, degradation)
- `notebooks/`: one notebook per stage of the project, with results
- `figures/`: the plots

## Running it
Python 3.12. Install with `pip install -r requirements.txt`.
FastF1 downloads session data on the first run.