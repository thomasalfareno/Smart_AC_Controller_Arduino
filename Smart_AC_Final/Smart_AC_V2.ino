#include <WiFiS3.h>
#include <WiFiServer.h>
#include <EEPROM.h>
#include <DHT.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>


#define RELAY_PIN 7
#define DHTPIN 2
#define DHTTYPE DHT22


const char* ssid = "NAME_SSID_2.4Ghz";
const char* password = "passw_SSID";


WiFiServer server(80);
DHT dht(DHTPIN, DHTTYPE);
LiquidCrystal_I2C lcd(0x27, 16, 2);


float suhu = NAN, kelembapan = NAN;
float smoothSuhu = NAN, smoothHum = NAN;
const float SMOOTH_ALPHA = 0.35;

float suhuOn = 31.0, suhuOff = 30.0;
bool relayState = false;
bool autoMode = true;
bool prevAutoMode = false;
bool prevRelayStateGlobal = false;
bool timerActive = false;
bool wifiOnline = false;

unsigned long dataSeq = 0;

unsigned long timerStartMs = 0;
unsigned long timerDurationMs = 0;
unsigned long lastSensorRead = 0;
unsigned long lastLCDUpdate = 0;
unsigned long lastWiFiAttempt = 0;
unsigned long lastEEPROMWrite = 0;

unsigned long cooldownConfigSeconds = 30;
unsigned long cooldownRemainingSeconds = 0;

const unsigned long WIFI_RETRY_INTERVAL = 5000;
const unsigned long SENSOR_INTERVAL = 2000;
const unsigned long EEPROM_WRITE_MIN_INTERVAL = 5000;
const unsigned long LCD_MIN_UPDATE = 700;


const int ADDR_SUHUON = 0;
const int ADDR_SUHOOFF = 4;
const int ADDR_AUTOMODE = 8;
const int ADDR_RELAY = 9;
const int ADDR_TIMER_REMAIN = 10;
const int ADDR_TIMER_ACTIVE = 14;
const int ADDR_COOLDOWN_CFG = 15;
const int ADDR_COOLDOWN_REMAIN = 19;
const int ADDR_MAGIC = 100;
const uint8_t MAGIC = 0xA5;

char jsonBuffer[900];


String padRight(const String &s, uint8_t len) {
  String t = s;
  while (t.length() < len) t += ' ';
  if (t.length() > len) t = t.substring(0, len);
  return t;
}
void lcdWriteLine(uint8_t row, const String &text) {
  lcd.setCursor(0, row);
  lcd.print(padRight(text, 16));
}
void updateLCDLine0() {
  String l = "T:";
  if (!isnan(smoothSuhu)) l += String(smoothSuhu, 1); else l += "--";
  l += "C H:";
  if (!isnan(smoothHum)) l += String((int)smoothHum); else l += "--";
  l += "%";
  lcdWriteLine(0, l);
}
void updateLCDLine1() {
  String l = relayState ? "AC:ON " : "AC:OFF";
  if (timerActive) l += "TIMER ";
  else if (autoMode) l += "AUTO ";
  else l += "MANUAL";

  if (timerActive) {
    unsigned long elapsed = millis() - timerStartMs;
    unsigned long rem = (elapsed >= timerDurationMs) ? 0 : (timerDurationMs - elapsed) / 1000;
    String rems = String(rem) + "s";
    while (l.length() < 11) l += ' ';
    l = l.substring(0, 11) + padRight(rems, 5);
  } else {
    while (l.length() < 13) l += ' ';
    l = l.substring(0, 13);
  }
  String wifiSym = wifiOnline ? "ON" : "OFF";
  if (l.length() >= 16) l = l.substring(0, 13) + wifiSym;
  else { while (l.length() < 13) l += ' '; l += wifiSym; }
  lcdWriteLine(1, l);
}
void tampilLCDFull() {
  updateLCDLine0();
  delay(3);
  updateLCDLine1();
}


void safeEEPROMPut(int addr, uint32_t val) {
  uint32_t old = 0; EEPROM.get(addr, old);
  if (old != val) {
    EEPROM.put(addr, val);
    lastEEPROMWrite = millis();
  }
}
void safeEEPROMPutFloat(int addr, float val) {
  float old = 0; EEPROM.get(addr, old);
  if (old != val) {
    EEPROM.put(addr, val);
    lastEEPROMWrite = millis();
  }
}
void safeEEPROMUpdate8(int addr, uint8_t val) {
  uint8_t old = EEPROM.read(addr);
  if (old != val) {
    EEPROM.update(addr, val);
    lastEEPROMWrite = millis();
  }
}

void simpanAllToEEPROM() {
  if (millis() - lastEEPROMWrite < EEPROM_WRITE_MIN_INTERVAL) return;
  safeEEPROMPutFloat(ADDR_SUHUON, suhuOn);
  safeEEPROMPutFloat(ADDR_SUHOOFF, suhuOff);
  safeEEPROMUpdate8(ADDR_AUTOMODE, autoMode ? 1 : 0);
  safeEEPROMUpdate8(ADDR_RELAY, relayState ? 1 : 0);

  uint32_t timerRemain = 0;
  if (timerActive) {
    unsigned long elapsed = millis() - timerStartMs;
    timerRemain = (elapsed >= timerDurationMs) ? 0 : (timerDurationMs - elapsed) / 1000;
  }
  safeEEPROMPut(ADDR_TIMER_REMAIN, timerRemain);
  safeEEPROMUpdate8(ADDR_TIMER_ACTIVE, timerActive ? 1 : 0);
  safeEEPROMPut(ADDR_COOLDOWN_CFG, (uint32_t)cooldownConfigSeconds);
  safeEEPROMPut(ADDR_COOLDOWN_REMAIN, (uint32_t)cooldownRemainingSeconds);
#if defined(ESP32) || defined(ESP8266)
  EEPROM.commit();
#endif
}

void muatEEPROM() {
#if defined(ESP32) || defined(ESP8266)
  EEPROM.begin(512);
#endif
  uint8_t magic = EEPROM.read(ADDR_MAGIC);
  if (magic != MAGIC) {

    suhuOn = 31.0f; suhuOff = 30.0f;
    autoMode = true;
    relayState = false;
    cooldownConfigSeconds = 30;
    cooldownRemainingSeconds = 0;
    EEPROM.put(ADDR_SUHUON, suhuOn);
    EEPROM.put(ADDR_SUHOOFF, suhuOff);
    EEPROM.update(ADDR_AUTOMODE, autoMode ? 1 : 0);
    EEPROM.update(ADDR_RELAY, relayState ? 1 : 0);
    EEPROM.put(ADDR_TIMER_REMAIN, (uint32_t)0);
    EEPROM.update(ADDR_TIMER_ACTIVE, 0);
    EEPROM.put(ADDR_COOLDOWN_CFG, (uint32_t)cooldownConfigSeconds);
    EEPROM.put(ADDR_COOLDOWN_REMAIN, (uint32_t)0);
    EEPROM.update(ADDR_MAGIC, MAGIC);
#if defined(ESP32) || defined(ESP8266)
    EEPROM.commit();
#endif
    Serial.println("EEPROM: first-run defaults written (suhuOn=31, suhuOff=30)");
  } else {
    float f;
    EEPROM.get(ADDR_SUHUON, f); if (!isnan(f) && f > -100 && f < 200) suhuOn = f;
    EEPROM.get(ADDR_SUHOOFF, f); if (!isnan(f) && f > -100 && f < 200) suhuOff = f;
    autoMode = (EEPROM.read(ADDR_AUTOMODE) == 1);
    relayState = (EEPROM.read(ADDR_RELAY) == 1);
    uint32_t timerRemain = 0; EEPROM.get(ADDR_TIMER_REMAIN, timerRemain);
    uint8_t timerAct = EEPROM.read(ADDR_TIMER_ACTIVE);
    timerActive = (timerAct == 1);
    if (timerActive && timerRemain > 0) {
      timerDurationMs = timerRemain * 1000UL;
      timerStartMs = millis();
      relayState = true;
      digitalWrite(RELAY_PIN, HIGH);
    } else {
      timerActive = false; timerDurationMs = 0; timerStartMs = 0;
    }
    uint32_t ccfg = 0; EEPROM.get(ADDR_COOLDOWN_CFG, ccfg); if (ccfg != 0) cooldownConfigSeconds = ccfg;
    uint32_t cremain = 0; EEPROM.get(ADDR_COOLDOWN_REMAIN, cremain); cooldownRemainingSeconds = cremain;
    if (!timerActive) digitalWrite(RELAY_PIN, relayState ? HIGH : LOW);
    Serial.println("EEPROM: nilai dimuat");
  }
}


void setRelay(bool on, bool persist=true) {
  if (relayState == on) return;
  relayState = on;
  digitalWrite(RELAY_PIN, relayState ? HIGH : LOW);
  if (!relayState) {
    cooldownRemainingSeconds = cooldownConfigSeconds;
    safeEEPROMPut(ADDR_COOLDOWN_REMAIN, (uint32_t)cooldownRemainingSeconds);
  }
  if (persist) safeEEPROMUpdate8(ADDR_RELAY, relayState ? 1 : 0);
  updateLCDLine1();
}

void startTimer(uint32_t totalSeconds) {
  if (totalSeconds == 0) return;

  prevRelayStateGlobal = relayState;
  prevAutoMode = autoMode;

  autoMode = false;
  timerActive = true;
  timerDurationMs = totalSeconds * 1000UL;
  timerStartMs = millis();

  setRelay(true, false);

  safeEEPROMPut(ADDR_TIMER_REMAIN, totalSeconds);
  safeEEPROMUpdate8(ADDR_TIMER_ACTIVE, 1);

  tampilLCDFull();
}

void finishTimer() {
  timerActive = false;
  timerDurationMs = 0;
  timerStartMs = 0;

  setRelay(prevRelayStateGlobal, true);
  autoMode = prevAutoMode;

  safeEEPROMPut(ADDR_TIMER_REMAIN, 0);
  safeEEPROMUpdate8(ADDR_TIMER_ACTIVE, 0);
  safeEEPROMUpdate8(ADDR_AUTOMODE, autoMode ? 1 : 0);
  tampilLCDFull();
}


void tryWiFiReconnect() {
  unsigned long now = millis();
  bool currentlyConnected = (WiFi.status() == WL_CONNECTED);

  if (currentlyConnected && !wifiOnline) {
    wifiOnline = true;

    updateLCDLine1();
    Serial.println("WiFi connected -> Online (tidak mengubah autoMode)");
    return;
  }

  if (!currentlyConnected && wifiOnline) {
    wifiOnline = false;
    if (!timerActive) {

      autoMode = true;
      safeEEPROMUpdate8(ADDR_AUTOMODE, 1);
      Serial.println("WiFi lost -> Auto ENABLED (offline)");
    } else {
      prevAutoMode = true;
      Serial.println("WiFi lost -> timer aktif, prevAutoMode set");
    }
    updateLCDLine1();
  }

  if (!currentlyConnected) {
    if (now - lastWiFiAttempt >= WIFI_RETRY_INTERVAL) {
      lastWiFiAttempt = now;
      WiFi.begin(ssid, password);
      String sec = relayState ? "AC:ON " : "AC:OFF";
      if (autoMode) sec += "AUTO "; else if (timerActive) sec += "TIMER "; else sec += "MANUAL";
      if (sec.length() < 11) while (sec.length() < 11) sec += ' ';
      sec = sec.substring(0,11) + "...";
      lcdWriteLine(1, sec);
      Serial.println("Mencoba reconnect WiFi...");
    }
  } else {
    wifiOnline = true;
  }
}


String getParamValue(const String &str, const String &name) {
  int p = str.indexOf(name + "=");
  if (p < 0) return "";
  int start = p + name.length() + 1;
  int end = str.indexOf('&', start);
  if (end < 0) {
    int sp = str.indexOf(' ', start);
    if (sp >= 0) end = sp; else end = str.length();
  }
  return str.substring(start, end);
}

String readRequest(WiFiClient &client, unsigned long timeoutMs = 200) {
  unsigned long start = millis();
  String req = "";
  while (client.connected() && (millis() - start < timeoutMs)) {
    while (client.available()) {
      char c = client.read();
      req += c;
      if (req.endsWith("\r\n\r\n") || req.endsWith("\n\n")) return req;
    }
    delay(1);
  }
  return req;
}


void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  dht.begin();
#if defined(ESP32) || defined(ESP8266)
  EEPROM.begin(512);
#endif
  Wire.begin();
  lcd.init();
  lcd.backlight();
  lcd.clear();
  lcdWriteLine(0, "Memulai...");
  muatEEPROM();

  WiFi.begin(ssid, password);
  lastWiFiAttempt = millis();
  server.begin();

  delay(200);
  tampilLCDFull();
}


void loop() {
  unsigned long now = millis();

  tryWiFiReconnect();

  if (now - lastSensorRead >= SENSOR_INTERVAL) {
    lastSensorRead = now;
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    bool changed = false;
    if (!isnan(t)) {
      if (isnan(smoothSuhu)) smoothSuhu = t;
      else smoothSuhu = smoothSuhu * (1.0 - SMOOTH_ALPHA) + t * SMOOTH_ALPHA;
      suhu = t; changed = true;
    }
    if (!isnan(h)) {
      if (isnan(smoothHum)) smoothHum = h;
      else smoothHum = smoothHum * (1.0 - SMOOTH_ALPHA) + h * SMOOTH_ALPHA;
      kelembapan = h; changed = true;
    }
    if (changed) updateLCDLine0();
  }

  static unsigned long lastCooldownTick = 0;
  if (cooldownRemainingSeconds > 0 && now - lastCooldownTick >= 1000) {
    lastCooldownTick = now;
    cooldownRemainingSeconds = (cooldownRemainingSeconds > 0) ? cooldownRemainingSeconds - 1 : 0;
    if (now - lastEEPROMWrite >= EEPROM_WRITE_MIN_INTERVAL) safeEEPROMPut(ADDR_COOLDOWN_REMAIN, (uint32_t)cooldownRemainingSeconds);
  }

  if (timerActive) {
    unsigned long elapsed = now - timerStartMs;
    if (elapsed >= timerDurationMs) {
      finishTimer();
    } else {
      if (now - lastLCDUpdate >= 1000) { updateLCDLine1(); lastLCDUpdate = now; }
      if (now - lastEEPROMWrite >= EEPROM_WRITE_MIN_INTERVAL) {
        uint32_t remainSec = (timerDurationMs - elapsed) / 1000;
        safeEEPROMPut(ADDR_TIMER_REMAIN, remainSec);
        safeEEPROMUpdate8(ADDR_TIMER_ACTIVE, 1);
      }
    }
  } else {
    if (autoMode && !isnan(suhu) && cooldownRemainingSeconds == 0) {
      if (suhu >= suhuOn && !relayState) { setRelay(true); simpanAllToEEPROM(); }
      else if (suhu <= suhuOff && relayState) { setRelay(false); simpanAllToEEPROM(); }
    }
  }

  if (now - lastLCDUpdate >= LCD_MIN_UPDATE) { updateLCDLine1(); lastLCDUpdate = now; }

  WiFiClient client = server.available();
  if (client) {
    String req = readRequest(client, 220);
    int idxLineEnd = req.indexOf('\n');
    String firstLine = idxLineEnd > 0 ? req.substring(0, idxLineEnd) : req;

    if (firstLine.indexOf("GET /data") >= 0) {
      client.println("HTTP/1.1 200 OK");
      client.println("Content-Type: application/json");
      client.println("Connection: close");
      client.println();

      unsigned long timerRemSec = 0;
      if (timerActive) {
        unsigned long elapsed = now - timerStartMs;
        timerRemSec = (elapsed >= timerDurationMs) ? 0 : (timerDurationMs - elapsed) / 1000;
      }

      dataSeq++;

      float outSuhu = isnan(suhu) ? -1.0 : suhu;
      float outHum  = isnan(kelembapan) ? -1.0 : kelembapan;
      float outSuhuSm = isnan(smoothSuhu) ? -1.0 : smoothSuhu;
      float outHumSm  = isnan(smoothHum) ? -1.0 : smoothHum;

      snprintf(jsonBuffer, sizeof(jsonBuffer),
               "{\"suhu\":%.1f,\"hum\":%.1f,\"suhu_sm\":%.1f,\"hum_sm\":%.1f,\"relay\":%s,\"auto\":%s,\"timer_active\":%s,\"timer_remain_s\":%lu,\"suhu_on\":%.1f,\"suhu_off\":%.1f,\"cooldown_cfg_s\":%lu,\"cooldown_remain_s\":%lu,\"wifi\":%s,\"seq\":%lu,\"ts\":%lu}",
               outSuhu, outHum, outSuhuSm, outHumSm,
               relayState ? "true" : "false", autoMode ? "true" : "false",
               timerActive ? "true" : "false", timerRemSec, suhuOn, suhuOff,
               (unsigned long)cooldownConfigSeconds, (unsigned long)cooldownRemainingSeconds,
               wifiOnline ? "true" : "false",
               dataSeq, (unsigned long)(now / 1000UL));
      client.println(jsonBuffer);
      client.stop();
    }
    else if (firstLine.indexOf("GET /on") >= 0) {

      setRelay(true); autoMode = false; simpanAllToEEPROM();
      client.println("HTTP/1.1 200 OK");
      client.println("Content-Type: application/json");
      client.println("Connection: close");
      client.println();
      snprintf(jsonBuffer, sizeof(jsonBuffer), "{\"success\":true,\"relay\":true,\"auto\":%s,\"suhu_on\":%.1f,\"suhu_off\":%.1f}", autoMode?"true":"false", suhuOn, suhuOff);
      client.println(jsonBuffer);
      client.stop();
    }
    else if (firstLine.indexOf("GET /off") >= 0) {
      setRelay(false); autoMode = false; simpanAllToEEPROM();
      client.println("HTTP/1.1 200 OK");
      client.println("Content-Type: application/json");
      client.println("Connection: close");
      client.println();
      snprintf(jsonBuffer, sizeof(jsonBuffer), "{\"success\":true,\"relay\":false,\"auto\":%s,\"suhu_on\":%.1f,\"suhu_off\":%.1f}", autoMode?"true":"false", suhuOn, suhuOff);
      client.println(jsonBuffer);
      client.stop();
    }
    else if (firstLine.indexOf("GET /setauto?") >= 0) {
      String onv = getParamValue(firstLine, "on");
      String offv = getParamValue(firstLine, "off");
      if (onv.length() && offv.length()) {
        suhuOn = onv.toFloat(); suhuOff = offv.toFloat();
        prevAutoMode = false; timerActive = false;
        safeEEPROMPutFloat(ADDR_SUHUON, suhuOn);
        safeEEPROMPutFloat(ADDR_SUHOOFF, suhuOff);
        safeEEPROMUpdate8(ADDR_AUTOMODE, 1);
        safeEEPROMPut(ADDR_TIMER_REMAIN, 0);
        safeEEPROMUpdate8(ADDR_TIMER_ACTIVE, 0);
        autoMode = true;
      }
      client.println("HTTP/1.1 200 OK");
      client.println("Content-Type: application/json");
      client.println("Connection: close");
      client.println();
      snprintf(jsonBuffer, sizeof(jsonBuffer), "{\"success\":true,\"auto\":%s,\"suhu_on\":%.1f,\"suhu_off\":%.1f}", autoMode?"true":"false", suhuOn, suhuOff);
      client.println(jsonBuffer);
      client.stop();
    }
    else if (firstLine.indexOf("GET /timer?") >= 0) {
      String hs = getParamValue(firstLine, "h");
      String ms = getParamValue(firstLine, "m");
      String ss = getParamValue(firstLine, "s");
      uint32_t h = hs.length()? hs.toInt():0; uint32_t m = ms.length()? ms.toInt():0; uint32_t s = ss.length()? ss.toInt():0;
      uint32_t total = h*3600 + m*60 + s;
      if (total > 0) { startTimer(total); simpanAllToEEPROM(); }
      client.println("HTTP/1.1 200 OK");
      client.println("Content-Type: application/json");
      client.println("Connection: close");
      client.println();
      snprintf(jsonBuffer, sizeof(jsonBuffer), "{\"success\":%s,\"timer_sec\":%lu}", total>0?"true":"false", (unsigned long)total);
      client.println(jsonBuffer);
      client.stop();
    }
    else if (firstLine.indexOf("GET /autooff") >= 0) {
      autoMode = false; safeEEPROMUpdate8(ADDR_AUTOMODE, 0); simpanAllToEEPROM();
      client.println("HTTP/1.1 200 OK");
      client.println("Content-Type: application/json");
      client.println("Connection: close");
      client.println();
      snprintf(jsonBuffer, sizeof(jsonBuffer), "{\"success\":true,\"auto\":false}");
      client.println(jsonBuffer);
      client.stop();
    }
    else if (firstLine.indexOf("GET /setcooldown?") >= 0) {
      String sc = getParamValue(firstLine, "sec");
      if (sc.length()) {
        uint32_t sec = sc.toInt();
        cooldownConfigSeconds = sec;
        safeEEPROMPut(ADDR_COOLDOWN_CFG, sec);
      }
      client.println("HTTP/1.1 200 OK");
      client.println("Content-Type: application/json");
      client.println("Connection: close");
      client.println();
      snprintf(jsonBuffer, sizeof(jsonBuffer), "{\"success\":true,\"cooldown_cfg_s\":%lu}", (unsigned long)cooldownConfigSeconds);
      client.println(jsonBuffer);
      client.stop();
    }
    else {

      client.println("HTTP/1.1 200 OK");
      client.println("Content-Type: text/html");
      client.println("Connection: close");
      client.println();
      client.print(F(R"rawliteral(
<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Smart AC — Kontrol</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
:root{ --bg:#050608; --card: rgba(255,255,255,0.04); --glass: rgba(255,255,255,0.03); --accent:#6EE7B7; --accent-2:#60a5fa; --muted:#99a6b3; --danger:#ff6b6b; --radius:16px; --text:#e6eef3; --glass-blur:14px; --maxw:420px; }
*{box-sizing:border-box}
html,body{height:100%;margin:0;font-family:'Poppins',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:linear-gradient(180deg,#040507 0%, #071017 100%);color:var(--text);-webkit-font-smoothing:antialiased}
.container{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.card{width:100%;max-width:var(--maxw);background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));border-radius:var(--radius);padding:18px;border:1px solid rgba(255,255,255,0.04);backdrop-filter:blur(var(--glass-blur));box-shadow:0 12px 40px rgba(0,0,0,0.6);overflow:hidden}
.header{display:flex;justify-content:space-between;align-items:center}
.title{font-size:18px;font-weight:600}
.status-dot{display:inline-flex;align-items:center;gap:8px;font-size:13px;color:var(--muted)}
.status-ind{width:10px;height:10px;border-radius:50%;background:#ffb86b;box-shadow:0 0 6px rgba(0,0,0,0.6)}
.temp-row{display:flex;justify-content:space-between;align-items:center;margin-top:16px}
.temp-left{display:flex;flex-direction:column}
.temp-big{font-size:44px;font-weight:700;color:var(--accent)}
.hum{color:var(--muted);margin-top:6px}
.right-panel{text-align:right}
.relay{font-weight:800}
.mode{color:var(--muted);font-size:13px;margin-top:6px}
.controls{display:flex;gap:10px;margin-top:14px}
.btn{flex:1;padding:10px;border-radius:12px;border:none;cursor:pointer;background:transparent;color:var(--text);font-weight:700;box-shadow:0 8px 20px rgba(0,0,0,0.5);transition:transform .12s, box-shadow .12s}
.btn:active{transform:translateY(1px)}
.btn.primary{background:linear-gradient(180deg,var(--accent),#2dd4bf);color:#04201a}
.btn.danger{background:linear-gradient(180deg,#ef4444,#f87171)}
.controls-2{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.input{flex:1;padding:8px;border-radius:10px;border:1px solid rgba(255,255,255,0.04);background:transparent;color:var(--text)}
.small{font-size:13px;color:var(--muted);margin-top:10px}
.row{display:flex;gap:8px;align-items:center}
.card-footer{margin-top:12px;display:flex;flex-direction:column;gap:8px}
.info-line{display:flex;justify-content:space-between;color:var(--muted);font-size:13px}
.toast{position:fixed;left:50%;transform:translateX(-50%);bottom:28px;background:rgba(0,0,0,0.6);padding:10px 14px;border-radius:12px;backdrop-filter:blur(6px);color:#fff;opacity:0;pointer-events:none;transition:opacity .2s}
.toast.show{opacity:1;pointer-events:auto}
.badge{padding:6px 8px;border-radius:999px;background:rgba(255,255,255,0.03);font-weight:700;font-size:12px}
@media(max-width:420px){ .temp-big{font-size:36px} .card{padding:14px} .controls{flex-direction:column} .btn{width:100%} }
</style>
</head>
<body>
<div class="container">
  <div class="card" role="application" aria-label="Smart AC Controller">
    <div class="header">
      <div class="title">Smart AC Controller</div>
      <div class="status-dot"><span id="wifiDot" class="status-ind"></span><span id="wifiText">Mencari WiFi...</span></div>
    </div>

    <div class="temp-row">
      <div class="temp-left">
        <div id="tempVal" class="temp-big">--°C</div>
        <div id="humVal" class="hum">Kelembapan: --%</div>
      </div>
      <div class="right-panel">
        <div id="relayText" class="relay">AC: --</div>
        <div id="modeText" class="mode">Mode: --</div>
        <div id="timerDisplay" class="small"></div>
      </div>
    </div>

    <div class="controls">
      <button class="btn primary" id="btnOn"><i class="fa fa-power-off"></i> ON</button>
      <button class="btn" id="btnOff"><i class="fa fa-power-off"></i> OFF</button>
    </div>

    <div class="controls-2">
      <input id="sOn" class="input" type="number" step="0.1" placeholder="Suhu ON (°C)">
      <input id="sOff" class="input" type="number" step="0.1" placeholder="Suhu OFF (°C)">
      <button class="btn" id="btnSaveAuto">Simpan & Aktifkan Auto</button>
    </div>

    <div style="margin-top:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
      <input id="th" class="input" type="number" placeholder="h" min="0" style="width:64px">
      <input id="tm" class="input" type="number" placeholder="m" min="0" style="width:64px">
      <input id="ts" class="input" type="number" placeholder="s" min="0" style="width:64px">
      <button class="btn" id="btnTimer">Mulai Timer</button>
    </div>

    <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
      <button class="btn" id="btnCooldown60">Cooldown 60s</button>
      <button class="btn" id="btnAutoOff">Stop Auto</button>
      <button class="btn" id="btnEnableAuto">Aktifkan Auto</button>
    </div>

    <div class="card-footer">
      <div class="info-line"><div>Cooldown tersisa</div><div id="cooldownText" class="badge">-</div></div>
      <div class="info-line"><div>Threshold</div><div id="thresholdText" class="badge">ON 31 / OFF 30</div></div>
      <div class="small">Semua perubahan disimpan ke EEPROM perangkat (tetap ada setelah listrik mati).</div>
    </div>
  </div>
</div>

<div id="toast" class="toast"></div>

<script>
const toastEl = document.getElementById('toast');
function toast(msg, t=1400){ toastEl.textContent = msg; toastEl.classList.add('show'); setTimeout(()=>toastEl.classList.remove('show'), t); }
async function apiGET(path){ try{ const r = await fetch(path, {cache:'no-store'}); if(!r.ok) throw new Error('HTTP '+r.status); return await r.json(); } catch(e){ return null; } }
async function apiGET_nojson(path){ try{ await fetch(path); } catch(e){} }
let lastData = null;
let lastSeq = 0;

async function updateUI(){
  const d = await apiGET('/data');
  const sOn = document.getElementById('sOn'), sOff = document.getElementById('sOff');

  if(!d){
    document.getElementById('wifiDot').style.background = '#ff6b6b';
    document.getElementById('wifiText').textContent = 'OFFLINE';
    if(lastData){
      document.getElementById('tempVal').textContent = (lastData.suhu!=-1)? lastData.suhu+'°C' : '--°C';
      document.getElementById('humVal').textContent = (lastData.hum!=-1)? 'Kelembapan: '+lastData.hum+'%':'Kelembapan: --%';
      document.getElementById('relayText').textContent = 'AC: ' + (lastData.relay?'ON':'OFF');
      document.getElementById('modeText').textContent = 'Mode: ' + (lastData.auto?'AUTO':(lastData.timer_active?'TIMER':'MANUAL'));
    }
    return;
  }

  // ignore out-of-order responses
  if (typeof d.seq !== 'undefined' && d.seq < lastSeq) return;
  if (typeof d.seq !== 'undefined') lastSeq = d.seq;

  lastData = d;

  document.getElementById('wifiDot').style.background = d.wifi ? '#7ee787' : '#ffb86b';
  document.getElementById('wifiText').textContent = d.wifi ? 'ONLINE' : 'OFFLINE';

  // prefer smoothed values (suhu_sm / hum_sm) for consistency with LCD
  const suhuToShow = (typeof d.suhu_sm !== 'undefined' && d.suhu_sm!==-1) ? d.suhu_sm : d.suhu;
  const humToShow  = (typeof d.hum_sm !== 'undefined' && d.hum_sm!==-1) ? d.hum_sm : d.hum;

  document.getElementById('tempVal').textContent = (suhuToShow>=-0.5)? Number(suhuToShow).toFixed(1)+'°C' : '--°C';
  document.getElementById('humVal').textContent = (humToShow>=0)? 'Kelembapan: '+Math.round(humToShow)+'%' : 'Kelembapan: --%';
  document.getElementById('relayText').textContent = 'AC: ' + (d.relay?'ON':'OFF');
  document.getElementById('modeText').textContent = 'Mode: ' + (d.auto?'AUTO':(d.timer_active?'TIMER':'MANUAL'));
  document.getElementById('cooldownText').textContent = (typeof d.cooldown_remain_s !== 'undefined')? d.cooldown_remain_s+'s' : '-';
  document.getElementById('thresholdText').textContent = 'ON '+d.suhu_on+' / OFF '+d.suhu_off;

  // Hanya perbarui input suhu jika user tidak sedang mengetik (focus).
  if (sOn && document.activeElement !== sOn) {
    if (sOn.value === '' || sOn.value != String(d.suhu_on)) sOn.value = String(d.suhu_on);
  }
  if (sOff && document.activeElement !== sOff) {
    if (sOff.value === '' || sOff.value != String(d.suhu_off)) sOff.value = String(d.suhu_off);
  }

  if(d.timer_active) document.getElementById('timerDisplay').textContent = 'Timer: '+d.timer_remain_s+'s tersisa';
  else document.getElementById('timerDisplay').textContent = '';
}

// Optimistic ON/OFF handlers
async function optimisticFetch(path, optimisticState) {
  const prevRelay = lastData ? lastData.relay : false;
  document.getElementById('relayText').textContent = 'AC: ' + (optimisticState ? 'ON' : 'OFF');
  try {
    const r = await fetch(path);
    if (!r.ok) throw new Error('HTTP '+r.status);
    const j = await r.json();
    // update UI from server response
    setTimeout(updateUI, 200);
    return j;
  } catch (e) {
    // revert
    document.getElementById('relayText').textContent = 'AC: ' + (prevRelay ? 'ON' : 'OFF');
    toast('Perintah gagal: '+e.message, 1400);
    updateUI();
    return null;
  }
}

document.getElementById('btnOn').addEventListener('click', async ()=>{ await optimisticFetch('/on', true); toast('Perintah ON dikirim'); });
document.getElementById('btnOff').addEventListener('click', async ()=>{ await optimisticFetch('/off', false); toast('Perintah OFF dikirim'); });

// Optimistic save auto
document.getElementById('btnSaveAuto').addEventListener('click', async ()=>{
  const on = document.getElementById('sOn').value;
  const off = document.getElementById('sOff').value;
  if(!on || !off) return alert('Isi Suhu ON dan OFF terlebih dahulu.');
  // optimistic UI
  document.getElementById('thresholdText').textContent = 'ON '+on+' / OFF '+off;
  document.getElementById('modeText').textContent = 'Mode: AUTO';
  try {
    const r = await fetch('/setauto?on='+encodeURIComponent(on)+'&off='+encodeURIComponent(off));
    if (!r.ok) throw new Error('HTTP '+r.status);
    toast('Threshold tersimpan & Auto aktif');
    setTimeout(updateUI, 300);
  } catch (e) {
    toast('Gagal menyimpan threshold',1500);
    updateUI();
  }
});

// Timer
document.getElementById('btnTimer').addEventListener('click', async ()=>{
  const h = parseInt(document.getElementById('th').value||0);
  const m = parseInt(document.getElementById('tm').value||0);
  const s = parseInt(document.getElementById('ts').value||0);
  const total = h*3600 + m*60 + s;
  if(total <= 0) return alert('Masukkan durasi timer (h/m/s).');
  try {
    const r = await fetch('/timer?h='+h+'&m='+m+'&s='+s);
    if (!r.ok) throw new Error('HTTP '+r.status);
    toast('Timer dimulai');
    setTimeout(updateUI,500);
  } catch(e) { toast('Gagal memulai timer',1200); }
});

// Cooldown set 60s
document.getElementById('btnCooldown60').addEventListener('click', async ()=>{
  try {
    const r = await fetch('/setcooldown?sec=60');
    if (!r.ok) throw new Error('HTTP '+r.status);
    toast('Cooldown diset 60 detik');
    setTimeout(updateUI,400);
  } catch(e) { toast('Gagal set cooldown',1200); }
});

// Auto off / enable
document.getElementById('btnAutoOff').addEventListener('click', async ()=>{
  try { await fetch('/autooff'); toast('Mode auto dimatikan'); setTimeout(updateUI,300); } catch(e){ toast('Gagal',1200); }
});
document.getElementById('btnEnableAuto').addEventListener('click', async ()=>{
  const on = document.getElementById('sOn').value || '31';
  const off = document.getElementById('sOff').value || '30';
  try { await fetch('/setauto?on='+encodeURIComponent(on)+'&off='+encodeURIComponent(off)); toast('Auto diaktifkan'); setTimeout(updateUI,300); } catch(e){ toast('Gagal',1200); }
});

// polling interval (slightly relaxed to reduce race on slow connections)
setInterval(updateUI, 1200);
updateUI();

// Enter key -> start timer
['th','tm','ts'].forEach(id => {
  const el = document.getElementById(id);
  if(el) el.addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ e.preventDefault(); document.getElementById('btnTimer').click(); } });
});
</script>
</body>
</html>
      )rawliteral"));
      client.stop();
    }
  }
  delay(1);
  if (millis() - lastEEPROMWrite >= EEPROM_WRITE_MIN_INTERVAL) simpanAllToEEPROM();
}
