# main.py -- scan multiple RFID tags, print each new UID once

from machine import Pin
import time
from mfrc522 import MFRC522

# ─── Pin definitions ───────────────────────────────────────────────────────────
# RC522 SDA/CS  → ESP32 GPIO22
# RC522 SCK     → ESP32 GPIO5
# RC522 MOSI    → ESP32 GPIO19
# RC522 MISO    → ESP32 GPIO21
# RC522 RST     → tied to 3.3 V (we’ll use a dummy pin in software)
# RC522 3.3 V/VCC → 3.3 V
# RC522 GND     → GND

sck  = 5
mosi = 19
miso = 21
rst  = 2    # dummy GPIO (RC522 RST is hard‑wired high)
cs   = 22

# instantiate reader with pin numbers (driver will do its own SPI init)
rfid = MFRC522(sck, mosi, miso, rst, cs)

print("RFID reader ready. Tap tags to the antenna.\n")

seen = set()

while True:
    status, _type = rfid.request(rfid.REQIDL)
    if status == rfid.OK:
        status, raw_uid = rfid.anticoll()
        if status == rfid.OK:
            uid = "".join("{:02X}".format(b) for b in raw_uid)
            if uid not in seen:
                seen.add(uid)
                print("✔ New tag:", uid)
            else:
                print("· Seen tag:", uid)
    time.sleep_ms(300)
