#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// =========================================================================
// WIFI + MQTT
// =========================================================================
const char* WIFI_SSID   = "D209";
const char* WIFI_PASS   = "pivolinD209";
const char* MQTT_SERVER = "147.175.105.185";
const int   MQTT_PORT   = 1883;
const char* TOPIC_DATA  = "peltier/data";
const char* TOPIC_CMD   = "peltier/cmd";

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
// PARAMETRE
// =========================================================================
const int SAMPLE_MS       = 5000;
const int PUMP_CONST      = 128;   // Konštantná pumpa pre Mód 2
const int PELTIER_CONST   = 64;    // Konštantný TEC pre Mód 3 (25%)

// =========================================================================
// PID PARAMETRE – Mód 2 (TEC reguluje)
// =========================================================================
float Kp_tec = -50.0;
float Ki_tec = -0.053;
float Kd_tec = -25.0;

// =========================================================================
// PID PARAMETRE – Mód 3 (Pumpa reguluje)
// =========================================================================
float Kp_pump = 103.8135;
float Ki_pump = 0.051495;
float Kd_pump = 0.0;
int   min_pwm = 75;
int   max_pwm = 180;

// Spoločný setpoint
float setpoint = 21.0;

// =========================================================================
// PID INTERNÉ PREMENNÉ
// =========================================================================
float integral    = 0.0;
float prev_error  = 0.0;
unsigned long prev_time = 0;

// =========================================================================
// MÓDY
// =========================================================================
#define MODE_STOP      0
#define MODE_STABILIZE 1
#define MODE_PID_TEC   2
#define MODE_PID_PUMP  3
#define MODE_MANUAL    4

int currentMode = MODE_STOP;
int manualTEC   = 153;
int manualPump  = 128;

// =========================================================================
// OBJEKTY
// =========================================================================
WiFiClient        wifiClient;
PubSubClient      mqtt(wifiClient);
OneWire           oneWire(PIN_TEMP);
DallasTemperature sensors(&oneWire);

unsigned long lastSample = 0;

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

// =========================================================================
// PID – Mód 2 (TEC reguluje, pumpa konštantná)
// =========================================================================
int computePID_TEC(float temp) {
  unsigned long now = millis();
  float dt = (now - prev_time) / 1000.0;
  if (dt <= 0) dt = 0.001;

  float error      = setpoint - temp;
  integral        += error * dt;
  float derivative = (error - prev_error) / dt;
  float output     = Kp_tec * error +
                     Ki_tec * integral +
                     Kd_tec * derivative;

  prev_error = error;
  prev_time  = now;

  return constrain((int)abs(output), 0, 204);
}

// =========================================================================
// PID – Mód 3 (Pumpa reguluje, TEC konštantný)
// s Feed-Forward a Anti-Windup
// =========================================================================
int computePID_PUMP(float temp) {
  unsigned long now = millis();
  float dt = (now - prev_time) / 1000.0;
  if (dt <= 0) dt = 0.001;

  float error  = setpoint - temp;
  float p_term = Kp_pump * error;
  float d_term = Kd_pump * (error - prev_error) / dt;

  // Feed-Forward – teoretický pracovný bod
  float u_bias = (setpoint - 8.43) / 0.0559;

  float i_term_new = integral + (Ki_pump * error * dt);
  float output     = p_term + i_term_new + d_term + u_bias;

  // Anti-Windup (Clamping)
  if (output > max_pwm) {
    output = max_pwm;
    if (error < 0) integral += Ki_pump * error * dt;
  } else if (output < min_pwm) {
    output = min_pwm;
    if (error > 0) integral += Ki_pump * error * dt;
  } else {
    integral += Ki_pump * error * dt;
  }

  prev_error = error;
  prev_time  = now;

  return (int)output;
}

// =========================================================================
// MQTT CALLBACK – príkazy z RPi
// =========================================================================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String cmd = "";
  for (unsigned int i = 0; i < length; i++) cmd += (char)payload[i];
  cmd.trim();

  Serial.print(">> MQTT cmd: "); Serial.println(cmd);

  if (cmd == "STABILIZE") {
    currentMode = MODE_STABILIZE;
    digitalWrite(PIN_FAN, HIGH);
    ledcWrite(CH_PELTIER, PELTIER_CONST);
    ledcWrite(CH_PUMP, PUMP_CONST);
    resetPID();
    Serial.println("# STATUS: USTALENIE - TEC 25%, Pumpa 50%");

  } else if (cmd == "PID_TEC") {
    currentMode = MODE_PID_TEC;
    digitalWrite(PIN_FAN, HIGH);
    ledcWrite(CH_PUMP, PUMP_CONST);
    resetPID();
    Serial.println("# STATUS: MOD 2 - PID TEC aktívny");

  } else if (cmd == "PID") {
    currentMode = MODE_PID_PUMP;
    digitalWrite(PIN_FAN, HIGH);
    ledcWrite(CH_PELTIER, PELTIER_CONST);
    resetPID();
    Serial.println("# STATUS: MOD 3 - PID PUMPA aktívny");

  } else if (cmd == "STOP") {
    currentMode = MODE_STOP;
    allOff();
    Serial.println("# STATUS: STOP");

  } else if (cmd == "HEATER_ON") {
    // --- NOVÝ PRÍKAZ: Zapnutie výhrevného telieska (Simulácia poruchy) ---
    digitalWrite(PIN_SSR, HIGH);
    Serial.println("# STATUS: PORUCHA - VYHREV ZAPNUTY");

  } else if (cmd == "HEATER_OFF") {
    // --- NOVÝ PRÍKAZ: Vypnutie výhrevného telieska ---
    digitalWrite(PIN_SSR, LOW);
    Serial.println("# STATUS: PORUCHA - VYHREV VYPNUTY");

  } else if (cmd.startsWith("MANUAL:")) {
    // Formát: MANUAL:153:128
    int sep = cmd.indexOf(':', 7);
    if (sep > 0) {
      manualTEC  = cmd.substring(7, sep).toInt();
      manualPump = cmd.substring(sep + 1).toInt();
    }
    currentMode = MODE_MANUAL;
    digitalWrite(PIN_FAN, HIGH);
    ledcWrite(CH_PELTIER, manualTEC);
    ledcWrite(CH_PUMP, manualPump);
    Serial.println("# STATUS: MOD 1 - MANUAL");

  } else if (cmd.startsWith("SET_SP:")) {
    setpoint = cmd.substring(7).toFloat();
    Serial.println("# Setpoint: " + String(setpoint));

  } else if (cmd.startsWith("SET_KP:")) {
    // Nastavuje Kp pre aktívny mód
    float val = cmd.substring(7).toFloat();
    if (currentMode == MODE_PID_TEC)  Kp_tec  = val;
    else                               Kp_pump = val;
    resetPID();

  } else if (cmd.startsWith("SET_KI:")) {
    float val = cmd.substring(7).toFloat();
    if (currentMode == MODE_PID_TEC)  Ki_tec  = val;
    else                               Ki_pump = val;
    resetPID();

  } else if (cmd.startsWith("SET_KD:")) {
    float val = cmd.substring(7).toFloat();
    if (currentMode == MODE_PID_TEC)  Kd_tec  = val;
    else                               Kd_pump = val;

  } else if (cmd.startsWith("SET_MIN:")) {
    min_pwm = cmd.substring(8).toInt();

  } else if (cmd.startsWith("SET_MAX:")) {
    max_pwm = cmd.substring(8).toInt();
  } 
}

// =========================================================================
// WIFI PRIPOJENIE
// =========================================================================
void connectWiFi() {
  Serial.print("WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500); Serial.print("."); attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print(" OK: "); Serial.println(WiFi.localIP());
  } else {
    Serial.println(" CHYBA – reštartujem");
    ESP.restart();
  }
}

// =========================================================================
// MQTT PRIPOJENIE
// =========================================================================
void connectMQTT() {
  while (!mqtt.connected()) {
    Serial.print("MQTT...");
    if (mqtt.connect("ESP32-Peltier")) {
      Serial.println(" OK");
      mqtt.subscribe(TOPIC_CMD);
    } else {
      Serial.print(" chyba: "); Serial.println(mqtt.state());
      delay(2000);
    }
  }
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

  connectWiFi();

  mqtt.setServer(MQTT_SERVER, MQTT_PORT);
  mqtt.setCallback(mqttCallback);
  connectMQTT();

  Serial.println("# ==========================================");
  Serial.println("# Peltier IoT Control");
  Serial.println("# Prikazy cez MQTT: STABILIZE | PID_TEC | PID | MANUAL:x:y | STOP");
  Serial.println("# SET_SP:<v> | SET_KP:<v> | SET_KI:<v> | SET_KD:<v>");
  Serial.println("# time_ms,temp_C,tec_pwm,pump_pwm,mode");
  Serial.println("# ==========================================");
}

// =========================================================================
// LOOP
// =========================================================================
void loop() {
  if (!mqtt.connected()) connectMQTT();
  mqtt.loop();

  unsigned long now = millis();
  if (now - lastSample < SAMPLE_MS) return;
  lastSample = now;

  if (currentMode == MODE_STOP) return;

  // Meranie teploty
  sensors.requestTemperatures();
  float temp = sensors.getTempCByIndex(0);

  if (temp == DEVICE_DISCONNECTED_C) {
    Serial.println("# CHYBA: DS18B20 odpojeny!");
    return;
  }

  int tec_pwm  = 0;
  int pump_pwm = PUMP_CONST;
  String modeStr = "STABILIZE";

  if (currentMode == MODE_PID_TEC) {
    tec_pwm  = computePID_TEC(temp);
    pump_pwm = PUMP_CONST;
    ledcWrite(CH_PELTIER, tec_pwm);
    modeStr = "MODE2";

  } else if (currentMode == MODE_PID_PUMP) {
    tec_pwm  = PELTIER_CONST;
    pump_pwm = computePID_PUMP(temp);
    ledcWrite(CH_PUMP, pump_pwm);
    modeStr = "MODE3";

  } else if (currentMode == MODE_MANUAL) {
    tec_pwm  = manualTEC;
    pump_pwm = manualPump;
    modeStr  = "MODE1";

  } else if (currentMode == MODE_STABILIZE) {
    tec_pwm  = PELTIER_CONST;
    pump_pwm = PUMP_CONST;
    modeStr  = "STABILIZE";
  }

  // Publikuj na MQTT
  String payload = String(now) + "," +
                   String(temp, 2) + "," +
                   String(tec_pwm) + "," +
                   String(pump_pwm) + "," +
                   modeStr;

  mqtt.publish(TOPIC_DATA, payload.c_str());
  Serial.println(payload);
}