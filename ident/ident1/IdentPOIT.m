clear; clc;

% Načítanie
data     = readtable('meranie_20260528_121335.csv');
time_s   = data.time_ms / 1000;
temp     = data.temp_C;
pwm_tec  = data.tec_pwm;

% Čas skoku
idx_step = find(pwm_tec > 0, 1, 'first');
t_step   = time_s(idx_step);

T0    = mean(temp(time_s < t_step));
T_inf = mean(temp(end-20:end));
dT    = T_inf - T0;

fprintf('T0    = %.2f C\n', T0);
fprintf('T_inf = %.2f C\n', T_inf);
fprintf('dT    = %.2f C\n', dT);

% Graf
figure('Position', [100 100 1100 450]);
yyaxis left
plot(time_s, temp, 'b-', 'LineWidth', 1.5); hold on;
yline(T0,    'b--', sprintf('T0 = %.2f°C',    T0),    'LabelHorizontalAlignment','left');
yline(T_inf, 'g--', sprintf('T∞ = %.2f°C', T_inf), 'LabelHorizontalAlignment','left');
ylabel('Teplota [°C]');

yyaxis right
plot(time_s, pwm_tec, 'r-', 'LineWidth', 2);
ylabel('PWM TEC');
ylim([-10 270]);

xline(t_step, 'k--', 'SKOK', 'LineWidth', 1.5);
xlabel('Čas [s]');
title('Step Response – Mód 1');
grid on;

% Invertovany pohlad - teplota ako kladny skok
figure('Position', [100 100 1100 450]);
temp_inv = T0 - temp;  % invertujeme - uvidis kladny skok

plot(time_s - t_step, temp_inv, 'b-', 'LineWidth', 1.5); hold on;
yline(T0 - T_inf, 'g--', sprintf('\\DeltaT = %.2f°C', T0 - T_inf), 'LabelHorizontalAlignment', 'left');
xline(0, 'k--', 'SKOK', 'LineWidth', 1.5);
xlim([-500 13000]);
ylim([-1 22]);
xlabel('Čas od skoku [s]');
ylabel('\DeltaT [°C]');
title('Step Response – invertovaný pohľad');
grid on;

%%

% Graf 1 - Teplota vs Setpoint
figure
plot(time, y, 'b-', 'LineWidth', 1.5); hold on;
plot(time, w, 'r--', 'LineWidth', 1.2);
ylabel('Teplota [°C]');
xlabel('Čas [s]');
title('Prechodová charakteristika – Mód 2 (TEC)');
legend('Teplota y(t)', 'Setpoint w(t)', 'Location', 'best');
grid on;

% Graf 2 - Akcny zasah
figure
plot(time, u, 'r-', 'LineWidth', 1.5);
yline(0,    'k--', 'Horná saturácia (0)',    'LineWidth', 1);
yline(-255, 'k--', 'Dolná saturácia (-255)', 'LineWidth', 1);
ylabel('Akčný zásah PWM');
xlabel('Čas [s]');
title('Akčný zásah regulátora – Mód 2 (TEC)');
legend('u(t)', 'Location', 'best');
grid on;


