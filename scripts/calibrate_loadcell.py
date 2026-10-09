#!/usr/bin/env python3
"""
calibrate_loadcell.py — One-time calibration for HX711 load cells
IIT Bhilai | Ashish Devadas

Run this BEFORE starting sensor_logger.py or web_server.py.
Follow the on-screen prompts.

Usage:
    python3 scripts/calibrate_loadcell.py

Output:
    Prints the calibration factor to paste into src/sensors.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Check hardware
try:
    from hx711 import HX711
    import RPi.GPIO as GPIO
    HW = True
except ImportError:
    HW = False


def calibrate_one(name: str, dout: int, pd_sck: int, known_mass_g: float) -> float:
    """
    Interactive calibration for one load cell.
    Returns calibration factor (grams per raw ADC unit).
    """
    print(f"\n{'='*50}")
    print(f"Calibrating: {name}  (DOUT={dout}, SCK={pd_sck})")
    print(f"Known calibration mass: {known_mass_g} g")
    print('='*50)

    if not HW:
        print("  [SIM] No hardware detected — returning mock factor")
        return -102.3

    hx = HX711(dout=dout, pd_sck=pd_sck)
    hx.set_reading_format("MSB", "MSB")
    hx.set_reference_unit(1)   # raw units for calibration
    hx.reset()

    # Step 1: tare (empty platform)
    input("\n  1. Remove ALL weight from the load cell, then press Enter...")
    hx.tare()
    print("  Tared (zero offset recorded).")

    # Step 2: place known mass
    input(f"\n  2. Place exactly {known_mass_g} g on the load cell, then press Enter...")
    time.sleep(2)

    # Average 20 readings
    N = 20
    readings = []
    print(f"  Reading {N} samples... ", end="", flush=True)
    for _ in range(N):
        v = hx.get_weight(5)
        readings.append(v)
        print(".", end="", flush=True)
        time.sleep(0.2)
    print(" done")

    readings.sort()
    # Trim 10% outliers
    trim = max(1, N // 10)
    trimmed = readings[trim:-trim]
    avg_raw = sum(trimmed) / len(trimmed)

    # calibration_factor = known_mass / avg_raw
    # (set_reference_unit(1) means raw units)
    cal_factor = avg_raw / known_mass_g
    print(f"\n  Average raw reading: {avg_raw:.1f}")
    print(f"  ✓ Calibration factor: {cal_factor:.4f}")
    print(f"    Paste into src/sensors.py:")
    print(f'    LOAD_CELL_CALIBRATION["{name}"] = {cal_factor:.4f}')

    hx.reset()
    GPIO.cleanup()
    return cal_factor


def main():
    from src.sensors import HX711_CONFIGS

    KNOWN_MASS_G = 500.0   # use a 500g known weight (adjust to what you have)

    print("HX711 Load Cell Calibration Utility")
    print("IIT Bhilai | Ashish Devadas")
    print(f"\nUsing calibration mass: {KNOWN_MASS_G} g")
    mass_input = input("Press Enter to use default, or type a different mass in grams: ").strip()
    if mass_input:
        try:
            KNOWN_MASS_G = float(mass_input)
        except ValueError:
            print("Invalid input — using default 500 g")

    results = {}
    for cfg in HX711_CONFIGS:
        factor = calibrate_one(
            name=cfg["label"],
            dout=cfg["dout"],
            pd_sck=cfg["pd_sck"],
            known_mass_g=KNOWN_MASS_G,
        )
        results[cfg["label"]] = factor

    print("\n" + "="*50)
    print("CALIBRATION COMPLETE")
    print("="*50)
    print("\nPaste these values into src/sensors.py:\n")
    print("LOAD_CELL_CALIBRATION = {")
    for label, factor in results.items():
        print(f'    "{label}": {factor:.4f},')
    print("}")
    print()


if __name__ == "__main__":
    main()
