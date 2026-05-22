"""
dashboard.py
─────────────────────────────────────────────────────────────
Web Dashboard realtime cho hệ thống điểm danh AIoT

Cài đặt:
    pip install flask flask-socketio paho-mqtt

Chạy:
    python dashboard.py

Mở trình duyệt:
    http://localhost:5000
"""

from flask import Flask, render_template_string
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
import sqlite3
import ssl
import threading
import json
import os
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# CẤU HÌNH
# ══════════════════════════════════════════════════════════════
MQTT_BROKER = os.getenv("MQTT_BROKER", "44664d8119b54fadaf9870a37274af6b.s1.eu.hivemq.cloud")
MQTT_PORT   = int(os.getenv("MQTT_PORT", "8883"))
MQTT_USER   = os.getenv("MQTT_USER", "").strip()
MQTT_PASS   = os.getenv("MQTT_PASS", "").strip()

TOPIC_RESULT  = "diemdanh/ketqua"
TOPIC_TRIGGER = "diemdanh/camera/trigger"
TOPIC_RELAY   = "diemdanh/relay/control"

DB_FILE = "attendance.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "diemdanh_secret"
socketio = SocketIO(app, cors_allowed_origins="*")

# ══════════════════════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════════════════════
def get_records(limit=50):
    try:
        conn = sqlite3.connect(DB_FILE)
        rows = conn.execute(
            "SELECT name, timestamp, confident FROM records ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return [{"name": r[0], "time": r[1], "confident": r[2]} for r in rows]
    except:
        return []

def get_stats():
    try:
        conn = sqlite3.connect(DB_FILE)
        total   = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        today   = conn.execute(
            "SELECT COUNT(*) FROM records WHERE DATE(timestamp) = DATE('now')"
        ).fetchone()[0]
        unique  = conn.execute("SELECT COUNT(DISTINCT name) FROM records").fetchone()[0]
        conn.close()
        return {"total": total, "today": today, "unique": unique}
    except:
        return {"total": 0, "today": 0, "unique": 0}

# ══════════════════════════════════════════════════════════════
# HTML DASHBOARD
# ══════════════════════════════════════════════════════════════
HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AIoT Điểm Danh</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
<style>
:root {
  --bg: #07080f;
  --panel: #0d0f1c;
  --border: #1a1d2e;
  --accent: #00f5a0;
  --accent2: #00c8ff;
  --warn: #ff6b35;
  --text: #e8eaf6;
  --muted: #4a4d6a;
  --card: #111326;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Syne', sans-serif;
  min-height: 100vh;
  overflow-x: hidden;
}

/* Grid background */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  background-image:
    linear-gradient(rgba(0,245,160,0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,245,160,0.03) 1px, transparent 1px);
  background-size: 40px 40px;
  pointer-events: none;
  z-index: 0;
}

.container { max-width: 1200px; margin: 0 auto; padding: 0 24px; position: relative; z-index: 1; }

/* Header */
header {
  border-bottom: 1px solid var(--border);
  padding: 20px 0;
  margin-bottom: 32px;
}
.header-inner {
  display: flex;
  align-items: center;
  gap: 16px;
}
.logo-mark {
  width: 40px; height: 40px;
  border: 2px solid var(--accent);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px;
  box-shadow: 0 0 20px rgba(0,245,160,0.3);
  flex-shrink: 0;
}
.logo-text h1 {
  font-size: 18px; font-weight: 800; letter-spacing: .04em;
  color: var(--text);
}
.logo-text p { font-size: 12px; color: var(--muted); font-family: 'Space Mono', monospace; }
.header-right { margin-left: auto; display: flex; align-items: center; gap: 12px; }

/* Live indicator */
.live-dot {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; font-family: 'Space Mono', monospace;
  color: var(--muted);
}
.dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--muted);
  transition: background .3s;
}
.dot.online { background: var(--accent); box-shadow: 0 0 8px var(--accent); animation: pulse 2s infinite; }
.dot.trigger { background: var(--warn); box-shadow: 0 0 8px var(--warn); }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }

/* Stats row */
.stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 28px; }
.stat-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px 24px;
  position: relative;
  overflow: hidden;
  transition: border-color .2s;
}
.stat-card:hover { border-color: var(--accent); }
.stat-card::after {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--accent), var(--accent2));
}
.stat-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .1em; margin-bottom: 8px; font-family: 'Space Mono', monospace; }
.stat-value { font-size: 36px; font-weight: 800; color: var(--accent); line-height: 1; }
.stat-sub { font-size: 12px; color: var(--muted); margin-top: 4px; }

/* Main grid */
.main-grid { display: grid; grid-template-columns: 1fr 340px; gap: 20px; }

/* Table panel */
.panel {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}
.panel-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}
.panel-title { font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); font-family: 'Space Mono', monospace; }
.badge { font-size: 11px; padding: 3px 10px; border-radius: 20px; background: rgba(0,245,160,.1); color: var(--accent); font-family: 'Space Mono', monospace; }

table { width: 100%; border-collapse: collapse; }
th {
  text-align: left; padding: 10px 20px;
  font-size: 10px; color: var(--muted);
  text-transform: uppercase; letter-spacing: .1em;
  border-bottom: 1px solid var(--border);
  font-family: 'Space Mono', monospace;
}
td { padding: 13px 20px; font-size: 13px; border-bottom: 1px solid rgba(26,29,46,.6); }
tr:last-child td { border-bottom: none; }
tr { transition: background .15s; }
tr:hover td { background: rgba(0,245,160,.03); }
tr.new-row td { animation: flashRow .8s ease; }
@keyframes flashRow {
  0% { background: rgba(0,245,160,.15); }
  100% { background: transparent; }
}
.name-cell { font-weight: 600; color: var(--text); }
.time-cell { font-family: 'Space Mono', monospace; font-size: 11px; color: var(--muted); }
.conf-cell { font-family: 'Space Mono', monospace; font-size: 12px; }
.conf-bar { display: flex; align-items: center; gap: 8px; }
.conf-track { flex: 1; height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; }
.conf-fill { height: 100%; border-radius: 2px; background: linear-gradient(90deg, var(--accent2), var(--accent)); transition: width .5s; }

/* Side panel */
.side-panel { display: flex; flex-direction: column; gap: 16px; }

/* Event log */
.log-body { padding: 12px; max-height: 280px; overflow-y: auto; }
.log-body::-webkit-scrollbar { width: 4px; }
.log-body::-webkit-scrollbar-track { background: transparent; }
.log-body::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
.log-item {
  display: flex; gap: 10px; padding: 8px 8px;
  border-radius: 6px; margin-bottom: 4px;
  font-size: 12px; font-family: 'Space Mono', monospace;
  animation: slideIn .3s ease;
}
@keyframes slideIn { from { opacity:0; transform:translateX(-8px); } to { opacity:1; transform:none; } }
.log-ts { color: var(--muted); flex-shrink: 0; font-size: 10px; margin-top: 1px; }
.log-msg { color: var(--text); line-height: 1.4; word-break: break-all; }
.log-item.success { background: rgba(0,245,160,.06); }
.log-item.warn { background: rgba(255,107,53,.06); }
.log-item.info { background: rgba(0,200,255,.06); }
.log-item.success .log-msg { color: var(--accent); }
.log-item.warn .log-msg { color: var(--warn); }
.log-item.info .log-msg { color: var(--accent2); }

/* Status card */
.status-grid { padding: 16px; display: flex; flex-direction: column; gap: 10px; }
.status-row { display: flex; justify-content: space-between; align-items: center; font-size: 12px; }
.status-key { color: var(--muted); font-family: 'Space Mono', monospace; font-size: 11px; }
.status-val { font-weight: 600; font-family: 'Space Mono', monospace; font-size: 11px; }
.status-val.green { color: var(--accent); }
.status-val.blue { color: var(--accent2); }
.status-val.orange { color: var(--warn); }

/* Alert banner */
.alert {
  position: fixed; top: 20px; right: 20px; z-index: 999;
  background: var(--card);
  border: 1px solid var(--accent);
  border-radius: 10px;
  padding: 14px 20px;
  max-width: 300px;
  box-shadow: 0 0 30px rgba(0,245,160,.2);
  display: none;
  animation: slideDown .3s ease;
}
.alert.show { display: block; }
.alert.warn-alert { border-color: var(--warn); box-shadow: 0 0 30px rgba(255,107,53,.2); }
@keyframes slideDown { from{opacity:0;transform:translateY(-10px)} to{opacity:1;transform:none} }
.alert-title { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing:.08em; font-family:'Space Mono',monospace; margin-bottom:4px; }
.alert-body { font-size: 14px; font-weight: 700; }
.alert-body.green { color: var(--accent); }
.alert-body.orange { color: var(--warn); }

footer {
  text-align: center; padding: 32px 0 20px;
  font-size: 11px; color: var(--muted);
  font-family: 'Space Mono', monospace;
}
</style>
</head>
<body>
<div class="container">

  <header>
    <div class="header-inner">
      <div class="logo-mark">⬡</div>
      <div class="logo-text">
        <h1>AIOT ĐIỂM DANH</h1>
        <p>Face Recognition Attendance System</p>
      </div>
      <div class="header-right">
        <div class="live-dot">
          <div class="dot" id="mqtt-dot"></div>
          <span id="mqtt-status">Đang kết nối...</span>
        </div>
      </div>
    </div>
  </header>

  <!-- Stats -->
  <div class="stats-row">
    <div class="stat-card">
      <div class="stat-label">Tổng điểm danh</div>
      <div class="stat-value" id="stat-total">—</div>
      <div class="stat-sub">lượt ghi nhận</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Hôm nay</div>
      <div class="stat-value" id="stat-today">—</div>
      <div class="stat-sub">lượt hôm nay</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Số người</div>
      <div class="stat-value" id="stat-unique">—</div>
      <div class="stat-sub">người khác nhau</div>
    </div>
  </div>

  <!-- Main -->
  <div class="main-grid">

    <!-- Table -->
    <div class="panel">
      <div class="panel-header">
        <span class="panel-title">Lịch sử điểm danh</span>
        <span class="badge" id="record-count">0 bản ghi</span>
      </div>
      <div style="overflow-x:auto">
        <table>
          <thead>
            <tr>
              <th>Tên sinh viên</th>
              <th>Thời gian</th>
              <th>Độ chính xác</th>
            </tr>
          </thead>
          <tbody id="records-body">
            <tr><td colspan="3" style="text-align:center;color:var(--muted);padding:40px">Chưa có dữ liệu điểm danh</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Side -->
    <div class="side-panel">

      <!-- System status -->
      <div class="panel">
        <div class="panel-header">
          <span class="panel-title">Trạng thái hệ thống</span>
        </div>
        <div class="status-grid">
          <div class="status-row">
            <span class="status-key">MQTT Broker</span>
            <span class="status-val blue" id="s-broker">Đang kết nối</span>
          </div>
          <div class="status-row">
            <span class="status-key">ESP32</span>
            <span class="status-val" id="s-esp32">Chờ tín hiệu</span>
          </div>
          <div class="status-row">
            <span class="status-key">AI Engine</span>
            <span class="status-val" id="s-ai">Sẵn sàng</span>
          </div>
          <div class="status-row">
            <span class="status-key">Relay</span>
            <span class="status-val" id="s-relay">CLOSED</span>
          </div>
          <div class="status-row">
            <span class="status-key">Lần cuối</span>
            <span class="status-val" id="s-last">—</span>
          </div>
        </div>
      </div>

      <!-- Event log -->
      <div class="panel" style="flex:1">
        <div class="panel-header">
          <span class="panel-title">Event Log</span>
          <button onclick="clearLog()" style="font-size:11px;color:var(--muted);background:none;border:none;cursor:pointer;font-family:'Space Mono',monospace">XOÁ</button>
        </div>
        <div class="log-body" id="log-body">
          <div class="log-item info">
            <span class="log-ts">--:--</span>
            <span class="log-msg">Hệ thống khởi động...</span>
          </div>
        </div>
      </div>

    </div>
  </div>

  <footer>AIoT Face Recognition Attendance System &nbsp;|&nbsp; ESP32 + HiveMQ + OpenCV</footer>
</div>

<!-- Alert -->
<div class="alert" id="alert-box">
  <div class="alert-title" id="alert-title">THÔNG BÁO</div>
  <div class="alert-body" id="alert-body"></div>
</div>

<script>
const socket = io();
let records = [];

// ── Socket events ────────────────────────────
socket.on('connect', () => {
  addLog('WebSocket kết nối thành công', 'info');
});

socket.on('mqtt_status', data => {
  const dot = document.getElementById('mqtt-dot');
  const txt = document.getElementById('mqtt-status');
  const sb  = document.getElementById('s-broker');
  if (data.connected) {
    dot.className = 'dot online';
    txt.textContent = 'MQTT Online';
    sb.textContent = 'CONNECTED';
    sb.className = 'status-val green';
    addLog('MQTT broker kết nối thành công', 'success');
  } else {
    dot.className = 'dot';
    txt.textContent = 'MQTT Offline';
    sb.textContent = 'DISCONNECTED';
    sb.className = 'status-val orange';
  }
});

socket.on('trigger', data => {
  document.getElementById('mqtt-dot').className = 'dot trigger';
  document.getElementById('s-esp32').textContent = 'TRIGGERED';
  document.getElementById('s-esp32').className = 'status-val orange';
  document.getElementById('s-ai').textContent = 'Đang nhận diện...';
  document.getElementById('s-ai').className = 'status-val blue';
  addLog('ESP32: PERSON_DETECTED', 'warn');
  setTimeout(() => {
    document.getElementById('mqtt-dot').className = 'dot online';
  }, 1000);
});

socket.on('result', data => {
  const result = data.result;
  document.getElementById('s-last').textContent = new Date().toLocaleTimeString('vi-VN');
  document.getElementById('s-ai').textContent = 'Sẵn sàng';
  document.getElementById('s-ai').className = 'status-val green';
  document.getElementById('s-esp32').textContent = 'Chờ tín hiệu';
  document.getElementById('s-esp32').className = 'status-val';

  if (result.startsWith('PRESENT:')) {
    const name = result.split(':')[1];
    addLog(`✓ Nhận diện: ${name}`, 'success');
    showAlert(`✓ ${name}`, 'green', 'ĐIỂM DANH THÀNH CÔNG');
    document.getElementById('s-relay').textContent = 'OPEN';
    document.getElementById('s-relay').className = 'status-val green';
    setTimeout(() => {
      document.getElementById('s-relay').textContent = 'CLOSED';
      document.getElementById('s-relay').className = 'status-val';
    }, 5000);
    loadRecords();
    loadStats();
  } else if (result === 'UNKNOWN') {
    addLog('✗ Khuôn mặt không nhận ra', 'warn');
    showAlert('Không nhận ra!', 'orange', 'CẢNH BÁO', true);
  } else {
    addLog(`✗ ${result}`, 'warn');
  }
});

socket.on('init_data', data => {
  records = data.records || [];
  renderTable();
  updateStats(data.stats || {});
});

// ── Load data ────────────────────────────────
function loadRecords() {
  fetch('/api/records')
    .then(r => r.json())
    .then(data => { records = data; renderTable(); });
}

function loadStats() {
  fetch('/api/stats')
    .then(r => r.json())
    .then(data => updateStats(data));
}

function updateStats(s) {
  document.getElementById('stat-total').textContent  = s.total  ?? '—';
  document.getElementById('stat-today').textContent  = s.today  ?? '—';
  document.getElementById('stat-unique').textContent = s.unique ?? '—';
}

// ── Render table ─────────────────────────────
function renderTable(newName) {
  const tbody = document.getElementById('records-body');
  document.getElementById('record-count').textContent = records.length + ' bản ghi';
  if (!records.length) {
    tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:var(--muted);padding:40px">Chưa có dữ liệu</td></tr>';
    return;
  }
  tbody.innerHTML = records.map((r, i) => {
    const conf  = r.confident ? Math.round(r.confident * 100) : 0;
    const dt    = new Date(String(r.time).replace(' ', 'T'));
    const timeStr = isNaN(dt.getTime()) ? r.time : dt.toLocaleString('vi-VN');
    const isNew = i === 0 && newName && r.name === newName;
    return `<tr class="${isNew ? 'new-row' : ''}">
      <td class="name-cell">${r.name}</td>
      <td class="time-cell">${timeStr}</td>
      <td class="conf-cell">
        <div class="conf-bar">
          <div class="conf-track"><div class="conf-fill" style="width:${conf}%"></div></div>
          <span style="color:var(--accent);font-size:11px">${conf}%</span>
        </div>
      </td>
    </tr>`;
  }).join('');
}

// ── Log ──────────────────────────────────────
function addLog(msg, type='info') {
  const body = document.getElementById('log-body');
  const ts   = new Date().toLocaleTimeString('vi-VN', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
  const el   = document.createElement('div');
  el.className = `log-item ${type}`;
  el.innerHTML = `<span class="log-ts">${ts}</span><span class="log-msg">${msg}</span>`;
  body.insertBefore(el, body.firstChild);
  while (body.children.length > 30) body.removeChild(body.lastChild);
}

function clearLog() {
  document.getElementById('log-body').innerHTML = '';
}

// ── Alert ─────────────────────────────────────
let alertTimer;
function showAlert(msg, color, title='THÔNG BÁO', isWarn=false) {
  const box   = document.getElementById('alert-box');
  const body  = document.getElementById('alert-body');
  const ttl   = document.getElementById('alert-title');
  box.className = 'alert show' + (isWarn ? ' warn-alert' : '');
  ttl.textContent = title;
  body.className = `alert-body ${color}`;
  body.textContent = msg;
  clearTimeout(alertTimer);
  alertTimer = setTimeout(() => box.classList.remove('show'), 4000);
}

// ── Init ──────────────────────────────────────
loadRecords();
loadStats();
setInterval(() => { loadRecords(); loadStats(); }, 10000);
</script>
</body>
</html>
"""

# ══════════════════════════════════════════════════════════════
# FLASK ROUTES
# ══════════════════════════════════════════════════════════════
@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/records")
def api_records():
    return json.dumps(get_records(), ensure_ascii=False), 200, {"Content-Type": "application/json"}

@app.route("/api/stats")
def api_stats():
    return json.dumps(get_stats()), 200, {"Content-Type": "application/json"}

# ══════════════════════════════════════════════════════════════
# MQTT → SocketIO bridge
# ══════════════════════════════════════════════════════════════
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("[MQTT] Kết nối thành công!")
        client.subscribe(TOPIC_RESULT)
        client.subscribe(TOPIC_TRIGGER)
        client.subscribe(TOPIC_RELAY)
        socketio.emit("mqtt_status", {"connected": True})
    else:
        print(f"[MQTT] Lỗi kết nối rc={rc}")
        socketio.emit("mqtt_status", {"connected": False})

def on_disconnect(client, userdata, rc, properties=None):
    print("[MQTT] Mất kết nối")
    socketio.emit("mqtt_status", {"connected": False})

def on_message(client, userdata, msg):
    topic   = msg.topic
    payload = msg.payload.decode("utf-8").strip()
    print(f"[MQTT] {topic}: {payload}")

    if topic == TOPIC_TRIGGER:
        socketio.emit("trigger", {"payload": payload})
    elif topic == TOPIC_RESULT:
        socketio.emit("result", {"result": payload})

def start_mqtt():
    if not MQTT_USER or not MQTT_PASS:
        print("[LỖI] Chưa cấu hình MQTT_USER/MQTT_PASS cho Dashboard.")
        print("      PowerShell ví dụ:")
        print("      $env:MQTT_USER='your_user'")
        print("      $env:MQTT_PASS='your_password'")
        return

    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_message    = on_message

    print(f"[MQTT] Đang kết nối {MQTT_BROKER}:{MQTT_PORT} ...")
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_forever()

# ══════════════════════════════════════════════════════════════
# SOCKETIO events
# ══════════════════════════════════════════════════════════════
@socketio.on("connect")
def on_socket_connect():
    socketio.emit("init_data", {
        "records": get_records(),
        "stats": get_stats()
    })

# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 50)
    print("  AIOT ĐIỂM DANH — Web Dashboard")
    print("=" * 50)
    print("  Mở trình duyệt: http://localhost:5000")
    print("=" * 50)

    # Chạy MQTT trong thread riêng
    mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
    mqtt_thread.start()

    # Chạy Flask
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)
