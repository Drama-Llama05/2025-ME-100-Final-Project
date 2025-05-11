import network, ntptime, time, socket, _thread   # bring in Wi-Fi, NTP sync, timing, HTTP sockets, threading
from machine import Pin                         # GPIO control for LEDs
from mfrc522 import MFRC522                     # RC522 RFID reader driver

# ─── USER CONFIG ────────────────────────────────────────────────────────────────
SSID = "Berkeley-IoT"                         # Wi-Fi SSID
PASSWORD = "4J,8cFlZ"                          # Wi-Fi password

AUTHORIZED_USERS = {                            # map each RFID UID to a tool name
    "A1745C3EB7": "Tool 1",
    "42455C3E65": "Tool 2",
    "43975C3EB6": "Tool 3",
    "B56F5C3EB8": "Tool 4",
    "72475C3E57": "Tool 5",
    "31395C3E6A": "Tool 6",
    "E8B05B3E3D": "Tool 7",
    "68585C3E52": "Tool 8",
    "786E5C3E74": "Tool 9",
    "00FE5B3E9B": "Tool 10"
}

# RC522 pins
SCK  = 5                                     # SPI clock pin for RC522
MOSI = 19                                    # SPI MOSI pin
MISO = 21                                    # SPI MISO pin
RST  = 2                                     # RC522 reset pin tied high
CS   = 22                                    # RC522 chip-select pin

# status LEDs
led_green = Pin(25, mode=Pin.OUT)            # green LED output pin
led_red   = Pin(13, mode=Pin.OUT)            # red LED output pin

LOGFILE = 'log.csv'                          # CSV log filename
PORT    = 80                                 # HTTP port for web server

# ─── WIFI & TIME ───────────────────────────────────────────────────────────────
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)       # create station WLAN interface
    wlan.active(True)                         # enable Wi-Fi radio
    wlan.connect(SSID, PASSWORD)              # start connection to AP
    print("Connecting to Wi-Fi...", end='')
    while not wlan.isconnected():
        time.sleep_ms(500)                    # wait 500ms
        print('.', end='')                   # progress indicator
    print("\nConnected, IP =", wlan.ifconfig()[0])  # display IP
    led_green.value(1); led_red.value(1)      # blink LEDs to signal connect
    time.sleep_ms(500)
    led_green.value(0); led_red.value(0)
    return wlan.ifconfig()[0]                # return device IP address


def sync_time():
    try:
        ntptime.settime()                     # attempt NTP sync
        print("Clock synced via NTP.")
    except:
        print("NTP sync failed.")           # handle failure quietly


def timestamp():
    try:
        utc_secs = time.time()               # get seconds since epoch
    except AttributeError:
        utc_secs = time.mktime(time.localtime())  # fallback if time.time missing
    pst_secs = utc_secs - 7 * 3600           # adjust UTC to PDT (UTC-7h)
    tm = time.localtime(pst_secs)            # convert to broken-down tuple
    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*tm[0:6])  # formatted string

# ─── LOGGING ────────────────────────────────────────────────────────────────────
# ensure CSV exists with correct header (added 'state' column)
try:
    open(LOGFILE, 'r').close()             # check for existing log file
except OSError:
    with open(LOGFILE, 'w') as f:
        f.write("timestamp,uid,username,state\n")  # create header if absent


def log_access(uid, username):
    # count prior entries for this UID
    count = 0
    try:
        with open(LOGFILE, 'r') as f:
            next(f)  # skip header row
            for line in f:
                parts = line.strip().split(',')
                if parts[1] == uid:
                    count += 1               # increment count if UID matches
    except OSError:
        pass                                 # ignore if file read fails

    new_count = count + 1                   # this access number
    state = "Checked Out" if (new_count % 2) == 1 else "Checked In"  # odd→out, even→in

    ts = timestamp()                        # generate timestamp string
    with open(LOGFILE, 'a') as f:
        f.write("{},{},{},{}\n".format(ts, uid, username, state))  # append new row
    print("Logged:", uid, username, state, "at", ts)  # console feedback

# ─── RFID SETUP ─────────────────────────────────────────────────────────────────
rfid = MFRC522(SCK, MOSI, MISO, RST, CS)    # initialize RFID reader hardware
seen = set()                                # track seen UIDs to mark new vs repeat

# ─── WEB SERVER ────────────────────────────────────────────────────────────────
def web_server():
    addr = socket.getaddrinfo('0.0.0.0', PORT)[0][-1]  # resolve bind address
    srv = socket.socket()                     # create socket
    srv.bind(addr)                            # bind to 0.0.0.0:PORT
    srv.listen(1)                             # listen queue depth 1
    print("Web server listening on port", PORT)

    while True:
        cl, _ = srv.accept()                  # block until client connects
        req = cl.recv(1024).decode('utf-8', 'ignore')  # read HTTP request

        if 'GET /log.csv' in req:
            # raw CSV download
            cl.send("HTTP/1.0 200 OK\r\n")
            cl.send("Content-Type: text/csv\r\n")
            cl.send("Content-Disposition: attachment; filename=\"{}\"\r\n".format(LOGFILE))
            cl.send("\r\n")
            try:
                with open(LOGFILE, 'r') as f:
                    for line in f:
                        cl.send(line)        # stream each log line
            except:
                cl.send("HTTP/1.0 500 Internal Server Error\r\n\r\n")

        elif 'GET /clear' in req:
            # Clear log CSV (reset header)
            with open(LOGFILE, 'w') as f:
                f.write("timestamp,uid,Tool,state\n")  # reset header
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
  <title>Tool Log Viewer</title>
  <style>
    body { font-family: sans-serif; padding: 1rem; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ccc; padding: 0.5rem; }
    th { background: #f4f4f4; }
    button { margin: 1rem 0; padding: 0.5rem 1rem; }
  </style>
</head>
<body>
  <h1>Tool Log Viewer</h1>
  <button onclick="clearLog()">Clear Log</button>
  <div id="log">Loading…</div>
  <script>
    function loadLog() {
      fetch('log.csv').then(r => r.text()).then(txt => {
        const lines = txt.trim().split('\\n').slice(1).reverse();
        let html = '<table>'
                 + '<tr>'
                 + '<th>Timestamp</th>'
                 + '<th>UID</th>'
                 + '<th>Tool</th>'
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
        fetch('clear').then(() => loadLog());
      }
    }

    window.onload = loadLog;
    setInterval(loadLog, 5000);
  </script>
</body>
</html>
""")  # serve viewer page
        cl.close()                              # ensure connection closed

# ─── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    ip = connect_wifi()                       # join Wi-Fi
    sync_time()                               # sync RTC
    _thread.start_new_thread(web_server, ())  # run web server in background

    print("RFID scanner ready. Visit http://{}/ to view live log.".format(ip))
    while True:
        status, _ = rfid.request(rfid.REQIDL) # poll for tag presence
        if status == rfid.OK:
            status, raw = rfid.anticoll()     # anti-collision UID read
            if status == rfid.OK:
                uid = "".join("{:02X}".format(b) for b in raw)  # format UID hex

                if uid not in seen:
                    print("✔ New tag:", uid)
                    seen.add(uid)           # mark this UID seen
                else:
                    print("· Seen tag:", uid)

                if uid in AUTHORIZED_USERS:
                    user = AUTHORIZED_USERS[uid]  # valid tool
                    print(f"User Verified: {user} ({uid})")
                    led_green.value(1); time.sleep_ms(500); led_green.value(0)  # blink green
                    log_access(uid, user)    # record check-out/in
                else:
                    user = "Unrecognized Tool"
                    print(f"Unauthorized User Access Attempt: {uid}")
                    led_red.value(1); time.sleep_ms(500); led_red.value(0)      # blink red
                    log_access(uid, user)    # record failed attempt

        time.sleep_ms(200)                     # short delay to debounce

if __name__ == "__main__":
    main()                                    # start the application
