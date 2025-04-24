from machine import Pin, PWM
import time

# Initialize the PWM object on pin 12 with a starting frequency of 300Hz and a fixed duty cycle.
buzzer = PWM(Pin(num), freq=300, duty=700)

try:
    while True:
        # Gradually increase the frequency from 300Hz to 1500Hz.
        for freq in range(300, 1201, 4):
            buzzer.freq(freq)
            time.sleep(0.01)
            
        # Gradually decrease the frequency from 1500Hz back down to 300Hz.
        for freq in range(1200, 299, -4):
            buzzer.freq(freq)
            time.sleep(0.01)
            
except KeyboardInterrupt:
    # Allow the loop to be exited gracefully with a keyboard interrupt.
    pass

# Clean up the PWM when finished.
buzzer.deinit()

