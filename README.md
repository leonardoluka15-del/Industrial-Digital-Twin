# AQUA — Industrial Digital Twin

A CPU-friendly Python simulation of a variable-speed pumping station. Control a virtual motor, pump and tank; introduce faults; inspect process trends and export experiments.

## Run on Windows

Install Python 3.11 or 3.12, extract the project, and open its folder in VS Code. In the terminal:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

If you installed 3.11, replace `-3.12` with `-3.11`. Open the local address printed by Streamlit, normally http://localhost:8501.

## Run on Linux / macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

## First experiment

1. Click Start. Automatic control raises the tank to its 3 m setpoint.
2. Increase demand from 12 to 20 L/s; observe the controller's response.
3. Introduce 70% pipe blockage and watch flow drop and diagnostics change.
4. Clear the blockage, introduce a leak, and inspect the water balance.
5. Pause and export the operating history.

Manual mode lets you control motor speed directly. Automatic mode uses PID with demand feedforward and conditional integration to limit windup. Pump shutdown permits motor coast-down. Fault controls persist after Reset; Reset clears plant state and history.

## Model and limits

SI units internally; flow displays in L/s. The tank has a 4 m² area and 5 m height. The centrifugal pump curve is H = 18 n² − RQ², R = 8000/(1−blockage)². Solving against tank static head gives flow. Motor speed follows a 1.5 s first-order lag. An explicit 0.2 s integration step updates mass and thermal balances. Overflow and insufficient water are accounted for. Pump head is expressed as gauge pressure at the discharge; simplified pipe geometry has no extra elevation offset.

Electrical input assumes 68% hydraulic conversion efficiency plus speed-dependent idle loss. Motor temperature uses a simplified lumped thermal model. Parameters are illustrative rather than manufacturer-calibrated. Diagnostics use rules and independent virtual measurements, not a trained model. There is no real equipment connection, persistent database, predictive remaining-life estimate or validated safety controller.

The dashboard refreshes once per second. Simulation speed controls simulated seconds advanced per refresh; it is not a guaranteed real-time clock. History is bounded to 6,000 physics samples (20 simulated minutes); energy remains cumulative since Reset. Browser sessions have independent in-memory plants. Restarting the server clears them.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests cover mass conservation including overflow, setpoint convergence, blockage response, shutdown, sensor disagreement and time-step validation.

## Structure

- `app.py`: Streamlit interface, plots and downloads
- `twin/plant.py`: physics, PID and diagnostics
- `tests/test_plant.py`: simulation checks
- `.streamlit/config.toml`: dashboard theme

No API keys, paid services or GPU required.
