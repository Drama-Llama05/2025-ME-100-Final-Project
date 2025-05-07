# main.py

import network, ntptime, time, socket, _thread
from machine import Pin
from mfrc522 import MFRC522
from servo import Servo

# ─── USER CONFIG ────────────────────────────────────────────────────────────────
SSID     = 'Berkeley-IoT'
PASSWORD = 'CsN,55Pd'

# map each valid UID to a user name
AUTHORIZED_USERS = {
    "8E8939033D": "User 1",
    "1AB631039E": "User 2",
    "17182D0220": "User 3",
    "2BE9960256": "User 4",
    "4B88BB027A": "User 5",
    "299D4603F1": "User 6",
    "026FC101AD": "User 7"
}

# RC522 pins
SCK  = 5
MOSI = 19
MISO = 21
RST  = 2     # dummy GPIO (wired high)
CS   = 22

# status LEDs
led_green = Pin(25, mode=Pin.OUT)
led_red   = Pin(13, mode=Pin.OUT)

#motor
motor = Servo(pin=4)
motor.move(0)

#swith
switch = Pin(36, Pin.IN, Pin.PULL_DOWN)

LOGFILE = 'log.csv'
PORT    = 80

# ─── WIFI & TIME ───────────────────────────────────────────────────────────────
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    print("Connecting to Wi-Fi...", end='')
    while not wlan.isconnected():
        time.sleep_ms(500)
        print('.', end='')
    print("\nConnected, IP =", wlan.ifconfig()[0])
    led_green.value(1)
    led_red.value(1)
    time.sleep_ms(500)
    led_green.value(0)
    led_red.value(0)
    return wlan.ifconfig()[0]

def sync_time():
    try:
        ntptime.settime()
        print("Clock synced via NTP.")
    except:
        print("NTP sync failed.")

def timestamp():
    # get current UTC seconds (fallback if time.time() missing)
    try:
        utc_secs = time.time()
    except AttributeError:
        utc_secs = time.mktime(time.localtime())
    # PST = UTC - 8h
    pst_secs = utc_secs - 8 * 3600
    tm = time.localtime(pst_secs)
    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*tm[0:6])

# ─── LOGGING ────────────────────────────────────────────────────────────────────
# ensure CSV exists with correct header
try:
    open(LOGFILE, 'r').close()
except OSError:
    with open(LOGFILE, 'w') as f:
        f.write("timestamp,uid,username\n")

def log_access(uid, username):
    with open(LOGFILE, 'a') as f:
        f.write("{},{},{}\n".format(timestamp(), uid, username))
    print("Logged:", uid, username, "at", timestamp())

# ─── RFID SETUP ─────────────────────────────────────────────────────────────────
rfid = MFRC522(SCK, MOSI, MISO, RST, CS)
seen = set()

# ─── WEB SERVER ────────────────────────────────────────────────────────────────
def web_server():
    addr = socket.getaddrinfo('0.0.0.0', PORT)[0][-1]
    srv = socket.socket()
    srv.bind(addr)
    srv.listen(1)
    print("Web server listening on port", PORT)

    while True:
        cl, _ = srv.accept()
        req = cl.recv(1024).decode('utf-8', 'ignore')

        if 'GET /log.csv' in req:
            # raw CSV download
            cl.send("HTTP/1.0 200 OK\r\n")
            cl.send("Content-Type: text/csv\r\n")
            cl.send("Content-Disposition: attachment; filename=\"{}\"\r\n".format(LOGFILE))
            cl.send("\r\n")
            try:
                with open(LOGFILE, 'r') as f:
                    for line in f:
                        cl.send(line)
            except:
                cl.send("HTTP/1.0 500 Internal Server Error\r\n\r\n")

        elif 'GET /clear' in req:
            # Clear log CSV
            with open(LOGFILE, 'w') as f:
                f.write("timestamp,uid,username\n")
            cl.send("HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n")
            cl.send("<html><body><h1>Log Cleared</h1><p><a href='/'>Return to log viewer</a></p></body></html>")

        else:
            # interactive HTML page
            cl.send("HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n")
            cl.send("""\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>RFID Log Viewer</title>
  <style>
    body { font-family: sans-serif; padding: 1rem; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ccc; padding: 0.5rem; }
    th { background: #f4f4f4; }
    button { margin: 1rem 0; padding: 0.5rem 1rem; }
  </style>
</head>
<body>
  <h1>RFID Tag Log</h1>
  <button onclick="clearLog()">Clear Log</button>
  <div id="log">Loading…</div>
  <script>
    function loadLog() {
      fetch('log.csv').then(r => r.text()).then(txt => {
        const lines = txt.trim().split('\\n').slice(1).reverse();  // REVERSE to show latest first
        let html = '<table>'
                 + '<tr><th>Timestamp</th><th>UID</th><th>Username</th></tr>';
        lines.forEach(line => {
          if (!line) return;
          const [ts, uid, user] = line.split(',');
          html += `<tr><td>${ts}</td><td>${uid}</td><td>${user}</td></tr>`;
        });
        html += '</table>';
        document.getElementById('log').innerHTML = html;
      }).catch(() => {
        document.getElementById('log').innerText = 'Error loading log.';
      });
    }

    function clearLog() {
      if (confirm('Are you sure you want to clear the log?')) {
        fetch('clear').then(() => loadLog());
      }
    }

    window.onload = loadLog;
    setInterval(loadLog, 5000);
  </script>
</body>
</html>
""")
        cl.close()

# ─── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    ip = connect_wifi()
    sync_time()
    _thread.start_new_thread(web_server, ())

    print("RFID scanner ready. Visit http://{}/ to view live log.".format(ip))
    while True:
            
        status, _ = rfid.request(rfid.REQIDL)
        if status == rfid.OK:
            status, raw = rfid.anticoll()
            if status == rfid.OK:
                uid = "".join("{:02X}".format(b) for b in raw)

                # indicate new vs. seen
                if uid not in seen:
                    print("✔ New tag:", uid)
                    seen.add(uid)
                else:
                    print("· Seen tag:", uid)

                # check authorization
                if uid in AUTHORIZED_USERS:
                    user = AUTHORIZED_USERS[uid]
                    print(f"User Verified: {user} ({uid})")
                    led_green.value(1)
                    log_access(uid, user)
                    motor.move(90) # turn servo to 0°
                    time.sleep(1)
                    led_green.value(0)
                    while switch.value():
                        time.sleep_ms(50)
                    print("closing")
                    motor.move(0)
                else:
                    user = "Unauthorized"
                    print(f"Unauthorized User Access Attempt: {uid}")
                    led_red.value(1)
                    time.sleep_ms(500)
                    led_red.value(0)
                    log_access(uid, user)


        time.sleep_ms(200)


if __name__ == "__main__":
    main()
