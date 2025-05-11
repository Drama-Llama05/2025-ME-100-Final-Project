from machine import Pin, PWM  # GPIO pin control and PWM for tones
import time                  # for pause durations

class Buzzer:
    def __init__(self, pin):
        # store the pin number for later use
        self.pin = pin
        print(f"Buzzer initialized on pin {self.pin}")

    def alert(self, freq=300, duty=700, duration=0.25):
        """
        - freq: PWM frequency in Hz
        - duty: duty cycle (0–1023 for 10‑bit PWM)
        - duration: buzz length in seconds
        """
        buzzer_pwm = PWM(Pin(self.pin))   # create PWM on buzzer pin
        buzzer_pwm.freq(freq)             # set tone frequency
        buzzer_pwm.duty(duty)             # set duty cycle (volume)
        time.sleep(duration)              # buzz for given duration
        buzzer_pwm.deinit()               # stop PWM and silence buzzer
        
    def alarm(self):
        buzzer_pwm = PWM(Pin(self.pin))   # start PWM for sweep alarm
        # sweep frequency up from 300Hz to 1200Hz
        for freq in range(300, 1201, 4):
            buzzer_pwm.freq(freq)         # update PWM frequency
            time.sleep(0.01)              # short delay for audible glide
                
        # gradually sweep down from 1200Hz back to 300Hz
        for freq in range(1200, 299, -4):
            buzzer_pwm.freq(freq)         # update PWM frequency
            time.sleep(0.01)              # maintain smooth transition
                
        buzzer_pwm.deinit()               # stop PWM and silence buzzer
