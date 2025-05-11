import network, ntptime, time, socket, _thread    # Wi-Fi, NTP, timing, sockets, threading
from machine import Pin                          # GPIO pin control
from buzzer import Buzzer                        # buzzer driver
import ujson as json                             # lightweight JSON module

# ─── USER CONFIG ────────────────────────────────────────────────────────────────
WIFI_SSID             = 'Berkeley-IoT'         # Wi-Fi SSID
WIFI_PASSWORD         = '%5j6EP5('             # Wi-Fi password
STATIC_IP             = '10.41.196.7'          # static IP address
SUBNET_MASK           = '255.255.252.0'        # network mask
GATEWAY               = '10.41.196.1'          # gateway router
DNS_SERVER            = '128.32.206.9'         # DNS server
TIMEZONE_OFFSET_HOURS = -7                     # offset from UTC hours
BUSINESS_START_HOUR   = 9                      # business hours start
BUSINESS_END_HOUR     = 17                     # business hours end
ALERT_INTERVAL_MS     = 10_000                 # ms between buzz alerts

# ─── STATE ─────────────────────────────────────────────────────────────────────
override_force   = False                       # force after-hours mode
override_disable = False                       # disable after-hours mode
alarm_active     = False                       # ongoing alarm sweep flag
last_buzz        = 0                           # timestamp of last alert
prev_motion      = False                       # previous PIR state
events           = []                          # recent events list

# ─── HARDWARE ──────────────────────────────────────────────────────────────────
pir    = Pin(36, Pin.IN)                       # PIR motion sensor input
buzz   = Buzzer(12)                            # buzzer on pin 12
led    = Pin(25, Pin.OUT)                      # status LED output

# ─── NETWORK SETUP ─────────────────────────────────────────────────────────────
sta = network.WLAN(network.STA_IF)             # station interface
sta.active(True)                               # enable Wi-Fi
sta.ifconfig((STATIC_IP, SUBNET_MASK, GATEWAY, DNS_SERVER))  # apply static config
sta.connect(WIFI_SSID, WIFI_PASSWORD)          # connect using credentials
print("Connecting to Wi-Fi...", end='')      # show progress
for _ in range(20):                            # wait up to 20s
    if sta.isconnected(): break
    time.sleep(1); print('.', end='')
print()
if not sta.isconnected(): raise RuntimeError("Wi-Fi failed")  # abort on fail
IP = sta.ifconfig()[0]                         # get IP address
print("Connected, IP =", IP)                 # display IP

# ─── NTP ───────────────────────────────────────────────────────────────────────
try:
    ntptime.settime()                          # sync RTC with NTP
    print("Clock synced")
except:
    print("NTP sync failed")                 # ignore failure

# ─── TIME HELPERS ───────────────────────────────────────────────────────────────
def get_localtime():
    return time.localtime(time.time() + TIMEZONE_OFFSET_HOURS*3600)  # local time tuple

def fmt(ts):
    m,d,y,H,M,S = ts[1],ts[2],ts[0],ts[3],ts[4],ts[5]  # unpack components
    return f"{m:02d}/{d:02d}/{y:04d} {H:02d}:{M:02d}:{S:02d}"  # formatted

def timestamp():
    t = time.time() + TIMEZONE_OFFSET_HOURS*3600  # adjusted epoch
    y,m,d,H,M,S = time.localtime(t)[0:6]
    return f"{y:04d}-{m:02d}-{d:02d} {H:02d}:{M:02d}:{S:02d}"  # ISO style

# ─── BUSINESS LOGIC ────────────────────────────────────────────────────────────
def is_business_hour(h):
    return BUSINESS_START_HOUR <= h < BUSINESS_END_HOUR  # within hours

def effective_business(h):
    biz = is_business_hour(h)
    if override_force and biz:      return False         # force off
    if override_disable and not biz: return True         # disable off-hours
    return biz                                          # default

# ─── WEB SERVER THREAD ──────────────────────────────────────────────────────────
INDEX_HTML = """\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Motion Status</title>
<style>
  body{font-family:sans-serif;padding:1rem}
  #controls button{margin-right:.5rem}
  table{border-collapse:collapse;width:100%;margin-top:1rem}
  th,td{border:1px solid #ccc;padding:.5rem}
  th{background:#f4f4f4}
</style>
</head><body>
  <h1>Motion Sensor Status</h1>
  <div id="status">
    <p>Clock: <span id="clock">…</span></p>
    <p>Business hours now? <span id="biz">…</span></p>
    <p>Mode: <span id="mode">…</span></p>
  </div>
  <div id="controls">
    <button onclick="action('force')">Force After-hours</button>
    <button onclick="action('disable')">Disable After-hours</button>
    <button onclick="action('stop')">Stop Alarm</button>
    <button onclick="action('clear')">Clear Log</button>
  </div>
  <h2>Recent Activations</h2>
  <table id="events">
    <tr><th>Timestamp</th><th>Type</th></tr>
  </table>
  <script>
  function loadStatus(){
    fetch('status').then(r=>r.json()).then(d=>{
      document.getElementById('clock').innerText = d.clock;
      document.getElementById('biz').innerText   = d.business;
      document.getElementById('mode').innerText  = d.mode;
      let rows = d.events.map(e=>`<tr><td>${e[0]}</td><td>${e[1]}</td></tr>`).join('');
      document.getElementById('events').innerHTML =
        '<tr><th>Timestamp</th><th>Type</th></tr>'+rows;
    });
  }
  function action(cmd){
    fetch(cmd).then(_=>loadStatus());
  }
  window.onload = loadStatus;
  setInterval(loadStatus,5000);
  </script>
</body></html>
"""  # static HTML template

def web_server():
    s = socket.socket()                         # create socket
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # reuse addr
    s.bind(('0.0.0.0',80))                      # bind all interfaces
    s.listen(5)                                 # max 5 queued
    s.settimeout(0.5)                           # accept timeout
    print("Web server running…")               # startup message

    global override_force, override_disable, alarm_active, events

    while True:
        try:
            cl,_ = s.accept()                   # accept client or timeout
            req = cl.recv(1024).decode()       # read request

            if 'GET /status' in req:
                lt  = get_localtime()          # current local time
                biz = is_business_hour(lt[3])
                eff = effective_business(lt[3])
                resp = {                       # prepare JSON response
                  'clock': fmt(lt),
                  'business': 'Yes' if biz else 'No',
                  'mode': 'Business Mode' if eff else 'After-hours Mode',
                  'events': events
                }
                j = json.dumps(resp)            # serialize JSON
                cl.send("HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n")
                cl.send(j)                      # send JSON payload

            elif 'GET /force' in req:
                override_force, override_disable = True, False  # set flags
                cl.send("HTTP/1.0 200 OK\r\n\r\n")

            elif 'GET /disable' in req:
                override_disable, override_force = True, False  # set flags
                cl.send("HTTP/1.0 200 OK\r\n\r\n")

            elif 'GET /stop' in req:
                buzz.cancel_flag = True          # stop ongoing alarm
                alarm_active = False             # reset flag
                cl.send("HTTP/1.0 200 OK\r\n\r\n")

            elif 'GET /clear' in req:
                events.clear()                  # clear event log
                cl.send("HTTP/1.0 200 OK\r\n\r\n")

            else:
                cl.send("HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n")
                cl.send(INDEX_HTML)             # serve dashboard

            cl.close()                          # close client socket
        except OSError:
            pass                                 # ignore accept timeouts

# launch server thread
_thread.start_new_thread(web_server, ())        # run server concurrently

print(f"Ready @ http://{IP}/")                # print dashboard URL

# ─── MAIN LOOP ─────────────────────────────────────────────────────────────────
while True:
    now    = time.ticks_ms()                   # current time ms
    motion = bool(pir.value())                 # read PIR sensor
    lt     = get_localtime()                   # local time tuple
    eff    = effective_business(lt[3])         # determine operating mode

    if motion and not prev_motion:             # on motion start
        ts = timestamp()                       # ISO timestamp
        print("Motion at", ts)
        if eff:
            if time.ticks_diff(now,last_buzz) >= ALERT_INTERVAL_MS:
                buzz.alert()                   # short alert tone
                last_buzz = now                # update last alert time
                events.insert(0,[ts,'alert'])  # prepend event
                if len(events)>10: events.pop()
        else:
            alarm_active = True                # enable continuous alarm
            events.insert(0,[ts,'alarm'])      # prepend event
            if len(events)>10: events.pop()

    if alarm_active:                            # if sweeping alarm active
        buzz.alarm()                            # perform frequency sweep

    prev_motion = motion                       # store current state
    time.sleep_ms(50)                          # debounce delay
