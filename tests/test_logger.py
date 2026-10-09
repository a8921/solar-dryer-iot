"""
test_logger.py — Unit tests for the Solar Dryer IoT system
IIT Bhilai | Ashish Devadas

Run:
    pytest tests/ -v
"""

import math
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import _moisture_content_wb, _collector_efficiency


# ── Moisture content tests ─────────────────────────────────────────────────────
class TestMoistureContent:

    def test_initial_mc(self):
        """At t=0, mc should equal initial_mc_wb."""
        mc = _moisture_content_wb(2000.0, 2000.0, 92.0)
        assert abs(mc - 92.0) < 0.01

    def test_dry_mass_reached(self):
        """When weight equals dry mass, MC should be 0."""
        wd = 2000.0 * (1 - 92 / 100)   # = 160 g
        mc = _moisture_content_wb(wd, 2000.0, 92.0)
        assert mc == 0.0

    def test_below_dry_mass_clamped(self):
        """Weight below dry mass should clamp to 0."""
        wd = 2000.0 * (1 - 92 / 100)
        mc = _moisture_content_wb(wd - 50, 2000.0, 92.0)
        assert mc == 0.0

    def test_half_drying(self):
        """Halfway through drying — MC should be between 0 and 92."""
        # After losing half the free water:
        initial  = 2000.0
        wd       = initial * 0.08          # 160 g dry mass
        water_i  = initial - wd            # 1840 g initial water
        mid_w    = wd + water_i / 2        # 1080 g
        mc       = _moisture_content_wb(mid_w, initial, 92.0)
        assert 0 < mc < 92.0

    def test_target_12pct(self):
        """A specific weight corresponding to 12% MC should return ~12."""
        # M_wb = (W - Wd) / W → W = Wd / (1 - M_wb/100)
        wd = 2000.0 * 0.08
        w_at_12 = wd / (1 - 12/100)
        mc = _moisture_content_wb(w_at_12, 2000.0, 92.0)
        assert abs(mc - 12.0) < 0.1

    def test_mc_decreases_with_weight(self):
        """MC must decrease as weight decreases."""
        initial = 2000.0
        weights = [2000, 1800, 1500, 1200, 800, 500, 200]
        mcs     = [_moisture_content_wb(w, initial, 92.0) for w in weights]
        for i in range(len(mcs) - 1):
            assert mcs[i] >= mcs[i+1], f"MC not monotone at index {i}"

    def test_mc_in_range(self):
        """MC must always be in [0, 100]."""
        for w in range(100, 2100, 100):
            mc = _moisture_content_wb(float(w), 2000.0, 92.0)
            assert 0 <= mc <= 100

    def test_different_initial_mc(self):
        """Works for different initial moisture contents."""
        mc = _moisture_content_wb(1000.0, 1000.0, 75.0)
        assert abs(mc - 75.0) < 0.01


# ── Collector efficiency tests ─────────────────────────────────────────────────
class TestCollectorEfficiency:

    def test_positive_delta_t(self):
        """Normal operation — should return positive efficiency."""
        eta = _collector_efficiency(t_in=30, t_out=55)
        assert eta > 0

    def test_zero_delta_t(self):
        """No temperature gain — efficiency should be 0."""
        eta = _collector_efficiency(t_in=40, t_out=40)
        assert eta == 0.0

    def test_negative_delta_t(self):
        """T_out < T_in — physically invalid, should return 0."""
        eta = _collector_efficiency(t_in=50, t_out=40)
        assert eta == 0.0

    def test_paper_condition(self):
        """
        Paper reports η=19.56% at 0.06 kg/s with ~10°C collector ΔT.
        Check we get a plausible value in that regime.
        ṁ=0.06, Cp=1006, ΔT=6.5°C, G=800, Ac=2 → η≈24%
        """
        eta = _collector_efficiency(t_in=40, t_out=46.5,
                                     mdot=0.06, cp=1006, Ac=2.0, G=800)
        assert 15 < eta < 50

    def test_capped_at_100(self):
        """Pathological inputs must not exceed 100%."""
        eta = _collector_efficiency(t_in=20, t_out=200)
        assert eta <= 100.0

    def test_higher_mdot_gives_higher_eta(self):
        """Higher flow rate → more heat extracted → higher efficiency."""
        e1 = _collector_efficiency(30, 55, mdot=0.02)
        e2 = _collector_efficiency(30, 55, mdot=0.06)
        assert e2 > e1

    def test_irradiance_scaling(self):
        """Doubling irradiance should halve efficiency (same heat out).
        Use small ΔT so neither result hits the 100% cap."""
        e1 = _collector_efficiency(30, 34, G=400)
        e2 = _collector_efficiency(30, 34, G=800)
        assert e1 > e2
        assert abs(e1 / e2 - 2.0) < 0.01


# ── Sensor simulation tests ────────────────────────────────────────────────────
class TestSensorSimulation:

    def test_dht11_simulated_returns_valid(self):
        """Simulated DHT11 should return valid readings in physical range."""
        from src.sensors import DHT11Sensor
        s = DHT11Sensor(pin=4, label="collector_in")
        r = s.read()   # will use sim since no hardware
        assert r.valid
        assert 0 <= r.temperature <= 100
        assert 0 <= r.humidity    <= 100

    def test_loadcell_simulated_returns_valid(self):
        """Simulated load cell should return positive weight."""
        from src.sensors import LoadCell
        lc = LoadCell(dout=5, pd_sck=6, label="sample_1")
        r  = lc.read()
        assert r.valid
        assert r.weight > 0

    def test_sensor_array_read_all_keys(self):
        """read_all() must return all expected keys."""
        from src.sensors import SensorArray, DHT11_LABELS
        arr = SensorArray()
        data = arr.read_all()
        for lbl in DHT11_LABELS:
            assert f"dht_{lbl}_temp"     in data
            assert f"dht_{lbl}_humidity" in data
            assert f"dht_{lbl}_valid"    in data
        assert "total_weight" in data
        assert "timestamp"    in data

    def test_sensor_array_sim_data_types(self):
        """Simulated readings should be floats."""
        from src.sensors import SensorArray
        arr  = SensorArray()
        data = arr.read_all()
        assert isinstance(data["dht_collector_in_temp"],     float)
        assert isinstance(data["dht_collector_in_humidity"], float)
        assert isinstance(data["total_weight"],              float)
