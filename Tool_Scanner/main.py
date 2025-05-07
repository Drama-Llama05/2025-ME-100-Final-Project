# main.py

import network, ntptime, time, socket, _thread
from machine import Pin
from mfrc522 import MFRC522

# ─── USER CONFIG ────────────────────────────────────────────────────────────────
SSID = "Berkeley-IoT"
PASSWORD = "4J,8cFlZ"

# map each valid UID to a user name
AUTHORIZED_USERS = {
    "A1745C3EB7": "Tool 1",
    "42455C3E65": "Tool 2",
    "43975C3EB6": "Tool 3",
    "B56F5C3EB8": "Tool 4",
    "72475C3E57": "Tool 5",
    "31395C3E6A": "Tool 6",
    "E8B05B3E3D": "Tool 7",
    "68585C3E52": "Tool 8",
    "786E5C3E74": "Tool 9",
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
    # PST = UTC - 7h
    pst_secs = utc_secs - 7 * 3600
    tm = time.localtime(pst_secs)
    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*tm[0:6])

# ─── LOGGING ────────────────────────────────────────────────────────────────────
# ensure CSV exists with correct header (added 'state' column)
try:
    open(LOGFILE, 'r').close()
except OSError:
    with open(LOGFILE, 'w') as f:
        f.write("timestamp,uid,username,state\n")

def log_access(uid, username):
    # count prior entries for this UID
    count = 0
    try:
        with open(LOGFILE, 'r') as f:
            next(f)  # skip header
            for line in f:
                parts = line.strip().split(',')
                if parts[1] == uid:
                    count += 1
    except OSError:
        pass

    # determine new state: odd→Checked Out, even→Checked In
    new_count = count + 1
    state = "Checked Out" if (new_count % 2) == 1 else "Checked In"

    ts = timestamp()
    with open(LOGFILE, 'a') as f:
        f.write("{},{},{},{}\n".format(ts, uid, username, state))
    print("Logged:", uid, username, state, "at", ts)

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
            # Clear log CSV (reset header)
            with open(LOGFILE, 'w') as f:
                f.write("timestamp,uid,username,state\n")
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
      fetch('/log.csv').then(r => r.text()).then(txt => {
        const lines = txt.trim().split('\\n').slice(1).reverse();
        let html = '<table>'
                 + '<tr>'
                 + '<th>Timestamp</th>'
                 + '<th>UID</th>'
                 + '<th>Username</th>'
                 + '<th>State</th>'
                 + '</tr>';
        lines.forEach(line => {
          if (!line) return;
          const [ts, uid, user, state] = line.split(',');
          html += `<tr>
                     <td>${ts}</td>
                     <td>${uid}</td>
                     <td>${user}</td>
                     <td>${state}</td>
                   </tr>`;
        });
        html += '</table>';
        document.getElementById('log').innerHTML = html;
      }).catch(() => {
        document.getElementById('log').innerText = 'Error loading log.';
      });
    }

    function clearLog() {
      if (confirm('Are you sure you want to clear the log?')) {
        fetch('/clear').then(() => loadLog());
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

                if uid not in seen:
                    print("✔ New tag:", uid)
                    seen.add(uid)
                else:
                    print("· Seen tag:", uid)

                if uid in AUTHORIZED_USERS:
                    user = AUTHORIZED_USERS[uid]
                    print(f"User Verified: {user} ({uid})")
                    led_green.value(1); time.sleep_ms(500); led_green.value(0)
                    log_access(uid, user)
                else:
                    user = "Unauthorized"
                    print(f"Unauthorized User Access Attempt: {uid}")
                    led_red.value(1); time.sleep_ms(500); led_red.value(0)
                    log_access(uid, user)

        time.sleep_ms(200)


if __name__ == "__main__":
    main()
