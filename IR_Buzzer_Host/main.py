import machine                    # core hardware functions
import network                    # Wi-Fi interface
import ntptime                    # NTP time synchronization
import time                       # delays and ticks
import socket                     # TCP/IP sockets
from machine import Pin           # GPIO pin control
from buzzer import Buzzer         # buzzer driver class

# Configuration
WIFI_SSID = 'Berkeley-IoT'        # Wi-Fi network name
WIFI_PASSWORD = '%5j6EP5('        # Wi-Fi network password
TIMEZONE_OFFSET_HOURS = -7        # local offset from UTC (PDT)
BUSINESS_START_HOUR = 9            # business hours start
BUSINESS_END_HOUR = 17             # business hours end
ALERT_INTERVAL_MS = 10_000         # min ms between alerts

# Connect to Wi-Fi (STA only)
sta = network.WLAN(network.STA_IF)  # create station interface
sta.active(True)                   # enable Wi-Fi
if not sta.isconnected():         # if not already connected
    sta.connect(WIFI_SSID, WIFI_PASSWORD)  # connect to AP
    for _ in range(20):
        if sta.isconnected(): break
        time.sleep(1)              # wait up to 20s
if not sta.isconnected():
    raise RuntimeError("Failed to connect to Wi-Fi")  # abort on failure
sta_ip = sta.ifconfig()[0]         # get assigned IP
print(f"Connected. IP: {sta_ip}")  # show IP

# Sync time via NTP
try:
    ntptime.settime()              # set RTC from NTP server
    print("NTP time synchronized")
except Exception as e:
    print("NTP sync failed:", e)  # report failure

# Hardware setup
buzzer_pin = 12                    # GPIO for buzzer
pir = Pin(36, Pin.IN)              # PIR motion sensor input
buzz = Buzzer(buzzer_pin)          # instantiate buzzer driver

# State variables
last_buzz = 0                      # timestamp of last alert
prev_motion = False                # previous motion state
last_motion_time = "N/A"          # last detection timestamp
last_alarm_time = "N/A"           # last alarm timestamp
events = []                        # recent event list (ts, type)
override_force = False             # force after-hours mode
override_disable = False           # disable after-hours mode
alarm_active = False               # flag for sweeping alarm
count = 0                          # alarm repetition counter

# HTTP server setup
addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]  # bind to all interfaces
sock = socket.socket()             # create TCP socket
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # allow reuse
sock.bind(addr)                    # bind port 80
sock.listen(5)                      # queue up to 5 clients
sock.settimeout(0.5)               # non-blocking accept
print(f"Serving status page at http://{sta_ip}")  # notify user

# Time helpers
def get_localtime():
    return time.localtime(time.time() + TIMEZONE_OFFSET_HOURS * 3600)  # local struct

def fmt(t):
    # format tuple (Y,M,D,h,m,s) to MM/DD/YYYY hh:mm:ss
    return "{:02d}/{:02d}/{:04d} {:02d}:{:02d}:{:02d}".format(t[1], t[2], t[0], t[3], t[4], t[5])

# Main loop
while True:
    now_ms = time.ticks_ms()       # current ms counter
    motion = bool(pir.value())     # read PIR output
    t_local = get_localtime()      # get local time tuple
    hour = t_local[3]              # extract hour
    is_business = BUSINESS_START_HOUR <= hour < BUSINESS_END_HOUR  # business check

    # Apply overrides to business mode
    if override_force and is_business:
        effective_business = False
    elif override_disable and not is_business:
        effective_business = True
    else:
        effective_business = is_business

    # Serve web page and handle button actions
    try:
        client, addr = sock.accept()  # non-blocking accept
        data = client.recv(1024).decode()  # read request
        if 'GET /force' in data:
            override_force = True      # user forced after-hours
            override_disable = False
        elif 'GET /disable' in data:
            override_disable = True    # user disabled after-hours
            override_force = False
        elif 'GET /stop_alarm' in data:
            buzz.cancel_flag = True    # signal buzzer to stop
            print("data")            # debug print
            alarm_active = False       # stop sweep mode

        # send HTTP header and page
        client.send('HTTP/1.0 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n')
        biz_text = 'Yes' if is_business else 'No'
        mode_text = 'Business Mode' if effective_business else 'After-hours Mode'
        rows = ''.join(f"<tr><td>{ts}</td><td>{typ}</td></tr>" for ts, typ in events)  # build table rows
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
        client.send(html)            # send the HTML body
        client.close()               # close client socket
    except OSError:
        pass                          # no incoming request

    # Handle active alarm sweeping up to 10 times
    if alarm_active and count <= 10:
        buzz.alarm()                  # perform frequency sweep
        count += 1                    # increment count
    if count >= 10:
        count = 0                     # reset counter
        alarm_active = False          # disable sweep

    # Motion detection & buzzer logic
    if motion and not prev_motion:  # on rising edge
        last_motion_time = fmt(t_local)
        print("Motion detected at", last_motion_time)
        if effective_business:
            # Business: alert at most once per interval
            if time.ticks_diff(now_ms, last_buzz) >= ALERT_INTERVAL_MS:
                buzz.alert()         # short buzz
                last_alarm_time = last_motion_time
                last_buzz = now_ms   # update last buzz time
                events.insert(0, (last_alarm_time, 'alert'))  # log event
                if len(events) > 10: events.pop()  # keep recent 10
        else:
            # After-hours: continuous sweeping alarm
            alarm_active = True
            last_alarm_time = last_motion_time
            events.insert(0, (last_alarm_time, 'alarm'))
            if len(events) > 10: events.pop()
    elif not motion and prev_motion:
        print("No motion detected.")

    prev_motion = motion           # update previous state
    time.sleep_ms(50)              # small delay to debounce
