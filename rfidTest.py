# main.py
import time
from machine import Pin, SPI
from mfrc522 import MFRC522

print("RFID demo starting…")

spi = SPI(2, baudrate=2_500_000, polarity=0, phase=0)
rdr = MFRC522(spi, gpioRst=Pin(26), gpioCs=Pin(4))

while True:
    print("run")
    stat, _ = rdr.request(MFRC522.REQALL)
    if stat == MFRC522.OK:
        stat, uid = rdr.anticoll()
        if stat == MFRC522.OK:
            print("Tag:", "0x%02x%02x%02x%02x" % tuple(uid))
    time.sleep_ms(200)
