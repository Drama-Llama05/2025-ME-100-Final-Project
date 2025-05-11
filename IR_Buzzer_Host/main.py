import network, ntptime, time, socket, _thread
from machine import Pin
from buzzer import Buzzer
import ujson as json   # MicroPython’s JSON module

# ─── USER CONFIG ────────────────────────────────────────────────────────────────
WIFI_SSID             = 'Berkeley-IoT'
WIFI_PASSWORD         = '%5j6EP5('
STATIC_IP             = '10.41.196.7'
SUBNET_MASK           = '255.255.252.0'
GATEWAY               = '10.41.196.1'
DNS_SERVER            = '128.32.206.9'
TIMEZONE_OFFSET_HOURS = -7      # PST
BUSINESS_START_HOUR   = 9
BUSINESS_END_HOUR     = 17
ALERT_INTERVAL_MS     = 10_000  # ms between buzzer alerts

# ─── STATE ─────────────────────────────────────────────────────────────────────
override_force   = False
override_disable = False
alarm_active     = False
last_buzz        = 0
prev_motion      = False
events           = []  # list of [timestamp, "alert"|"alarm"]

# ─── HARDWARE ──────────────────────────────────────────────────────────────────
pir    = Pin(36, Pin.IN)
buzz   = Buzzer(12)
led    = Pin(25, Pin.OUT)  # status LED

# ─── NETWORK SETUP ─────────────────────────────────────────────────────────────
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.ifconfig((STATIC_IP, SUBNET_MASK, GATEWAY, DNS_SERVER))
sta.connect(WIFI_SSID, WIFI_PASSWORD)
print("Connecting to Wi-Fi...", end='')
for _ in range(20):
    if sta.isconnected(): break
    time.sleep(1); print('.', end='')
print()
if not sta.isconnected(): raise RuntimeError("Wi-Fi failed")
IP = sta.ifconfig()[0]
print("Connected, IP =", IP)

# ─── NTP ───────────────────────────────────────────────────────────────────────
try:
    ntptime.settime()
    print("Clock synced")
except:
    print("NTP sync failed")

# ─── TIME HELPERS ───────────────────────────────────────────────────────────────
def get_localtime():
    return time.localtime(time.time() + TIMEZONE_OFFSET_HOURS*3600)

def fmt(ts):
    m,d,y,H,M,S = ts[1],ts[2],ts[0],ts[3],ts[4],ts[5]
    return f"{m:02d}/{d:02d}/{y:04d} {H:02d}:{M:02d}:{S:02d}"

def timestamp():
    t = time.time() + TIMEZONE_OFFSET_HOURS*3600
    y,m,d,H,M,S = time.localtime(t)[0:6]
    return f"{y:04d}-{m:02d}-{d:02d} {H:02d}:{M:02d}:{S:02d}"

# ─── BUSINESS LOGIC ────────────────────────────────────────────────────────────
def is_business_hour(h):
    return BUSINESS_START_HOUR <= h < BUSINESS_END_HOUR

def effective_business(h):
    biz = is_business_hour(h)
    if override_force and biz:     return False
    if override_disable and not biz: return True
    return biz

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
      document.getElementById('events').innerHTML = '<tr><th>Timestamp</th><th>Type</th></tr>'+rows;
    });
  }
  function action(cmd){
    fetch(cmd).then(_=>loadStatus());
  }
  window.onload = loadStatus;
  setInterval(loadStatus,5000);
  </script>
</body></html>
"""

def web_server():
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    s.bind(('0.0.0.0',80)); s.listen(5); s.settimeout(0.5)
    print("Web server running…")

    global override_force, override_disable, alarm_active

    while True:
        try:
            cl,_ = s.accept()
            req = cl.recv(1024).decode()

            if 'GET /status' in req:
                lt  = get_localtime()
                biz = is_business_hour(lt[3])
                eff = effective_business(lt[3])
                resp = {
                  'clock': fmt(lt),
                  'business': 'Yes' if biz else 'No',
                  'mode': 'Business Mode' if eff else 'After-hours Mode',
                  'events': events
                }
                j = json.dumps(resp)
                cl.send("HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n")
                cl.send(j)

            elif 'GET /force' in req:
                override_force, override_disable = True, False
                cl.send("HTTP/1.0 200 OK\r\n\r\n")

            elif 'GET /disable' in req:
                override_disable, override_force = True, False
                cl.send("HTTP/1.0 200 OK\r\n\r\n")

            elif 'GET /stop' in req:
                buzz.cancel_flag = True
                alarm_active = False
                cl.send("HTTP/1.0 200 OK\r\n\r\n")

            else:
                cl.send("HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n")
                cl.send(INDEX_HTML)

            cl.close()
        except OSError:
            pass

# launch server thread
_thread.start_new_thread(web_server, ())

print(f"Ready @ http://{IP}/")

# ─── MAIN LOOP ─────────────────────────────────────────────────────────────────
while True:
    now   = time.ticks_ms()
    motion= bool(pir.value())
    lt    = get_localtime()
    eff   = effective_business(lt[3])

    if motion and not prev_motion:
        ts = timestamp()
        print("Motion at", ts)
        if eff:
            if time.ticks_diff(now,last_buzz) >= ALERT_INTERVAL_MS:
                buzz.alert()
                last_buzz = now
                events.insert(0,[ts,'alert'])
                if len(events)>10: events.pop()
        else:
            alarm_active = True
            events.insert(0,[ts,'alarm'])
            if len(events)>10: events.pop()

    if alarm_active:
        buzz.alarm()

    prev_motion = motion
    time.sleep_ms(50)

