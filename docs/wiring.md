# Wiring Guide — Indirect Solar Dryer IoT
**IIT Bhilai | Ashish Devadas**

---

## Components

| Component | Quantity | Purpose |
|-----------|----------|---------|
| Raspberry Pi 5 | 1 | Main controller + web server |
| DHT11 sensor | 4 | Temperature + humidity at 4 positions |
| HX711 load cell amplifier | 2 | 24-bit ADC for load cells |
| Load cell (any rated ≥ 2 kg) | 2 | Weight measurement of drying sample |
| 10 kΩ resistor | 4 | Pull-up for DHT11 data lines |

---

## DHT11 Sensor Wiring (×4)

Each DHT11 has 3 pins: VCC, DATA, GND.

| Sensor | Role | DATA → Pi BCM Pin |
|--------|------|-------------------|
| DHT11 #1 | Collector inlet air | GPIO 4 |
| DHT11 #2 | Collector outlet air | GPIO 17 |
| DHT11 #3 | Drying chamber top | GPIO 27 |
| DHT11 #4 | Drying chamber bottom | GPIO 22 |

**All VCC → 3.3V (Pin 1)**  
**All GND → GND (Pin 6)**  
**Pull-up:** 10 kΩ resistor between each DATA pin and 3.3V

```
DHT11 VCC  ──── 3.3V
DHT11 DATA ──┬─ GPIO_xx
             └─ 10kΩ ── 3.3V
DHT11 GND  ──── GND
```

---

## HX711 Load Cell Wiring (×2)

| HX711 | Load Cell | DOUT Pin | SCK Pin |
|-------|-----------|----------|---------|
| #1 (sample_1) | Main drying tray | GPIO 5 | GPIO 6 |
| #2 (sample_2) | Secondary/reference | GPIO 13 | GPIO 19 |

**HX711 VCC → 5V (Pin 2)**  
**HX711 GND → GND**

```
HX711 VCC   ──── 5V
HX711 GND   ──── GND
HX711 DOUT  ──── GPIO 5  (or 13 for second unit)
HX711 SCK   ──── GPIO 6  (or 19 for second unit)

Load Cell wires:
  Red   → E+
  Black → E-
  White → A+
  Green → A-
```

---

## Sensor Placement in Dryer

```
                    ╔══════════════════════════════╗
                    ║      SOLAR COLLECTOR         ║
    DHT11 #1 ──────▶║  [inlet]          [outlet] ◀──── DHT11 #2
    (collector_in)  ║                              ║    (collector_out)
                    ╚══════════════════════════════╝
                                  │
                                  ▼ (hot air)
                    ╔══════════════════════════════╗
   DHT11 #3 ───────▶║           TOP                ║
   (chamber_top)    ║   ┌─────────────────────┐   ║
                    ║   │   DRYING TRAY        │   ║
                    ║   │  [Load Cell #1]      │   ║
                    ║   │  [Load Cell #2]      │   ║
                    ║   └─────────────────────┘   ║
   DHT11 #4 ───────▶║          BOTTOM              ║
   (chamber_bottom) ╚══════════════════════════════╝
```

---

## Raspberry Pi 5 Pinout Reference (BCM)

```
              3.3V [1] [2] 5V
  SDA1/GPIO2   [3] [4] 5V
  SCL1/GPIO3   [5] [6] GND
   DHT11_1  GPIO4 [7] [8] GPIO14/TXD
                GND [9] [10] GPIO15/RXD
  DHT11_2 GPIO17 [11] [12] GPIO18
  DHT11_3 GPIO27 [13] [14] GND
             ... 
  DHT11_4 GPIO22 [15] [16] GPIO23
             ...
   HX711_1  GPIO5 [29] [30] GND
   HX711_1  GPIO6 [31] [32] GPIO12
             ...
   HX711_2 GPIO13 [33] [34] GND
   HX711_2 GPIO19 [35] [36] GPIO16
```

---

## Notes

1. **Power:** Power the Pi from a 5V/3A adapter. The sensors draw minimal current.
2. **DHT11 timing:** DHT11 needs at least 1 second between reads. The code handles this automatically with retry logic.
3. **Load cell placement:** Mount load cells in a flat, stable fixture. Temperature gradients can affect zero offset — run `calibrate_loadcell.py` at operating temperature.
4. **Wi-Fi:** The Pi's built-in Wi-Fi is sufficient. Connect it to the same network as your phone/laptop to access the dashboard.
