clc; clear; close all;

%% 1. NAČÍTANIE DÁT
T        = readtable('export_last2.0h_20260604_144803.csv');
t_raw    = T.time_ms / 1000;
temp     = T.temp_C;
pwm_tec  = T.tec_pwm;
mode_str = T.mode;
sp_col   = T.setpoint;

%% 2. DETEKCIA ZMENY SETPOINTU NA 18 °C
% Nájdeme prvý riadok kde setpoint preskočí na 18
SP_target = 18.0;
idx0 = find(sp_col == SP_target, 1, 'first');

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
delta     = T0 - T_ss;                        % veľkosť kroku (záporný = chladenie)
e_ss      = SP - T_ss;                        % trvalá odchýlka

% Minimum teploty (prekmit pri chladení)
[T_min, i_min] = min(T_r);
overshoot = max(0, (T_ss - T_min) / abs(delta) * 100);  % [%]

%% 5. ČAS NÁBEHU (10 % → 90 % kroku)
% Pri poklese teploty (chladenie): T klesá od T0 smerom k SP
i10    = find(T_r <= T0 - 0.10*abs(delta), 1);
i90    = find(T_r <= T0 - 0.90*abs(delta), 1);
if ~isempty(i10) && ~isempty(i90)
    t_rise = t_r(i90) - t_r(i10);
else
    t_rise = NaN;
end

%% 6. DOBA USTALENIA (±2 % a ±5 % pásmo)
dt = mean(diff(t_r));
for tol = [2, 5]
    band    = tol/100 * abs(delta);
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
if ~isempty(i_sp)
    fprintf('Prve dosiahnutie SP: %.1f s\n', t_r(i_sp));
else
    fprintf('Prve dosiahnutie SP: nedosiahnuté\n');
end
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

% --- Teplota ---
subplot(2,2,[1 2]); hold on; grid on;
xregion(t(1), 0, 'FaceColor',[0.9 0.9 0.9], 'DisplayName','Pred zmenou SP');
plot(t, temp, 'b-', 'LineWidth', 1.5, 'DisplayName', 'Teplota');

% Setpoint ako schodovitý skok
sp_signal = ones(size(t)) * SP_old;
sp_signal(idx0:end) = SP;
plot(t, sp_signal, 'r--', 'LineWidth', 1.5, 'DisplayName', ...
    sprintf('Setpoint (%.0f -> %.0f °C)', SP_old, SP));

yline(T_ss, 'k--', 'LineWidth', 1.2, ...
    'DisplayName', sprintf('T_{ss} = %.3f °C', T_ss));

band2 = 2/100 * abs(delta);
band5 = 5/100 * abs(delta);
yline(T_ss + band2, 'g--', 'LineWidth', 0.8, 'DisplayName', '+/-2% pasmo');
yline(T_ss - band2, 'g--', 'LineWidth', 0.8, 'HandleVisibility','off');
yline(T_ss + band5, '--', 'Color',[1 0.5 0], 'LineWidth', 0.8, 'DisplayName','+/-5% pasmo');
yline(T_ss - band5, '--', 'Color',[1 0.5 0], 'LineWidth', 0.8, 'HandleVisibility','off');
xline(0, 'k-', 'LineWidth', 2, 'DisplayName', 'Zmena SP');

if ~isempty(i_min)
    plot(t_r(i_min), T_min, 'rv', 'MarkerSize', 9, 'MarkerFaceColor','r', ...
        'DisplayName', sprintf('Min = %.3f °C', T_min));
end

xlabel('Cas [s]'); ylabel('Teplota [°C]');
title(sprintf('Priebeh regulacie', SP_old, SP));
legend('Location','best','FontSize',8);
xlim([-100, t_r(end)]);   % orez: 100 s pred zmenou SP + celý priebeh po zmene

% --- PWM TEC ---
subplot(2,2,3); hold on; grid on;
plot(t, pwm_tec, 'Color',[0.85 0.45 0], 'LineWidth', 1.2);
xline(0, 'k-', 'LineWidth', 2);
xlabel('Cas [s]'); ylabel('PWM TEC [-]'); title('Akcny zasah');
xlim([-100, t_r(end)]);

% --- Regulačná odchýlka ---
subplot(2,2,4); hold on; grid on;
area(t, SP - temp, 'FaceAlpha',0.25, 'FaceColor','b', 'EdgeColor','b');
yline(0,'k-');
xline(0,'k-','LineWidth',2);
xlabel('Cas [s]'); ylabel('e(t) [°C]'); title('Regulacna odchylka');
xlim([-100, t_r(end)]);

sgtitle(sprintf('Analyza kvality regulacie', SP),'FontSize',13,'FontWeight','bold');