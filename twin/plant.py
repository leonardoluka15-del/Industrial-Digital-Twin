"""Educational SI-unit centrifugal pump and storage tank model."""
from dataclasses import dataclass
import random
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

    pumps: int = 1
    strategy: str = 'Single'
    pump_trip: bool = False
    noise: float = 0.0
    filter_tau: float = 1.0
    profile: str = 'Constant'

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
        self.rng = random.Random(42)
        self.filtered_level = self.level
        self.filtered_last = self.level
        self.second_speed = 0.0
        self.second_temperature = 25.0
        self.runtime = [0.0, 0.0]
        self.starts = [0, 0]
        self.was_on = [False, False]
        self.lead = 0
        self.lag = False
        self.config_changes = []

    def step(self, cfg: Settings, dt: float = 0.2):
        if not 0 < dt <= 1:
            raise ValueError('Time step must be in (0, 1] seconds')
        if cfg.pumps not in (1, 2) or cfg.demand < 0 or not 0 <= cfg.blockage <= .95 or cfg.leak < 0:
            raise ValueError('Invalid pump count, flow or blockage')
        settings = vars(cfg).copy()
        if not self.config_changes or self.config_changes[-1]['settings'] != settings:
            self.config_changes.append({'time_s': self.time, 'settings': settings})
            self.config_changes = self.config_changes[-1000:]
        demand = cfg.demand
        if cfg.profile == 'Step': demand *= 1 if self.time < 60 else 1.6
        if cfg.profile == 'Cyclic': demand *= 1 + .4 * math.sin(2 * math.pi * self.time / 180)
        truth = self.level
        measured = min(self.capacity, max(0.0, truth + cfg.sensor_bias + self.rng.gauss(0, cfg.noise)))
        alpha = 1 if cfg.filter_tau <= 0 else 1 - math.exp(-dt / cfg.filter_tau)
        self.filtered_level += alpha * (measured - self.filtered_level)
        self.lead = 1 if cfg.pump_trip and cfg.pumps == 2 else 0
        if cfg.pumps == 2 and cfg.strategy == 'Balanced' and not cfg.pump_trip:
            self.lead = int(self.time // 300) % 2
        if cfg.pumps == 2 and cfg.strategy == 'Assist':
            if self.filtered_level < cfg.target - .35: self.lag = True
            if self.filtered_level > cfg.target - .05: self.lag = False
        else: self.lag = False
        active_count = 2 if self.lag and not cfg.pump_trip else 1
        error = cfg.target - self.filtered_level
        derivative = -(self.filtered_level - self.filtered_last) / dt
        feedforward = math.sqrt((self.level + 8000 * (demand / active_count)**2) / 18)
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
        commands = [0.0, 0.0]
        commands[self.lead] = command
        if self.lag: commands[1-self.lead] = command
        if cfg.pump_trip: commands[0] = 0.0
        if not cfg.pump_enabled: commands = [0.0, 0.0]
        speeds = [self.speed, self.second_speed]
        for i in range(2):
            speeds[i] += (commands[i] - speeds[i]) * (1 - math.exp(-dt / 1.5))
            on = commands[i] > .01
            if on and not self.was_on[i]: self.starts[i] += 1
            self.was_on[i] = on
            self.runtime[i] += dt * (speeds[i] > .01)
        self.speed, self.second_speed = speeds
        resistance = 8000 / max(0.03, 1 - cfg.blockage)**2
        flows = [math.sqrt(max(0, 18 * n**2 - truth) / resistance) for n in speeds]
        heads = [truth + resistance * q**2 for q in flows]
        powers = [1000 * 9.81 * q * h / .68 + 120 * n**2 for q,h,n in zip(flows,heads,speeds)]
        flow, power = sum(flows), sum(powers)
        pressure = max(heads) * 1000 * 9.81 / 1e5
        leakage = cfg.leak * math.sqrt(self.level / self.capacity)
        available = self.level * self.area / dt + flow
        outlet = min(demand + leakage, available)
        delivered = min(demand, outlet)
        actual_leak = max(0, outlet - delivered)
        unclipped = self.level + (flow - outlet) * dt / self.area
        overflow = max(0, unclipped - self.capacity) * self.area / dt
        self.level = min(self.capacity, max(0, unclipped))
        cooling = 0.8 if cfg.cooling_failure else 7.0
        self.temperature += (powers[0] * 0.22 - cooling * (self.temperature - 25)) * dt / 1600
        self.second_temperature += (powers[1] * .22 - 7 * (self.second_temperature - 25)) * dt / 1600
        self.energy += power * dt / 3_600_000
        self.time += dt
        self.last_measurement = measured
        self.filtered_last = self.filtered_level
        # Physics residuals use independent flow/level truth, as if a second sensor existed.
        expected_flow = sum(math.sqrt(max(0, 18 * n**2 - truth) / 8000) for n in speeds)
        alerts = []
        if self.level > 4.7: alerts.append('High tank level')
        if self.level < 0.4: alerts.append('Low tank level')
        if expected_flow > 0.003 and flow < expected_flow * 0.75: alerts.append('Flow restriction suspected')
        if abs(measured - truth) > max(0.2, 4 * cfg.noise): alerts.append('Level sensor disagreement')
        if actual_leak > 0.001: alerts.append('Unaccounted water loss')
        if self.temperature > 65: alerts.append('High motor temperature')
        if delivered < demand * 0.95: alerts.append('Demand not met')
        if cfg.pump_trip: alerts.append('Pump 1 tripped')
        for alert in set(alerts) - self._active:
            self.events.append({'time_s': round(self.time, 1), 'event': alert})
        self._active = set(alerts)
        self.events = self.events[-200:]
        row = dict(time_s=self.time, level_m=self.level, measured_level_m=measured,
                   target_m=cfg.target, speed_pct=self.speed*100, inflow_ls=flow*1000,
                   demand_ls=demand*1000, delivered_ls=delivered*1000,
                   leak_ls=actual_leak*1000, overflow_ls=overflow*1000,
                   pressure_bar=pressure, power_kw=power/1000,
                   temperature_c=self.temperature, energy_kwh=self.energy,
                   filtered_level_m=self.filtered_level, pump1_flow_ls=flows[0]*1000,
                   pump2_flow_ls=flows[1]*1000, pump2_speed_pct=self.second_speed*100,
                   pump2_temperature_c=self.second_temperature,
                   pump1_runtime_s=self.runtime[0], pump2_runtime_s=self.runtime[1],
                   pump1_starts=self.starts[0], pump2_starts=self.starts[1])
        self.rows.append(row)
        self.rows = self.rows[-6000:]
        return row, alerts

    def advance(self, cfg, seconds=1.0):
        result = None
        for _ in range(round(seconds / 0.2)):
            result = self.step(cfg)
        return result
