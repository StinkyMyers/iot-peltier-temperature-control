import os
import serial
import csv
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button
from datetime import datetime

# NASTAVENIA - uprav port
PORT     = "COM12"
BAUD     = 115200
CSV_DIR  = "data"
os.makedirs(CSV_DIR, exist_ok=True)
CSV_FILE = os.path.join(CSV_DIR, f"ident_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

# SERIAL + CSV
ser     = serial.Serial(PORT, BAUD, timeout=1)
csvfile = open(CSV_FILE, 'w', newline='')
writer  = csv.writer(csvfile)
writer.writerow(['time_ms', 'temp_C', 'tec_pwm', 'pump_pwm'])
print(f"Zapisujem do: {CSV_FILE}")

times = []
temps = []
pwms  = []

# GRAF
fig, ax1 = plt.subplots(figsize=(13, 6))
plt.subplots_adjust(bottom=0.22)
ax2 = ax1.twinx()

line_temp, = ax1.plot([], [], 'b-o', markersize=2, linewidth=1.5, label='Teplota [°C]')
line_pwm,  = ax2.plot([], [], 'r-',  linewidth=2.5, label='PWM TEC')

ax1.set_xlabel('Čas [s]')
ax1.set_ylabel('Teplota [°C]', color='blue')
ax2.set_ylabel('PWM Peltier [0-255]', color='red')
ax2.set_ylim(-10, 270)
ax1.set_title('Identifikácia systému – Peltier Cooler')
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

# TLAČIDLÁ
ax_btn_stab = fig.add_axes([0.15, 0.05, 0.18, 0.08])
ax_btn_step = fig.add_axes([0.38, 0.05, 0.18, 0.08])
ax_btn_stop = fig.add_axes([0.61, 0.05, 0.18, 0.08])

btn_stab = Button(ax_btn_stab, 'STABILIZE\n(50% pumpa)', color='steelblue', hovercolor='deepskyblue')
btn_step = Button(ax_btn_step, 'STEP\n(TEC 60%)',        color='darkorange', hovercolor='orange')
btn_stop = Button(ax_btn_stop, 'STOP\n(vypnúť všetko)', color='firebrick',   hovercolor='red')

def send_stabilize(event):
    ser.write(b'STABILIZE\n')
    status_text.set_text('Stav: USTÁLENIE – pumpa 50%, TEC vypnutý')
    status_text.get_bbox_patch().set_facecolor('deepskyblue')
    print(">> STABILIZE odoslané")

def send_step(event):
    ser.write(b'STEP\n')
    status_text.set_text('Stav: SKOK – TEC 60%, pumpa 50%')
    status_text.get_bbox_patch().set_facecolor('orange')
    print(">> STEP odoslané")

def send_stop(event):
    ser.write(b'STOP\n')
    status_text.set_text('Stav: ZASTAVENÉ')
    status_text.get_bbox_patch().set_facecolor('salmon')
    print(">> STOP odoslané")

btn_stab.on_clicked(send_stabilize)
btn_step.on_clicked(send_step)
btn_stop.on_clicked(send_stop)

# ŽIVÁ AKTUALIZÁCIA
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
            pwm  = int(parts[2])
            pump = int(parts[3])
        except:
            continue

        if temp < -100:
            continue

        writer.writerow([t_ms, temp, pwm, pump])
        csvfile.flush()

        times.append(t_ms / 1000.0)
        temps.append(temp)
        pwms.append(pwm)

    if len(times) > 1:
        line_temp.set_data(times, temps)
        line_pwm.set_data(times, pwms)
        ax1.relim()
        ax1.autoscale_view()

    return line_temp, line_pwm

ani = animation.FuncAnimation(
    fig, update, interval=500, blit=False, cache_frame_data=False
)

plt.tight_layout()
plt.show()

# Po zatvorení
csvfile.close()
ser.close()
print(f"Hotovo. Dáta uložené: {CSV_FILE}")