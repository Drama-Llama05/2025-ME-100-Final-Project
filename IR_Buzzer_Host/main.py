import machine
import network
import ntptime
import time
import socket
from machine import Pin
from buzzer import Buzzer

# Configuration
WIFI_SSID = 'Berkeley-IoT'
WIFI_PASSWORD = '%5j6EP5('
TIMEZONE_OFFSET_HOURS = -7  # e.g., PDT
BUSINESS_START_HOUR = 9
BUSINESS_END_HOUR = 17
ALERT_INTERVAL_MS = 10_000  # ms

# Connect to Wi-Fi (STA only)
sta = network.WLAN(network.STA_IF)
sta.active(True)
if not sta.isconnected():
    sta.connect(WIFI_SSID, WIFI_PASSWORD)
    for _ in range(20):
        if sta.isconnected():
            break
        time.sleep(1)
if not sta.isconnected():
    raise RuntimeError("Failed to connect to Wi-Fi")
sta_ip = sta.ifconfig()[0]
print(f"Connected. IP: {sta_ip}")

# Sync time via NTP
try:
    ntptime.settime()
    print("NTP time synchronized")
except Exception as e:
    print("NTP sync failed:", e)

# Hardware setup
buzzer_pin = 12
pir = Pin(36, Pin.IN)
buzz = Buzzer(buzzer_pin)

# State variables
last_buzz = 0           # last alert timestamp
prev_motion = False
last_motion_time = "N/A"
last_alarm_time = "N/A"
events = []             # (timestamp, type)
override_force = False  # force after-hours
override_disable = False# disable after-hours
alarm_active = False
count = 0

# HTTP server setup
addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
sock = socket.socket()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(addr)
sock.listen(5)
sock.settimeout(0.5)
print(f"Serving status page at http://{sta_ip}")

# Time helpers
def get_localtime():
    return time.localtime(time.time() + TIMEZONE_OFFSET_HOURS * 3600)

def fmt(t):
    return "{:02d}/{:02d}/{:04d} {:02d}:{:02d}:{:02d}".format(t[1], t[2], t[0], t[3], t[4], t[5])

# Main loop
while True:
    now_ms = time.ticks_ms()
    motion = bool(pir.value())
    t_local = get_localtime()
    hour = t_local[3]
    is_business = BUSINESS_START_HOUR <= hour < BUSINESS_END_HOUR
    # Apply overrides
    if override_force and is_business:
        effective_business = False
    elif override_disable and not is_business:
        effective_business = True
    else:
        effective_business = is_business

    # Serve web page and handle button actions
    try:
        client, addr = sock.accept()
        data = client.recv(1024).decode()
        if 'GET /force' in data:
            override_force = True
            override_disable = False
        elif 'GET /disable' in data:
            override_disable = True
            override_force = False
        elif 'GET /stop_alarm' in data:
            buzz.cancel_flag = True
            print("data")
            alarm_active = False
        client.send('HTTP/1.0 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n')
        biz_text = 'Yes' if is_business else 'No'
        mode_text = 'Business Mode' if effective_business else 'After-hours Mode'
        rows = ''.join(f"<tr><td>{ts}</td><td>{typ}</td></tr>" for ts, typ in events)
        html = f"""\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Motion Sensor Status</title>
  <meta http-equiv="refresh" content="5">
</head>
<body>
  <h1>Motion Sensor Status</h1>
  <p>Clock: {fmt(t_local)}</p>
  <p>Business hours now? {biz_text}</p>
  <p>Mode: {mode_text}</p>
  <form action="force"><button>Force After-hours</button></form>
  <form action="disable"><button>Disable After-hours</button></form>
  <form action="stop_alarm"><button>Stop Alarm</button></form>
  <h2>Recent Activations</h2>
  <table border="1" cellpadding="4" cellspacing="0">
    <tr><th>Timestamp</th><th>Type</th></tr>
    {rows}
  </table>
</body>
</html>
"""
        client.send(html)
        client.close()
    except OSError:
        pass
    if alarm_active and count <= 10:
        buzz.alarm()
        count+=1
    if count >= 10:
        count = 0
        alarm_active = False
    # Motion detection & buzzer logic
    if motion and not prev_motion:
        last_motion_time = fmt(t_local)
        print("Motion detected at", last_motion_time)
        if effective_business:
            # Business: alert at most once per interval
            if time.ticks_diff(now_ms, last_buzz) >= ALERT_INTERVAL_MS:
                buzz.alert()
                last_alarm_time = last_motion_time
                last_buzz = now_ms
                events.insert(0, (last_alarm_time, 'alert'))
                if len(events) > 10:
                    events.pop()
        else:
            # After-hours: manual alarm sweeps with cancel
            alarm_active = True
            last_alarm_time = last_motion_time
            events.insert(0, (last_alarm_time, 'alarm'))
            if len(events) > 10:
                events.pop()
    elif not motion and prev_motion:
        print("No motion detected.")

    prev_motion = motion
    time.sleep_ms(50)

