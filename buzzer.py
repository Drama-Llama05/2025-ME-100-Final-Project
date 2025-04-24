# buzzer.py
from machine import Pin, PWM
import time

class Buzzer:
    def __init__(self, pin):
        # store the pin number
        self.pin = pin
        print(f"Buzzer initialized on pin {self.pin}")

    def alert(self, freq=300, duty=700, duration=1):
        """
        - freq: PWM frequency in Hz
        - duty: duty cycle (0–1023 for 10‑bit PWM)
        - duration: buzz length in seconds
        """
        buzzer_pwm = PWM(Pin(self.pin))
        buzzer_pwm.freq(freq)
        buzzer_pwm.duty(duty)
        time.sleep(duration)
        buzzer_pwm.deinit()


