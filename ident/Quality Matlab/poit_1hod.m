clc; clear; close all;

%% 1. NAČÍTANIE DÁT
T        = readtable('export_last1.0h_20260604_115712.csv');
t_raw    = T.time_ms / 1000;
temp     = T.temp_C;
pwm_tec  = T.tec_pwm;
mode_str = T.mode;
sp_col   = T.setpoint;

%% 2. DETEKCIA ZMENY SETPOINTU
idx0   = find(strcmp(mode_str, 'MODE2'), 1, 'first');
SP_old = sp_col(idx0 - 1);
SP     = sp_col(idx0);
T0     = temp(idx0);

% Čas prepočítaný tak, že t=0 je moment zmeny SP
t = t_raw - t_raw(idx0);

% Dáta od zmeny SP
t_r = t(idx0:end);
T_r = temp(idx0:end);

fprintf('SP: %.1f -> %.1f oC  |  T0 = %.2f oC\n', SP_old, SP, T0);

%% 3. USTÁLENÁ HODNOTA (posledných 20 % dát)
n      = length(t_r);
T_ss   = mean(T_r(round(0.8*n):end));
fprintf('T_ss = %.4f oC\n', T_ss);

%% 4. ZÁKLADNÉ PARAMETRE
delta     = T0 - T_ss;                        % veľkosť kroku
e_ss      = SP - T_ss;                        % trvalá odchýlka
[T_min, i_min] = min(T_r);
overshoot = max(0, (T_ss - T_min) / delta * 100);   % [%]

%% 5. ČAS NÁBEHU (10 % → 90 % kroku)
i10    = find(T_r <= T0 - 0.10*delta, 1);
i90    = find(T_r <= T0 - 0.90*delta, 1);
t_rise = t_r(i90) - t_r(i10);

%% 6. DOBA USTALENIA (±2 % a ±5 % pásmo)
dt = mean(diff(t_r));
for tol = [2, 5]
    band    = tol/100 * delta;
    outside = find(T_r < T_ss - band | T_r > T_ss + band);
    if isempty(outside)
        ts = 0;
    else
        ts = t_r(outside(end)) + dt;
    end
    fprintf('Settling time +/-%.0f%%: %.1f s\n', tol, ts);
end

%% 7. PRVÉ DOSIAHNUTIE SP
i_sp = find(T_r <= SP, 1);
fprintf('Rise time (10->90%%): %.1f s\n', t_rise);
fprintf('Prve dosiahnutie SP: %.1f s\n', t_r(i_sp));
fprintf('Preregulovanie: %.2f %%\n', overshoot);
fprintf('Trvala odchylka: %.4f oC\n', e_ss);

%% 8. INTEGRÁLNE KRITÉRIÁ
e    = SP - T_r;
IAE  = sum(abs(e)) * dt;
ISE  = sum(e.^2) * dt;
ITAE = sum(abs(e) .* t_r) * dt;
fprintf('IAE=%.2f  ISE=%.2f  ITAE=%.2f\n', IAE, ISE, ITAE);

%% 9. GRAFY
figure('Color','white','Position',[50 50 1100 650]);

% Teplota
subplot(2,2,[1 2]); hold on; grid on;
xregion(t(1), 0, 'FaceColor',[0.9 0.9 0.9], 'DisplayName','Pred zmenou SP');
plot(t, temp, 'b-', 'LineWidth', 1.5, 'DisplayName', 'Teplota');
% Setpoint ako schodovitý skok
sp_signal = ones(size(t)) * SP_old;
sp_signal(idx0:end) = SP;
plot(t, sp_signal, 'r--', 'LineWidth', 1.5, 'DisplayName', 'Setpoint');
yline(T_ss, 'k--', 'LineWidth', 1.2, 'DisplayName', sprintf('T_{ss} = %.3f oC', T_ss));
band2 = 2/100 * delta;
band5 = 5/100 * delta;
yline(T_ss + band2, 'g--', 'LineWidth', 0.8, 'DisplayName', '+/-2% pasmo');
yline(T_ss - band2, 'g--', 'LineWidth', 0.8, 'HandleVisibility','off');
yline(T_ss + band5, '--', 'Color',[1 0.5 0], 'LineWidth', 0.8, 'DisplayName','+/-5% pasmo');
yline(T_ss - band5, '--', 'Color',[1 0.5 0], 'LineWidth', 0.8, 'HandleVisibility','off');
xline(0, 'k-', 'LineWidth', 2, 'DisplayName', 'Zmena SP');
plot(t_r(i_min), T_min, 'rv', 'MarkerSize', 9, 'MarkerFaceColor','r', ...
     'DisplayName', sprintf('Min = %.3f oC', T_min));
xlabel('Cas [s]'); ylabel('Teplota [oC]');
title('Priebeh regulacie'); legend('Location','best','FontSize',8);

% PWM TEC
subplot(2,2,3); hold on; grid on;
plot(t, pwm_tec, 'Color',[0.85 0.45 0], 'LineWidth', 1.2);
xline(0, 'k-', 'LineWidth', 2);
xlabel('Cas [s]'); ylabel('PWM TEC [-]'); title('Akcny zasah');

% Regulačná odchýlka
subplot(2,2,4); hold on; grid on;
area(t, SP - temp, 'FaceAlpha',0.25, 'FaceColor','b', 'EdgeColor','b');
yline(0,'k-'); xline(0,'k-','LineWidth',2);
xlabel('Cas [s]'); ylabel('e(t) [oC]'); title('Regulacna odchylka');

sgtitle('Analyza kvality regulacie', 'FontSize',13,'FontWeight','bold');