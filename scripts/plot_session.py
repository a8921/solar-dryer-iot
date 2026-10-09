#!/usr/bin/env python3
"""
plot_session.py — Post-session analysis plots from dryer_log.csv
IIT Bhilai | Ashish Devadas

Generates publication-quality figures matching the paper's analysis style.

Run:
    python3 scripts/plot_session.py
    python3 scripts/plot_session.py --csv data/dryer_log.csv --out media/
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── Style ─────────────────────────────────────────────────────────────────────
BG     = "#0f1117"
SURF   = "#1a1f2e"
TEXT   = "#e2e8f0"
GRID   = "#1e293b"
COLORS = ["#3b82f6", "#ef4444", "#eab308", "#f97316", "#22c55e", "#a855f7"]

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG,
    "axes.edgecolor":   GRID, "axes.labelcolor": TEXT,
    "axes.titlecolor":  TEXT, "xtick.color": TEXT,
    "ytick.color":      TEXT, "text.color": TEXT,
    "grid.color":       GRID, "grid.linewidth": 0.5,
    "lines.linewidth":  2.0,  "font.family": "sans-serif",
})


def load_csv(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def to_float(rows, key):
    return [float(r[key]) if r.get(key) not in (None, "", "None") else None
            for r in rows]


def time_labels(rows):
    return [r.get("datetime", "")[-8:-3] for r in rows]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=str(ROOT / "data" / "dryer_log.csv"))
    parser.add_argument("--out", default=str(ROOT / "media"))
    args = parser.parse_args()

    csv_path = Path(args.csv)
    out_dir  = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not csv_path.exists():
        print(f"No CSV found at {csv_path} — generating sample data for demo")
        _generate_sample_csv(csv_path)

    rows   = load_csv(csv_path)
    labels = time_labels(rows)
    t_arr  = np.arange(len(rows))

    # ── 1. Temperature profiles ───────────────────────────────────────────────
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    fig.suptitle("Solar Dryer — Temperature & Humidity Profiles", fontsize=13)

    keys_t = ["dht_collector_in_temp", "dht_collector_out_temp",
              "dht_chamber_top_temp",  "dht_chamber_bottom_temp"]
    lbls_t = ["Collector In", "Collector Out", "Chamber Top", "Chamber Bottom"]
    ax = axes[0]
    for key, lbl, c in zip(keys_t, lbls_t, COLORS):
        y = to_float(rows, key)
        ax.plot(t_arr, y, label=lbl, color=c)
    ax.set_ylabel("Temperature (°C)"); ax.legend(loc="upper right", fontsize=8)
    ax.grid(True); ax.set_ylim(bottom=20)

    keys_h = ["dht_collector_in_humidity", "dht_collector_out_humidity",
              "dht_chamber_top_humidity",  "dht_chamber_bottom_humidity"]
    ax = axes[1]
    for key, lbl, c in zip(keys_h, lbls_t, COLORS):
        y = to_float(rows, key)
        ax.plot(t_arr, y, label=lbl, color=c)
    ax.set_ylabel("Humidity (%RH)"); ax.legend(loc="upper right", fontsize=8)
    ax.grid(True)

    # x-ticks
    step = max(1, len(rows) // 10)
    ax.set_xticks(t_arr[::step])
    ax.set_xticklabels(labels[::step], rotation=30, ha="right", fontsize=8)
    ax.set_xlabel("Time (HH:MM)")

    plt.tight_layout()
    out = out_dir / "temp_humidity.png"
    plt.savefig(out, dpi=150, bbox_inches="tight"); plt.close()
    print(f"  → {out}")

    # ── 2. Drying curve ───────────────────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    fig.suptitle("Drying Curve — Weight Loss & Moisture Content", fontsize=13)

    weight = to_float(rows, "total_weight")
    mc     = to_float(rows, "moisture_content_wb")
    ax1.plot(t_arr, weight, color=COLORS[0], label="Sample weight (g)")
    ax1.axhline(y=200, color=COLORS[4], linestyle="--", linewidth=1, label="Dry mass estimate")
    ax1.set_ylabel("Weight (g)"); ax1.legend(fontsize=8); ax1.grid(True)

    ax2.plot(t_arr, mc, color=COLORS[1], label="Moisture content wb (%)")
    ax2.axhline(y=12, color=COLORS[4], linestyle="--", linewidth=1, label="Target 12 %")
    ax2.set_ylabel("MC wet basis (%)"); ax2.legend(fontsize=8); ax2.grid(True)
    ax2.set_xticks(t_arr[::step])
    ax2.set_xticklabels(labels[::step], rotation=30, ha="right", fontsize=8)
    ax2.set_xlabel("Time (HH:MM)")

    plt.tight_layout()
    out = out_dir / "drying_curve.png"
    plt.savefig(out, dpi=150, bbox_inches="tight"); plt.close()
    print(f"  → {out}")

    # ── 3. Drying rate & collector efficiency ─────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    fig.suptitle("Drying Rate & Collector Thermal Efficiency", fontsize=13)

    dr  = to_float(rows, "drying_rate_g_per_min")
    eff = to_float(rows, "collector_efficiency_pct")
    ax1.plot(t_arr, dr, color=COLORS[4], label="Drying rate (g/min)")
    ax1.fill_between(t_arr, [v if v else 0 for v in dr], alpha=0.15, color=COLORS[4])
    ax1.set_ylabel("Drying rate (g/min)"); ax1.legend(fontsize=8); ax1.grid(True)

    ax2.plot(t_arr, eff, color=COLORS[2], label="Collector efficiency (%)")
    ax2.axhline(y=19.56, color=COLORS[3], linestyle="--", linewidth=1,
                label="Paper best: 19.56% @ 0.06 kg/s")
    ax2.set_ylabel("η collector (%)"); ax2.legend(fontsize=8); ax2.grid(True)
    ax2.set_xticks(t_arr[::step])
    ax2.set_xticklabels(labels[::step], rotation=30, ha="right", fontsize=8)
    ax2.set_xlabel("Time (HH:MM)")

    plt.tight_layout()
    out = out_dir / "efficiency.png"
    plt.savefig(out, dpi=150, bbox_inches="tight"); plt.close()
    print(f"  → {out}")

    print(f"\n✓ 3 plots saved to {out_dir}/")


def _generate_sample_csv(path: Path):
    """Generate 13 hours of simulated dryer data for demo/testing."""
    import math, random, os
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "timestamp", "datetime",
        "dht_collector_in_temp", "dht_collector_in_humidity",
        "dht_collector_out_temp","dht_collector_out_humidity",
        "dht_chamber_top_temp",  "dht_chamber_top_humidity",
        "dht_chamber_bottom_temp","dht_chamber_bottom_humidity",
        "lc_sample_1_weight",    "lc_sample_2_weight",
        "total_weight", "moisture_content_wb", "drying_rate_g_per_min",
        "collector_efficiency_pct", "all_sensors_valid",
    ]
    rows = []
    base_ts = 1728288000  # 2024-10-07 07:00 UTC (7 AM)
    weight = 2000.0
    for i in range(780):   # 13 hours × 60 min = 780 rows (1 min intervals)
        t   = base_ts + i * 60
        h   = i / 60.0
        tau = math.pi * h / 13
        sol = max(0, math.sin(tau))

        t_in  = 28 + 5  * sol + random.uniform(-.5,.5)
        t_out = 45 + 25 * sol + random.uniform(-.5,.5)
        t_top = 35 + 20 * sol + random.uniform(-.5,.5)
        t_bot = 32 + 18 * sol + random.uniform(-.5,.5)
        h_in  = 55 - 10 * sol + random.uniform(-.5,.5)
        h_out = 35 - 8  * sol + random.uniform(-.5,.5)
        h_top = 40 - 15 * sol + random.uniform(-.5,.5)
        h_bot = 45 - 12 * sol + random.uniform(-.5,.5)

        dr = max(0, 2.5 * sol + random.uniform(-.1,.1))
        weight = max(340, weight - dr)
        wd = 2000 * 0.08
        mc = max(0, (weight - wd) / weight * 100)
        eff = max(0, _collector_efficiency_sim(t_in, t_out))

        rows.append({
            "timestamp": t, "datetime": datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S"),
            "dht_collector_in_temp":   round(t_in,1),
            "dht_collector_in_humidity": round(h_in,1),
            "dht_collector_out_temp":  round(t_out,1),
            "dht_collector_out_humidity": round(h_out,1),
            "dht_chamber_top_temp":    round(t_top,1),
            "dht_chamber_top_humidity": round(h_top,1),
            "dht_chamber_bottom_temp": round(t_bot,1),
            "dht_chamber_bottom_humidity": round(h_bot,1),
            "lc_sample_1_weight": round(weight*0.5,1),
            "lc_sample_2_weight": round(weight*0.5,1),
            "total_weight":           round(weight,1),
            "moisture_content_wb":    round(mc,2),
            "drying_rate_g_per_min":  round(dr,4),
            "collector_efficiency_pct": round(eff,2),
            "all_sensors_valid": True,
        })

    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader(); w.writerows(rows)
    print(f"Generated {len(rows)} rows of sample data → {path}")


def _collector_efficiency_sim(t_in, t_out, mdot=0.06, cp=1006, Ac=2.0, G=800):
    if t_out <= t_in or G <= 0:
        return 0
    return min(100, (mdot * cp * (t_out - t_in)) / (G * Ac) * 100)


if __name__ == "__main__":
    main()
