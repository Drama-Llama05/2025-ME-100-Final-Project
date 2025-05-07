# buzzer.py
from machine import Pin, PWM
import time

class Buzzer:
    def __init__(self, pin):
        # store the pin number
        self.pin = pin
        print(f"Buzzer initialized on pin {self.pin}")

    def alert(self, freq=300, duty=700, duration=0.25):
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
        
    def alarm(self):
        buzzer_pwm = PWM(Pin(self.pin))
        for freq in range(300, 1201, 4):
            buzzer_pwm.freq(freq)
            time.sleep(0.01)
                
            # Gradually decrease the frequency from 1500Hz back down to 300Hz.
        for freq in range(1200, 299, -4):
           buzzer_pwm.freq(freq)
           time.sleep(0.01)
                
        buzzer_pwm.deinit()
