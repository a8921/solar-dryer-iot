#!/usr/bin/env python3
"""
web_server.py — Flask dashboard for the Indirect Solar Dryer IoT monitor
IIT Bhilai | Ashish Devadas

Run:
    python3 web_server.py [--port 5000] [--interval 60] [--sim]

Open:
    http://<pi-ip-address>:5000   (from any device on the same WiFi)
"""

import argparse
import csv
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, send_file

# ── Path setup ─────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).parent
DATA_DIR = ROOT / "data"
CSV_PATH = DATA_DIR / "dryer_log.csv"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("web_server")

app = Flask(__name__, template_folder="templates", static_folder="static")

# Global logger instance (started in main)
_dryer_logger = None


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/current")
def api_current():
    """Latest sensor snapshot as JSON."""
    if _dryer_logger is None:
        return jsonify({"error": "logger not started"}), 503
    data = _dryer_logger.latest
    if not data:
        return jsonify({"error": "no data yet"}), 204
    return jsonify(data)


@app.route("/api/history")
def api_history():
    """
    Last N rows from CSV as JSON array.
    Query param: ?rows=120 (default 120 = 2 hours at 60s interval)
    """
    rows_req = min(int(app.config.get("MAX_HISTORY", 1440)),
                   max(1, _safe_int(app.request_args_get("rows", 120), 120)))
    rows = _read_csv_tail(CSV_PATH, rows_req)
    return jsonify(rows)


def _safe_int(val, default):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _read_csv_tail(path: Path, n: int) -> list:
    if not path.exists():
        return []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows   = list(reader)
    return rows[-n:]


@app.route("/api/download")
def api_download():
    """Download full CSV log."""
    if not CSV_PATH.exists():
        return "No data yet", 404
    return send_file(
        CSV_PATH,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"dryer_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    )


@app.route("/api/tare", methods=["POST"])
def api_tare():
    """Tare both load cells (POST /api/tare)."""
    if _dryer_logger is None:
        return jsonify({"error": "logger not started"}), 503
    try:
        for lc in _dryer_logger.sensors.load_cells:
            lc.tare()
        return jsonify({"status": "tared"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/status")
def api_status():
    """Health check."""
    return jsonify({
        "status":       "ok",
        "hw_available": _get_hw_available(),
        "csv_rows":     _csv_row_count(CSV_PATH),
        "uptime_s":     _uptime(),
    })


def _get_hw_available():
    try:
        from src.sensors import HW_AVAILABLE
        return HW_AVAILABLE
    except Exception:
        return False


def _csv_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path) as f:
        return max(0, sum(1 for _ in f) - 1)   # subtract header


_start_time = None
def _uptime():
    import time
    return round(time.time() - _start_time, 0) if _start_time else 0


# ── Monkey-patch request_args_get for route usage ─────────────────────────────
from flask import request as _req

@app.context_processor
def inject_request():
    return {}

# Replace the helper with actual Flask request access
def _fix_route():
    pass  # request.args is accessed in the route directly


@app.route("/api/history")
def api_history_fixed():
    from flask import request
    rows_req = _safe_int(request.args.get("rows", 120), 120)
    rows_req = min(1440, max(1, rows_req))
    rows     = _read_csv_tail(CSV_PATH, rows_req)
    return jsonify(rows)


# Remove the unfixed version and keep only the fixed one
app.view_functions.pop("api_history", None)


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    import time
    global _dryer_logger, _start_time

    parser = argparse.ArgumentParser(description="Solar Dryer Web Server")
    parser.add_argument("--port",     type=int,   default=5000)
    parser.add_argument("--host",     type=str,   default="0.0.0.0")
    parser.add_argument("--interval", type=int,   default=60,
                        help="Sensor read interval in seconds")
    parser.add_argument("--weight",   type=float, default=2000.0,
                        help="Initial sample weight in grams")
    parser.add_argument("--sim",      action="store_true",
                        help="Force simulation mode (no hardware needed)")
    args = parser.parse_args()

    if args.sim:
        os.environ["SOLAR_DRYER_SIM"] = "1"

    sys.path.insert(0, str(ROOT))
    from src.logger import DryerLogger

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _dryer_logger = DryerLogger(
        interval=args.interval,
        initial_weight=args.weight,
    )
    _dryer_logger.start()
    _start_time = time.time()

    log.info("Dashboard: http://%s:%d", args.host, args.port)
    log.info("Simulation mode: %s", args.sim or not _dryer_logger.sensors.__class__.__module__)

    try:
        app.run(host=args.host, port=args.port, debug=False, threaded=True)
    finally:
        _dryer_logger.stop()


if __name__ == "__main__":
    main()
