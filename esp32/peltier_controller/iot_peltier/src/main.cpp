#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// PINY
const int PIN_PELTIER = 18;
const int PIN_FAN     = 19;
const int PIN_PUMP    = 21;
const int PIN_SSR     = 25;
const int PIN_TEMP    = 4;

// PWM
const int PWM_FREQ   = 5000;
const int PWM_RES    = 8;
const int CH_PELTIER = 0;
const int CH_PUMP    = 1;

// PARAMETRE
const int PUMP_STABLE = 128;  // 50% pumpa počas ustálenia
const int TEC_STEP    = 153;  // 60% TEC pri skoku
const int SAMPLE_MS   = 2000; // meranie každé 2s

OneWire oneWire(PIN_TEMP);
DallasTemperature sensors(&oneWire);

unsigned long startTime = 0;
int currentTEC  = 0;
int currentPump = 0;

// POMOCNÉ FUNKCIE
void allOff() {
  ledcWrite(CH_PELTIER, 0);
  ledcWrite(CH_PUMP, 0);
  digitalWrite(PIN_FAN, LOW);
  digitalWrite(PIN_SSR, LOW);
  currentTEC  = 0;
  currentPump = 0;
  Serial.println("# STATUS: Vsetko vypnute");
}

void setStabilize() {
  // Fáza 1: ustálenie - pumpa 50%, TEC vypnutý
  digitalWrite(PIN_FAN, HIGH);
  ledcWrite(CH_PUMP, PUMP_STABLE);
  ledcWrite(CH_PELTIER, 0);
  currentTEC  = 0;
  currentPump = PUMP_STABLE;
  if (startTime == 0) startTime = millis();
  Serial.println("# STATUS: USTALENIE - pumpa 50%, TEC vypnuty");
}

void setStep() {
  // Fáza 2: skok - TEC na 60%
  digitalWrite(PIN_FAN, HIGH);
  ledcWrite(CH_PUMP, PUMP_STABLE);
  ledcWrite(CH_PELTIER, TEC_STEP);
  currentTEC  = TEC_STEP;
  currentPump = PUMP_STABLE;
  Serial.println("# STATUS: SKOK - TEC 60%, pumpa 50%");
}

// SETUP
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

  // Uvítacia správa s návodom
  Serial.println("# ==========================================");
  Serial.println("# Peltier identifikacny system");
  Serial.println("# Prikazy: STABILIZE | STEP | STOP");
  Serial.println("# Format dat: time_ms,temp_C,tec_pwm,pump_pwm");
  Serial.println("# ==========================================");
  Serial.println("# time_ms,temp_C,tec_pwm,pump_pwm");
}

// LOOP
void loop() {
  // Čítanie príkazov
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    cmd.toUpperCase();

    if      (cmd == "STABILIZE") setStabilize();
    else if (cmd == "STEP")      setStep();
    else if (cmd == "STOP")      { allOff(); startTime = 0; }
    else {
      Serial.print("# NEZNAMY PRIKAZ: ");
      Serial.println(cmd);
    }
  }

  // Meranie len ak systém beží
  if (startTime == 0) {
    delay(500);
    return;
  }

  sensors.requestTemperatures();
  float t = sensors.getTempCByIndex(0);

  if (t == DEVICE_DISCONNECTED_C) {
    Serial.println("# CHYBA: DS18B20 odpojeny!");
    delay(SAMPLE_MS);
    return;
  }

  unsigned long elapsed = millis() - startTime;
  Serial.print(elapsed);
  Serial.print(",");
  Serial.print(t, 2);
  Serial.print(",");
  Serial.print(currentTEC);
  Serial.print(",");
  Serial.println(currentPump);

  delay(SAMPLE_MS);
}