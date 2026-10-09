"""
sensors.py — Hardware abstraction layer for the Indirect Solar Dryer IoT system
IIT Bhilai | Ashish Devadas

Supports:
  - 4× DHT11 temperature/humidity sensors (GPIO direct)
  - 2× HX711 load-cell amplifiers (24-bit ADC)
  - Mock/simulation mode when running off-Pi (testing on any PC)
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

# ── DHT11 GPIO pin assignments ─────────────────────────────────────────────────
# Positions: collector_in, collector_out, chamber_top, chamber_bottom
DHT11_PINS = [4, 17, 27, 22]       # BCM numbering
DHT11_LABELS = [
    "collector_in",    # solar collector inlet air
    "collector_out",   # solar collector outlet air
    "chamber_top",     # drying chamber top
    "chamber_bottom",  # drying chamber bottom
]

# ── HX711 pin assignments ──────────────────────────────────────────────────────
HX711_CONFIGS = [
    {"dout": 5,  "pd_sck": 6,  "label": "sample_1"},   # main drying sample
    {"dout": 13, "pd_sck": 19, "label": "sample_2"},   # secondary / reference
]

# ── Calibration factors (run calibrate_loadcell.py to determine yours) ────────
# Units: grams per raw ADC unit
LOAD_CELL_CALIBRATION = {
    "sample_1": -102.3,   # replace after calibration
    "sample_2": -98.7,    # replace after calibration
}
LOAD_CELL_OFFSET = {
    "sample_1": 0,
    "sample_2": 0,
}


@dataclass
class DHT11Reading:
    label:       str
    pin:         int
    temperature: Optional[float] = None   # °C
    humidity:    Optional[float] = None   # %RH
    valid:       bool = False
    error:       Optional[str] = None


@dataclass
class LoadCellReading:
    label:  str
    weight: Optional[float] = None   # grams
    raw:    Optional[int]   = None
    valid:  bool = False
    error:  Optional[str] = None


# ── Detect hardware availability ───────────────────────────────────────────────
def _hw_available() -> bool:
    try:
        import RPi.GPIO          # noqa: F401
        import adafruit_dht      # noqa: F401
        import board             # noqa: F401
        return True
    except (ImportError, NotImplementedError):
        return False

HW_AVAILABLE = _hw_available()


# ── DHT11 reader ──────────────────────────────────────────────────────────────
class DHT11Sensor:
    """Wrapper around adafruit_dht.DHT11 with retry logic."""

    MAX_RETRIES = 5
    RETRY_DELAY = 2.0   # seconds — DHT11 needs time between reads

    def __init__(self, pin: int, label: str):
        self.pin   = pin
        self.label = label
        self._dev  = None
        if HW_AVAILABLE:
            self._init_device()

    def _init_device(self):
        try:
            import adafruit_dht, board
            board_pin = getattr(board, f"D{self.pin}")
            self._dev = adafruit_dht.DHT11(board_pin, use_pulseio=False)
            log.debug("DHT11 on pin %d (%s) initialised", self.pin, self.label)
        except Exception as e:
            log.warning("DHT11 init failed pin %d: %s", self.pin, e)

    def read(self) -> DHT11Reading:
        if not HW_AVAILABLE or self._dev is None:
            return self._simulated_read()

        for attempt in range(self.MAX_RETRIES):
            try:
                t = self._dev.temperature
                h = self._dev.humidity
                if t is not None and h is not None:
                    return DHT11Reading(
                        label=self.label, pin=self.pin,
                        temperature=float(t), humidity=float(h),
                        valid=True,
                    )
            except RuntimeError as e:
                log.debug("DHT11 read attempt %d/%d pin %d: %s",
                          attempt+1, self.MAX_RETRIES, self.pin, e)
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
            except Exception as e:
                log.error("DHT11 error pin %d: %s", self.pin, e)
                return DHT11Reading(label=self.label, pin=self.pin,
                                    valid=False, error=str(e))

        return DHT11Reading(label=self.label, pin=self.pin,
                            valid=False, error="max retries exceeded")

    def _simulated_read(self) -> DHT11Reading:
        import math, random
        t = 45 + 10 * math.sin(time.time() / 600) + random.uniform(-1, 1)
        h = 30 + 5  * math.sin(time.time() / 400) + random.uniform(-1, 1)
        if "collector" in self.label:
            t += 15
        return DHT11Reading(label=self.label, pin=self.pin,
                            temperature=round(t, 1), humidity=round(h, 1),
                            valid=True)

    def exit(self):
        if self._dev:
            try:
                self._dev.exit()
            except Exception:
                pass


# ── HX711 load cell reader ────────────────────────────────────────────────────
class LoadCell:
    """Wrapper around hx711 library."""

    N_SAMPLES = 5   # median-average readings

    def __init__(self, dout: int, pd_sck: int, label: str):
        self.dout   = dout
        self.pd_sck = pd_sck
        self.label  = label
        self._hx    = None
        if HW_AVAILABLE:
            self._init_device()

    def _init_device(self):
        try:
            from hx711 import HX711
            self._hx = HX711(dout=self.dout, pd_sck=self.pd_sck)
            self._hx.set_reading_format("MSB", "MSB")
            self._hx.set_reference_unit(LOAD_CELL_CALIBRATION[self.label])
            self._hx.reset()
            self._hx.tare()
            log.info("HX711 (%s) tared successfully", self.label)
        except Exception as e:
            log.warning("HX711 init failed (%s): %s", self.label, e)

    def read(self) -> LoadCellReading:
        if not HW_AVAILABLE or self._hx is None:
            return self._simulated_read()
        try:
            vals = [self._hx.get_weight(1) for _ in range(self.N_SAMPLES)]
            vals.sort()
            weight = float(vals[self.N_SAMPLES // 2])   # median
            self._hx.power_down()
            self._hx.power_up()
            return LoadCellReading(label=self.label, weight=round(weight, 1), valid=True)
        except Exception as e:
            log.error("HX711 read error (%s): %s", self.label, e)
            return LoadCellReading(label=self.label, valid=False, error=str(e))

    def _simulated_read(self) -> LoadCellReading:
        import math, random
        # Simulate 2 kg sample losing ~150 g/hour
        elapsed_h = (time.time() % 86400) / 3600
        weight = max(200, 2000 - 150 * elapsed_h + random.uniform(-5, 5))
        return LoadCellReading(label=self.label,
                               weight=round(weight, 1), valid=True)

    def tare(self):
        if self._hx:
            try:
                self._hx.tare()
                log.info("HX711 (%s) tared", self.label)
            except Exception as e:
                log.error("Tare failed (%s): %s", self.label, e)


# ── Sensor array manager ───────────────────────────────────────────────────────
class SensorArray:
    """Manages all 4 DHT11s and 2 HX711s; returns a unified reading dict."""

    def __init__(self):
        self.dht_sensors = [
            DHT11Sensor(pin=DHT11_PINS[i], label=DHT11_LABELS[i])
            for i in range(len(DHT11_PINS))
        ]
        self.load_cells = [
            LoadCell(dout=cfg["dout"], pd_sck=cfg["pd_sck"], label=cfg["label"])
            for cfg in HX711_CONFIGS
        ]
        log.info("SensorArray ready  hw=%s  sim=%s",
                 HW_AVAILABLE, not HW_AVAILABLE)

    def read_all(self) -> dict:
        """
        Returns a flat dict of all sensor readings + derived metrics.
        Keys:
            dht_<label>_temp, dht_<label>_humidity, dht_<label>_valid
            lc_<label>_weight, lc_<label>_valid
            total_weight, moisture_content_wb, timestamp
        """
        ts = time.time()
        result = {"timestamp": ts}

        # DHT11 readings
        for s in self.dht_sensors:
            r = s.read()
            result[f"dht_{r.label}_temp"]     = r.temperature
            result[f"dht_{r.label}_humidity"] = r.humidity
            result[f"dht_{r.label}_valid"]    = r.valid

        # Load cell readings
        total_w = 0.0
        lc_valid = True
        for lc in self.load_cells:
            r = lc.read()
            result[f"lc_{r.label}_weight"] = r.weight
            result[f"lc_{r.label}_valid"]  = r.valid
            if r.valid and r.weight is not None:
                total_w += r.weight
            else:
                lc_valid = False
        result["total_weight"] = round(total_w, 1) if lc_valid else None

        return result

    def cleanup(self):
        for s in self.dht_sensors:
            s.exit()
        if HW_AVAILABLE:
            try:
                import RPi.GPIO as GPIO
                GPIO.cleanup()
            except Exception:
                pass
