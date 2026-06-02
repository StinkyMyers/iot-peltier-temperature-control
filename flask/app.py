from flask import Flask, render_template, jsonify, send_file, session, redirect, url_for, request
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import csv
import os
import json
import paho.mqtt.client as mqtt
from datetime import datetime

# =============================================
# NASTAVENIA
# =============================================
EXPORT_DIR = "data"
os.makedirs(EXPORT_DIR, exist_ok=True)

CSV_FILE  = os.path.join(EXPORT_DIR, f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
JSON_FILE = os.path.join(EXPORT_DIR, f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

# =============================================
# FLASK
# =============================================
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI']        = 'sqlite:///peltier.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY']                     = 'peltier_secret'

db       = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# =============================================
# POUŽÍVATELIA
# =============================================
USERS = {
    'operator':  {'password': 'Pelt1er2026POIT', 'role': 'operator'},
    'spectator': {'password': '',                 'role': 'spectator'},
}

# =============================================
# LOGIN DEKORÁTOR
# =============================================
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated
    return decorator

# =============================================
# DATABASE MODEL
# =============================================
class Measurement(db.Model):
    id       = db.Column(db.Integer,    primary_key=True)
    time_ms  = db.Column(db.Integer,    nullable=False)
    temp_C   = db.Column(db.Float,      nullable=False)
    tec_pwm  = db.Column(db.Integer,    nullable=False)
    pump_pwm = db.Column(db.Integer,    nullable=False)
    mode     = db.Column(db.String(10), nullable=False)
    created  = db.Column(db.DateTime,   default=datetime.utcnow)

with app.app_context():
    db.create_all()

# =============================================
# STAV SYSTÉMU
# =============================================
state = {
    'initialized': False,
    'running':     False,
    'mode':        'STOP',
    'tec_pwm':     0,
    'pump_pwm':    0,
}

pid_params = {
    'setpoint': 21.0,
    'Kp':       103.8135,
    'Ki':       0.051495,
    'Kd':       0.0,
}

recommended_pid = {
    'mode2': {'Kp': -50.0,    'Ki': -0.053,   'Kd': -25.0},
    'mode3': {'Kp': 103.8135, 'Ki': 0.051495, 'Kd': 0.0},
}

# =============================================
# THINGSBOARD
# =============================================
TB_HOST  = "mqtt.eu.thingsboard.cloud"
TB_PORT  = 1883
TB_TOKEN = "UA2ZCPppyx4ruOppNDuJ"

tb_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
tb_client.username_pw_set(TB_TOKEN)

def tb_connect():
    try:
        tb_client.connect(TB_HOST, TB_PORT, keepalive=60)
        tb_client.loop_start()
        print(">> ThingsBoard pripojený")
    except Exception as e:
        print(f">> ThingsBoard chyba: {e}")

def tb_send(temp, tec_pwm, pump_pwm, mode, setpoint):
    try:
        payload = json.dumps({
            "temperature": temp,
            "tec_pwm":     tec_pwm,
            "pump_pwm":    pump_pwm,
            "mode":        mode,
            "setpoint":    setpoint,
        })
        tb_client.publish("v1/devices/me/telemetry", payload, qos=1)
    except Exception as e:
        print(f">> TB send chyba: {e}")

# =============================================
# ESP32 MQTT LISTENER
# =============================================
MQTT_BROKER     = "localhost"
MQTT_TOPIC_DATA = "peltier/data"
MQTT_TOPIC_CMD  = "peltier/cmd"

esp_client    = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
esp_connected = False

def on_esp_message(client, userdata, msg):
    if not state['running']:
        return

    line = msg.payload.decode().strip()
    if not line or line.startswith('#'):
        return

    parts = line.split(',')
    if len(parts) < 5:
        return

    try:
        t_ms     = int(parts[0])
        temp     = float(parts[1])
        tec_pwm  = int(parts[2])
        pump_pwm = int(parts[3])
        mode     = parts[4]
    except:
        return

    if temp < -100:
        return

    # SQL – jediný zdroj pravdy
    with app.app_context():
        try:
            m = Measurement(
                time_ms=t_ms, temp_C=temp,
                tec_pwm=tec_pwm, pump_pwm=pump_pwm, mode=mode
            )
            db.session.add(m)
            db.session.commit()
        except Exception as e:
            print(f">> DB chyba: {e}")
            db.session.rollback()

    # ThingsBoard
    tb_send(temp, tec_pwm, pump_pwm, mode, pid_params['setpoint'])

    # WebSocket → frontend
    socketio.emit('data', {
        'time_s':   t_ms / 1000.0,
        'temp':     temp,
        'pwm':      tec_pwm,
        'pump':     pump_pwm,
        'mode':     mode,
        'setpoint': pid_params['setpoint'],
    })

    print(f">> {temp}°C | TEC:{tec_pwm} | Pump:{pump_pwm} | {mode}")

def send_to_esp(cmd):
    try:
        esp_client.publish(MQTT_TOPIC_CMD, cmd)
        print(f">> ESP32 cmd: {cmd}")
    except Exception as e:
        print(f">> ESP cmd chyba: {e}")

def connect_esp_mqtt():
    global esp_connected
    if esp_connected:
        return
    try:
        esp_client.on_message = on_esp_message
        esp_client.connect(MQTT_BROKER, 1883, keepalive=60)
        esp_client.subscribe(MQTT_TOPIC_DATA)
        esp_client.loop_start()
        esp_connected = True
        print(">> ESP32 MQTT listener spustený")
    except Exception as e:
        print(f">> ESP MQTT chyba: {e}")

# =============================================
# SOCKETIO PRÍKAZY
# =============================================
@socketio.on('command')
def handle_command(data):
    cmd = data.get('cmd', '')

    if cmd == 'OPEN':
        state['initialized'] = True
        state['running']     = False
        state['mode']        = 'STOP'
        state['tec_pwm']     = 0
        state['pump_pwm']    = 0
        connect_esp_mqtt()
        socketio.emit('system_status', {'initialized': True, 'running': False})
        print(">> OPEN")

    elif cmd == 'CLOSE':
        state['initialized'] = False
        state['running']     = False
        state['mode']        = 'STOP'
        send_to_esp('STOP')
        socketio.emit('system_status', {'initialized': False, 'running': False})
        print(">> CLOSE")

    elif cmd == 'START':
        if state['initialized']:
            state['running'] = True
            send_to_esp('STABILIZE')
            socketio.emit('system_status', {'initialized': True, 'running': True})
            print(">> START")

    elif cmd == 'STOP':
        state['running']  = False
        state['mode']     = 'STOP'
        state['tec_pwm']  = 0
        state['pump_pwm'] = 0
        send_to_esp('STOP')
        socketio.emit('system_status', {
            'initialized': state['initialized'], 'running': False
        })
        print(">> STOP")

    elif cmd == 'MODE1':
        if state['running']:
            tec  = int(data.get('tec_pwm', 153))
            pump = int(data.get('pump_pwm', 128))
            state.update({'mode': 'MODE1', 'tec_pwm': tec, 'pump_pwm': pump})
            send_to_esp(f'MANUAL:{tec}:{pump}')

    elif cmd == 'MODE2':
        if state['running']:
            state.update({'mode': 'MODE2', 'pump_pwm': 128})
            send_to_esp('PID_TEC')

    elif cmd == 'MODE3':
        if state['running']:
            state.update({'mode': 'MODE3', 'tec_pwm': 64})
            send_to_esp('PID')

    elif cmd == 'SET_PID':
        pid_params.update({
            'setpoint': float(data.get('setpoint', 21.0)),
            'Kp':       float(data.get('Kp', 103.8135)),
            'Ki':       float(data.get('Ki', 0.051495)),
            'Kd':       float(data.get('Kd', 0.0)),
        })
        send_to_esp(f'SET_SP:{pid_params["setpoint"]}')
        send_to_esp(f'SET_KP:{pid_params["Kp"]}')
        send_to_esp(f'SET_KI:{pid_params["Ki"]}')
        send_to_esp(f'SET_KD:{pid_params["Kd"]}')
        socketio.emit('pid_updated', pid_params)

    print(f">> Príkaz: {cmd}")

@socketio.on('get_recommended')
def get_recommended(mode):
    key = 'mode2' if mode == 'MODE2' else 'mode3'
    socketio.emit('recommended_pid', recommended_pid[key])

# =============================================
# ROUTES
# =============================================
@app.route('/')
@login_required()
def index():
    return render_template('index.html', role=session.get('role'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = USERS.get(username)
        if user and user['password'] == password:
            session['user'] = username
            session['role'] = user['role']
            return redirect(url_for('index'))
        error = 'Nesprávne meno alebo heslo'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/history')
@login_required()
def get_history():
    with app.app_context():
        rows = Measurement.query.order_by(Measurement.id.desc()).limit(500).all()
        return jsonify([{
            'time_ms':  r.time_ms,
            'temp_C':   r.temp_C,
            'tec_pwm':  r.tec_pwm,
            'pump_pwm': r.pump_pwm,
            'mode':     r.mode,
            'created':  r.created.isoformat()
        } for r in reversed(rows)])

@app.route('/api/download/csv')
@login_required()
def download_csv():
    with app.app_context():
        rows = Measurement.query.order_by(Measurement.id).all()
        with open(CSV_FILE, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['time_ms', 'temp_C', 'tec_pwm', 'pump_pwm', 'mode', 'created'])
            for r in rows:
                w.writerow([r.time_ms, r.temp_C, r.tec_pwm,
                             r.pump_pwm, r.mode, r.created.isoformat()])
    return send_file(CSV_FILE, as_attachment=True)

@app.route('/api/download/json')
@login_required()
def download_json():
    with app.app_context():
        rows = Measurement.query.order_by(Measurement.id).all()
        data = [{
            'time_ms':  r.time_ms,
            'temp_C':   r.temp_C,
            'tec_pwm':  r.tec_pwm,
            'pump_pwm': r.pump_pwm,
            'mode':     r.mode,
            'ts':       r.created.isoformat()
        } for r in rows]
        with open(JSON_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    return send_file(JSON_FILE, as_attachment=True)

# =============================================
# ŠTART
# =============================================
if __name__ == '__main__':
    tb_connect()
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)