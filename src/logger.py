"""
logger.py — Data logging daemon for the Indirect Solar Dryer
IIT Bhilai | Ashish Devadas

Reads all sensors on a configurable interval, appends to CSV,
calculates drying metrics, and broadcasts state to web_server.
"""

import csv
import json
import logging
import os
import signal
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
LOG_INTERVAL_S   = 60        # read interval (seconds)
DATA_DIR         = Path(__file__).parent.parent / "data"
CSV_FILENAME     = "dryer_log.csv"
STATE_FILE       = DATA_DIR / "current_state.json"
INITIAL_WEIGHT_G = 2000.0    # initial wet sample mass (g)
DRY_BASIS_MC_0   = 92.0      # initial moisture content % w.b. (from paper)

CSV_HEADER = [
    "timestamp", "datetime",
    "dht_collector_in_temp",  "dht_collector_in_humidity",
    "dht_collector_out_temp", "dht_collector_out_humidity",
    "dht_chamber_top_temp",   "dht_chamber_top_humidity",
    "dht_chamber_bottom_temp","dht_chamber_bottom_humidity",
    "lc_sample_1_weight",     "lc_sample_2_weight",
    "total_weight",
    "moisture_content_wb",    "drying_rate_g_per_min",
    "collector_efficiency_pct",
    "all_sensors_valid",
]


def _moisture_content_wb(current_weight_g: float, initial_weight_g: float,
                          initial_mc_wb: float) -> float:
    """
    Calculate wet-basis moisture content (%).
    M_wb = (W_water / W_total) × 100
    Dry mass: Wd = Wi × (1 - MCi/100)
    M_wb(t) = (Wt - Wd) / Wt × 100
    """
    wd = initial_weight_g * (1.0 - initial_mc_wb / 100.0)
    if current_weight_g <= wd:
        return 0.0
    mc = (current_weight_g - wd) / current_weight_g * 100.0
    return round(mc, 2)


def _collector_efficiency(t_in: float, t_out: float,
                           mdot: float = 0.06,
                           cp: float   = 1006.0,
                           Ac: float   = 2.0,
                           G: float    = 800.0) -> float:
    """
    Instantaneous thermal efficiency of the solar collector.
    η = ṁ·Cp·(T_out - T_in) / (G·Ac)
    Default values from paper's optimal 0.06 kg/s condition.
    """
    if G <= 0 or t_out <= t_in:
        return 0.0
    eta = (mdot * cp * (t_out - t_in)) / (G * Ac) * 100.0
    return round(min(eta, 100.0), 2)


class DryerLogger:
    """
    Main logging loop. Runs in a background thread.
    Exposes `latest` dict for web_server to read (thread-safe via lock).
    """

    def __init__(self,
                 interval:       int   = LOG_INTERVAL_S,
                 initial_weight: float = INITIAL_WEIGHT_G,
                 initial_mc:     float = DRY_BASIS_MC_0):
        from .sensors import SensorArray
        self.interval       = interval
        self.initial_weight = initial_weight
        self.initial_mc     = initial_mc
        self.sensors        = SensorArray()
        self._lock          = threading.Lock()
        self._latest: dict  = {}
        self._prev_weight:  Optional[float] = None
        self._prev_ts:      Optional[float] = None
        self._running       = False
        self._thread:       Optional[threading.Thread] = None

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._csv_path = DATA_DIR / CSV_FILENAME
        self._ensure_csv_header()

    # ── Public API ─────────────────────────────────────────────────────────────
    @property
    def latest(self) -> dict:
        with self._lock:
            return dict(self._latest)

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info("DryerLogger started  interval=%ds", self.interval)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.interval + 5)
        self.sensors.cleanup()
        log.info("DryerLogger stopped")

    # ── Internal ───────────────────────────────────────────────────────────────
    def _loop(self):
        while self._running:
            try:
                self._tick()
            except Exception as e:
                log.error("Logger tick error: %s", e, exc_info=True)
            time.sleep(self.interval)

    def _tick(self):
        raw = self.sensors.read_all()
        ts  = raw["timestamp"]
        dt  = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

        # Derived metrics
        tw = raw.get("total_weight")
        mc = None
        dr = None
        if tw is not None:
            mc = _moisture_content_wb(tw, self.initial_weight, self.initial_mc)
            if self._prev_weight is not None and self._prev_ts is not None:
                dt_min = (ts - self._prev_ts) / 60.0
                if dt_min > 0:
                    dr = round((self._prev_weight - tw) / dt_min, 4)
            self._prev_weight = tw
            self._prev_ts     = ts

        # Collector efficiency
        t_in  = raw.get("dht_collector_in_temp")
        t_out = raw.get("dht_collector_out_temp")
        ce    = None
        if t_in is not None and t_out is not None:
            ce = _collector_efficiency(t_in, t_out)

        all_valid = all([
            raw.get("dht_collector_in_valid"),
            raw.get("dht_collector_out_valid"),
            raw.get("dht_chamber_top_valid"),
            raw.get("dht_chamber_bottom_valid"),
            raw.get("lc_sample_1_valid"),
            raw.get("lc_sample_2_valid"),
        ])

        row = {
            "timestamp":                   round(ts, 1),
            "datetime":                    dt,
            "dht_collector_in_temp":       raw.get("dht_collector_in_temp"),
            "dht_collector_in_humidity":   raw.get("dht_collector_in_humidity"),
            "dht_collector_out_temp":      raw.get("dht_collector_out_temp"),
            "dht_collector_out_humidity":  raw.get("dht_collector_out_humidity"),
            "dht_chamber_top_temp":        raw.get("dht_chamber_top_temp"),
            "dht_chamber_top_humidity":    raw.get("dht_chamber_top_humidity"),
            "dht_chamber_bottom_temp":     raw.get("dht_chamber_bottom_temp"),
            "dht_chamber_bottom_humidity": raw.get("dht_chamber_bottom_humidity"),
            "lc_sample_1_weight":          raw.get("lc_sample_1_weight"),
            "lc_sample_2_weight":          raw.get("lc_sample_2_weight"),
            "total_weight":                tw,
            "moisture_content_wb":         mc,
            "drying_rate_g_per_min":       dr,
            "collector_efficiency_pct":    ce,
            "all_sensors_valid":           all_valid,
        }

        self._append_csv(row)
        self._write_state(row)
        with self._lock:
            self._latest = row

        log.info("Logged | w=%.1fg  mc=%.1f%%  T_out=%.1f°C",
                 tw or 0, mc or 0, t_out or 0)

    def _ensure_csv_header(self):
        if not self._csv_path.exists() or self._csv_path.stat().st_size == 0:
            with open(self._csv_path, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=CSV_HEADER).writeheader()

    def _append_csv(self, row: dict):
        with open(self._csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADER, extrasaction="ignore")
            writer.writerow(row)

    def _write_state(self, row: dict):
        tmp = STATE_FILE.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(row, f, default=str)
        tmp.replace(STATE_FILE)   # atomic replace
