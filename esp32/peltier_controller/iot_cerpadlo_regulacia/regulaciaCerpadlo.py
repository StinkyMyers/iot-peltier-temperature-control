import os
import serial
import csv
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button, TextBox
from datetime import datetime

# =============================================
# NASTAVENIA
# =============================================
PORT     = "COM5"   # Uprav podla svojho ESP
BAUD     = 115200
CSV_DIR  = "data"
os.makedirs(CSV_DIR, exist_ok=True)
CSV_FILE = os.path.join(CSV_DIR, f"ident_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

# =============================================
# SERIAL + CSV
# =============================================
ser     = serial.Serial(PORT, BAUD, timeout=1)
csvfile = open(CSV_FILE, 'w', newline='')
writer  = csv.writer(csvfile)
writer.writerow(['time_ms', 'temp_C', 'tec_pwm', 'pump_pwm', 'mode'])
print(f"Zapisujem do: {CSV_FILE}")

times  = []
temps  = []
pwms   = [] # Sem budeme tentokrat ukladat PWM PUMPY

# =============================================
# GRAF
# =============================================
fig, ax1 = plt.subplots(figsize=(14, 7))
plt.subplots_adjust(bottom=0.35)
ax2 = ax1.twinx()

line_temp, = ax1.plot([], [], 'b-o', markersize=2, linewidth=1.5, label='Teplota [°C]')
line_pwm,  = ax2.plot([], [], 'r-',  linewidth=2.5, label='PWM Pumpa')
line_sp,   = ax1.plot([], [], 'g--', linewidth=1.5, label='Setpoint')

ax1.set_xlabel('Čas [s]')
ax1.set_ylabel('Teplota [°C]', color='blue')
ax2.set_ylabel('PWM Pumpa [0-255]', color='red')
ax2.set_ylim(-10, 270)
ax1.set_title('Regulácia Pumpy (Peltier Konštantný)')
ax1.grid(True)

lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

status_text = ax1.text(
    0.02, 0.95, 'Stav: Čakám na príkaz',
    transform=ax1.transAxes, fontsize=10,
    verticalalignment='top',
    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8)
)

setpoint_val = [21.0]

# =============================================
# TLAČIDLÁ
# =============================================
ax_btn_stab = fig.add_axes([0.08, 0.18, 0.15, 0.07])
ax_btn_pid  = fig.add_axes([0.26, 0.18, 0.15, 0.07])
ax_btn_stop = fig.add_axes([0.44, 0.18, 0.15, 0.07])

btn_stab = Button(ax_btn_stab, 'STABILIZE\npumpa 50%',  color='steelblue',  hovercolor='deepskyblue')
btn_pid  = Button(ax_btn_pid,  'PID\nspusti reguláciu', color='darkorange',  hovercolor='orange')
btn_stop = Button(ax_btn_stop, 'STOP\nvypnúť všetko',  color='firebrick',   hovercolor='red')

# =============================================
# PID PARAMETRE – TextBoxy
# =============================================
# Stlačili sme to, aby sa vošli aj min/max limity
ax_sp  = fig.add_axes([0.05, 0.07, 0.08, 0.06])
ax_kp  = fig.add_axes([0.15, 0.07, 0.09, 0.06])
ax_ki  = fig.add_axes([0.26, 0.07, 0.09, 0.06])
ax_min = fig.add_axes([0.37, 0.07, 0.09, 0.06])
ax_max = fig.add_axes([0.48, 0.07, 0.09, 0.06])

tb_sp  = TextBox(ax_sp,  'SP°C\n', initial='21.0')
tb_kp  = TextBox(ax_kp,  'Kp\n',   initial='103.81')
tb_ki  = TextBox(ax_ki,  'Ki\n',   initial='0.0515')
tb_min = TextBox(ax_min, 'Min\n',  initial='75')
tb_max = TextBox(ax_max, 'Max\n',  initial='255')

ax_btn_apply = fig.add_axes([0.60, 0.07, 0.12, 0.06])
btn_apply = Button(ax_btn_apply, 'Použiť PID', color='green', hovercolor='limegreen')

# =============================================
# FUNKCIE
# =============================================
def send_stabilize(event):
    ser.write(b'STABILIZE\n')
    status_text.set_text('Stav: USTÁLENIE')
    status_text.get_bbox_patch().set_facecolor('deepskyblue')
    print(">> STABILIZE odoslané")

def send_pid(event):
    ser.write(b'PID\n')
    status_text.set_text('Stav: PID regulácia aktívna')
    status_text.get_bbox_patch().set_facecolor('orange')
    print(">> PID odoslané")

def send_stop(event):
    ser.write(b'STOP\n')
    status_text.set_text('Stav: ZASTAVENÉ')
    status_text.get_bbox_patch().set_facecolor('salmon')
    print(">> STOP odoslané")

def apply_pid(event):
    try:
        sp  = float(tb_sp.text)
        kp  = float(tb_kp.text)
        ki  = float(tb_ki.text)
        p_min = int(tb_min.text)
        p_max = int(tb_max.text)

        ser.write(f'SET_SP:{sp}\n'.encode())
        ser.write(f'SET_KP:{kp}\n'.encode())
        ser.write(f'SET_KI:{ki}\n'.encode())
        ser.write(f'SET_MIN:{p_min}\n'.encode())
        ser.write(f'SET_MAX:{p_max}\n'.encode())

        setpoint_val[0] = sp
        print(f">> PID upravený: SP={sp} Kp={kp} Ki={ki} Min={p_min} Max={p_max}")
        status_text.set_text(f'Stav: PID aktualizovaný – SP={sp}°C')
    except ValueError:
        print(">> Chyba: neplatné hodnoty PID")

btn_stab.on_clicked(send_stabilize)
btn_pid.on_clicked(send_pid)
btn_stop.on_clicked(send_stop)
btn_apply.on_clicked(apply_pid)

# =============================================
# ŽIVÁ AKTUALIZÁCIA
# =============================================
def update(frame):
    while ser.in_waiting:
        try:
            line = ser.readline().decode('utf-8').strip()
        except:
            continue

        if not line:
            continue

        if line.startswith('#'):
            print(line)
            if 'STATUS' in line:
                status_text.set_text(f'Stav: {line.split("STATUS:")[-1].strip()}')
            continue

        parts = line.split(',')
        if len(parts) < 4:
            continue

        try:
            t_ms = int(parts[0])
            temp = float(parts[1])
            tec_pwm  = int(parts[2])
            pump_pwm = int(parts[3])
        except:
            continue

        if temp < -100:
            continue

        writer.writerow([t_ms, temp, tec_pwm, pump_pwm, parts[4] if len(parts) > 4 else ''])
        csvfile.flush()

        t_s = t_ms / 1000.0
        times.append(t_s)
        temps.append(temp)
        # Pridávame do grafu PWM PUMPY (nie Peltier)
        pwms.append(pump_pwm)

    if len(times) > 1:
        line_temp.set_data(times, temps)
        line_pwm.set_data(times, pwms)
        line_sp.set_data([times[0], times[-1]],
                         [setpoint_val[0], setpoint_val[0]])
        ax1.relim()
        ax1.autoscale_view()

    return line_temp, line_pwm, line_sp

ani = animation.FuncAnimation(
    fig, update, interval=500, blit=False, cache_frame_data=False
)

plt.tight_layout()
plt.show()

# Po zatvorení
csvfile.close()
ser.close()
print(f"Hotovo. Dáta uložené: {CSV_FILE}")