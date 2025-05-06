# main.py
import machine
from machine import Pin
import time
from buzzer import Buzzer
import network
import espnow

# A WLAN interface must be active to send()/recv()
wlan = network.WLAN(network.WLAN.IF_STA)
wlan.active(True)
wlan.disconnect()   # Because ESP8266 auto-connects to last Access Point

e = espnow.ESPNow()
e.active(True)

buzzer_pin      = 12
ir_pin          = 36
BUZZ_INTERVAL_MS = 5_000  # minimum ms between buzzes

# Setup
buzz       = Buzzer(buzzer_pin)
pir_sensor = Pin(ir_pin, Pin.IN)
last_buzz  = 0            # timestamp of last buzz
prev_motion = False       # previous PIR state
while True:
    now    = time.ticks_ms()
    motion = bool(pir_sensor.value())
    #host, msg = e.recv()
#     if msg: # msg == None if timeout in recv()
#         buzz.alert(freq=440, duty=512, duration=0.5)
#         print(host, msg)
#         if msg == b'end':
#             break
    # Rising edge: motion just started
    
    if motion and not prev_motion:
        print("Motion detected.")
        if time.ticks_diff(now, last_buzz) >= BUZZ_INTERVAL_MS:
            buzz.alert(freq=440, duty=512, duration=0.5)
            print("  ↳ Buzzer sounded.")
            last_buzz = now

    # Falling edge: motion just ended
    elif not motion and prev_motion:
        print("No motion detected.")

    prev_motion = motion
    time.sleep_ms(50)

