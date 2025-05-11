import network, ntptime, time, socket, _thread  # networking, NTP, timing, sockets, threading
from machine import Pin                   # GPIO control
from mfrc522 import MFRC522               # RFID reader driver
from servo import Servo                   # Servo motor controller

# ─── USER CONFIG ────────────────────────────────────────────────────────────────
SSID     = 'Berkeley-IoT'                 # Wi-Fi network name
PASSWORD = 'CsN,55Pd'                      # Wi-Fi password

AUTHORIZED_USERS = {                       # map tag UID to username
    "8E8939033D": "User 1",
    "1AB631039E": "User 2",
    "17182D0220": "User 3",
    "2BE9960256": "User 4",
    "4B88BB027A": "User 5",
    "299D4603F1": "User 6",
    "026FC101AD": "User 7"
}

# RC522 pins
SCK  = 5                                 # SPI clock pin
MOSI = 19                                # SPI MOSI pin
MISO = 21                                # SPI MISO pin
RST  = 2                                 # reset pin tied high
CS   = 22                                # chip-select pin

# status LEDs
led_green = Pin(25, mode=Pin.OUT)         # green LED output
led_red   = Pin(13, mode=Pin.OUT)         # red LED output

# motor
motor = Servo(pin=4)                      # attach servo to GPIO4
motor.move(0)                             # initialize servo to 0°

# switch
switch = Pin(36, Pin.IN, Pin.PULL_DOWN)    # door-closed switch w/ pull-down

LOGFILE = 'log.csv'                       # log filename
PORT    = 80                              # HTTP server port

# ─── WIFI & TIME ─────────────────────────────────────────────────────────────
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)   # create station interface
    wlan.active(True)                     # enable Wi-Fi
    wlan.connect(SSID, PASSWORD)          # connect to AP
    print("Connecting to Wi-Fi...", end='')
    while not wlan.isconnected():
        time.sleep_ms(500)                # wait for connection
        print('.', end='')               # progress indicator
    print("\nConnected, IP =", wlan.ifconfig()[0])
    led_green.value(1); led_red.value(1)  # blink LEDs on success
    time.sleep_ms(500)
    led_green.value(0); led_red.value(0)
    return wlan.ifconfig()[0]            # return assigned IP

def sync_time():
    try:
        ntptime.settime()                 # sync RTC via NTP
        print("Clock synced via NTP.")
    except:
        print("NTP sync failed.")       # handle no NTP

def timestamp():
    try:
        utc_secs = time.time()           # get UTC seconds
    except AttributeError:
        utc_secs = time.mktime(time.localtime())  # fallback
    pst_secs = utc_secs - 8 * 3600      # PST offset
    tm = time.localtime(pst_secs)       # broken-out time
    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*tm[0:6])

# ─── LOGGING ────────────────────────────────────────────────────────────────────
try:
    open(LOGFILE, 'r').close()          # check for existing log
except OSError:
    with open(LOGFILE, 'w') as f:
        f.write("timestamp,uid,username\n")  # create header if missing

def log_access(uid, username):
    with open(LOGFILE, 'a') as f:
        f.write("{},{},{}\n".format(timestamp(), uid, username))  # append entry
    print("Logged:", uid, username, "at", timestamp())

# ─── RFID SETUP ─────────────────────────────────────────────────────────────────
rfid = MFRC522(SCK, MOSI, MISO, RST, CS)  # init RFID reader
seen = set()                              # track seen UIDs

# ─── WEB SERVER ────────────────────────────────────────────────────────────────
def web_server():
    addr = socket.getaddrinfo('0.0.0.0', PORT)[0][-1]  # listen on all interfaces
    srv = socket.socket()             # create TCP socket
    srv.bind(addr)                    # bind to port
    srv.listen(1)                     # listen for one connection
    print("Web server listening on port", PORT)

    while True:
        cl, _ = srv.accept()          # accept client
        req = cl.recv(1024).decode('utf-8', 'ignore')  # read request

        if 'GET /log.csv' in req:
            cl.send("HTTP/1.0 200 OK\r\n")          # send CSV
            cl.send("Content-Type: text/csv\r\n")
            cl.send("Content-Disposition: attachment; filename=\"{}\"\r\n".format(LOGFILE))
            cl.send("\r\n")
            try:
                with open(LOGFILE, 'r') as f:
                    for line in f:      # stream log lines
                        cl.send(line)
            except:
                cl.send("HTTP/1.0 500 Internal Server Error\r\n\r\n")

        elif 'GET /clear' in req:
            with open(LOGFILE, 'w') as f:
                f.write("timestamp,uid,username\n")  # overwrite with header
            cl.send("HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n")
            cl.send("<html><body><h1>Log Cleared</h1><p><a href='/'>Return to log viewer</a></p></body></html>")

        else:
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
""")  # send the live-view page
        cl.close()                      # close connection

# ─── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    ip = connect_wifi()               # join Wi-Fi
    sync_time()                       # sync clock
    _thread.start_new_thread(web_server, ())  # start server thread

    print(f"RFID scanner ready. Visit http://{ip}/ to view live log.")
    while True:
        status, _ = rfid.request(rfid.REQIDL)  # poll for tag
        if status == rfid.OK:
            status, raw = rfid.anticoll()      # read UID
            if status == rfid.OK:
                uid = "".join(f"{b:02X}" for b in raw)  # format hex

                if uid not in seen:
                    print("✔ New tag:", uid)
                    seen.add(uid)       # mark new
                else:
                    print("· Seen tag:", uid)

                if uid in AUTHORIZED_USERS:
                    user = AUTHORIZED_USERS[uid]  # lookup user
                    print(f"User Verified: {user} ({uid})")
                    led_green.value(1)    # indicate success
                    log_access(uid, user)  # record access
                    motor.move(90)       # unlock
                    time.sleep(1)
                    led_green.value(0)    # turn off LED
                    while switch.value():  # wait for door close
                        time.sleep_ms(50)
                    print("closing")
                    motor.move(0)        # relock
                else:
                    user = "Unauthorized"
                    print(f"Unauthorized User Access Attempt: {uid}")
                    led_red.value(1)      # flash red LED
                    time.sleep_ms(500)
                    led_red.value(0)
                    log_access(uid, user)  # log attempt

        time.sleep_ms(200)               # debounce delay

if __name__ == "__main__":
    main()                              # start program
