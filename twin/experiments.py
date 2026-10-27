"""Reproducible offline experiments and whole-run performance scores."""
from dataclasses import replace
from .plant import Plant

def scores(rows):
    if not rows: return {}
    dt = .2
    volume = sum(r['delivered_ls'] / 1000 * dt for r in rows)
    return {
        'Tracking RMSE (m)': (sum((r['level_m']-r['target_m'])**2 for r in rows)/len(rows))**.5,
        'Energy (kWh)': rows[-1]['energy_kwh'],
        'Delivered (m³)': volume,
        'Specific energy (kWh/m³)': rows[-1]['energy_kwh']/volume if volume else None,
        'Unserved demand (m³)': sum(max(0,r['demand_ls']-r['delivered_ls'])/1000*dt for r in rows),
        'Overflow (m³)': sum(r['overflow_ls']/1000*dt for r in rows),
    }

def compare(cfg, seconds=300):
    results = []
    for name, changes in [('Single',dict(pumps=1,strategy='Single')),
                          ('Standby',dict(pumps=2,strategy='Standby')),
                          ('Assist',dict(pumps=2,strategy='Assist')),
                          ('Balanced',dict(pumps=2,strategy='Balanced'))]:
        plant=Plant()
        settings=replace(cfg, **changes)
        for _ in range(round(seconds/.2)): plant.step(settings)
        results.append({'Strategy':name, **scores(plant.rows)})
    return results
