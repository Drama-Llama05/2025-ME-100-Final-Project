# 2025-ME-100-Final-Project
Smart IoT-Based Tool Cabinet


A MicroPython-driven smart tool cabinet that automates access control, tool tracking, and logging for shared engineering workshops. The system uses ESP32 microcontrollers, RFID readers, motion sensors, buzzers, LEDs, and a servo-driven lock to secure tools, authenticate users, and maintain a real-time inventory log accessible over Wi‑Fi.

---

## Features

- **User Authentication & Access Control**: Scan personal RFID cards to disarm the cabinet and unlock via a servo motor.
  - Currently authorized users:
    - Stickers
      - "A1745C3EB7"   : Not Yet Assigned
      - "42455C3E65"   : Not Yet Assigned
      - "43975C3EB6"   : Not Yet Assigned
      - "B56F5C3EB8"   : Not Yet Assigned
      - "72475C3E57"   : Not Yet Assigned
      - "31395C3E6A"   : Not Yet Assigned
      - "E8B05B3E3D"   : Not Yet Assigned
      - "68585C3E52"   : Not Yet Assigned
      - "786E5C3E74"   : Not Yet Assigned
- **Tool Tracking**: RFID tags on tools combined with load-cell measurements detect check‑outs and returns.
- **Real-Time Logging**: Tag taps are timestamped and appended to a CSV (`log.csv`) on each ESP32; logs are served over HTTP.
- **Visual & Audible Alerts**:
  - Green LED: cabinet unlocked/disarmed.
  - Flashing Red LED & Buzzer: cabinet armed or failed authentication.
- **Motion‑Sensitive Activation**: PIR motion sensor enables the RFID reader only when a user is present to reduce Wi‑Fi interference.

---

## Hardware Components

- **3 × ESP32** (MicroPython)
- **2 × RFID‑RC522 readers**
- **Several RFID tags**
- **1 × Servo motor** (cabinet latch)
- **1 × PIR motion sensor**
- **2 × Buzzers**
- **2 × LEDs** (status indicators)

---

## Project Structure

```
├── lib/
│   └── mfrc522.py            # MFRC522 driver for MicroPython
├── rfid_scanner/
│   └── main.py               # RFID tag logging + web server
├── buzzer_alarm/
│   └── main.py               # Siren-style buzzer control
├── servo_lock/
│   └── main.py               # Servo-based door lock control
├── led_indicator/
│   └── main.py               # LED status logic
├── motion_sensor/
│   └── main.py               # PIR‑triggered activation logic
└── README.md                 # Project overview and setup instructions
```

---

## Prerequisites

1. **MicroPython firmware** installed on each ESP32 (version 1.20+ recommended)
2. **Wi‑Fi network credentials** for logging and HTTP server
3. **WebREPL** (optional) for remote REPL access
4. **Thonny**, **ampy**, or **rshell** for file uploads

---

## Installation & Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/<username>/lab‑security‑iot.git
   cd lab‑security‑iot
   ```

2. **Install driver library**

   - Copy `lib/mfrc522.py` onto each ESP32’s `/lib` folder.

3. **Configure Wi‑Fi**

   - In each `main.py`, update `SSID` and `PASSWORD` constants with your network credentials.

4. **Deploy code to ESP32s**

   ```bash
   ampy --port /dev/ttyUSB0 put rfid_scanner/main.py main.py
   ampy --port /dev/ttyUSB1 put buzzer_alarm/main.py main.py
   # ...repeat for other modules
   ```

5. **Reset boards**

   - Each ESP32 will print its IP and start its main loop automatically.

---

## Usage

- Point your browser to `http://<ESP32_IP>/` (shown in REPL) to download the CSV log of all RFID tag events.
- Scan your RFID card to unlock; subsequent scans log tool tags in `log.csv` with timestamps.
- Observe LEDs and buzzer for status and alerts.

---

## Contributors

- **Erik Dahlhaus**
- **Ryan Zheng**
- **Paul Biener**

---
