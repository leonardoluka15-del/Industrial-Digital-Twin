"""Educational SI-unit centrifugal pump and storage tank model."""
from dataclasses import dataclass, asdict
import math

@dataclass
class Settings:
    target: float = 3.0
    demand: float = 0.012  # m3/s
    mode: str = 'Automatic'
    manual_speed: float = 0.65
    kp: float = 0.55
    ki: float = 0.015
    kd: float = 0.0
    blockage: float = 0.0
    leak: float = 0.0  # m3/s at full tank
    sensor_bias: float = 0.0
    cooling_failure: bool = False
    pump_enabled: bool = True

class Plant:
    area = 4.0  # m2
    capacity = 5.0  # m

    def __init__(self):
        self.time = 0.0
        self.level = 2.0
        self.speed = 0.0
        self.temperature = 25.0
        self.integral = 0.0
        self.last_measurement = self.level
        self.energy = 0.0
        self.rows = []
        self.events = []
        self._active = set()

    def step(self, cfg: Settings, dt: float = 0.2):
        if not 0 < dt <= 1:
            raise ValueError('Time step must be in (0, 1] seconds')
        measured = min(self.capacity, max(0.0, self.level + cfg.sensor_bias))
        error = cfg.target - measured
        derivative = -(measured - self.last_measurement) / dt
        feedforward = math.sqrt((self.level + 8000 * cfg.demand**2) / 18)
        candidate = self.integral + error * dt
        raw = feedforward + cfg.kp * error + cfg.ki * candidate + cfg.kd * derivative
        command = min(1.0, max(0.0, raw))
        if cfg.mode == 'Automatic':
            if cfg.pump_enabled and (0 <= raw <= 1 or raw > 1 and error < 0 or raw < 0 and error > 0):
                self.integral = candidate
        else:
            command = cfg.manual_speed
        if not cfg.pump_enabled:
            command = 0.0
        self.speed += (command - self.speed) * (1 - math.exp(-dt / 1.5))
        resistance = 8000 / max(0.03, 1 - cfg.blockage)**2
        flow = math.sqrt(max(0, 18 * self.speed**2 - self.level) / resistance)
        head = self.level + resistance * flow**2
        pressure = head * 1000 * 9.81 / 1e5
        efficiency = 0.68
        power = 1000 * 9.81 * flow * head / efficiency + 120 * self.speed**2
        leakage = cfg.leak * math.sqrt(self.level / self.capacity)
        available = self.level * self.area / dt + flow
        outlet = min(cfg.demand + leakage, available)
        delivered = min(cfg.demand, outlet)
        actual_leak = max(0, outlet - delivered)
        unclipped = self.level + (flow - outlet) * dt / self.area
        overflow = max(0, unclipped - self.capacity) * self.area / dt
        self.level = min(self.capacity, max(0, unclipped))
        cooling = 0.8 if cfg.cooling_failure else 7.0
        self.temperature += (power * 0.22 - cooling * (self.temperature - 25)) * dt / 1600
        self.energy += power * dt / 3_600_000
        self.time += dt
        self.last_measurement = measured
        # Physics residuals use independent flow/level truth, as if a second sensor existed.
        expected_flow = math.sqrt(max(0, 18 * self.speed**2 - self.level) / 8000)
        alerts = []
        if self.level > 4.7: alerts.append('High tank level')
        if self.level < 0.4: alerts.append('Low tank level')
        if expected_flow > 0.003 and flow < expected_flow * 0.75: alerts.append('Flow restriction suspected')
        if abs(measured - self.level) > 0.2: alerts.append('Level sensor disagreement')
        if actual_leak > 0.001: alerts.append('Unaccounted water loss')
        if self.temperature > 65: alerts.append('High motor temperature')
        if delivered < cfg.demand * 0.95: alerts.append('Demand not met')
        for alert in set(alerts) - self._active:
            self.events.append({'time_s': round(self.time, 1), 'event': alert})
        self._active = set(alerts)
        self.events = self.events[-200:]
        row = dict(time_s=self.time, level_m=self.level, measured_level_m=measured,
                   target_m=cfg.target, speed_pct=self.speed*100, inflow_ls=flow*1000,
                   demand_ls=cfg.demand*1000, delivered_ls=delivered*1000,
                   leak_ls=actual_leak*1000, overflow_ls=overflow*1000,
                   pressure_bar=pressure, power_kw=power/1000,
                   temperature_c=self.temperature, energy_kwh=self.energy)
        self.rows.append(row)
        self.rows = self.rows[-6000:]
        return row, alerts

    def advance(self, cfg, seconds=1.0):
        result = None
        for _ in range(round(seconds / 0.2)):
            result = self.step(cfg)
        return result
