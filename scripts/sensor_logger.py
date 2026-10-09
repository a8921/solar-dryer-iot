#!/usr/bin/env python3
"""
sensor_logger.py — Standalone data logging daemon (no web server)
IIT Bhilai | Ashish Devadas

Reads all 4 DHT11s and 2 HX711s every 60 seconds.
Saves to data/dryer_log.csv.

Run:
    python3 scripts/sensor_logger.py
    python3 scripts/sensor_logger.py --interval 30 --sim
"""

import argparse
import logging
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sensor_logger")


def main():
    parser = argparse.ArgumentParser(description="Solar Dryer Data Logger")
    parser.add_argument("--interval", type=int,   default=60)
    parser.add_argument("--weight",   type=float, default=2000.0,
                        help="Initial sample weight (g)")
    parser.add_argument("--sim",      action="store_true",
                        help="Simulation mode — no Pi hardware needed")
    args = parser.parse_args()

    if args.sim:
        import os
        os.environ["SOLAR_DRYER_SIM"] = "1"

    from src.logger import DryerLogger

    logger = DryerLogger(interval=args.interval, initial_weight=args.weight)
    logger.start()
    log.info("Logging every %d s — Ctrl+C to stop", args.interval)

    def _stop(sig, frame):
        log.info("Stopping...")
        logger.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _stop)
    signal.signal(signal.SIGTERM, _stop)
    signal.pause()


if __name__ == "__main__":
    main()
