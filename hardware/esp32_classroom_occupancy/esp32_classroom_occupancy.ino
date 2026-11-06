// Smart Classroom Occupancy - ESP32
// Sensors: 2x IR (entry/exit), LDR, flame sensor, DHT11
// Outputs: 4-relay module (fire alarm, fan, 2 lights), DC motor (door), 16x2 LCD, Telegram alerts
//
// SETUP: replace the placeholders below with your own values.
// Never commit real WiFi passwords or Telegram bot tokens to GitHub.

#include <LiquidCrystal.h>
int rs = 13, en = 12, d4 = 14, d5 = 27, d6 = 26, d7 = 25;
LiquidCrystal lcd(rs, en, d4, d5, d6, d7);

int LIR = 15;
int RIR = 2;
int LDR = 4;
int FIRE = 18;

int RELAY_1 = 19;
int RELAY_2 = 21;
int RELAY_3 = 22;
int RELAY_4 = 23;

int IN1 = 33;
int IN2 = 32;

int movingstate = 0;

#include <DHT.h>
#define dhtpin 5
#define dhttype DHT11
DHT dht (dhtpin, dhttype);
float t, p;


#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <UniversalTelegramBot.h>
#include <ArduinoJson.h>

// ---- Replace these with your own details ----
const char* ssid = "YOUR_WIFI_NAME";
const char* password = "YOUR_WIFI_PASSWORD";
WiFiClient  client;

#define BOT_TOKEN "YOUR_TELEGRAM_BOT_TOKEN"   // create a bot with @BotFather
#define CHAT_ID "YOUR_TELEGRAM_CHAT_ID"       // get it from @userinfobot
// ---------------------------------------------

WiFiClientSecure secured_client;
UniversalTelegramBot bot(BOT_TOKEN, secured_client);


void setup() 
{
  Serial.begin(9600);
  dht.begin();

  pinMode(LIR, INPUT);
  pinMode(RIR, INPUT);
  pinMode(LDR, INPUT);
  pinMode(FIRE, INPUT);

  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(RELAY_1, OUTPUT);
  pinMode(RELAY_2, OUTPUT);
  pinMode(RELAY_3, OUTPUT);
  pinMode(RELAY_4, OUTPUT);


  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  
  digitalWrite(RELAY_1, LOW);
  digitalWrite(RELAY_2, LOW);
  digitalWrite(RELAY_3, LOW);
  digitalWrite(RELAY_4, LOW);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    lcd.clear();
    lcd.print("WIFI Connecting");
    Serial.println("WIFI Connecting");
    delay(500);
  }
  lcd.clear();
  lcd.print("WIFI Connected");
  Serial.println("WIFI Connected");

  secured_client.setCACert(TELEGRAM_CERTIFICATE_ROOT);

  bot.sendMessage(CHAT_ID, "CLASS ROOM OCCUPANCY.....");
  delay(300);

  lcd.clear();
  lcd.begin(16, 2);
  lcd.setCursor(0, 0);
  lcd.print("CLASS ROOM");
  lcd.setCursor(0, 1);
  lcd.print("OCCUPANCY");
  delay(1000);
  lcd.clear();
}

void loop() 
{
  // Manual motor control over serial: F = forward, B = backward, S = stop
  if (Serial.available() > 0)
  {
    char ch = Serial.read();
    Serial.print("Received: ");
    Serial.println(ch);

    if (ch == 'F')
    {
      FORWARD();
    }
    else if (ch == 'B')
    {
      BACKWARD();
    }
    else if (ch == 'S')
    {
      STOP();
    }
  }
  SENSORS();
}


void SENSORS()
{
  int ldrvalue = digitalRead(LDR);
  int lirstate = digitalRead(LIR);
  int rirstate = digitalRead(RIR);
  int firestate = digitalRead(FIRE);

  t = dht.readTemperature();
  p = dht.readHumidity();

  Serial.print("LDR: ");
  Serial.println(ldrvalue);

  if (isnan(t) || isnan(p))
  {
    Serial.println("DHT11 reading failed");
    lcd.setCursor(0, 0);
    lcd.print("DHT SENSOR ERROR");
    lcd.setCursor(0, 1);
    lcd.print("Check DHT11     ");
  }
  else
  {
    Serial.print("Temperature: ");
    Serial.println(t);
    Serial.print("Humidity: ");
    Serial.println(p);

    // Temperature and humidity display
    lcd.setCursor(0, 0);
    lcd.print("T:");
    lcd.print(t, 1);
    lcd.print((char)223);
    lcd.print("C H:");
    lcd.print(p, 0);
    lcd.print("%   ");

    lcd.setCursor(0, 1);

    if (firestate == LOW)
    {
      lcd.print("FIRE DETECTED   ");
      bot.sendMessage(CHAT_ID, "FIRE DETECTED.....");
      digitalWrite(RELAY_1, HIGH);
    }
    else if (t > 30 && (lirstate == LOW || rirstate == LOW))
    {
      lcd.print("TEMP IS HIGH    ");
      digitalWrite(RELAY_2, HIGH);
    }
    else
    {
      lcd.print("TEMP NORMAL     ");
      digitalWrite(RELAY_2, LOW);
    }

    if (firestate != LOW)
      digitalWrite(RELAY_1, LOW);
  }

  // Light control
  if (ldrvalue == HIGH && lirstate == LOW)
  {
    digitalWrite(RELAY_3, HIGH);
    digitalWrite(RELAY_4, LOW);
  }
  else if (ldrvalue == HIGH && rirstate == LOW)
  {
    digitalWrite(RELAY_3, LOW);
    digitalWrite(RELAY_4, HIGH);
  }
  else
  {
    digitalWrite(RELAY_3, LOW);
    digitalWrite(RELAY_4, LOW);
  }

  // Automatic motor operation
  if (movingstate == 0)
  {
    STOP();

    if (lirstate == LOW)
    {
      movingstate = 1;
      FORWARD();
    }
    else if (rirstate == LOW)
    {
      movingstate = 2;
      BACKWARD();
    }
  }
  else if (movingstate == 1)
  {
    if (lirstate == HIGH)
    {
      BACKWARD();
      movingstate = 0;
    }
    else
    {
      STOP();
    }
  }
  else if (movingstate == 2)
  {
    if (rirstate == HIGH)
    {
      FORWARD();
      movingstate = 0;
    }
    else
    {
      STOP();
    }
  }
}


void FORWARD()
{
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  delay(600);
  STOP();
}

void BACKWARD()
{
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
  delay(600);
  STOP();
}

void STOP()
{
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
}
