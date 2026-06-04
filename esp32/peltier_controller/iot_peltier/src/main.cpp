#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// =========================================================================
// PINY
// =========================================================================
const int PIN_PELTIER = 18;
const int PIN_FAN     = 19;
const int PIN_PUMP    = 21;
const int PIN_SSR     = 25;
const int PIN_TEMP    = 4;

// =========================================================================
// PWM
// =========================================================================
const int PWM_FREQ   = 5000;
const int PWM_RES    = 8;
const int CH_PELTIER = 0;
const int CH_PUMP    = 1;

// =========================================================================
// PID PARAMETRE
// =========================================================================
float Kp       = -50.0;
float Ki       = -0.053;
float Kd       = -25.0;
float setpoint = 10.0;   // žiadaná teplota °C

// =========================================================================
// PID INTERNÉ PREMENNÉ
// =========================================================================
float integral    = 0.0;
float prev_error  = 0.0;
float prev_temp   = 0.0;
unsigned long prev_time = 0;

// =========================================================================
// NASTAVENIA EXPERIMENTU
// =========================================================================
const int PUMP_PWM  = 128;   // pumpa konštantná 50%
const int SAMPLE_MS = 2000;  // vzorkovanie každé 2s

// Módy
#define MODE_STOP       0
#define MODE_STABILIZE  1
#define MODE_PID        2

int currentMode = MODE_STOP;

// =========================================================================
// SENZOR
// =========================================================================
OneWire oneWire(PIN_TEMP);
DallasTemperature sensors(&oneWire);

// =========================================================================
// POMOCNÉ FUNKCIE
// =========================================================================
void allOff() {
  ledcWrite(CH_PELTIER, 0);
  ledcWrite(CH_PUMP, 0);
  digitalWrite(PIN_FAN, LOW);
  digitalWrite(PIN_SSR, LOW);
}

void resetPID() {
  integral   = 0.0;
  prev_error = 0.0;
  prev_time  = millis();
}

int computePID(float current_temp) {
  unsigned long now = millis();
  float dt = (now - prev_time) / 1000.0;  // sekundy
  if (dt <= 0) dt = 0.001;

  float error      = setpoint - current_temp;
  integral        += error * dt;
  float derivative = (error - prev_error) / dt;

  float output = Kp * error + Ki * integral + Kd * derivative;

  prev_error = error;
  prev_time  = now;

  // Saturácia 0-255
  return constrain((int)abs(output), 0, 255 * 0.8);
}

// =========================================================================
// SETUP
// =========================================================================
void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(PIN_FAN, OUTPUT);
  pinMode(PIN_SSR, OUTPUT);
  digitalWrite(PIN_FAN, LOW);
  digitalWrite(PIN_SSR, LOW);

  ledcSetup(CH_PELTIER, PWM_FREQ, PWM_RES);
  ledcAttachPin(PIN_PELTIER, CH_PELTIER);
  ledcSetup(CH_PUMP, PWM_FREQ, PWM_RES);
  ledcAttachPin(PIN_PUMP, CH_PUMP);

  allOff();
  sensors.begin();

  Serial.println("# ==========================================");
  Serial.println("# Peltier PID Control");
  Serial.println("# Prikazy: STABILIZE | PID | STOP");
  Serial.println("# SET_SP:<value>  napr. SET_SP:15.0");
  Serial.println("# SET_KP:<value>  napr. SET_KP:-50.0");
  Serial.println("# SET_KI:<value>  napr. SET_KI:-0.053");
  Serial.println("# SET_KD:<value>  napr. SET_KD:-25.0");
  Serial.println("# time_ms,temp_C,tec_pwm,pump_pwm,mode");
  Serial.println("# ==========================================");
}

// =========================================================================
// LOOP
// =========================================================================
unsigned long lastSample = 0;

void loop() {
  // -----------------------------------------------------------------------
  // ČÍTANIE PRÍKAZOV
  // -----------------------------------------------------------------------
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "STABILIZE") {
      currentMode = MODE_STABILIZE;
      digitalWrite(PIN_FAN, HIGH);
      ledcWrite(CH_PUMP, PUMP_PWM);
      ledcWrite(CH_PELTIER, 0);
      resetPID();
      Serial.println("# STATUS: USTALENIE - pumpa 50%, TEC vypnuty");

    } else if (cmd == "PID") {
      currentMode = MODE_PID;
      digitalWrite(PIN_FAN, HIGH);
      ledcWrite(CH_PUMP, PUMP_PWM);
      resetPID();
      Serial.println("# STATUS: PID aktívny");

    } else if (cmd == "STOP") {
      currentMode = MODE_STOP;
      allOff();
      Serial.println("# STATUS: STOP");

    } else if (cmd.startsWith("SET_SP:")) {
      setpoint = cmd.substring(7).toFloat();
      Serial.print("# Setpoint nastavený: ");
      Serial.println(setpoint);

    } else if (cmd.startsWith("SET_KP:")) {
      Kp = cmd.substring(7).toFloat();
      Serial.print("# Kp nastavený: ");
      Serial.println(Kp);

    } else if (cmd.startsWith("SET_KI:")) {
      Ki = cmd.substring(7).toFloat();
      Serial.print("# Ki nastavený: ");
      Serial.println(Ki);

    } else if (cmd.startsWith("SET_KD:")) {
      Kd = cmd.substring(7).toFloat();
      Serial.print("# Kd nastavený: ");
      Serial.println(Kd);
    }
  }

  // -----------------------------------------------------------------------
  // MERANIE A REGULÁCIA
  // -----------------------------------------------------------------------
  if (currentMode == MODE_STOP) {
    delay(500);
    return;
  }

  unsigned long now = millis();
  if (now - lastSample < SAMPLE_MS) return;
  lastSample = now;

  // Meranie teploty
  sensors.requestTemperatures();
  float temp = sensors.getTempCByIndex(0);

  if (temp == DEVICE_DISCONNECTED_C) {
    Serial.println("# CHYBA: DS18B20 odpojeny!");
    return;
  }

  int tec_pwm = 0;

  // PID výpočet
  if (currentMode == MODE_PID) {
    tec_pwm = computePID(temp);
    ledcWrite(CH_PELTIER, tec_pwm);
  }

  // Výpis dát
  Serial.print(now);
  Serial.print(",");
  Serial.print(temp, 2);
  Serial.print(",");
  Serial.print(tec_pwm);
  Serial.print(",");
  Serial.print(PUMP_PWM);
  Serial.print(",");
  Serial.println(currentMode == MODE_PID ? "PID" : "STABILIZE");
}